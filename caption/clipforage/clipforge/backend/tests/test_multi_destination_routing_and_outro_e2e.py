"""
Phase 8 & Phase 9 End-to-End Verification Suite:
Multi-Destination Publishing, Channel Routing & Automatic Outro System.

Covers:
- Phase 9 Full Lifecycle Tests (Tests 01-05):
  1. Multi-channel OAuth connection, metadata isolation, and Video/Image outro CRUD + versioning
  2. Monitored source -> destination mapping (1:1, 1:N, N:M) and disconnect preservation
  3. Propagation of destination_ids across all 4 ingestion entrypoints:
     (a) Monitored channel check-now + countdown decision resolution + clip_selection_task
     (b) Manual YouTube URL + Batch URL
     (c) Manual local file upload
     (d) Upload Studio batch creation + chunk upload + sequential processing
  4. Destination variant rendering (outputs/{video_id}/clips/{clip_id}/destinations/{dest_id}/final.mp4
     + variant_meta.json), base clip SHA-256 & mtime immutability, cache hit & invalidation,
     zero subtitles (-sn), +faststart moov-before-mdat, aspect ratio preservation, >60s Shorts flag
  5. Private-by-default scheduling, publish-now, per-target cancel, edit protection (409),
     and end-to-end mocked target execution

- All 15 Phase 8 Failure Scenarios (Failure 01-15):
  01) Explicit empty destination_ids ([]) blocks auto-publish & keeps draft
  02) No destination connected blocks publishing (400 / ValueError / failed task)
  03) Destination disconnected after mapping preserves ChannelDestination + warning & disables
      auto_publish when no active destination remains
  04) Expired / missing-scope OAuth triggers needs_reauth and blocks publishing
  05) OAuth refresh failure fails affected target only without touching sibling targets
  06) Outro missing / None publishes base clip cleanly
  07) Outro file deleted or unavailable on disk returns clear error (404 / failed target, no silent fallback)
  08) Unsupported / corrupt outro format rejected (HTTP 400)
  09) Outro rendering FFmpeg failure fails only affected target
  10) Final render corruption fails validation (missing/zero/corrupt/non-faststart/subtitle check)
  11) 1 of 3 destinations failing lets remaining 2 succeed independently
  12) Concurrent PublishTarget claim atomicity & idempotency (only one claim wins; duplicate cannot upload twice)
  13) Retry after partial success skips already-published sibling targets
  14) Destination changed or outro version/duration edited invalidates stale variant
  15) Monitored source channel disabled or deleted mid-flight handled safely without wrong-channel publish

All tests isolate filesystem state into pytest tmp_path, set PUBLISH_MODE="test", mock external
YouTube/yt-dlp/LLM calls, tag synthetic test rows, and perform strict FK-safe DB + storage cleanup.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from backend.core.config import settings
from backend.core.storage import storage_service
from backend.main import app
from backend.models.artifact_sync import managed_upload_sync
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import (
    ArtifactRecord,
    ArtifactType,
    Channel,
    ChannelDestination,
    Clip,
    ClipVariant,
    DestinationOutro,
    Job,
    JobStatus,
    PublishRecord,
    PublishStatus,
    PublishTarget,
    StorageReservationCoordinator,
    TaskExecution,
    UploadBatch,
    Video,
    VideoDecision,
    VideoDecisionStatus,
    VideoTrackingQueue,
)
from backend.services.outro_service import (
    OutroRenderError,
    _is_valid_cached_variant,
    get_ffmpeg_binary,
    get_ffprobe_binary,
    has_faststart_moov_before_mdat,
    probe_media_with_ffprobe,
    render_clip_with_outro,
    render_or_reuse_destination_variant_sync,
    resolve_safe_outro_path,
)
from backend.services.publisher import (
    SCOPES,
    get_youtube_client,
    resolve_publish_destinations,
    validate_destination_ids,
)
from backend.tasks.analysis_tasks import clip_selection_task
from backend.tasks.clip_tasks import publish_clip_task, publish_task
from backend.tasks.orchestration import resolve_video_decision_sync
from backend.tasks.studio_tasks import process_studio_batch_sequential_task


# ─── Protected Baseline Channel Guard ─────────────────────────────────────────
PROTECTED_PRODUCTION_IDS = {
    "518b3118-2367-4f84-898f-ff97a61df306",  # orm_test_01
    "UCH90024qrJHA4amGRxnTldw",              # Tomorrow's Circuit
    "UCVe8CMJF4caRzuckVYV8CaQ",              # Nishant Chahar
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_valid_token_payload(account_email: str, scopes: list[str] | None = None, expiry: str = "2099-01-01T00:00:00Z", refresh_token: str = "test_refresh_token") -> dict:
    return {
        "token": f"tok_{uuid.uuid4().hex[:10]}",
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "scopes": list(SCOPES) if scopes is None else scopes,
        "expiry": expiry,
        "account": account_email,
    }


def _run_ffmpeg(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg fixture command failed: {' '.join(cmd)}\n{proc.stderr[-600:]}")


# ─── Module-Scoped Real Media Asset Factory ───────────────────────────────────

@pytest.fixture(scope="module")
def media_assets():
    """Generate real minimal vertical/landscape MP4, subtitle MP4, non-faststart MP4, PNG & invalid files."""
    ffmpeg = get_ffmpeg_binary()
    tmpdir = Path(tempfile.mkdtemp(prefix="cf_mde_media_"))
    try:
        # 1. Standard vertical 360x640, 2.0s MP4 with audio + faststart
        base_clip = tmpdir / "base_clip.mp4"
        _run_ffmpeg([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=navy:s=360x640:r=30:d=2.0",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=2.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ac", "2", "-ar", "44100",
            "-movflags", "+faststart",
            str(base_clip),
        ])

        # 2. Base clip containing a subtitle stream (to verify -sn stripping)
        srt_file = tmpdir / "sample.srt"
        srt_file.write_text("1\n00:00:00,100 --> 00:00:01,800\nBurned test caption\n", encoding="utf-8")
        base_clip_sub = tmpdir / "base_clip_sub.mp4"
        _run_ffmpeg([
            ffmpeg, "-y",
            "-i", str(base_clip),
            "-i", str(srt_file),
            "-map", "0:v", "-map", "0:a", "-map", "1:s",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
            "-movflags", "+faststart",
            str(base_clip_sub),
        ])

        # 3. 57.0s vertical clip (low fps/ultrafast -> fast encode) to verify >60s Shorts flag
        base_clip_57s = tmpdir / "base_clip_57s.mp4"
        _run_ffmpeg([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=darkgreen:s=360x640:r=5:d=57.0",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", "57.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "64k",
            "-movflags", "+faststart",
            str(base_clip_57s),
        ])

        # 4. Vertical video outro (720x1280 -> scales cleanly onto 360x640), 1.5s, with audio
        video_outro = tmpdir / "video_outro.mp4"
        _run_ffmpeg([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=crimson:s=720x1280:r=30:d=1.5",
            "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=44100:duration=1.5",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ac", "2", "-ar", "44100",
            "-movflags", "+faststart",
            str(video_outro),
        ])

        # 5. Landscape silent video outro (1280x720, no audio) to prove aspect letterbox + audio synthesis
        video_outro_landscape = tmpdir / "video_outro_landscape.mp4"
        _run_ffmpeg([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=teal:s=1280x720:r=30:d=1.2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            str(video_outro_landscape),
        ])

        # 6. Non-faststart MP4 (mdat before moov)
        non_faststart = tmpdir / "non_faststart.mp4"
        _run_ffmpeg([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=purple:s=360x640:r=30:d=1.5",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", "1.5",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ac", "2",
            str(non_faststart),
        ])

        # 7. Image outros (PNGs)
        image_outro = tmpdir / "image_outro.png"
        Image.new("RGB", (360, 640), color=(220, 40, 40)).save(image_outro)

        image_outro_v2 = tmpdir / "image_outro_v2.png"
        Image.new("RGB", (360, 640), color=(40, 180, 220)).save(image_outro_v2)

        # 8. Invalid / corrupt fixtures
        corrupt_mp4 = tmpdir / "corrupt.mp4"
        corrupt_mp4.write_bytes(b"NOT_A_REAL_MP4_CONTAINER_HEADER_000000")

        corrupt_png = tmpdir / "corrupt.png"
        corrupt_png.write_bytes(b"NOT_A_PNG_IMAGE")

        bad_txt = tmpdir / "invalid.txt"
        bad_txt.write_text("plain text outro", encoding="utf-8")

        bad_gif = tmpdir / "animated.gif"
        Image.new("RGB", (64, 64), color=(10, 10, 10)).save(bad_gif, format="GIF")

        # 9. Thumbnail image
        thumb_jpg = tmpdir / "thumb.jpg"
        Image.new("RGB", (360, 640), color=(30, 30, 60)).save(thumb_jpg, format="JPEG")

        yield SimpleNamespace(
            base_clip=base_clip,
            base_clip_sub=base_clip_sub,
            base_clip_57s=base_clip_57s,
            video_outro=video_outro,
            video_outro_landscape=video_outro_landscape,
            non_faststart=non_faststart,
            image_outro=image_outro,
            image_outro_v2=image_outro_v2,
            corrupt_mp4=corrupt_mp4,
            corrupt_png=corrupt_png,
            bad_txt=bad_txt,
            bad_gif=bad_gif,
            thumb_jpg=thumb_jpg,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Per-Test Isolation & FK-Safe Cleanup Tracker ─────────────────────────────

class EnvTracker:
    """Tracks every DB row and temp path created during a test and removes them safely in teardown."""

    def __init__(self, tmp_path: Path, media):
        self.tmp_path = tmp_path
        self.media = media
        self.channel_ids: set[str] = set()
        self.yt_channel_ids: set[str] = set()
        self.video_ids: set[str] = set()
        self.job_ids: set[str] = set()
        self.clip_ids: set[str] = set()
        self.batch_ids: set[str] = set()
        self.decision_ids: set[str] = set()
        self.outro_ids: set[str] = set()
        self.target_ids: set[str] = set()

    def track_channel(self, channel_id: str, yt_id: str | None = None) -> str:
        assert channel_id not in PROTECTED_PRODUCTION_IDS
        if yt_id:
            assert yt_id not in PROTECTED_PRODUCTION_IDS
            self.yt_channel_ids.add(yt_id)
        self.channel_ids.add(channel_id)
        return channel_id

    def write_token(self, yt_channel_id: str, account_email: str, scopes: list[str] | None = None, expiry: str = "2099-01-01T00:00:00Z", refresh_token: str = "rt_test_token") -> Path:
        token_dir = Path(settings.YOUTUBE_TOKEN_FILE).parent
        token_dir.mkdir(parents=True, exist_ok=True)
        path = token_dir / f"youtube_token_{yt_channel_id}.json"
        path.write_text(
            json.dumps(_make_valid_token_payload(account_email=account_email, scopes=scopes, expiry=expiry, refresh_token=refresh_token)),
            encoding="utf-8",
        )
        return path

    def create_channel(
        self,
        *,
        name: str,
        is_destination: bool = True,
        is_active: bool = True,
        is_test: bool = True,
        is_default_destination: bool = False,
        auto_clip: bool = False,
        auto_publish: bool = False,
        last_checked_at: datetime | None = None,
        processing_profile: dict | None = None,
        publish_destination_id: str | None = None,
        with_token: bool = False,
        account_email: str | None = None,
        scopes: list[str] | None = None,
        expiry: str = "2099-01-01T00:00:00Z",
        refresh_token: str = "rt_test_token",
    ) -> tuple[str, str]:
        suffix = uuid.uuid4().hex[:10]
        prefix = "mde_ch" if is_test else "yt_test_mde"
        ch_id = f"{prefix}_{suffix}"
        yt_id = f"UC_{prefix}_{suffix}"
        self.track_channel(ch_id, yt_id)

        with SyncSessionLocal() as session:
            ch = Channel(
                id=ch_id,
                youtube_channel_id=yt_id,
                channel_name=name,
                channel_url=f"https://www.youtube.com/channel/{yt_id}",
                is_active=is_active,
                auto_clip=auto_clip,
                auto_publish=auto_publish,
                last_checked_at=last_checked_at,
                publish_destination_id=publish_destination_id,
                processing_profile=processing_profile,
                is_destination=is_destination,
                is_default_destination=is_default_destination,
                is_test=is_test,
                created_at=datetime.now(timezone.utc),
            )
            session.add(ch)
            session.commit()

        if with_token:
            self.write_token(
                yt_id,
                account_email=account_email or f"{suffix}@example.com",
                scopes=scopes,
                expiry=expiry,
                refresh_token=refresh_token,
            )
        return ch_id, yt_id

    def create_video_and_clip(
        self,
        *,
        clip_title: str = "MDE E2E Short",
        duration: float = 2.0,
        source_asset: Path | None = None,
        publish_destination_id: str | None = None,
        channel_id: str | None = None,
        upload_batch_id: str | None = None,
        publish_status: str = PublishStatus.DRAFT.value,
        destination_ids: list[str] | None = None,
        job_id: str | None = None,
        clip_status: str = "completed",
    ) -> tuple[str, str, Path]:
        vid_id = f"mde_vid_{uuid.uuid4().hex[:10]}"
        clip_id = f"mde_clip_{uuid.uuid4().hex[:10]}"
        self.video_ids.add(vid_id)
        self.clip_ids.add(clip_id)

        src = source_asset or self.media.base_clip
        clip_rel = f"outputs/{vid_id}/clips/{clip_id}/final.mp4"
        clip_dest = settings.OUTPUT_DIR / vid_id / "clips" / clip_id / "final.mp4"
        clip_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, clip_dest)

        thumb_dest = settings.OUTPUT_DIR / vid_id / "clips" / clip_id / "thumb.jpg"
        shutil.copy2(self.media.thumb_jpg, thumb_dest)

        actual_dur = duration
        if source_asset is not None:
            try:
                p = probe_media_with_ffprobe(clip_dest)
                actual_dur = float(p.get("format", {}).get("duration") or duration)
            except Exception:
                pass

        now = datetime.now(timezone.utc)
        with SyncSessionLocal() as session:
            v = Video(
                id=vid_id,
                title=f"Source Video {vid_id}",
                youtube_url=f"https://www.youtube.com/watch?v={vid_id}",
                youtube_id=vid_id,
                channel_id=channel_id,
                upload_batch_id=upload_batch_id,
                duration=120.0,
                created_at=now,
            )
            session.add(v)
            if job_id:
                self.job_ids.add(job_id)
                session.add(Job(
                    id=job_id,
                    video_id=vid_id,
                    channel_id=channel_id,
                    source_url=v.youtube_url,
                    source_title=v.title,
                    status=JobStatus.COMPLETED.value,
                    progress=100,
                    current_step="Completed",
                    is_test=True,
                    created_at=now,
                    updated_at=now,
                ))
            c = Clip(
                id=clip_id,
                video_id=vid_id,
                title=clip_title,
                description="E2E test description",
                start_time=0.0,
                end_time=actual_dur,
                duration=actual_dur,
                score=0.95,
                output_path=clip_rel,
                thumbnail_path=str(thumb_dest),
                publish_status=publish_status,
                publish_destination_id=publish_destination_id,
                privacy="private",
                status=clip_status,
                run_identity=f"{job_id}_v1_h1" if job_id else None,
                created_at=now,
            )
            session.add(c)
            session.flush()
            if destination_ids:
                for did in destination_ids:
                    pt = PublishTarget(
                        id=str(uuid.uuid4()),
                        clip_id=clip_id,
                        destination_id=did,
                        status="pending",
                        privacy="private",
                        publish_stage="pending",
                        publish_progress=0.0,
                        idempotency_key=f"pub_{clip_id}_{did}",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(pt)
                    self.target_ids.add(pt.id)
            session.commit()
        return vid_id, clip_id, clip_dest

    def cleanup_db(self, baseline_reserved_bytes: int | None):
        with SyncSessionLocal() as session:
            # Discover dynamically created child rows linked to tracked channels/videos/batches/decisions
            if self.channel_ids:
                dec_rows = session.query(VideoDecision.id, VideoDecision.job_id).filter(
                    VideoDecision.channel_id.in_(list(self.channel_ids))
                ).all()
                for d_id, j_id in dec_rows:
                    self.decision_ids.add(d_id)
                    if j_id:
                        self.job_ids.add(j_id)

                vid_rows = session.query(Video.id).filter(Video.channel_id.in_(list(self.channel_ids))).all()
                for (v_id,) in vid_rows:
                    self.video_ids.add(v_id)

                job_rows = session.query(Job.id, Job.video_id).filter(Job.channel_id.in_(list(self.channel_ids))).all()
                for j_id, v_id in job_rows:
                    self.job_ids.add(j_id)
                    if v_id:
                        self.video_ids.add(v_id)

            if self.batch_ids:
                b_vids = session.query(Video.id, Video.processing_job_id).filter(
                    Video.upload_batch_id.in_(list(self.batch_ids))
                ).all()
                for v_id, j_id in b_vids:
                    self.video_ids.add(v_id)
                    if j_id:
                        self.job_ids.add(j_id)
                for bid in self.batch_ids:
                    matched = session.query(Job.id).filter(Job.config.like(f"%{bid}%")).all()
                    for (j_id,) in matched:
                        self.job_ids.add(j_id)

            if self.decision_ids:
                dj_rows = session.query(VideoDecision.job_id, VideoDecision.video_id).filter(
                    VideoDecision.id.in_(list(self.decision_ids))
                ).all()
                for j_id, v_id in dj_rows:
                    if j_id:
                        self.job_ids.add(j_id)
                    if v_id:
                        self.video_ids.add(v_id)

            # Catch test jobs created by videos/url, videos/batch, videos/upload mentioning tracked destinations
            for ch_id in self.channel_ids:
                matched_jobs = session.query(Job.id).filter(Job.config.like(f"%{ch_id}%")).all()
                for (j_id,) in matched_jobs:
                    self.job_ids.add(j_id)
            if self.job_ids:
                jv_rows = session.query(Job.video_id).filter(Job.id.in_(list(self.job_ids)), Job.video_id.isnot(None)).all()
                for (v_id,) in jv_rows:
                    self.video_ids.add(v_id)
                for j_id in self.job_ids:
                    c_rows = session.query(Clip.id).filter(Clip.run_identity.like(f"{j_id}%")).all()
                    for (c_id,) in c_rows:
                        self.clip_ids.add(c_id)

            if self.video_ids:
                vc_rows = session.query(Clip.id).filter(Clip.video_id.in_(list(self.video_ids))).all()
                for (c_id,) in vc_rows:
                    self.clip_ids.add(c_id)
                vj_rows = session.query(Job.id).filter(Job.video_id.in_(list(self.video_ids))).all()
                for (j_id,) in vj_rows:
                    self.job_ids.add(j_id)

            # FK-safe deletion order
            if self.clip_ids:
                session.query(VideoTrackingQueue).filter(VideoTrackingQueue.clip_id.in_(list(self.clip_ids))).delete(synchronize_session=False)
                session.query(PublishRecord).filter(PublishRecord.clip_id.in_(list(self.clip_ids))).delete(synchronize_session=False)
                session.query(PublishTarget).filter(PublishTarget.clip_id.in_(list(self.clip_ids))).delete(synchronize_session=False)
                session.query(TaskExecution).filter(TaskExecution.clip_id.in_(list(self.clip_ids))).delete(synchronize_session=False)
                session.query(ClipVariant).filter(ClipVariant.clip_id.in_(list(self.clip_ids))).delete(synchronize_session=False)

            if self.channel_ids:
                session.query(PublishTarget).filter(PublishTarget.destination_id.in_(list(self.channel_ids))).delete(synchronize_session=False)
            if self.target_ids:
                session.query(PublishTarget).filter(PublishTarget.id.in_(list(self.target_ids))).delete(synchronize_session=False)

            if self.job_ids:
                session.query(TaskExecution).filter(TaskExecution.job_id.in_(list(self.job_ids))).delete(synchronize_session=False)

            owner_ids = list(self.clip_ids | self.video_ids | self.job_ids)
            if owner_ids:
                session.query(ArtifactRecord).filter(ArtifactRecord.owner_id.in_(owner_ids)).delete(synchronize_session=False)

            if self.clip_ids:
                session.query(Clip).filter(Clip.id.in_(list(self.clip_ids))).delete(synchronize_session=False)
            if self.job_ids:
                session.query(Job).filter(Job.id.in_(list(self.job_ids))).delete(synchronize_session=False)
            if self.video_ids:
                session.query(Video).filter(Video.id.in_(list(self.video_ids))).delete(synchronize_session=False)
            if self.batch_ids:
                session.query(UploadBatch).filter(UploadBatch.id.in_(list(self.batch_ids))).delete(synchronize_session=False)
            if self.decision_ids:
                session.query(VideoDecision).filter(VideoDecision.id.in_(list(self.decision_ids))).delete(synchronize_session=False)

            if self.channel_ids:
                session.query(ChannelDestination).filter(
                    (ChannelDestination.source_channel_id.in_(list(self.channel_ids)))
                    | (ChannelDestination.destination_channel_id.in_(list(self.channel_ids)))
                ).delete(synchronize_session=False)
                # Break circular FK Channel.active_outro_id -> DestinationOutro.id before deleting outro/channel
                session.query(Channel).filter(Channel.id.in_(list(self.channel_ids))).update(
                    {"active_outro_id": None, "publish_destination_id": None},
                    synchronize_session=False,
                )
                session.query(DestinationOutro).filter(
                    DestinationOutro.channel_id.in_(list(self.channel_ids))
                ).delete(synchronize_session=False)
                session.query(Channel).filter(Channel.id.in_(list(self.channel_ids))).delete(synchronize_session=False)

            if self.outro_ids:
                session.query(DestinationOutro).filter(DestinationOutro.id.in_(list(self.outro_ids))).delete(synchronize_session=False)

            if baseline_reserved_bytes is not None:
                coord = session.query(StorageReservationCoordinator).filter_by(id="global").first()
                if coord:
                    coord.reserved_bytes = baseline_reserved_bytes

            session.commit()


@pytest.fixture
async def isolated_env(tmp_path, monkeypatch, media_assets):
    """Redirect storage/tokens/mock state to tmp_path, enable test mode, and enforce strict teardown."""
    base_dir = tmp_path.resolve()
    upload_dir = (base_dir / "uploads").resolve()
    output_dir = (base_dir / "outputs").resolve()
    token_dir = (base_dir / "tokens").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file = token_dir / "youtube_token.json"

    monkeypatch.setattr(settings, "BASE_DIR", base_dir)
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(settings, "YOUTUBE_TOKEN_FILE", str(token_file))
    monkeypatch.setattr(settings, "PUBLISH_MODE", "test")
    monkeypatch.setenv("PUBLISH_MODE", "test")

    if hasattr(storage_service, "provider"):
        if hasattr(storage_service.provider, "upload_dir"):
            monkeypatch.setattr(storage_service.provider, "upload_dir", upload_dir)
        if hasattr(storage_service.provider, "output_dir"):
            monkeypatch.setattr(storage_service.provider, "output_dir", output_dir)

    monkeypatch.setattr("backend.services.publisher.sync_authorized_destinations", lambda: None)
    monkeypatch.setattr("backend.api.routes.youtube_channels.sync_authorized_destinations", lambda: None)
    monkeypatch.setattr("backend.api.routes.publish.sync_authorized_destinations", lambda: None, raising=False)

    baseline_reserved = None
    with SyncSessionLocal() as session:
        coord = session.query(StorageReservationCoordinator).filter_by(id="global").first()
        if coord:
            baseline_reserved = coord.reserved_bytes

    tracker = EnvTracker(tmp_path=tmp_path, media=media_assets)
    try:
        yield tracker
    finally:
        await engine.dispose()
        tracker.cleanup_db(baseline_reserved)
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9 — FULL END-TO-END LIFECYCLE TESTS (01-05)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_lifecycle_01_connect_channels_and_outro_crud(isolated_env, media_assets):
    """
    Lifecycle 01:
    - OAuth URL + /connect flow for multiple destination channels with distinct google_account_identity
    - Dest A: MP4 video outro upload (201), GET metadata, preview stream (200)
    - Dest B: PNG image outro v1 (3.0s) -> PATCH duration=4.5s bumps version to 2
    - Dest C: No outro initially (404), add PNG (v1), replace with MP4 (v2, old deactivated), DELETE removes active outro
    """
    t = isolated_env

    # 1. Verify OAuth URL generation and mocked /api/youtube-channels/connect
    conn_suffix = uuid.uuid4().hex[:8]
    conn_yt_id = f"UC_yt_test_conn_{conn_suffix}"
    conn_ch_id = f"yt_test_conn_{conn_suffix}"
    t.track_channel(conn_ch_id, conn_yt_id)

    def _fake_exchange_code_for_token(code: str, redirect_uri: str = None):
        with SyncSessionLocal() as s:
            s.add(Channel(
                id=conn_ch_id,
                youtube_channel_id=conn_yt_id,
                channel_name="Connected Brand Alpha",
                channel_url=f"https://www.youtube.com/channel/{conn_yt_id}",
                thumbnail_url="https://example.com/thumb_alpha.png",
                is_active=True,
                is_destination=True,
                is_default_destination=False,
                is_test=False,
                created_at=datetime.now(timezone.utc),
            ))
            s.commit()
        t.write_token(conn_yt_id, account_email="alpha_owner@example.com")
        return {"channel_id": conn_yt_id, "title": "Connected Brand Alpha", "thumbnail_url": "https://example.com/thumb_alpha.png"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        oauth_resp = await client.get("/api/youtube-channels/oauth-url")
        assert oauth_resp.status_code == 200
        assert "select_account" in oauth_resp.json()["oauth_url"]

        with (
            patch("backend.api.routes.youtube_channels.exchange_code_for_token", side_effect=_fake_exchange_code_for_token),
            patch("backend.api.routes.youtube_channels.fetch_channel_analytics", return_value={"subscriber_count": 1200, "video_count": 15}),
        ):
            conn_resp = await client.post("/api/youtube-channels/connect", json={"code": f"auth_code_{conn_suffix}"})
            assert conn_resp.status_code == 200, conn_resp.text
            conn_data = conn_resp.json()["channel"]
            assert conn_data["id"] == conn_ch_id
            assert conn_data["google_account_identity"] == "alpha_owner@example.com"
            assert conn_data["upload_permission_status"] == "granted"
            assert conn_data["ready_for_publishing"] is True
            assert conn_data["has_outro"] is False

    # 2. Setup 3 isolated test destinations with distinct OAuth identities
    dest_a, _ = t.create_channel(name="Dest A Video Outro", is_destination=True, with_token=True, account_email="acct_a@example.com")
    dest_b, _ = t.create_channel(name="Dest B Image Outro", is_destination=True, with_token=True, account_email="acct_b@example.com")
    dest_c, _ = t.create_channel(name="Dest C No Outro", is_destination=True, with_token=True, account_email="acct_c@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Dest A: Upload MP4 video outro
        with open(media_assets.video_outro, "rb") as f:
            up_a = await client.post(
                f"/api/youtube-channels/{dest_a}/outro",
                data={"outro_type": "video"},
                files={"file": ("brand_outro.mp4", f, "video/mp4")},
            )
        assert up_a.status_code == 201, up_a.text
        outro_a = up_a.json()["outro"]
        assert outro_a["outro_type"] == "video"
        assert outro_a["version"] == 1
        assert 1.2 <= outro_a["duration_seconds"] <= 1.8
        assert outro_a["has_audio"] is True

        # GET metadata & preview stream for Dest A
        get_a = await client.get(f"/api/youtube-channels/{dest_a}/outro")
        assert get_a.status_code == 200
        assert get_a.json()["outro"]["id"] == outro_a["id"]

        prev_a = await client.get(f"/api/youtube-channels/{dest_a}/outro/preview")
        assert prev_a.status_code == 200
        assert prev_a.headers["content-type"].startswith("video/mp4")
        assert len(prev_a.content) > 1000

        # Dest B: Upload PNG image outro (default duration=3.0), then PATCH duration=4.5 -> version 2
        with open(media_assets.image_outro, "rb") as f:
            up_b = await client.post(
                f"/api/youtube-channels/{dest_b}/outro",
                data={"outro_type": "image"},
                files={"file": ("endcard.png", f, "image/png")},
            )
        assert up_b.status_code == 201, up_b.text
        outro_b_v1 = up_b.json()["outro"]
        assert outro_b_v1["outro_type"] == "image"
        assert outro_b_v1["duration_seconds"] == 3.0
        assert outro_b_v1["version"] == 1

        patch_b = await client.patch(f"/api/youtube-channels/{dest_b}/outro", json={"duration_seconds": 4.5})
        assert patch_b.status_code == 200, patch_b.text
        outro_b_v2 = patch_b.json()["outro"]
        assert outro_b_v2["duration_seconds"] == 4.5
        assert outro_b_v2["version"] == 2

        # Dest C: Initially no outro (404), then add PNG -> replace with MP4 -> DELETE active outro
        get_c0 = await client.get(f"/api/youtube-channels/{dest_c}/outro")
        assert get_c0.status_code == 404

        with open(media_assets.image_outro, "rb") as f:
            up_c1 = await client.post(
                f"/api/youtube-channels/{dest_c}/outro",
                data={"outro_type": "image", "duration_seconds": "2.5"},
                files={"file": ("c_img.png", f, "image/png")},
            )
        assert up_c1.status_code == 201
        c_v1_id = up_c1.json()["outro"]["id"]
        c_v1_path = resolve_safe_outro_path(up_c1.json()["outro"]["file_path"])
        assert c_v1_path.exists()

        with open(media_assets.video_outro, "rb") as f:
            up_c2 = await client.post(
                f"/api/youtube-channels/{dest_c}/outro",
                data={"outro_type": "video"},
                files={"file": ("c_vid.mp4", f, "video/mp4")},
            )
        assert up_c2.status_code == 201
        c_v2 = up_c2.json()["outro"]
        assert c_v2["version"] == 2
        assert c_v2["id"] != c_v1_id

        with SyncSessionLocal() as s:
            old_row = s.query(DestinationOutro).filter_by(id=c_v1_id).first()
            assert old_row is not None and old_row.is_active is False

        del_c = await client.delete(f"/api/youtube-channels/{dest_c}/outro")
        assert del_c.status_code == 200
        assert (await client.get(f"/api/youtube-channels/{dest_c}/outro")).status_code == 404
        assert c_v1_path.exists(), "Historical outro asset file should remain preserved on disk after delete/replace"

        # List destinations with include_test=true and verify distinct accounts + outro summaries
        list_resp = await client.get("/api/youtube-channels/?include_test=true")
        assert list_resp.status_code == 200
        by_id = {row["id"]: row for row in list_resp.json()}
        assert by_id[dest_a]["google_account_identity"] == "acct_a@example.com"
        assert by_id[dest_a]["has_outro"] is True
        assert by_id[dest_a]["active_outro"]["outro_type"] == "video"
        assert by_id[dest_b]["google_account_identity"] == "acct_b@example.com"
        assert by_id[dest_b]["active_outro"]["duration_seconds"] == 4.5
        assert by_id[dest_c]["google_account_identity"] == "acct_c@example.com"
        assert by_id[dest_c]["has_outro"] is False
        assert by_id[dest_c]["outro_status"] == "none"


@pytest.mark.asyncio
async def test_e2e_lifecycle_02_source_to_destination_mapping_and_nm(isolated_env, media_assets):
    """
    Lifecycle 02:
    - Map 3 destinations -> monitored Source 1 (1:N)
    - Map Dest A + Dest C -> monitored Source 2 (N:M)
    - Verify mapped_sources_count & update ordering cleanly
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="Dest Map A", is_destination=True, with_token=True)
    dest_b, _ = t.create_channel(name="Dest Map B", is_destination=True, with_token=True)
    dest_c, _ = t.create_channel(name="Dest Map C", is_destination=True, with_token=True)
    src_1, _ = t.create_channel(name="Source 1", is_destination=False, auto_clip=True, auto_publish=True)
    src_2, _ = t.create_channel(name="Source 2", is_destination=False, auto_clip=True, auto_publish=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.put(f"/api/channels/{src_1}/destinations", json={"destination_channel_ids": [dest_a, dest_b, dest_c]})
        assert r1.status_code == 200, r1.text
        assert r1.json()["destination_channel_ids"] == [dest_a, dest_b, dest_c]
        assert r1.json()["publish_destination_id"] == dest_a

        r2 = await client.put(f"/api/channels/{src_2}/destinations", json={"destination_channel_ids": [dest_a, dest_c]})
        assert r2.status_code == 200, r2.text
        assert r2.json()["destination_channel_ids"] == [dest_a, dest_c]

        g1 = await client.get(f"/api/channels/{src_1}/destinations")
        assert g1.status_code == 200
        assert len(g1.json()["destinations"]) == 3
        assert g1.json()["active_destinations_count"] == 3
        assert g1.json()["disconnected_destinations_count"] == 0

        yt_list = await client.get("/api/youtube-channels/?include_test=true")
        by_id = {c["id"]: c for c in yt_list.json()}
        assert by_id[dest_a]["mapped_sources_count"] == 2
        assert by_id[dest_b]["mapped_sources_count"] == 1
        assert by_id[dest_c]["mapped_sources_count"] == 2

        # Replace mapping on Source 1 to [dest_c, dest_a] (existing rows keep created_at sort in GET/PUT list; primary updates to dest_c)
        r1_upd = await client.put(f"/api/channels/{src_1}/destinations", json={"destination_channel_ids": [dest_c, dest_a]})
        assert r1_upd.status_code == 200
        assert set(r1_upd.json()["destination_channel_ids"]) == {dest_c, dest_a}
        assert len(r1_upd.json()["destination_channel_ids"]) == 2
        assert r1_upd.json()["publish_destination_id"] == dest_c

        yt_list2 = await client.get("/api/youtube-channels/?include_test=true")
        by_id2 = {c["id"]: c for c in yt_list2.json()}
        assert by_id2[dest_b]["mapped_sources_count"] == 0
        assert by_id2[dest_c]["mapped_sources_count"] == 2


@pytest.mark.asyncio
async def test_e2e_lifecycle_03_destination_propagation_across_all_4_entrypoints(isolated_env, media_assets, tmp_path):
    """
    Lifecycle 03:
    Verify selected / mapped destination_ids propagate faithfully through:
    (a) Monitored channel check-now -> VideoDecision -> resolve_video_decision_sync -> clip_selection_task -> PublishTargets
    (b) Manual YouTube URL (/api/videos/url) with explicit destination_ids AND channel_id inheritance + /api/videos/batch
    (c) Manual local file upload (/api/videos/upload)
    (d) Upload Studio batch (/api/studio/batches -> videos/init -> chunk -> process -> process_studio_batch_sequential_task)
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="Prop Dest A", is_destination=True, with_token=True)
    dest_b, _ = t.create_channel(name="Prop Dest B", is_destination=True, with_token=True)
    dest_c, _ = t.create_channel(name="Prop Dest C", is_destination=True, with_token=True)

    # Monitored source with baseline already established so check-now emits the new mock video
    src_id, _ = t.create_channel(
        name="Prop Source",
        is_destination=False,
        auto_clip=True,
        auto_publish=True,
        last_checked_at=datetime.now(timezone.utc) - timedelta(hours=1),
        processing_profile={
            "clip_mode": "equal_split",
            "target_duration": 20.0,
            "monitoring_baseline": {
                "baseline_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "known_historical_ids": ["old_hist_vid"],
            },
        },
        publish_destination_id=dest_a,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        map_r = await client.put(f"/api/channels/{src_id}/destinations", json={"destination_channel_ids": [dest_a, dest_b, dest_c]})
        assert map_r.status_code == 200

        # ── (a) Monitoring check-now -> countdown decision -> clip_selection_task ──
        new_yt_vid = f"yt_mon_{uuid.uuid4().hex[:8]}"
        mock_vids = [{
            "id": new_yt_vid,
            "title": "Monitored New Arrival",
            "url": f"https://www.youtube.com/watch?v={new_yt_vid}",
            "duration": 180.0,
            "thumbnails": [{"url": "https://example.com/t.jpg"}],
        }]
        with (
            patch("backend.services.channel_monitor.get_channel_videos", new=AsyncMock(return_value=mock_vids)),
            patch("backend.tasks.orchestration.resolve_video_decision_countdown_task.apply_async") as mock_countdown,
        ):
            chk = await client.post(f"/api/channels/{src_id}/check-now")
            assert chk.status_code == 200, chk.text
            assert chk.json()["new_videos_found"] == 1
            decision_id = chk.json()["decisions"][0]["decision_id"]
            t.decision_ids.add(decision_id)
            mock_countdown.assert_called_once()

        with SyncSessionLocal() as s:
            dec = s.query(VideoDecision).filter_by(id=decision_id).first()
            assert dec is not None
            assert dec.channel_profile_snapshot["destination_ids"] == [dest_a, dest_b, dest_c]

        captured_start_kwargs = {}
        with patch(
            "backend.tasks.orchestration.start_video_processing_task.apply_async",
            side_effect=lambda **kw: captured_start_kwargs.update(kw.get("kwargs", {})) or SimpleNamespace(id="celery_mon_1"),
        ):
            res_dec = resolve_video_decision_sync(decision_id, action="countdown")
        mon_job_id = res_dec["job_id"]
        t.job_ids.add(mon_job_id)
        assert captured_start_kwargs["destination_ids"] == [dest_a, dest_b, dest_c]
        assert captured_start_kwargs["auto_publish"] is True

        # Prepare Video + scored_clips.json artifact so clip_selection_task runs natively against Postgres
        mon_vid_id = f"mde_mon_v_{uuid.uuid4().hex[:8]}"
        t.video_ids.add(mon_vid_id)
        scored_tmp = tmp_path / "scored.json"
        scored_tmp.write_text(json.dumps([
            {"title": "Monitored Highlight 1", "start": 0.0, "end": 2.0, "duration": 2.0, "score": 0.92, "text": "hello world", "description": "desc 1"}
        ]), encoding="utf-8")
        with SyncSessionLocal() as s:
            s.add(Video(id=mon_vid_id, title="Monitored New Arrival", youtube_id=new_yt_vid, youtube_url=f"https://www.youtube.com/watch?v={new_yt_vid}", channel_id=src_id, duration=180.0))
            j_mon = s.query(Job).filter_by(id=mon_job_id).first()
            assert json.loads(j_mon.config)["destination_ids"] == [dest_a, dest_b, dest_c]
            j_mon.video_id = mon_vid_id
            s.commit()

        with managed_upload_sync(
            owner_type="video",
            owner_id=mon_vid_id,
            artifact_type=ArtifactType.SCORED_CLIPS,
            storage_key=f"uploads/{mon_vid_id}/scored_clips.json",
            retention_policy="temporary",
        ) as up_path:
            shutil.copy2(scored_tmp, up_path)

        with patch("backend.services.source_metadata_engine.get_or_analyze_source_seo_metadata", return_value=None):
            clip_ids = clip_selection_task.apply(args=[{
                "video_id": mon_vid_id,
                "job_id": mon_job_id,
                "candidate_set_hash": "h_mon",
                "scoring_version": "v1",
            }]).get()

        assert len(clip_ids) == 1
        t.clip_ids.update(clip_ids)
        with SyncSessionLocal() as s:
            c_mon = s.query(Clip).filter_by(id=clip_ids[0]).first()
            assert c_mon.publish_destination_id == dest_a
            pts = s.query(PublishTarget).filter_by(clip_id=c_mon.id).all()
            assert {p.destination_id for p in pts} == {dest_a, dest_b, dest_c}

        # ── (b) Manual YouTube URL (explicit multi-dest + inherited channel_id) & Batch ──
        dispatched_calls = []
        with (
            patch("backend.services.queue_manager.get_active_manual_jobs_count_async", new=AsyncMock(return_value=0)),
            patch("backend.services.queue_manager.dispatch_celery_job", side_effect=lambda jid, kw: dispatched_calls.append((jid, kw)) or f"task_{jid}"),
        ):
            r_url = await client.post("/api/videos/url", data={
                "url": f"https://www.youtube.com/watch?v=test_{uuid.uuid4().hex[:6]}",
                "clip_mode": "equal_split",
                "target_duration": "20",
                "destination_ids": json.dumps([dest_a, dest_b]),
                "is_test": "true",
            })
            assert r_url.status_code == 200, r_url.text
            url_job_id = r_url.json()["job_id"]
            t.job_ids.add(url_job_id)

            r_inh = await client.post("/api/videos/url", data={
                "url": f"https://www.youtube.com/watch?v=test_{uuid.uuid4().hex[:6]}",
                "clip_mode": "equal_split",
                "target_duration": "20",
                "channel_id": src_id,
                "is_test": "true",
            })
            assert r_inh.status_code == 200, r_inh.text
            inh_job_id = r_inh.json()["job_id"]
            t.job_ids.add(inh_job_id)

            r_batch = await client.post("/api/videos/batch", json={
                "urls": [
                    f"https://www.youtube.com/watch?v=test_{uuid.uuid4().hex[:6]}",
                    f"https://www.youtube.com/watch?v=test_{uuid.uuid4().hex[:6]}",
                ],
                "clip_mode": "equal_split",
                "target_duration": 20.0,
                "destination_ids": [dest_b, dest_c],
                "is_test": True,
            })
            assert r_batch.status_code == 200, r_batch.text
            batch_job_ids = [item["job_id"] for item in r_batch.json()["jobs"]]
            t.job_ids.update(batch_job_ids)

        with SyncSessionLocal() as s:
            assert json.loads(s.query(Job).filter_by(id=url_job_id).first().config)["destination_ids"] == [dest_a, dest_b]
            assert json.loads(s.query(Job).filter_by(id=inh_job_id).first().config)["destination_ids"] == [dest_a, dest_b, dest_c]
            for bjid in batch_job_ids:
                assert json.loads(s.query(Job).filter_by(id=bjid).first().config)["destination_ids"] == [dest_b, dest_c]

        # ── (c) Manual File Upload ──
        with (
            patch("backend.services.queue_manager.get_active_manual_jobs_count_async", new=AsyncMock(return_value=0)),
            patch("backend.services.queue_manager.dispatch_celery_job", side_effect=lambda jid, kw: f"task_{jid}"),
        ):
            with open(media_assets.base_clip, "rb") as f:
                r_up = await client.post(
                    "/api/videos/upload",
                    data={
                        "clip_mode": "equal_split",
                        "target_duration": "20",
                        "destination_ids": json.dumps([dest_a, dest_c]),
                        "is_test": "true",
                    },
                    files={"file": ("manual_upload.mp4", f, "video/mp4")},
                )
        assert r_up.status_code == 200, r_up.text
        up_job_id = r_up.json()["job_id"]
        t.job_ids.add(up_job_id)
        with SyncSessionLocal() as s:
            up_cfg = json.loads(s.query(Job).filter_by(id=up_job_id).first().config)
            assert up_cfg["destination_ids"] == [dest_a, dest_c]
            assert up_cfg["publish_destination_id"] == dest_a

        # ── (d) Upload Studio Batch (create -> init -> chunk -> process -> sequential task) ──
        file_bytes = media_assets.base_clip.read_bytes()
        file_len = len(file_bytes)
        r_sb = await client.post("/api/studio/batches", json={
            "idempotency_key": f"mde_sb_{uuid.uuid4().hex[:10]}",
            "name": "MDE Studio Batch",
            "destination_ids": [dest_a, dest_b],
        })
        assert r_sb.status_code == 201, r_sb.text
        sb_id = r_sb.json()["id"]
        t.batch_ids.add(sb_id)
        assert r_sb.json()["destination_ids"] == [dest_a, dest_b]

        r_init = await client.post(f"/api/studio/batches/{sb_id}/videos/init", json={
            "client_item_id": f"item_{uuid.uuid4().hex[:8]}",
            "source_filename": "studio_clip.mp4",
            "file_size": file_len,
        })
        assert r_init.status_code == 201, r_init.text
        sv_id = r_init.json()["id"]
        t.video_ids.add(sv_id)

        r_chunk = await client.put(
            f"/api/studio/uploads/{sv_id}/chunk",
            headers={"Content-Range": f"bytes 0-{file_len - 1}/{file_len}"},
            content=file_bytes,
        )
        assert r_chunk.status_code == 200, r_chunk.text
        assert r_chunk.json()["status"] == "uploaded"

        with patch("backend.tasks.studio_tasks.process_studio_batch_sequential_task.delay") as mock_seq_delay:
            r_proc = await client.post(
                f"/api/studio/batches/{sb_id}/process",
                json={"destination_ids": [dest_a, dest_b, dest_c], "clip_mode": "equal_split", "clips_count": 2},
            )
            assert r_proc.status_code == 200, r_proc.text
            assert r_proc.json()["destination_ids"] == [dest_a, dest_b, dest_c]
            mock_seq_delay.assert_called_once()

        studio_dispatched = []
        with (
            patch("backend.services.queue_manager.get_active_manual_jobs_count_sync", return_value=0),
            patch("backend.services.queue_manager.dispatch_celery_job", side_effect=lambda jid, kw: studio_dispatched.append((jid, kw)) or f"st_{jid}"),
        ):
            seq_res = process_studio_batch_sequential_task.run(batch_id=sb_id)
        assert seq_res["status"] == "processing_started"
        studio_job_id = seq_res["job_id"]
        t.job_ids.add(studio_job_id)
        with SyncSessionLocal() as s:
            sj = s.query(Job).filter_by(id=studio_job_id).first()
            sj_cfg = json.loads(sj.config)
            assert sj_cfg["destination_ids"] == [dest_a, dest_b, dest_c]
            assert sj_cfg["publish_destination_id"] == dest_a
        assert studio_dispatched[0][1]["destination_ids"] == [dest_a, dest_b, dest_c]


@pytest.mark.asyncio
async def test_e2e_lifecycle_04_destination_variant_rendering_caching_and_invariants(isolated_env, media_assets):
    """
    Lifecycle 04:
    - Render outputs/{video_id}/clips/{clip_id}/destinations/{dest_id}/final.mp4 + variant_meta.json
    - Base clip final.mp4 SHA-256 & mtime NEVER mutated
    - Subtitles stripped (-sn) even when base clip carries mov_text subtitles
    - Landscape outro letterboxed cleanly without distortion onto vertical 360x640 canvas
    - +faststart moov-before-mdat atom order verified
    - Cache hit on repeat call; cache invalidated on PATCH duration / replacement
    - >60.0s combined duration triggers exceeds_shorts_limit=True in preview-info
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="Var Dest Video", is_destination=True, with_token=True)
    dest_b, _ = t.create_channel(name="Var Dest Image", is_destination=True, with_token=True)
    dest_c, _ = t.create_channel(name="Var Dest None", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Use landscape silent outro for Dest A to verify padding + silent audio synthesis
        with open(media_assets.video_outro_landscape, "rb") as f:
            assert (await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("land.mp4", f, "video/mp4")})).status_code == 201
        with open(media_assets.image_outro, "rb") as f:
            assert (await client.post(f"/api/youtube-channels/{dest_b}/outro", data={"outro_type": "image", "duration_seconds": "4.5"}, files={"file": ("end.png", f, "image/png")})).status_code == 201

        vid_id, clip_id, base_path = t.create_video_and_clip(
            clip_title="Subtitled Variant Test",
            source_asset=media_assets.base_clip_sub,
            destination_ids=[dest_a, dest_b, dest_c],
        )
        base_sha_before = _sha256_file(base_path)
        base_mtime_before = base_path.stat().st_mtime_ns

        # Preview-info before render
        pi_before = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_a}/preview-info")
        assert pi_before.status_code == 200
        assert pi_before.json()["variant_ready"] is False
        assert pi_before.json()["has_outro"] is True
        assert pi_before.json()["exceeds_shorts_limit"] is False

        # Preview triggers render & returns faststart MP4
        prev_a = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_a}/preview")
        assert prev_a.status_code == 200
        variant_a_dir = settings.OUTPUT_DIR / vid_id / "clips" / clip_id / "destinations" / dest_a
        variant_a_mp4 = variant_a_dir / "final.mp4"
        variant_a_meta = variant_a_dir / "variant_meta.json"
        assert variant_a_mp4.exists()
        assert variant_a_meta.exists()

        meta_json = json.loads(variant_a_meta.read_text(encoding="utf-8"))
        assert meta_json["destination_id"] == dest_a
        assert meta_json["faststart"] is True
        assert meta_json["width"] == 360 and meta_json["height"] == 640

        # Verify zero subtitles & moov before mdat & synthesized audio
        probed = probe_media_with_ffprobe(variant_a_mp4)
        streams = probed["streams"]
        assert [s for s in streams if s.get("codec_type") == "subtitle"] == []
        assert len([s for s in streams if s.get("codec_type") == "audio"]) == 1
        assert has_faststart_moov_before_mdat(variant_a_mp4) is True
        assert float(probed["format"]["duration"]) >= 2.8

        # Base clip MUST remain completely untouched
        assert _sha256_file(base_path) == base_sha_before
        assert base_path.stat().st_mtime_ns == base_mtime_before

        # Cache hit verification via render_or_reuse_destination_variant_sync
        with SyncSessionLocal() as s:
            clip_obj = s.query(Clip).filter_by(id=clip_id).first()
            hit = render_or_reuse_destination_variant_sync(clip=clip_obj, destination_id=dest_a, session=s)
            assert hit["reused_cache"] is True
            assert hit["rendered"] is False

        # Dest C (no outro) returns untouched base clip & leaves destinations/{dest_c}/final.mp4 absent
        prev_c = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_c}/preview")
        assert prev_c.status_code == 200
        assert not (settings.OUTPUT_DIR / vid_id / "clips" / clip_id / "destinations" / dest_c / "final.mp4").exists()

        # Dest B PNG outro render + duration update cache invalidation
        prev_b1 = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_b}/preview")
        assert prev_b1.status_code == 200
        pi_b1 = (await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_b}/preview-info")).json()
        assert pi_b1["variant_ready"] is True
        assert pi_b1["stale_variant"] is False

        patch_b = await client.patch(f"/api/youtube-channels/{dest_b}/outro", json={"duration_seconds": 6.0})
        assert patch_b.status_code == 200

        pi_b2 = (await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_b}/preview-info")).json()
        assert pi_b2["variant_ready"] is False
        assert pi_b2["stale_variant"] is True
        assert pi_b2["outro"]["version"] == 2

        with SyncSessionLocal() as s:
            clip_obj = s.query(Clip).filter_by(id=clip_id).first()
            re_rendered = render_or_reuse_destination_variant_sync(clip=clip_obj, destination_id=dest_b, session=s)
            assert re_rendered["rendered"] is True
            assert re_rendered["reused_cache"] is False
            assert re_rendered["outro_version"] == 2
            assert re_rendered["combined_duration"] >= 7.5

        # Exceeds 60s YouTube Shorts limit check on 57s clip + 6.0s outro
        _, clip_57_id, _ = t.create_video_and_clip(
            clip_title="57s Clip",
            source_asset=media_assets.base_clip_57s,
            destination_ids=[dest_b],
        )
        pi_long = (await client.get(f"/api/publish/clips/{clip_57_id}/destinations/{dest_b}/preview-info")).json()
        assert pi_long["base_duration"] >= 56.5
        assert pi_long["combined_duration"] > 60.0
        assert pi_long["exceeds_shorts_limit"] is True


