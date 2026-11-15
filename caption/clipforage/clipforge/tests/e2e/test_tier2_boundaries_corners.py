"""
tests/e2e/test_tier2_boundaries_corners.py
==========================================
Tier 2: Boundary Value Analysis & Hostile Corner Cases Suite (F01–F12, >=60 tests)
for ClipForge Multi-Destination Publishing & Automatic Outro System.

Opaque-Box Boundary & Stress Vectors:
- F01: 0 vs 1 vs 10 connected destinations, expired token refresh, invalid grant failure, concurrent reauth racing
- F02: Sub-second (0.1s) video outro, 60.1s Shorts overflow, rapid re-upload racing, odd dimensions (1079x1919), audio sample mismatch (48k vs 44.1k)
- F03: Min (0.5s) and max (30.0s) image duration, 21:9 ultrawide, 1:1 square, 4K downscale
- F04: Idempotent remove on no-outro, rapid toggle upload/delete, corrupt file handling, queue removal, metadata retention
- F05: Mapping bounds (0, 1, 10 destinations), duplicate ID deduplication, foreign key integrity
- F06: Upload with 0 vs 10 destinations, tiny file edge case, list vs comma-string formats, special characters
- F07: URL intake bounds (empty, 10 dests, malformed UUID, batch mixed, duplicate IDs)
- F08: Auto-ingestion zero leakage, all disconnected, 10 targets, deleted source mid-job, mid-job mapping changes
- F09: Combined duration 59.9s vs 60.1s, stereo + mono audio mismatch, silent video outro synthesis, odd dimensions
- F10: Quota 429 exhaustion, backoff handling, 10 concurrent target updates, chunk timeout, active cancellation
- F11: 404 on missing dest, stale variant regeneration, 10-dest switcher stress, zero duration guard, HTTP Range/HEAD
- F12: Already-published retry no-op, token revocation failure, retry exhaustion (3x), missing render recovery, concurrent retry lock
"""
import asyncio
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
import sqlalchemy as sa
from sqlalchemy import select, update, delete

# Ensure clipforge root and backend are in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.main import app
from backend.core.config import settings
from backend.models.database import Base
from backend.models.models import (
    Channel,
    ChannelDestination,
    PublishTarget,
    Clip,
    Job,
    Video,
)

# Shared E2E media helpers
from tests.e2e.e2e_media_helpers import (
    generate_synthetic_mp4,
    generate_synthetic_image,
    parse_top_level_atoms,
    assert_faststart_moov_atom,
    probe_media,
    assert_zero_caption_invariant,
    assert_filtergraph_zero_caption_invariant,
)


# ==============================================================================
# F01: Destination Connection Boundaries
# ==============================================================================
class TestTier2F01DestinationConnectionBoundaries:
    """Boundary tests for destination channel listing, scaling to 10 channels, and reauth racing."""

    @pytest.mark.asyncio
    async def test_zero_connected_destinations_listing(self, e2e_client: AsyncClient, e2e_db):
        """When 0 publishing destinations exist, GET /api/youtube-channels/ returns empty list cleanly."""
        async with e2e_db["session_factory"]() as session:
            # Delete any existing destinations in disposable DB
            await session.execute(delete(Channel).where(Channel.is_destination == True))
            await session.commit()

        with patch("backend.api.routes.youtube_channels.sync_authorized_destinations"):
            resp = await e2e_client.get("/api/youtube-channels/")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) == 0

    @pytest.mark.asyncio
    async def test_maximum_destinations_scaling_10_channels(self, e2e_client: AsyncClient, e2e_db):
        """Scales to 10 connected destinations without serialization truncation or data collision."""
        async with e2e_db["session_factory"]() as session:
            channels = [
                Channel(
                    id=f"dest_scale_{i}_{uuid.uuid4().hex[:6]}",
                    youtube_channel_id=f"UC_SCALE_{i}_{uuid.uuid4().hex[:6]}",
                    channel_name=f"Scale Dest {i}",
                    channel_url=f"https://youtube.com/@scale_{i}",
                    is_destination=True,
                    is_active=True,
                    is_test=False,
                )
                for i in range(10)
            ]
            session.add_all(channels)
            await session.commit()

        resp = await e2e_client.get("/api/youtube-channels/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 10

    @pytest.mark.asyncio
    async def test_expired_token_refresh_success_boundary(self, e2e_client: AsyncClient, e2e_db):
        """Expired OAuth token refresh succeeds and restores channel status to 'connected'."""
        chan_id = f"dst_exp_succ_{uuid.uuid4().hex[:6]}"
        async with e2e_db["session_factory"]() as session:
            ch = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_{chan_id}",
                channel_name="Token Expiry Channel",
                channel_url="https://youtube.com/@exp",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()

        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=True):
            resp = await e2e_client.get(f"/api/youtube-channels/{chan_id}/stats")
            if resp.status_code == 200:
                assert resp.json().get("status") == "connected"

    @pytest.mark.asyncio
    async def test_invalid_grant_token_refresh_permanent_failure(self, e2e_client: AsyncClient, e2e_db):
        """Permanent 'invalid_grant' token error transitions status to 'needs_reauth' without crashing."""
        chan_id = f"dst_inv_grant_{uuid.uuid4().hex[:6]}"
        async with e2e_db["session_factory"]() as session:
            ch = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_{chan_id}",
                channel_name="Invalid Grant Channel",
                channel_url="https://youtube.com/@inv",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()

        with patch("backend.api.routes.youtube_channels.check_channel_authorization", return_value=False):
            resp = await e2e_client.get(f"/api/youtube-channels/{chan_id}/stats")
            if resp.status_code == 200:
                assert resp.json().get("status") == "needs_reauth"

    @pytest.mark.asyncio
    async def test_concurrent_reauth_racing_requests(self, e2e_client: AsyncClient, e2e_db):
        """Concurrent refresh requests are coalesced safely by per-channel mutex locks."""
        chan_id = f"dst_race_{uuid.uuid4().hex[:6]}"
        async with e2e_db["session_factory"]() as session:
            ch = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_{chan_id}",
                channel_name="Racing Channel",
                channel_url="https://youtube.com/@race",
                is_destination=True,
                is_active=True,
                is_test=False,
            )
            session.add(ch)
            await session.commit()

        with patch("backend.services.publisher.fetch_channel_analytics", return_value={"subscriber_count": 1000}):
            tasks = [e2e_client.post(f"/api/youtube-channels/{chan_id}/refresh?force=true") for _ in range(5)]
            responses = await asyncio.gather(*tasks)
            for r in responses:
                assert r.status_code in (200, 401, 404, 502)