@pytest.mark.asyncio
async def test_e2e_lifecycle_05_publishing_schedule_private_cancel_and_edit_protection(isolated_env, media_assets):
    """
    Lifecycle 05:
    - Schedule with privacy='public' -> forced privacy='private', status='queued', stage='scheduled'
    - Cancel single target cleanly; restore via PUT /publish/clips/{id}/destinations
    - Publish-now across 3 destinations -> execute publish_clip_task -> distinct YouTube IDs, private,
      outro_applied_id populated for A/B and None for C
    - PUT /publish/clips/{id}/destinations returns 409 when removing published or uploading targets
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="Pub Dest A", is_destination=True, with_token=True)
    dest_b, _ = t.create_channel(name="Pub Dest B", is_destination=True, with_token=True)
    dest_c, _ = t.create_channel(name="Pub Dest C", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(media_assets.video_outro, "rb") as f:
            r_oa = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("a.mp4", f, "video/mp4")})
            outro_a_id = r_oa.json()["outro"]["id"]
        with open(media_assets.image_outro, "rb") as f:
            r_ob = await client.post(f"/api/youtube-channels/{dest_b}/outro", data={"outro_type": "image", "duration_seconds": "2.0"}, files={"file": ("b.png", f, "image/png")})
            outro_b_id = r_ob.json()["outro"]["id"]

        _, clip_sched_id, _ = t.create_video_and_clip(clip_title="Lifecycle Scheduled Clip")
        future_iso = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()

        # Schedule with privacy='public' -> private-by-default enforced
        sched = await client.post("/api/publish/schedule", json={
            "clip_id": clip_sched_id,
            "destination_ids": [dest_a, dest_b, dest_c],
            "scheduled_at": future_iso,
            "privacy": "public",
            "title": "Scheduled Multi Short",
        })
        assert sched.status_code == 200, sched.text
        targets = sched.json()["targets"]
        assert len(targets) == 3
        for tg in targets:
            t.target_ids.add(tg["id"])
            assert tg["privacy"] == "private"
            assert tg["status"] == "queued"
            assert tg["publish_stage"] == "scheduled"

        tc_id = next(tg["id"] for tg in targets if tg["destination_id"] == dest_c)
        cancel_c = await client.post(f"/api/publish/targets/{tc_id}/cancel")
        assert cancel_c.status_code == 200
        assert cancel_c.json()["status"] == "cancelled"

        # Update destinations back to all 3 while none are uploading/published
        upd_dest = await client.put(f"/api/publish/clips/{clip_sched_id}/destinations", json={"destination_ids": [dest_a, dest_b, dest_c]})
        assert upd_dest.status_code == 200
        assert set(upd_dest.json()["destination_ids"]) == {dest_a, dest_b, dest_c}

        cancel_all = await client.post(f"/api/publish/clips/{clip_sched_id}/cancel")
        assert cancel_all.status_code == 200
        assert cancel_all.json()["status"] == "cancelled"

        # Publish-now across all 3 destinations on a fresh draft clip -> dispatches 3 independent tasks
        _, clip_id, base_path = t.create_video_and_clip(clip_title="Lifecycle Publish Clip")
        dispatched = []
        with patch(
            "backend.tasks.clip_tasks.publish_clip_task.apply_async",
            side_effect=lambda *args, **kw: dispatched.append((args, kw)) or SimpleNamespace(id=f"tk_{len(dispatched)}"),
        ):
            pub_now = await client.post("/api/publish/publish-now", json={
                "clip_id": clip_id,
                "destination_ids": [dest_a, dest_b, dest_c],
                "privacy": "public",
            })
        assert pub_now.status_code == 202, pub_now.text
        assert len(dispatched) == 3

        # Execute each dispatched publish_clip_task in test mode (fast sleep mock)
        uploaded_paths = []
        from backend.services.publisher import _mock_upload_short

        def _fast_mock_upload(*args, **kw):
            uploaded_paths.append((kw.get("channel_id"), str(kw.get("video_path"))))
            with patch("time.sleep", return_value=None):
                return _mock_upload_short(
                    title=kw["title"],
                    description=kw["description"],
                    idempotency_key=kw["idempotency_key"],
                    progress_callback=kw.get("progress_callback"),
                    clip_id=kw.get("clip_id"),
                    privacy=kw.get("privacy", "private"),
                )

        with patch("backend.services.publisher.upload_short", side_effect=_fast_mock_upload):
            for args, kw in dispatched:
                task_args = list(args) if args else list(kw.get("args", []))
                task_kwargs = kw["kwargs"] if "kwargs" in kw else kw
                res = publish_clip_task.apply(args=task_args, kwargs=task_kwargs).get()
                assert res["status"] == "published"
                assert res["privacy"] == "private"

        with SyncSessionLocal() as s:
            c_db = s.query(Clip).filter_by(id=clip_id).first()
            assert c_db.publish_status == "published"
            assert c_db.privacy == "private"
            pts = {pt.destination_id: pt for pt in s.query(PublishTarget).filter_by(clip_id=clip_id).all()}
            yt_ids = {pts[d].youtube_video_id for d in (dest_a, dest_b, dest_c)}
            assert len(yt_ids) == 3 and all(x and x.startswith("mock_") for x in yt_ids)
            assert pts[dest_a].outro_applied_id == outro_a_id and pts[dest_a].rendered_video_path
            assert pts[dest_b].outro_applied_id == outro_b_id and pts[dest_b].rendered_video_path
            assert pts[dest_c].outro_applied_id is None and pts[dest_c].rendered_video_path is None

        # 409 protection: cannot remove an already published destination
        conflict_pub = await client.put(f"/api/publish/clips/{clip_id}/destinations", json={"destination_ids": [dest_b, dest_c]})
        assert conflict_pub.status_code == 409

        # 409 protection: cannot remove an actively uploading destination
        _, clip2_id, _ = t.create_video_and_clip(destination_ids=[dest_a, dest_b])
        with SyncSessionLocal() as s:
            t_up = s.query(PublishTarget).filter_by(clip_id=clip2_id, destination_id=dest_a).first()
            t_up.status = "uploading"
            s.commit()
        conflict_up = await client.put(f"/api/publish/clips/{clip2_id}/destinations", json={"destination_ids": [dest_b]})
        assert conflict_up.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8 — ALL 15 FAILURE SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_failure_01_no_destination_selected_explicit_empty_blocks_autopublish(isolated_env, tmp_path):
    """
    Failure 01: Explicit destination_ids=[] blocks auto-publish & keeps clip as draft,
    even if source channel has active ChannelDestination defaults & auto_publish=True.
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F01 Dest A", is_destination=True, with_token=True)
    src_id, _ = t.create_channel(name="F01 Source", is_destination=False, auto_clip=True, auto_publish=True, publish_destination_id=dest_a)

    with SyncSessionLocal() as s:
        s.add(ChannelDestination(id=str(uuid.uuid4()), source_channel_id=src_id, destination_channel_id=dest_a, is_default=True))
        s.commit()
        assert resolve_publish_destinations({"destination_ids": []}, src_id, s) == []

    # Manual /videos/url with explicit empty destination_ids="[]" stores [] and None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("backend.services.queue_manager.get_active_manual_jobs_count_async", new=AsyncMock(return_value=0)),
            patch("backend.services.queue_manager.dispatch_celery_job", side_effect=lambda jid, kw: f"tk_{jid}"),
        ):
            r_url = await client.post("/api/videos/url", data={
                "url": f"https://www.youtube.com/watch?v=test_{uuid.uuid4().hex[:6]}",
                "clip_mode": "equal_split",
                "target_duration": "20",
                "destination_ids": "[]",
                "is_test": "true",
            })
        assert r_url.status_code == 200
        job_empty_id = r_url.json()["job_id"]
        t.job_ids.add(job_empty_id)
        with SyncSessionLocal() as s:
            cfg = json.loads(s.query(Job).filter_by(id=job_empty_id).first().config)
            assert cfg["destination_ids"] == []
            assert cfg["publish_destination_id"] is None

        # Clip pipeline with explicit destination_ids=[] creates 0 PublishTargets & publish_task skips
        vid_id = f"mde_f01_v_{uuid.uuid4().hex[:8]}"
        t.video_ids.add(vid_id)
        scored_tmp = tmp_path / "f01_scored.json"
        scored_tmp.write_text(json.dumps([{"title": "Draft Clip", "start": 0.0, "end": 2.0, "duration": 2.0, "score": 0.9}]), encoding="utf-8")
        f01_job = f"mde_f01_j_{uuid.uuid4().hex[:8]}"
        t.job_ids.add(f01_job)
        with SyncSessionLocal() as s:
            s.add(Video(id=vid_id, title="F01 Video", channel_id=src_id, youtube_id=vid_id))
            s.add(Job(id=f01_job, video_id=vid_id, channel_id=src_id, source_url="https://youtube.com/watch?v=x", config=json.dumps({"destination_ids": [], "auto_publish": True}), is_test=True))
            s.commit()

        with managed_upload_sync(owner_type="video", owner_id=vid_id, artifact_type=ArtifactType.SCORED_CLIPS, storage_key=f"uploads/{vid_id}/scored_clips.json", retention_policy="temporary") as p:
            shutil.copy2(scored_tmp, p)

        with patch("backend.services.source_metadata_engine.get_or_analyze_source_seo_metadata", return_value=None):
            cids = clip_selection_task.apply(args=[{"video_id": vid_id, "job_id": f01_job, "candidate_set_hash": "h01", "scoring_version": "v1"}]).get()
        t.clip_ids.update(cids)
        clip_id = cids[0]

        with SyncSessionLocal() as s:
            assert s.query(PublishTarget).filter_by(clip_id=clip_id).count() == 0
            c = s.query(Clip).filter_by(id=clip_id).first()
            assert c.publish_destination_id is None

        with patch("backend.services.publisher.upload_short") as mock_up:
            pub_res = publish_task.apply(args=[{"clip_id": clip_id, "job_id": f01_job, "status": "completed"}]).get()
            mock_up.assert_not_called()
        assert pub_res["status"] == "skipped_no_destinations"
        with SyncSessionLocal() as s:
            assert s.query(Clip).filter_by(id=clip_id).first().publish_status == "draft"

        # /publish/publish-now rejects explicit destination_ids=[] with 400
        _, clip2_id, _ = t.create_video_and_clip()
        r_400 = await client.post("/api/publish/publish-now", json={"clip_id": clip2_id, "destination_ids": []})
        assert r_400.status_code == 400


@pytest.mark.asyncio
async def test_failure_02_no_destination_connected(isolated_env):
    """
    Failure 02: No destination connected rejects publish-now/schedule with 400,
    validate_destination_ids raises ValueError, and direct publish_clip_task fails closed.
    """
    t = isolated_env
    _, clip_id, _ = t.create_video_and_clip(publish_destination_id=None)

    with SyncSessionLocal() as s:
        with pytest.raises(ValueError):
            validate_destination_ids(["nonexistent_dest_id"], s)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_now = await client.post("/api/publish/publish-now", json={"clip_id": clip_id})
        assert r_now.status_code == 400

        r_sched = await client.post("/api/publish/schedule", json={
            "clip_id": clip_id,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        })
        assert r_sched.status_code == 400

        r_bad = await client.post("/api/publish/publish-now", json={"clip_id": clip_id, "destination_ids": ["missing_dest"]})
        assert r_bad.status_code == 400

    with patch("backend.services.publisher.upload_short") as mock_up:
        task_res = publish_clip_task.apply(args=[clip_id], kwargs={"channel_id": None, "privacy": "private"}).get()
        mock_up.assert_not_called()
    assert task_res["status"] == "failed"


@pytest.mark.asyncio
async def test_failure_03_destination_disconnected_after_mapping(isolated_env):
    """
    Failure 03:
    - Disconnecting a destination via POST /api/youtube-channels/{id}/disconnect preserves
      ChannelDestination rows + emits warning on GET /api/channels/{src}/destinations
    - Disables source.auto_publish when no active destination remains; keeps auto_publish=True if
      a sibling active destination still exists
    - Blocks /publish-now (400) & fails closed in publish_task
    - Documents Bug A: /disconnect filters Channel.is_test == False (404 on is_test=True)
    """
    t = isolated_env
    # Use is_test=False with unique prefix for /disconnect (and track for strict deletion in finally)
    dest_disc, dest_disc_yt = t.create_channel(name="F03 Disconnectable", is_destination=True, is_test=False, with_token=True)
    dest_backup, _ = t.create_channel(name="F03 Active Backup", is_destination=True, is_test=False, with_token=True)
    dest_test_only, _ = t.create_channel(name="F03 Synthetic", is_destination=True, is_test=True, with_token=True)

    src_single, _ = t.create_channel(name="F03 Src Single", is_destination=False, auto_clip=True, auto_publish=True, publish_destination_id=dest_disc)
    src_multi, _ = t.create_channel(name="F03 Src Multi", is_destination=False, auto_clip=True, auto_publish=True, publish_destination_id=dest_disc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.put(f"/api/channels/{src_single}/destinations", json={"destination_channel_ids": [dest_disc]})).status_code == 200
        assert (await client.put(f"/api/channels/{src_multi}/destinations", json={"destination_channel_ids": [dest_disc, dest_backup]})).status_code == 200

        # Verify Bug A: /disconnect rejects is_test=True channels with 404
        bug_a_resp = await client.post(f"/api/youtube-channels/{dest_test_only}/disconnect")
        assert bug_a_resp.status_code == 404

        # Disconnect real dest_disc
        disc_resp = await client.post(f"/api/youtube-channels/{dest_disc}/disconnect")
        assert disc_resp.status_code == 200, disc_resp.text
        assert disc_resp.json()["is_active"] is False

        # Token file archived on disk
        tok_dir = Path(settings.YOUTUBE_TOKEN_FILE).parent
        assert not (tok_dir / f"youtube_token_{dest_disc_yt}.json").exists()
        assert (tok_dir / f"youtube_token_{dest_disc_yt}.disconnected.json").exists()

        # Verify ChannelDestination preserved + warnings reported + auto_publish disabled on src_single only
        g_single = await client.get(f"/api/channels/{src_single}/destinations")
        assert g_single.status_code == 200
        assert g_single.json()["destination_channel_ids"] == [dest_disc]
        assert g_single.json()["auto_publish"] is False
        assert g_single.json()["disconnected_destinations_count"] == 1
        assert g_single.json()["destinations"][0]["status"] == "disconnected"
        assert "disconnected" in (g_single.json()["destinations"][0]["warning"] or "").lower()

        g_multi = await client.get(f"/api/channels/{src_multi}/destinations")
        assert g_multi.status_code == 200
        assert g_multi.json()["auto_publish"] is True
        assert set(g_multi.json()["destination_channel_ids"]) == {dest_disc, dest_backup}

        # Publishing to disconnected destination is blocked (400 HTTP + failed task)
        _, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_disc])
        assert (await client.post("/api/publish/publish-now", json={"clip_id": clip_id, "destination_ids": [dest_disc]})).status_code == 400

        job_id = f"mde_f03_j_{uuid.uuid4().hex[:8]}"
        t.job_ids.add(job_id)
        with SyncSessionLocal() as s:
            s.add(Job(id=job_id, channel_id=src_single, source_url="https://youtube.com/watch?v=x", config=json.dumps({"auto_publish": True}), is_test=True))
            s.commit()

        with patch("backend.services.publisher.upload_short") as mock_up:
            pt_res = publish_task.apply(args=[{"clip_id": clip_id, "job_id": job_id, "status": "completed"}]).get()
            mock_up.assert_not_called()
        assert pt_res["status"] == "failed"