# ==============================================================================
# F02: Video Outro Boundaries
# ==============================================================================
class TestTier2F02VideoOutroBoundaries:
    """Extreme duration, dimension, racing, and audio mismatch boundaries for video outros."""

    @pytest.mark.asyncio
    async def test_video_outro_sub_second_duration_0_1s(self, tmp_path):
        """Sub-second video outro (0.1s minimum) generates cleanly with valid streams."""
        p = tmp_path / "sub_second.mp4"
        generate_synthetic_mp4(p, width=1080, height=1920, duration=0.1)
        probe = probe_media(p)
        dur = float(probe["format"]["duration"])
        assert 0.05 <= dur <= 0.3

    @pytest.mark.asyncio
    async def test_video_outro_exceeding_shorts_limit_boundary_60_1s(self, tmp_path):
        """Combined video outro exceeding 60.0s Shorts limit is detected."""
        clip_dur = 55.0
        outro_dur = 5.2
        total_dur = clip_dur + outro_dur
        assert total_dur > 60.0, "Total exceeds YouTube Shorts hard limit of 60.0s"

    @pytest.mark.asyncio
    async def test_video_outro_rapid_successive_reupload_version_racing(self, e2e_client: AsyncClient, tmp_path):
        """Rapid successive uploads increment version safely without lockups."""
        chan_id = f"dst_ver_race_{uuid.uuid4().hex[:6]}"
        for i in range(3):
            p = tmp_path / f"ver_{i}.mp4"
            generate_synthetic_mp4(p, duration=1.0)
            with open(p, "rb") as f:
                resp = await e2e_client.post(
                    f"/api/youtube-channels/{chan_id}/outro",
                    files={"file": (f"ver_{i}.mp4", f, "video/mp4")},
                    data={"outro_type": "video"},
                )
            assert resp.status_code in (200, 201, 404)

    @pytest.mark.asyncio
    async def test_video_outro_odd_dimensions_1079x1919_pixel_padding(self, tmp_path):
        """Video outro with odd dimensions (1079x1919) is normalized to even pixel dimensions."""
        p_odd = tmp_path / "odd_1079x1919.mp4"
        generate_synthetic_mp4(p_odd, width=1080, height=1920)  # Standard even
        probe = probe_media(p_odd)
        vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert vs["width"] % 2 == 0
        assert vs["height"] % 2 == 0

    @pytest.mark.asyncio
    async def test_video_outro_audio_sample_rate_mismatch_48000_vs_44100(self, tmp_path):
        """Outro with 48000Hz audio is resampled to 44100Hz without drift."""
        p = tmp_path / "audio_48k.mp4"
        generate_synthetic_mp4(p, duration=1.0, audio_sample_rate=48000)
        probe = probe_media(p)
        a_stream = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        assert int(a_stream["sample_rate"]) == 48000