@pytest.mark.asyncio
async def test_failure_04_expired_oauth_triggers_needs_reauth_and_blocks(isolated_env):
    """
    Failure 04: Expired non-refreshable OAuth or missing upload scope reports status='needs_reauth',
    blocks /publish-now (400), and fails closed in publish_clip_task.
    """
    t = isolated_env
    dest_exp, _ = t.create_channel(
        name="F04 Expired Auth",
        is_destination=True,
        with_token=True,
        expiry="2020-01-01T00:00:00Z",
        refresh_token="",
    )
    dest_missing, _ = t.create_channel(
        name="F04 Missing Token",
        is_destination=True,
        with_token=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        rows = {c["id"]: c for c in (await client.get("/api/youtube-channels/?include_test=true")).json()}
        assert rows[dest_exp]["status"] == "needs_reauth"
        assert rows[dest_exp]["upload_permission_status"] == "expired"
        assert rows[dest_exp]["ready_for_publishing"] is False

        assert rows[dest_missing]["status"] == "needs_reauth"
        assert rows[dest_missing]["upload_permission_status"] == "missing"
        assert rows[dest_missing]["ready_for_publishing"] is False

        _, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_exp])
        assert (await client.post("/api/publish/publish-now", json={"clip_id": clip_id, "destination_ids": [dest_exp]})).status_code == 400
        assert (await client.post("/api/publish/publish-now", json={"clip_id": clip_id, "destination_ids": [dest_missing]})).status_code == 400

    with SyncSessionLocal() as s:
        target = s.query(PublishTarget).filter_by(clip_id=clip_id, destination_id=dest_exp).first()
    with patch("backend.services.publisher.upload_short") as mock_up:
        res = publish_clip_task.apply(args=[clip_id], kwargs={"channel_id": dest_exp, "target_id": target.id, "privacy": "private"}).get()
        mock_up.assert_not_called()
    assert res["status"] == "failed"
    assert "OAuth" in res["error"]