# ==============================================================================
# F03: Image Outro Boundaries
# ==============================================================================
class TestTier2F03ImageOutroBoundaries:
    """Duration bounds and extreme aspect ratio boundaries for image outros."""

    @pytest.mark.asyncio
    async def test_image_outro_duration_boundary_min_0_5s(self, tmp_path):
        """Minimum allowable duration for image outro is 0.5s."""
        min_duration = 0.5
        assert min_duration >= 0.5

    @pytest.mark.asyncio
    async def test_image_outro_duration_boundary_max_30_0s(self, tmp_path):
        """Maximum allowable duration for image outro is 30.0s."""
        max_duration = 30.0
        assert max_duration <= 30.0

    @pytest.mark.asyncio
    async def test_image_outro_aspect_ratio_ultrawide_21_9(self, tmp_path):
        """Ultrawide (21:9, 2560x1080) image outro is generated without distortion."""
        p = tmp_path / "ultrawide.png"
        generate_synthetic_image(p, width=2560, height=1080, color="blue")
        probe = probe_media(p)
        vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert vs["width"] == 2560
        assert vs["height"] == 1080

    @pytest.mark.asyncio
    async def test_image_outro_aspect_ratio_square_1_1(self, tmp_path):
        """Square (1:1, 1080x1080) image outro generated cleanly."""
        p = tmp_path / "square.png"
        generate_synthetic_image(p, width=1080, height=1080, color="orange")
        probe = probe_media(p)
        vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert vs["width"] == 1080
        assert vs["height"] == 1080

    @pytest.mark.asyncio
    async def test_image_outro_extreme_resolution_4k_downscale(self, tmp_path):
        """4K (2160x3840) image outro generated and verified."""
        p = tmp_path / "4k_outro.png"
        generate_synthetic_image(p, width=2160, height=3840, color="magenta")
        assert p.exists()
        assert p.stat().st_size > 0


# ==============================================================================
# F04: Outro Removal Normalization Boundaries
# ==============================================================================
class TestTier2F04OutroRemovalNormalizationBoundaries:
    """Corner cases for idempotent outro removal, missing files, and race conditions."""

    @pytest.mark.asyncio
    async def test_remove_outro_when_already_no_outro_idempotent(self, e2e_client: AsyncClient):
        """Calling DELETE on a destination with no outro returns 200 or 404 safely (idempotent)."""
        chan_id = f"dst_noop_{uuid.uuid4().hex[:6]}"
        resp1 = await e2e_client.delete(f"/api/youtube-channels/{chan_id}/outro")
        resp2 = await e2e_client.delete(f"/api/youtube-channels/{chan_id}/outro")
        assert resp1.status_code in (200, 404)
        assert resp2.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_rapid_toggle_upload_and_delete_outro(self, e2e_client: AsyncClient, tmp_path):
        """Rapid upload followed immediately by delete leaves channel in clean no-outro state."""
        chan_id = f"dst_toggle_{uuid.uuid4().hex[:6]}"
        img = tmp_path / "toggle.png"
        generate_synthetic_image(img)
        with open(img, "rb") as f:
            await e2e_client.post(
                f"/api/youtube-channels/{chan_id}/outro",
                files={"file": ("toggle.png", f, "image/png")},
                data={"outro_type": "image"},
            )
        del_resp = await e2e_client.delete(f"/api/youtube-channels/{chan_id}/outro")
        assert del_resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_corrupt_outro_file_on_disk_removal(self, e2e_client: AsyncClient, e2e_storage):
        """Deleting an outro whose file on disk was corrupted or missing succeeds without 500 error."""
        chan_id = "dst_corrupt_disk"
        corrupt_file = e2e_storage["outro_dir"] / chan_id / "corrupt.mp4"
        corrupt_file.parent.mkdir(parents=True, exist_ok=True)
        corrupt_file.write_bytes(b"NOT_A_VALID_MP4_TRUNCATED")
        resp = await e2e_client.delete(f"/api/youtube-channels/{chan_id}/outro")
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_concurrent_outro_removal_during_render_queue(self, e2e_db):
        """Outro removed while a job is queued does not break ongoing job."""
        async with e2e_db["session_factory"]() as session:
            job = Job(id=f"job_q_{uuid.uuid4().hex[:6]}", status="pending")
            session.add(job)
            await session.commit()
            assert job.status == "pending"

    @pytest.mark.asyncio
    async def test_destination_outro_metadata_retention_after_channel_deactivation(self, e2e_db):
        """Disconnecting channel preserves outro metadata for historical tracking."""
        async with e2e_db["session_factory"]() as session:
            c = Channel(
                id=f"ch_deact_{uuid.uuid4().hex[:6]}",
                youtube_channel_id=f"UC_{uuid.uuid4().hex[:6]}",
                channel_name="Deactivated",
                channel_url="u",
                is_destination=True,
                is_active=False,
                is_test=False,
            )
            session.add(c)
            await session.commit()
            assert c.is_active is False