@pytest.mark.asyncio
async def test_failure_05_oauth_refresh_failure_isolates_affected_target(isolated_env):
    """
    Failure 05: OAuth token refresh failure raises in get_youtube_client for Dest B
    and fails ONLY Dest B target while sibling Dest A & Dest C upload cleanly.
    """
    t = isolated_env
    dest_a, yt_a = t.create_channel(name="F05 Dest A", is_destination=True, with_token=True)
    dest_b, yt_b = t.create_channel(
        name="F05 Dest B Refresh Fail",
        is_destination=True,
        with_token=True,
        expiry="2020-01-01T00:00:00Z",
        refresh_token="revoked_rt_123",
    )
    dest_c, yt_c = t.create_channel(name="F05 Dest C", is_destination=True, with_token=True)

    # First verify get_youtube_client actually fails closed when Google Credentials.refresh throws invalid_grant
    with patch("google.oauth2.credentials.Credentials.refresh", side_effect=RuntimeError("invalid_grant: Token has been expired or revoked.")):
        with pytest.raises(ValueError, match="refresh failed|invalid_grant"):
            get_youtube_client(channel_id=yt_b)

    vid_id, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a, dest_b, dest_c])
    job_id = f"mde_f05_j_{uuid.uuid4().hex[:8]}"
    t.job_ids.add(job_id)
    with SyncSessionLocal() as s:
        s.add(Job(id=job_id, video_id=vid_id, source_url="https://youtube.com/watch?v=x", config=json.dumps({"auto_publish": True}), is_test=True))
        s.commit()

    from backend.services.publisher import _mock_upload_short

    def _upload_with_refresh_check(*args, **kw):
        if kw.get("channel_id") == yt_b:
            with patch("google.oauth2.credentials.Credentials.refresh", side_effect=RuntimeError("invalid_grant: Token has been expired or revoked.")):
                get_youtube_client(channel_id=yt_b)
        with patch("time.sleep", return_value=None):
            return _mock_upload_short(
                title=kw["title"],
                description=kw["description"],
                idempotency_key=kw["idempotency_key"],
                progress_callback=kw.get("progress_callback"),
                clip_id=kw.get("clip_id"),
                privacy="private",
            )

    with patch("backend.services.publisher.upload_short", side_effect=_upload_with_refresh_check):
        res = publish_task.apply(args=[{"clip_id": clip_id, "job_id": job_id, "status": "completed"}]).get()

    assert res["status"] == "partial_failure"
    with SyncSessionLocal() as s:
        pts = {pt.destination_id: pt for pt in s.query(PublishTarget).filter_by(clip_id=clip_id).all()}
        assert pts[dest_a].status == "completed" and pts[dest_a].youtube_video_id
        assert pts[dest_c].status == "completed" and pts[dest_c].youtube_video_id
        assert pts[dest_b].status == "failed"
        assert "refresh" in (pts[dest_b].error_message or "").lower() or "invalid_grant" in (pts[dest_b].error_message or "").lower()