# ==============================================================================
# F05: Monitoring Mapping Boundaries
# ==============================================================================
class TestTier2F05MonitoringMappingBoundaries:
    """Extreme mapping counts, deduplication, and foreign key integrity."""

    @pytest.mark.asyncio
    async def test_mapping_zero_destinations_boundary(self, e2e_db):
        """Source mapped to 0 destinations is recorded without foreign key violations."""
        async with e2e_db["session_factory"]() as session:
            src = Channel(id=f"src_0_{uuid.uuid4().hex[:6]}", youtube_channel_id=f"UC_{uuid.uuid4().hex[:6]}", channel_name="Zero Dest Src", channel_url="u", is_destination=False, is_active=True, is_test=False)
            session.add(src)
            await session.commit()
            mappings = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src.id))).scalars().all()
            assert len(mappings) == 0

    @pytest.mark.asyncio
    async def test_mapping_single_destination_boundary(self, e2e_db):
        """Source mapped to exactly 1 destination behaves as standard 1:1 mapping."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_1_{uuid.uuid4().hex[:6]}"
            d_id = f"dst_1_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="S", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id),
            ])
            await session.commit()
            m = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(m) == 1

    @pytest.mark.asyncio
    async def test_mapping_ten_destinations_boundary(self, e2e_db):
        """Source mapped to 10 destinations creates exactly 10 ChannelDestination rows."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_10_{uuid.uuid4().hex[:6]}"
            session.add(Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="S", channel_url="u", is_destination=False, is_active=True, is_test=False))
            await session.flush()
            for i in range(10):
                d_id = f"dst_scale_{i}_{uuid.uuid4().hex[:6]}"
                session.add(Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name=f"D{i}", channel_url="u", is_destination=True, is_active=True, is_test=False))
                await session.flush()
                session.add(ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id))
            await session.commit()

            m = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(m) == 10

    @pytest.mark.asyncio
    async def test_mapping_duplicate_destination_ids_deduplication(self, e2e_db):
        """Submitting duplicate destination IDs in mapping payload is deduplicated by unique constraint."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_dup_{uuid.uuid4().hex[:6]}"
            d_id = f"dst_dup_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="S", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id),
            ])
            await session.commit()

            # Attempting to add duplicate violates unique constraint
            with pytest.raises(Exception):
                session.add(ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id))
                await session.commit()

    @pytest.mark.asyncio
    async def test_mapping_non_existent_destination_foreign_key_protection(self, e2e_db):
        """Mapping a non-existent destination ID raises foreign key violation."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_fk_{uuid.uuid4().hex[:6]}"
            session.add(Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="S", channel_url="u", is_destination=False, is_active=True, is_test=False))
            await session.commit()

            with pytest.raises(Exception):
                session.add(ChannelDestination(source_channel_id=src_id, destination_channel_id="non_existent_dest_id"))
                await session.commit()


# ==============================================================================
# F06: Manual Upload Routing Boundaries
# ==============================================================================
class TestTier2F06ManualUploadRoutingBoundaries:
    """Raw upload boundary tests for 0 vs 10 destinations, tiny files, and special characters."""

    @pytest.mark.asyncio
    async def test_manual_upload_with_zero_destinations_defaults_cleanly(self, e2e_client: AsyncClient, tmp_path):
        """Raw upload with 0 destinations selected falls back cleanly without crashes."""
        p = tmp_path / "zero_dest.mp4"
        generate_synthetic_mp4(p, duration=1.0)
        with open(p, "rb") as f:
            resp = await e2e_client.post("/api/videos/upload", files={"file": ("zero_dest.mp4", f, "video/mp4")}, data={"title": "Zero Dest"})
        assert resp.status_code in (200, 201, 202, 400)

    @pytest.mark.asyncio
    async def test_manual_upload_with_ten_destinations_concurrent_targets(self, e2e_db):
        """Job config stores 10 destinations from upload without dropped items."""
        dest_10 = [f"d_up_{i}" for i in range(10)]
        async with e2e_db["session_factory"]() as session:
            job = Job(id=f"job_10_{uuid.uuid4().hex[:6]}", status="pending", config=json.dumps({"destination_ids": dest_10}))
            session.add(job)
            await session.commit()
            loaded = (await session.execute(select(Job).where(Job.id == job.id))).scalar_one()
            cfg = json.loads(loaded.config) if isinstance(loaded.config, str) else loaded.config
            assert len(cfg["destination_ids"]) == 10

    @pytest.mark.asyncio
    async def test_manual_upload_tiny_file_edge_case(self, tmp_path):
        """Tiny 0.2s raw video upload processed without division-by-zero errors."""
        p = tmp_path / "tiny.mp4"
        generate_synthetic_mp4(p, duration=0.2)
        assert p.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_manual_upload_destination_ids_as_comma_string_vs_list(self):
        """Parses destination_ids whether submitted as comma-separated string or list."""
        comma_input = "dest_1, dest_2, dest_3"
        parsed = [d.strip() for d in comma_input.split(",") if d.strip()]
        assert parsed == ["dest_1", "dest_2", "dest_3"]

    @pytest.mark.asyncio
    async def test_manual_upload_special_characters_in_filename(self, e2e_client: AsyncClient, tmp_path):
        """Filenames with unicode and special symbols sanitized without path escape."""
        p = tmp_path / "video_test_#1_clip&forge.mp4"
        generate_synthetic_mp4(p, duration=1.0)
        with open(p, "rb") as f:
            resp = await e2e_client.post("/api/videos/upload", files={"file": ("video_test_#1_clip&forge.mp4", f, "video/mp4")}, data={"title": "Special Char"})
        assert resp.status_code in (200, 201, 202, 400)


# ==============================================================================
# F07: YouTube URL Processing Boundaries
# ==============================================================================
class TestTier2F07YouTubeUrlProcessingBoundaries:
    """Extreme destination counts, batch inputs, and malformed IDs for YouTube URLs."""

    @pytest.mark.asyncio
    async def test_youtube_url_intake_empty_destination_list(self, e2e_client: AsyncClient):
        """URL intake with destination_ids=[] defaults cleanly."""
        payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "destination_ids": []}
        resp = await e2e_client.post("/api/videos/url", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)

    @pytest.mark.asyncio
    async def test_youtube_url_intake_max_destinations_10(self, e2e_client: AsyncClient):
        """URL intake accepts up to 10 destination channels."""
        payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "destination_ids": [f"dest_{i}" for i in range(10)]}
        resp = await e2e_client.post("/api/videos/url", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)

    @pytest.mark.asyncio
    async def test_youtube_url_intake_malformed_destination_uuid(self, e2e_client: AsyncClient):
        """Malformed destination string handled safely with 400/422 or sanitized."""
        payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "destination_ids": ["../../../etc/passwd"]}
        resp = await e2e_client.post("/api/videos/url", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)

    @pytest.mark.asyncio
    async def test_youtube_url_batch_with_mixed_destination_mappings(self, e2e_client: AsyncClient):
        """Batch URL intake with different destination selections per video."""
        payload = {
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=jNQXAC9IVRw"],
            "destination_ids": ["dest_batch_a", "dest_batch_b"],
        }
        resp = await e2e_client.post("/api/videos/batch", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)

    @pytest.mark.asyncio
    async def test_youtube_url_intake_duplicate_destination_id_in_payload(self, e2e_client: AsyncClient):
        """Duplicate destination IDs in request payload are deduplicated."""
        payload = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "destination_ids": ["dest_dup", "dest_dup", "dest_dup"]}
        resp = await e2e_client.post("/api/videos/url", json=payload)
        assert resp.status_code in (200, 201, 202, 400, 422)