@pytest.mark.asyncio
async def test_failure_06_outro_missing_or_none_publishes_base_clip(isolated_env):
    """
    Failure 06: Destination without active outro publishes base clip untouched without rendering.
    """
    t = isolated_env
    dest_none, _ = t.create_channel(name="F06 No Outro", is_destination=True, with_token=True)
    _, clip_id, base_path = t.create_video_and_clip(destination_ids=[dest_none])

    with SyncSessionLocal() as s:
        target = s.query(PublishTarget).filter_by(clip_id=clip_id, destination_id=dest_none).first()

    seen_video_paths = []
    from backend.services.publisher import _mock_upload_short

    def _capture_upload(*args, **kw):
        seen_video_paths.append(Path(kw["video_path"]).resolve())
        with patch("time.sleep", return_value=None):
            return _mock_upload_short(title=kw["title"], description=kw["description"], idempotency_key=kw["idempotency_key"], clip_id=kw.get("clip_id"))

    with patch("backend.services.publisher.upload_short", side_effect=_capture_upload):
        res = publish_clip_task.apply(args=[clip_id], kwargs={"channel_id": dest_none, "target_id": target.id, "privacy": "private"}).get()

    assert res["status"] == "published"
    assert seen_video_paths == [base_path.resolve()]
    with SyncSessionLocal() as s:
        tg = s.query(PublishTarget).filter_by(id=target.id).first()
        assert tg.outro_applied_id is None
        assert tg.rendered_video_path is None


@pytest.mark.asyncio
async def test_failure_07_outro_file_deleted_on_disk_fails_closed(isolated_env, media_assets):
    """
    Failure 07: Outro configured in DB, then physical file deleted on disk:
    - GET /youtube-channels/{id}/outro/preview -> 404
    - GET /publish/clips/{c}/destinations/{d}/preview-info -> outro_file_missing=True
    - GET /publish/clips/{c}/destinations/{d}/preview -> 404
    - publish_clip_task fails closed with zero silent fallback to base clip upload
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F07 Deleted Outro", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(media_assets.video_outro, "rb") as f:
            up = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("del.mp4", f, "video/mp4")})
        assert up.status_code == 201
        outro_file = resolve_safe_outro_path(up.json()["outro"]["file_path"])
        assert outro_file.exists()
        outro_file.unlink()

        assert (await client.get(f"/api/youtube-channels/{dest_a}/outro/preview")).status_code == 404

        _, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a])
        pi = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_a}/preview-info")
        assert pi.status_code == 200
        assert pi.json()["outro_file_missing"] is True
        assert pi.json()["variant_ready"] is False

        prev = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_a}/preview")
        assert prev.status_code == 404

    with SyncSessionLocal() as s:
        target = s.query(PublishTarget).filter_by(clip_id=clip_id, destination_id=dest_a).first()
    with patch("backend.services.publisher.upload_short") as mock_up:
        res = publish_clip_task.apply(args=[clip_id], kwargs={"channel_id": dest_a, "target_id": target.id, "privacy": "private"}).get()
        mock_up.assert_not_called()
    assert res["status"] == "failed"
    assert "missing" in res["error"].lower()


@pytest.mark.asyncio
async def test_failure_08_unsupported_and_corrupt_outro_formats_rejected(isolated_env, media_assets):
    """
    Failure 08: Unsupported extension (.txt/.gif), invalid outro_type, invalid image duration,
    and corrupt MP4/PNG containers rejected cleanly with HTTP 400.
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F08 Format Reject", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(media_assets.bad_txt, "rb") as f:
            r1 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("bad.txt", f, "text/plain")})
        assert r1.status_code == 400

        with open(media_assets.bad_gif, "rb") as f:
            r2 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "image"}, files={"file": ("anim.gif", f, "image/gif")})
        assert r2.status_code == 400

        with open(media_assets.video_outro, "rb") as f:
            r3 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "audio"}, files={"file": ("a.mp4", f, "video/mp4")})
        assert r3.status_code == 400

        with open(media_assets.image_outro, "rb") as f:
            r4 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "image", "duration_seconds": "0.1"}, files={"file": ("a.png", f, "image/png")})
        assert r4.status_code == 400

        with open(media_assets.image_outro, "rb") as f:
            r5 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "image", "duration_seconds": "20.0"}, files={"file": ("a.png", f, "image/png")})
        assert r5.status_code == 400

        with open(media_assets.corrupt_mp4, "rb") as f:
            r6 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("corrupt.mp4", f, "video/mp4")})
        assert r6.status_code == 400

        with open(media_assets.corrupt_png, "rb") as f:
            r7 = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "image"}, files={"file": ("corrupt.png", f, "image/png")})
        assert r7.status_code == 400