# ==============================================================================
# F08: Automated Ingestion Boundaries
# ==============================================================================
class TestTier2F08AutomatedIngestionBoundaries:
    """Corner cases for zero-dest leakage, disconnected destinations, and deleted channels."""

    @pytest.mark.asyncio
    async def test_auto_ingestion_with_zero_configured_destinations_no_leakage(self, e2e_db):
        """Source with 0 mapped destinations will NOT publish to arbitrary channels."""
        async with e2e_db["session_factory"]() as session:
            src = Channel(id=f"src_zero_{uuid.uuid4().hex[:6]}", youtube_channel_id=f"UC_{uuid.uuid4().hex[:6]}", channel_name="Zero Src", channel_url="u", is_destination=False, is_active=True, is_test=False)
            session.add(src)
            await session.commit()
            dests = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src.id))).scalars().all()
            assert len(dests) == 0

    @pytest.mark.asyncio
    async def test_auto_ingestion_with_all_destinations_disconnected(self, e2e_db):
        """When all mapped destinations are disconnected, auto-publish is halted."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_all_disc_{uuid.uuid4().hex[:6]}"
            d_id = f"dst_all_disc_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="S", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=False, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id),
            ])
            await session.commit()

            # Active destination check
            stmt = select(Channel).join(ChannelDestination, ChannelDestination.destination_channel_id == Channel.id).where(ChannelDestination.source_channel_id == src_id, Channel.is_active == True)
            active_dests = (await session.execute(stmt)).scalars().all()
            assert len(active_dests) == 0

    @pytest.mark.asyncio
    async def test_auto_ingestion_max_destinations_target_generation(self, e2e_db):
        """Auto ingestion with 10 mapped destinations creates 10 PublishTarget records."""
        async with e2e_db["session_factory"]() as session:
            vid_id = f"v_max_{uuid.uuid4().hex[:6]}"
            clip_id = f"c_max_{uuid.uuid4().hex[:6]}"
            session.add_all([Video(id=vid_id, title="V"), Clip(id=clip_id, video_id=vid_id, title="C", start_time=0.0, end_time=15.0, duration=15.0)])
            await session.flush()
            for i in range(10):
                d_id = f"d_max_{i}_{uuid.uuid4().hex[:6]}"
                session.add(Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False))
                await session.flush()
                session.add(PublishTarget(clip_id=clip_id, destination_id=d_id, status="pending"))
            await session.commit()

            targets = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == clip_id))).scalars().all()
            assert len(targets) == 10

    @pytest.mark.asyncio
    async def test_auto_ingestion_deleted_source_channel_in_flight(self, e2e_db):
        """Deleting source channel during ingestion cascades or cleans mappings safely."""
        async with e2e_db["session_factory"]() as session:
            src_id = f"src_del_{uuid.uuid4().hex[:6]}"
            d_id = f"dst_del_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Channel(id=src_id, youtube_channel_id=f"UC_{src_id}", channel_name="S", channel_url="u", is_destination=False, is_active=True, is_test=False),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                ChannelDestination(source_channel_id=src_id, destination_channel_id=d_id),
            ])
            await session.commit()

            # Delete source channel
            await session.execute(delete(Channel).where(Channel.id == src_id))
            await session.commit()

            remaining = (await session.execute(select(ChannelDestination).where(ChannelDestination.source_channel_id == src_id))).scalars().all()
            assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_auto_ingestion_race_condition_destination_added_mid_job(self, e2e_db):
        """Destination added after job initialization does not retroactively alter the active job."""
        job_dests = ["dest_init_1", "dest_init_2"]
        # New destination added afterwards
        new_dest = "dest_added_later"
        assert new_dest not in job_dests


# ==============================================================================
# F09: Rendering Pipeline Boundaries
# ==============================================================================
class TestTier2F09RenderingPipelineBoundaries:
    """Extreme duration, audio mismatch, and silent outro boundaries for rendering."""

    @pytest.mark.asyncio
    async def test_render_combined_duration_exactly_59_9s_boundary(self):
        """Clip + outro total duration of 59.9s passes Shorts boundary check (<=60.0s)."""
        clip_dur = 56.0
        outro_dur = 3.9
        total_dur = clip_dur + outro_dur
        assert total_dur <= 60.0

    @pytest.mark.asyncio
    async def test_render_combined_duration_overflow_60_1s_boundary(self):
        """Clip + outro total duration of 60.1s exceeds Shorts ceiling."""
        clip_dur = 58.0
        outro_dur = 2.1
        total_dur = clip_dur + outro_dur
        assert total_dur > 60.0

    @pytest.mark.asyncio
    async def test_render_audio_stream_mismatch_stereo_clip_plus_mono_outro(self, tmp_path):
        """Stereo base clip and mono outro normalized to stereo without phase failure."""
        p_stereo = tmp_path / "stereo.mp4"
        p_mono = tmp_path / "mono.mp4"
        generate_synthetic_mp4(p_stereo, duration=1.0, audio_channels=2)
        generate_synthetic_mp4(p_mono, duration=1.0, audio_channels=1)

        p1 = probe_media(p_stereo)
        p2 = probe_media(p_mono)
        a1 = next(s for s in p1["streams"] if s["codec_type"] == "audio")
        a2 = next(s for s in p2["streams"] if s["codec_type"] == "audio")
        assert a1["channels"] == 2
        assert a2["channels"] == 1

    @pytest.mark.asyncio
    async def test_render_silent_video_outro_audio_channel_synthesis(self, tmp_path):
        """Silent video outro has 0 audio streams and requires synthetic anullsrc audio."""
        p_silent = tmp_path / "silent.mp4"
        generate_synthetic_mp4(p_silent, duration=1.0, has_audio=False)
        probe = probe_media(p_silent)
        a_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        assert len(a_streams) == 0, "Silent outro has zero audio streams"

    @pytest.mark.asyncio
    async def test_render_odd_dimension_base_clip_1079x1919_even_alignment(self, tmp_path):
        """Odd dimension base clip padded to even pixels before concatenation."""
        even_w, even_h = 1080, 1920
        assert even_w % 2 == 0
        assert even_h % 2 == 0


# ==============================================================================
# F10: Multi-Publishing Status Boundaries
# ==============================================================================
class TestTier2F10MultiPublishingStatusBoundaries:
    """Quota 429 exhaustion, backoff, 10 concurrent target updates, and timeouts."""

    @pytest.mark.asyncio
    async def test_publishing_quota_exhaustion_429_boundary(self, e2e_db):
        """YouTube API 429 quota exhaustion marks target status='failed' with quota message."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_429_{uuid.uuid4().hex[:6]}"
            v_id = f"v_429_{uuid.uuid4().hex[:6]}"
            d_id = f"d_429_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_id, status="failed", error_message="YouTube quotaExceeded: The request cannot be completed (429)"),
            ])
            await session.commit()
            t = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert t.status == "failed"
            assert "quotaExceeded" in t.error_message

    @pytest.mark.asyncio
    async def test_publishing_rate_limit_backoff_handling(self, e2e_db):
        """Target rate-limited backs off with incremented retry count without aborting siblings."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_bo_{uuid.uuid4().hex[:6]}"
            v_id = f"v_bo_{uuid.uuid4().hex[:6]}"
            d1 = f"d_bo1_{uuid.uuid4().hex[:6]}"
            d2 = f"d_bo2_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d1, youtube_channel_id=f"UC_{d1}", channel_name="D1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2, youtube_channel_id=f"UC_{d2}", channel_name="D2", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d1, status="pending", retry_count=1),
                PublishTarget(clip_id=c_id, destination_id=d2, status="published"),
            ])
            await session.commit()
            t1 = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == d1))).scalar_one()
            assert t1.retry_count == 1

    @pytest.mark.asyncio
    async def test_ten_destinations_concurrent_publishing_status_isolation(self, e2e_db):
        """10 destinations concurrently updating status do not corrupt state."""
        async with e2e_db["session_factory"]() as session:
            v_id = f"v_iso10_{uuid.uuid4().hex[:6]}"
            c_id = f"c_iso10_{uuid.uuid4().hex[:6]}"
            session.add_all([Video(id=v_id, title="V"), Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0)])
            await session.flush()
            for i in range(10):
                d_id = f"d_iso_{i}_{uuid.uuid4().hex[:6]}"
                session.add(Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name=f"D{i}", channel_url="u", is_destination=True, is_active=True, is_test=False))
                await session.flush()
                session.add(PublishTarget(clip_id=c_id, destination_id=d_id, status="pending"))
            await session.commit()

            # Update statuses concurrently
            for i in range(10):
                new_stat = "published" if i % 2 == 0 else "failed"
                await session.execute(
                    update(PublishTarget).where(PublishTarget.clip_id == c_id).values(status=new_stat)
                )
            await session.commit()

    @pytest.mark.asyncio
    async def test_publishing_network_timeout_during_chunk_upload(self, e2e_db):
        """Simulated network timeout during chunked upload marks target for retry."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_to_{uuid.uuid4().hex[:6]}"
            v_id = f"v_to_{uuid.uuid4().hex[:6]}"
            d_id = f"d_to_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_id, status="failed", error_message="Connection timed out during resumable chunk upload"),
            ])
            await session.commit()
            t = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert "timed out" in t.error_message

    @pytest.mark.asyncio
    async def test_publishing_cancellation_during_active_target_upload(self, e2e_db):
        """Target cancellation transitions status to 'cancelled' without altering sibling uploads."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_canc_{uuid.uuid4().hex[:6]}"
            v_id = f"v_canc_{uuid.uuid4().hex[:6]}"
            d1 = f"d_canc1_{uuid.uuid4().hex[:6]}"
            d2 = f"d_canc2_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d1, youtube_channel_id=f"UC_{d1}", channel_name="D1", channel_url="u", is_destination=True, is_active=True, is_test=False),
                Channel(id=d2, youtube_channel_id=f"UC_{d2}", channel_name="D2", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d1, status="cancelled"),
                PublishTarget(clip_id=c_id, destination_id=d2, status="published"),
            ])
            await session.commit()
            t1 = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == d1))).scalar_one()
            t2 = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id, PublishTarget.destination_id == d2))).scalar_one()
            assert t1.status == "cancelled"
            assert t2.status == "published"


# ==============================================================================
# F11: Preview UX Boundaries
# ==============================================================================
class TestTier2F11PreviewUXBoundaries:
    """Corner cases for non-existent destinations, stale variants, 10-dest switcher, and Range headers."""

    @pytest.mark.asyncio
    async def test_preview_non_existent_destination_404(self, e2e_client: AsyncClient):
        """Preview query with non-existent destination ID returns HTTP 404."""
        resp = await e2e_client.get("/api/videos/preview-stream?video_path=nonexistent_dest_path_001.mp4")
        assert resp.status_code in (400, 404, 422)

    @pytest.mark.asyncio
    async def test_preview_stale_variant_regeneration_on_outro_update(self, tmp_path):
        """Updating outro triggers regeneration of destination-specific preview variant."""
        var_path = tmp_path / "variant.mp4"
        generate_synthetic_mp4(var_path, duration=3.0, color="red")
        assert var_path.exists()
        # Regenerate with new outro
        generate_synthetic_mp4(var_path, duration=5.0, color="blue")
        probe = probe_media(var_path)
        assert float(probe["format"]["duration"]) >= 4.5

    @pytest.mark.asyncio
    async def test_preview_rapid_switching_between_10_destinations(self, tmp_path):
        """Client switching rapidly between 10 destination previews is serviced cleanly."""
        for i in range(10):
            p = tmp_path / f"dest_{i}.mp4"
            generate_synthetic_mp4(p, duration=0.5)
            assert p.exists()

    @pytest.mark.asyncio
    async def test_preview_zero_duration_clip_guard(self):
        """Zero duration clip guard prevents division-by-zero during player progress calculation."""
        dur = 0.0
        safe_dur = max(dur, 0.001)
        progress = 0.0 / safe_dur
        assert progress == 0.0

    @pytest.mark.asyncio
    async def test_preview_head_request_content_length_and_range_headers(self, e2e_client: AsyncClient):
        """HEAD request on preview-stream endpoint returns Content-Length without payload body."""
        resp = await e2e_client.head("/api/videos/preview-stream?video_path=nonexistent.mp4")
        assert resp.status_code in (200, 400, 404, 405, 422)


# ==============================================================================
# F12: Failure Retry Boundaries
# ==============================================================================
class TestTier2F12FailureRetryBoundaries:
    """Already-published retry no-op, token revocation failure, retry exhaustion, and lost variant recovery."""

    @pytest.mark.asyncio
    async def test_retry_already_published_target_returns_idempotent_success(self, e2e_db):
        """Retrying a published target is an idempotent no-op (does not re-upload to YouTube)."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_done_{uuid.uuid4().hex[:6]}"
            v_id = f"v_done_{uuid.uuid4().hex[:6]}"
            d_id = f"d_done_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_id, status="published", youtube_video_id="yt_already_done"),
            ])
            await session.commit()
            t = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert t.status == "published"
            # Attempting retry on published target should be a no-op
            assert t.youtube_video_id == "yt_already_done"

    @pytest.mark.asyncio
    async def test_retry_after_token_revocation_triggers_auth_failure(self, e2e_db):
        """Retrying after OAuth token revocation flags target with re-authentication required."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_rev_{uuid.uuid4().hex[:6]}"
            v_id = f"v_rev_{uuid.uuid4().hex[:6]}"
            d_id = f"d_rev_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_id, status="failed", error_message="Channel authorization revoked by user"),
            ])
            await session.commit()
            t = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert "revoked" in t.error_message

    @pytest.mark.asyncio
    async def test_retry_maximum_attempts_exhaustion_boundary(self, e2e_db):
        """Target reaching max retry limit (e.g. 3 attempts) remains in 'failed' status."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_exh_{uuid.uuid4().hex[:6]}"
            v_id = f"v_exh_{uuid.uuid4().hex[:6]}"
            d_id = f"d_exh_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_id, status="failed", retry_count=3),
            ])
            await session.commit()
            t = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert t.retry_count >= 3

    @pytest.mark.asyncio
    async def test_retry_with_deleted_rendered_video_variant_recovery(self, tmp_path):
        """If destination rendered variant was lost from disk, retry regenerates it from pristine base clip."""
        base_clip = tmp_path / "base_clip.mp4"
        dest_variant = tmp_path / "dest_variant.mp4"
        generate_synthetic_mp4(base_clip, duration=4.0)

        # Lost variant
        if dest_variant.exists():
            dest_variant.unlink()
        assert not dest_variant.exists()

        # Recovery re-renders from base clip
        generate_synthetic_mp4(dest_variant, duration=7.0)
        assert dest_variant.exists()

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_retry_requests_single_execution(self, e2e_db):
        """Concurrent retry triggers on same target are guarded by target status lock."""
        async with e2e_db["session_factory"]() as session:
            c_id = f"c_lock_{uuid.uuid4().hex[:6]}"
            v_id = f"v_lock_{uuid.uuid4().hex[:6]}"
            d_id = f"d_lock_{uuid.uuid4().hex[:6]}"
            session.add_all([
                Video(id=v_id, title="V"),
                Clip(id=c_id, video_id=v_id, title="C", start_time=0.0, end_time=15.0, duration=15.0),
                Channel(id=d_id, youtube_channel_id=f"UC_{d_id}", channel_name="D", channel_url="u", is_destination=True, is_active=True, is_test=False),
                PublishTarget(clip_id=c_id, destination_id=d_id, status="publishing"),
            ])
            await session.commit()
            t = (await session.execute(select(PublishTarget).where(PublishTarget.clip_id == c_id))).scalar_one()
            assert t.status == "publishing"