@pytest.mark.asyncio
async def test_failure_09_outro_rendering_ffmpeg_failure_isolates_target(isolated_env, media_assets):
    """
    Failure 09: FFmpeg outro rendering failure on Dest B fails ONLY Dest B target
    (Dest A & C still publish) and /preview endpoint maps OutroRenderError to HTTP 422.
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F09 Dest A", is_destination=True, with_token=True)
    dest_b, _ = t.create_channel(name="F09 Dest B Fail Render", is_destination=True, with_token=True)
    dest_c, _ = t.create_channel(name="F09 Dest C None", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(media_assets.video_outro, "rb") as f:
            assert (await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("a.mp4", f, "video/mp4")})).status_code == 201
        with open(media_assets.image_outro, "rb") as f:
            up_b = await client.post(f"/api/youtube-channels/{dest_b}/outro", data={"outro_type": "image", "duration_seconds": "2.0"}, files={"file": ("b.png", f, "image/png")})
            outro_b_id = up_b.json()["outro"]["id"]

        vid_id, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a, dest_b, dest_c])
        job_id = f"mde_f09_j_{uuid.uuid4().hex[:8]}"
        t.job_ids.add(job_id)
        with SyncSessionLocal() as s:
            s.add(Job(id=job_id, video_id=vid_id, source_url="https://youtube.com/watch?v=x", config=json.dumps({"auto_publish": True}), is_test=True))
            s.commit()

        from backend.services.publisher import _mock_upload_short

        orig_render = render_clip_with_outro

        def _selective_fail_render(base_video_path, output_path, outro, max_total_duration=180.0):
            if str(getattr(outro, "id", "")) == outro_b_id:
                raise OutroRenderError("FFmpeg outro render failed (code 1): simulated codec crash")
            return orig_render(base_video_path, output_path, outro, max_total_duration=max_total_duration)

        # Route preview should surface 422 on OutroRenderError
        with patch("backend.services.outro_service.render_clip_with_outro", side_effect=_selective_fail_render):
            prev_422 = await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_b}/preview")
            assert prev_422.status_code == 422

        def _upload_clean(*a, **kw):
            return _mock_upload_short(
                title=kw["title"],
                description=kw["description"],
                idempotency_key=kw["idempotency_key"],
                clip_id=kw.get("clip_id"),
                privacy="private",
            )

        # Task execution across [A, B, C] fails ONLY B while A & C complete
        with (
            patch("backend.services.outro_service.render_clip_with_outro", side_effect=_selective_fail_render),
            patch("backend.services.publisher.upload_short", side_effect=_upload_clean),
            patch("time.sleep", return_value=None),
        ):
            res = publish_task.apply(args=[{"clip_id": clip_id, "job_id": job_id, "status": "completed"}]).get()

        assert res["status"] == "partial_failure"
        with SyncSessionLocal() as s:
            pts = {pt.destination_id: pt for pt in s.query(PublishTarget).filter_by(clip_id=clip_id).all()}
            assert pts[dest_a].status == "completed"
            assert pts[dest_c].status == "completed"
            assert pts[dest_b].status == "failed"
            assert "FFmpeg outro render failed" in (pts[dest_b].error_message or "")


@pytest.mark.asyncio
async def test_failure_10_final_render_corruption_fails_validation(isolated_env, media_assets, tmp_path):
    """
    Failure 10: Final render validation rejects missing, 0-byte, corrupt bytes, non-faststart MP4,
    and subtitle-bearing MP4 variants; corrupted FFmpeg outputs raise OutroRenderError without promotion.
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F10 Render Val", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(media_assets.image_outro, "rb") as f:
            up = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "image", "duration_seconds": "2.0"}, files={"file": ("v.png", f, "image/png")})
        outro_id = up.json()["outro"]["id"]

    vid_id, clip_id, base_path = t.create_video_and_clip(destination_ids=[dest_a])
    variant_dir = settings.OUTPUT_DIR / vid_id / "clips" / clip_id / "destinations" / dest_a
    variant_dir.mkdir(parents=True, exist_ok=True)
    variant_mp4 = variant_dir / "final.mp4"
    meta_json = variant_dir / "variant_meta.json"

    with SyncSessionLocal() as s:
        outro_obj = s.query(DestinationOutro).filter_by(id=outro_id).first()
        from backend.services.outro_service import compute_outro_signature
        sig = compute_outro_signature(outro_obj, base_path)

    meta_json.write_text(json.dumps({"signature": sig}), encoding="utf-8")

    # (a) Missing file
    assert _is_valid_cached_variant(variant_mp4, meta_json, sig) is False

    # (b) 0-byte file
    variant_mp4.write_bytes(b"")
    assert _is_valid_cached_variant(variant_mp4, meta_json, sig) is False

    # (c) Corrupt bytes
    variant_mp4.write_bytes(b"corrupt_mp4_payload_12345")
    assert _is_valid_cached_variant(variant_mp4, meta_json, sig) is False

    # (d) Non-faststart MP4 (mdat before moov)
    shutil.copy2(media_assets.non_faststart, variant_mp4)
    assert has_faststart_moov_before_mdat(variant_mp4) is False
    assert _is_valid_cached_variant(variant_mp4, meta_json, sig) is False

    # (e) Subtitle-bearing MP4
    shutil.copy2(media_assets.base_clip_sub, variant_mp4)
    assert _is_valid_cached_variant(variant_mp4, meta_json, sig) is False

    # Self-healing re-render overwrites corrupt cache cleanly
    with SyncSessionLocal() as s:
        clip_obj = s.query(Clip).filter_by(id=clip_id).first()
        healed = render_or_reuse_destination_variant_sync(clip=clip_obj, destination_id=dest_a, session=s)
        assert healed["rendered"] is True and healed["reused_cache"] is False
        assert has_faststart_moov_before_mdat(Path(healed["video_path"])) is True

    # Simulate FFmpeg writing empty temp file (while letting ffprobe succeed) -> OutroRenderError and final file NOT promoted
    target_out = tmp_path / "never_promoted" / "final.mp4"
    real_sub_run = subprocess.run

    def _ffmpeg_empty_output(cmd, *a, **kw):
        if cmd and "ffprobe" in str(cmd[0]).lower():
            return real_sub_run(cmd, *a, **kw)
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    with SyncSessionLocal() as s:
        outro_obj = s.query(DestinationOutro).filter_by(id=outro_id).first()
        with patch("backend.services.outro_service.subprocess.run", side_effect=_ffmpeg_empty_output):
            with pytest.raises(OutroRenderError, match="missing or 0 bytes"):
                render_clip_with_outro(base_path, target_out, outro_obj)
    assert not target_out.exists()


@pytest.mark.asyncio
async def test_failure_11_partial_success_1_of_3_fails_2_succeed(isolated_env):
    """
    Failure 11: 1 of 3 destination uploads raises an error -> remaining 2 complete cleanly,
    Clip reports failed aggregate with clear '2/3 destinations succeeded; 1 failed' summary.
    """
    t = isolated_env
    dest_a, yt_a = t.create_channel(name="F11 Dest A", is_destination=True, with_token=True)
    dest_b, yt_b = t.create_channel(name="F11 Dest B", is_destination=True, with_token=True)
    dest_c, yt_c = t.create_channel(name="F11 Dest C", is_destination=True, with_token=True)

    vid_id, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a, dest_b, dest_c])
    job_id = f"mde_f11_j_{uuid.uuid4().hex[:8]}"
    t.job_ids.add(job_id)
    with SyncSessionLocal() as s:
        s.add(Job(id=job_id, video_id=vid_id, source_url="https://youtube.com/watch?v=x", config=json.dumps({"auto_publish": True}), is_test=True))
        s.commit()

    from backend.services.publisher import _mock_upload_short

    def _fail_b_upload(*args, **kw):
        if kw.get("channel_id") == yt_b:
            raise RuntimeError("YouTube 503 Backend Error on Dest B")
        with patch("time.sleep", return_value=None):
            return _mock_upload_short(title=kw["title"], description=kw["description"], idempotency_key=kw["idempotency_key"], clip_id=kw.get("clip_id"))

    with patch("backend.services.publisher.upload_short", side_effect=_fail_b_upload):
        res = publish_task.apply(args=[{"clip_id": clip_id, "job_id": job_id, "status": "completed"}]).get()

    assert res["status"] == "partial_failure"
    with SyncSessionLocal() as s:
        c = s.query(Clip).filter_by(id=clip_id).first()
        assert c.publish_status == "failed"
        assert "2/3 destinations succeeded; 1 failed" in (c.publish_error or "")
        pts = {pt.destination_id: pt for pt in s.query(PublishTarget).filter_by(clip_id=clip_id).all()}
        assert pts[dest_a].status == "completed" and pts[dest_a].youtube_video_id
        assert pts[dest_c].status == "completed" and pts[dest_c].youtube_video_id
        assert pts[dest_b].status == "failed" and "503" in (pts[dest_b].error_message or "")


@pytest.mark.asyncio
async def test_failure_12_concurrent_claim_atomicity_and_idempotency(isolated_env):
    """
    Failure 12:
    - Concurrent worker threads racing publish_task against the SAME PublishTarget row:
      conditional SQL UPDATE WHERE status == target.status allows only ONE claim to upload!
    - Same (job_id, clip_id) task claim returns already_claimed on duplicate execution
    - Fresh 'publishing' target is skipped cleanly by publish_task
    - PublishRecord(external_id) prevents duplicate upload in publish_clip_task
    - Duplicate POST /api/publish/publish-now skips already queued/completed targets
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F12 Dest A", is_destination=True, with_token=True)
    vid_id, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a])
    job_1 = f"mde_f12_j1_{uuid.uuid4().hex[:8]}"
    job_2 = f"mde_f12_j2_{uuid.uuid4().hex[:8]}"
    t.job_ids.update([job_1, job_2])
    with SyncSessionLocal() as s:
        s.add(Job(id=job_1, video_id=vid_id, source_url="https://youtube.com/watch?v=x", config=json.dumps({"auto_publish": True}), is_test=True))
        s.add(Job(id=job_2, video_id=vid_id, source_url="https://youtube.com/watch?v=x", config=json.dumps({"auto_publish": True}), is_test=True))
        s.commit()

    upload_counter = 0
    upload_lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=5)
    from backend.services.publisher import _mock_upload_short

    def _slow_sync_upload(*args, **kw):
        nonlocal upload_counter
        with upload_lock:
            upload_counter += 1
        time.sleep(0.15)
        with patch("time.sleep", return_value=None):
            return _mock_upload_short(title=kw["title"], description=kw["description"], idempotency_key=kw["idempotency_key"], clip_id=kw.get("clip_id"))

    def _worker_run(jid: str):
        # Align start so both threads race on PublishTarget conditional UPDATE
        barrier.wait()
        return publish_task.apply(args=[{"clip_id": clip_id, "job_id": jid, "status": "completed"}]).get()

    with patch("backend.services.publisher.upload_short", side_effect=_slow_sync_upload):
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(_worker_run, job_1)
            f2 = pool.submit(_worker_run, job_2)
            r1 = f1.result(timeout=15)
            r2 = f2.result(timeout=15)

    assert upload_counter == 1, f"Expected exactly 1 upload across concurrent workers, got {upload_counter}"
    assert "published" in (r1["status"], r2["status"])

    # Same job_1 duplicate dispatch hits check_and_claim_execution -> skipped/already_claimed
    with patch("backend.services.publisher.upload_short") as mock_dup:
        dup_res = publish_task.apply(args=[{"clip_id": clip_id, "job_id": job_1, "status": "completed"}]).get()
        mock_dup.assert_not_called()
    assert dup_res["status"] == "skipped" and dup_res["reason"] == "already_claimed"

    # PublishRecord.external_id idempotency on publish_clip_task + duplicate /publish-now returns 200 without re-queue
    with SyncSessionLocal() as s:
        tg = s.query(PublishTarget).filter_by(clip_id=clip_id, destination_id=dest_a).first()
        assert tg.status == "completed" and tg.youtube_video_id
        yt_saved = tg.youtube_video_id

    with patch("backend.services.publisher.upload_short") as mock_clip_task_up:
        re_res = publish_clip_task.apply(args=[clip_id], kwargs={"channel_id": dest_a, "target_id": tg.id, "privacy": "private"}).get()
        mock_clip_task_up.assert_not_called()
    assert re_res["status"] == "published" and re_res["youtube_id"] == yt_saved

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        dup_http = await client.post("/api/publish/publish-now", json={"clip_id": clip_id, "destination_ids": [dest_a]})
        assert dup_http.status_code == 200
        assert dup_http.json()["video_id"] == yt_saved

    # Verify fresh 'publishing' target is skipped by publish_task (stale guard check)
    vid2, clip2, _ = t.create_video_and_clip(destination_ids=[dest_a])
    job_3 = f"mde_f12_j3_{uuid.uuid4().hex[:8]}"
    t.job_ids.add(job_3)
    with SyncSessionLocal() as s:
        s.add(Job(id=job_3, video_id=vid2, source_url="https://youtube.com/watch?v=y", config=json.dumps({"auto_publish": True}), is_test=True))
        tg2 = s.query(PublishTarget).filter_by(clip_id=clip2, destination_id=dest_a).first()
        tg2.status = "publishing"
        tg2.updated_at = datetime.now(timezone.utc)
        s.commit()

    with patch("backend.services.publisher.upload_short") as mock_fresh_skip:
        fresh_res = publish_task.apply(args=[{"clip_id": clip2, "job_id": job_3, "status": "completed"}]).get()
        mock_fresh_skip.assert_not_called()
    assert fresh_res["status"] == "in_progress"


@pytest.mark.asyncio
async def test_failure_13_retry_after_partial_success_skips_published_siblings(isolated_env):
    """
    Failure 13: After partial failure (A & C published, B failed), retrying via
    POST /api/publish/targets/{b}/retry and /clips/{id}/retry NEVER re-uploads A or C
    and rejects retrying already-published target A with 400.
    """
    t = isolated_env
    dest_a, yt_a = t.create_channel(name="F13 Dest A", is_destination=True, with_token=True)
    dest_b, yt_b = t.create_channel(name="F13 Dest B", is_destination=True, with_token=True)
    dest_c, yt_c = t.create_channel(name="F13 Dest C", is_destination=True, with_token=True)

    _, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a, dest_b, dest_c])
    now = datetime.now(timezone.utc)
    with SyncSessionLocal() as s:
        pts = {pt.destination_id: pt for pt in s.query(PublishTarget).filter_by(clip_id=clip_id).all()}
        pts[dest_a].status = "completed"
        pts[dest_a].youtube_video_id = "yt_done_a"
        pts[dest_a].published_at = now
        pts[dest_c].status = "completed"
        pts[dest_c].youtube_video_id = "yt_done_c"
        pts[dest_c].published_at = now
        pts[dest_b].status = "failed"
        pts[dest_b].error_message = "Transient timeout"
        c = s.query(Clip).filter_by(id=clip_id).first()
        c.publish_status = "failed"
        c.youtube_short_id = "yt_done_a"
        s.commit()
        ta_id, tb_id = pts[dest_a].id, pts[dest_b].id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Published target cannot be retried
        assert (await client.post(f"/api/publish/targets/{ta_id}/retry")).status_code == 400

        # Clip-level retry dispatches ONLY the failed target (B), skipping A & C
        clip_dispatched = []
        with patch(
            "backend.tasks.clip_tasks.publish_clip_task.apply_async",
            side_effect=lambda *args, **kw: clip_dispatched.append((args, kw)) or SimpleNamespace(id="tk_clip_retry"),
        ):
            r_clip_retry = await client.post(f"/api/publish/clips/{clip_id}/retry")
        assert r_clip_retry.status_code == 202
        assert len(clip_dispatched) == 1
        assert clip_dispatched[0][1]["kwargs"]["target_id"] == tb_id

        # Reset B back to failed and test target-level retry POST /api/publish/targets/{tb_id}/retry
        with SyncSessionLocal() as s:
            tb = s.query(PublishTarget).filter_by(id=tb_id).first()
            tb.status = "failed"
            c = s.query(Clip).filter_by(id=clip_id).first()
            c.publish_status = "failed"
            s.commit()

        target_dispatched = []
        with patch(
            "backend.tasks.clip_tasks.publish_clip_task.apply_async",
            side_effect=lambda *args, **kw: target_dispatched.append((args, kw)) or SimpleNamespace(id="tk_tgt_retry"),
        ):
            r_tgt_retry = await client.post(f"/api/publish/targets/{tb_id}/retry")
        assert r_tgt_retry.status_code == 202
        assert len(target_dispatched) == 1

    from backend.services.publisher import _mock_upload_short
    retried_channels = []

    def _record_retry_upload(*args, **kw):
        retried_channels.append(kw.get("channel_id"))
        with patch("time.sleep", return_value=None):
            return _mock_upload_short(title=kw["title"], description=kw["description"], idempotency_key=kw["idempotency_key"], clip_id=kw.get("clip_id"))

    with patch("backend.services.publisher.upload_short", side_effect=_record_retry_upload):
        retry_args = list(target_dispatched[0][0]) if target_dispatched[0][0] else list(target_dispatched[0][1].get("args", []))
        res_retry = publish_clip_task.apply(args=retry_args, kwargs=target_dispatched[0][1]["kwargs"]).get()

    assert res_retry["status"] == "published"
    assert retried_channels == [yt_b]
    with SyncSessionLocal() as s:
        assert s.query(Clip).filter_by(id=clip_id).first().publish_status == "published"
        pts = {pt.destination_id: pt for pt in s.query(PublishTarget).filter_by(clip_id=clip_id).all()}
        assert pts[dest_a].youtube_video_id == "yt_done_a"
        assert pts[dest_c].youtube_video_id == "yt_done_c"
        assert pts[dest_b].status == "completed" and pts[dest_b].youtube_video_id


@pytest.mark.asyncio
async def test_failure_14_outro_edited_or_destination_changed_invalidates_stale_render(isolated_env, media_assets):
    """
    Failure 14:
    - Replacing / editing Dest B's outro invalidates prior cached variant; preview-info reports stale_variant=True;
      publish_clip_task renders & uploads v2 (NEVER serving stale v1)
    - Re-routing clip from Dest B -> Dest A uses Dest A's outro (NEVER Dest B's outro)
    """
    t = isolated_env
    dest_a, yt_a = t.create_channel(name="F14 Dest A", is_destination=True, with_token=True)
    dest_b, yt_b = t.create_channel(name="F14 Dest B", is_destination=True, with_token=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(media_assets.video_outro, "rb") as f:
            up_a = await client.post(f"/api/youtube-channels/{dest_a}/outro", data={"outro_type": "video"}, files={"file": ("a.mp4", f, "video/mp4")})
            outro_a_id = up_a.json()["outro"]["id"]

        with open(media_assets.image_outro, "rb") as f:
            up_b1 = await client.post(f"/api/youtube-channels/{dest_b}/outro", data={"outro_type": "image", "duration_seconds": "2.0"}, files={"file": ("b1.png", f, "image/png")})
            outro_b1_id = up_b1.json()["outro"]["id"]

        _, clip_id, _ = t.create_video_and_clip(destination_ids=[dest_b], publish_destination_id=dest_b)

        # Render initial cached variant for Dest B v1
        assert (await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_b}/preview")).status_code == 200

        # Replace Dest B outro with v2 (5.0s different image)
        with open(media_assets.image_outro_v2, "rb") as f:
            up_b2 = await client.post(f"/api/youtube-channels/{dest_b}/outro", data={"outro_type": "image", "duration_seconds": "5.0"}, files={"file": ("b2.png", f, "image/png")})
            outro_b2_id = up_b2.json()["outro"]["id"]
        assert outro_b2_id != outro_b1_id

        pi_stale = (await client.get(f"/api/publish/clips/{clip_id}/destinations/{dest_b}/preview-info")).json()
        assert pi_stale["stale_variant"] is True
        assert pi_stale["variant_ready"] is False
        assert pi_stale["outro"]["id"] == outro_b2_id

        with SyncSessionLocal() as s:
            tb = s.query(PublishTarget).filter_by(clip_id=clip_id, destination_id=dest_b).first()

        uploaded_durations = []
        from backend.services.publisher import _mock_upload_short

        def _check_v2_upload(*args, **kw):
            uploaded_durations.append(float(probe_media_with_ffprobe(Path(kw["video_path"]))["format"]["duration"]))
            with patch("time.sleep", return_value=None):
                return _mock_upload_short(title=kw["title"], description=kw["description"], idempotency_key=kw["idempotency_key"], clip_id=kw.get("clip_id"))

        with patch("backend.services.publisher.upload_short", side_effect=_check_v2_upload):
            pub_b = publish_clip_task.apply(args=[clip_id], kwargs={"channel_id": dest_b, "target_id": tb.id, "privacy": "private"}).get()

        assert pub_b["status"] == "published"
        assert uploaded_durations[0] >= 6.5, f"Expected v2 (~7s) render, got {uploaded_durations[0]}s"
        with SyncSessionLocal() as s:
            tb_done = s.query(PublishTarget).filter_by(id=tb.id).first()
            assert tb_done.outro_applied_id == outro_b2_id

        # Second clip: change destination from Dest B -> Dest A before publishing
        _, clip2_id, _ = t.create_video_and_clip(destination_ids=[dest_b], publish_destination_id=dest_b)
        assert (await client.get(f"/api/publish/clips/{clip2_id}/destinations/{dest_b}/preview")).status_code == 200
        assert (await client.put(f"/api/publish/clips/{clip2_id}/destinations", json={"destination_ids": [dest_a]})).status_code == 200

        with SyncSessionLocal() as s:
            ta_only = s.query(PublishTarget).filter_by(clip_id=clip2_id).all()
            assert len(ta_only) == 1 and ta_only[0].destination_id == dest_a
            ta_id = ta_only[0].id

        with patch("backend.services.publisher.upload_short", side_effect=_check_v2_upload):
            pub_a = publish_clip_task.apply(args=[clip2_id], kwargs={"channel_id": dest_a, "target_id": ta_id, "privacy": "private"}).get()

        assert pub_a["status"] == "published"
        with SyncSessionLocal() as s:
            ta_done = s.query(PublishTarget).filter_by(id=ta_id).first()
            assert ta_done.outro_applied_id == outro_a_id
            assert dest_a in (ta_done.rendered_video_path or "")


@pytest.mark.asyncio
async def test_failure_15_source_channel_disabled_or_deleted_mid_flight(isolated_env):
    """
    Failure 15:
    - Disabled monitored source channel (is_active=False) is skipped cleanly by run_channel_monitor
    - Deleting monitored source channel mid-flight while a VideoDecision is awaiting resolution
      sets decision.channel_id=NULL safely; countdown resolution does not crash and forces
      auto_publish=False so nothing publishes to any stale/wrong destination
    """
    t = isolated_env
    dest_a, _ = t.create_channel(name="F15 Dest A", is_destination=True, with_token=True)

    # Part 1: Disabled source channel ignored cleanly by monitor
    src_disabled, yt_src_dis = t.create_channel(
        name="F15 Disabled Source",
        is_destination=False,
        is_active=False,
        auto_clip=True,
        auto_publish=True,
        last_checked_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    from backend.models.database import AsyncSessionLocal
    from backend.services.channel_monitor import run_channel_monitor

    seen_urls = []
    async def _track_monitor_fetch(ch_url, max_results=5):
        seen_urls.append(ch_url)
        return []

    async with AsyncSessionLocal() as async_db:
        with patch("backend.services.channel_monitor.get_channel_videos", side_effect=_track_monitor_fetch):
            await run_channel_monitor(async_db)
    assert all(yt_src_dis not in u for u in seen_urls)

    # Part 2: Active source channel -> create VideoDecision -> delete source via HTTP -> resolve decision
    src_del, _ = t.create_channel(
        name="F15 Deleted MidFlight",
        is_destination=False,
        is_active=True,
        auto_clip=True,
        auto_publish=True,
        publish_destination_id=dest_a,
    )
    decision_id = str(uuid.uuid4())
    t.decision_ids.add(decision_id)
    now = datetime.now(timezone.utc)
    with SyncSessionLocal() as s:
        s.add(ChannelDestination(id=str(uuid.uuid4()), source_channel_id=src_del, destination_channel_id=dest_a, is_default=True))
        s.add(VideoDecision(
            id=decision_id,
            channel_id=src_del,
            youtube_id=f"yt_f15_{uuid.uuid4().hex[:8]}",
            youtube_url=f"https://www.youtube.com/watch?v=test_f15_{uuid.uuid4().hex[:6]}",
            video_title="Mid-flight Deleted Source Video",
            channel_profile_snapshot={"destination_ids": [dest_a], "auto_publish": True, "origin": "automatic_monitor"},
            overrides={"destination_ids": [dest_a], "auto_publish": True, "origin": "automatic_monitor"},
            status=VideoDecisionStatus.AWAITING_SETTINGS.value,
            decision_deadline=now + timedelta(seconds=20),
            created_at=now,
        ))
        s.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        del_r = await client.delete(f"/api/channels/{src_del}")
        assert del_r.status_code == 200

    with SyncSessionLocal() as s:
        dec = s.query(VideoDecision).filter_by(id=decision_id).first()
        assert dec is not None
        assert dec.channel_id is None, "ON DELETE SET NULL should clear channel_id without destroying record"

    captured_kwargs = {}
    with patch(
        "backend.tasks.orchestration.start_video_processing_task.apply_async",
        side_effect=lambda **kw: captured_kwargs.update(kw.get("kwargs", {})) or SimpleNamespace(id="tk_f15"),
    ):
        res_dec = resolve_video_decision_sync(decision_id, action="countdown")

    job_id = res_dec["job_id"]
    t.job_ids.add(job_id)
    assert captured_kwargs["auto_publish"] is False
    assert captured_kwargs["channel_id"] is None

    # Even if clip/job proceeds into publish_task, auto_publish=False holds clip cleanly in draft
    _, orphan_clip_id, _ = t.create_video_and_clip(destination_ids=[dest_a])
    with patch("backend.services.publisher.upload_short") as mock_up:
        pub_res = publish_task.apply(args=[{"clip_id": orphan_clip_id, "job_id": job_id, "status": "completed"}]).get()
        mock_up.assert_not_called()
    assert pub_res["status"] == "draft" and pub_res["reason"] == "auto_publish_disabled"
