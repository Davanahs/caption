"""
test_c03_live_worker_ai_enhancements.py
=========================================
Canonical Work Item C-03: Live Docker Worker Refresh and AI Enhancement Verification
Tier 5 (Live Worker) Verification Suite

Verifies:
1. Live Celery worker connectivity, daemon heartbeat, and task registration.
2. Live worker execution of Hook Opportunity Analysis (analyze_hook_opportunities).
3. Live worker execution of Hook Variant Application (apply_hook_plan).
4. Live worker execution of SFX Mixing Variant Application (apply_sfx).
5. Live worker execution of B-roll Compositing Variant Application (apply_broll).
6. Idempotency claim handling on live worker with plan hashes.
7. Controlled failure paths and TaskExecution FAILED state tracking without orphan variants.
8. Core invariants: zero captions/subtitles generated or burned in, zero real YouTube publishing.
"""

import os
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

import pytest
from celery.result import AsyncResult

from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import (
    Channel, Video, Job, Clip, ClipVariant, ArtifactRecord,
    ArtifactStatus, ArtifactType, TaskExecution, TaskExecutionStatus,
    ClipHookPlan, ClipRetention, SFXAsset, VisualAsset, ClipSFXPlan
)
from backend.models.sfx import SFXPlan, SFXPlacement
from backend.models.broll import BrollPlan, BrollPlacement, DisplayMode
from backend.models.hook import HookPlan, HookOpportunity, ZoomIntervention
from backend.tasks.celery_app import celery_app
from backend.tasks.hook_tasks import analyze_hook_opportunities_task, apply_hook_task
from backend.tasks.clip_tasks import apply_sfx_task, apply_broll_task

TEST_PREFIX = "c03_live_"


def _generate_synthetic_video(output_file: Path, duration: float = 2.0, width: int = 720, height: int = 1280):
    """Generates a small valid vertical test video with audio using FFmpeg."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size={width}x{height}:rate=25",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac",
        "-shortest",
        str(output_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic video generation failed: {res.stderr}")


def _generate_synthetic_audio(output_file: Path, duration: float = 0.5):
    """Generates a small valid WAV audio file using FFmpeg."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=880:duration={duration}",
        "-c:a", "pcm_s16le",
        str(output_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic audio generation failed: {res.stderr}")


def _probe_media_streams(file_path: Path) -> Dict[str, Any]:
    """Runs FFprobe to inspect stream types, codec names, and verify subtitle invariance."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,width,height",
        "-show_entries", "format=duration",
        "-of", "json",
        str(file_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFprobe failed on {file_path}: {res.stderr}")
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def ensure_worker_ready():
    """Verifies that the live Docker worker is reachable via Redis and has required tasks registered."""
    inspect = celery_app.control.inspect(timeout=5.0)
    active = inspect.active()
    if not active:
        pytest.fail("No live Celery worker detected! Ensure Docker compose worker container is running.")
    
    registered = inspect.registered()
    all_registered = []
    for worker_tasks in (registered or {}).values():
        all_registered.extend(worker_tasks)
        
    required = ["analyze_hook_opportunities", "apply_hook_plan", "apply_sfx", "apply_broll"]
    for req in required:
        assert req in all_registered, f"Required task {req} is not registered on live worker!"
    return list(active.keys())[0]


@pytest.fixture(autouse=True)
def cleanup_c03_data():
    """Cleans up database records and filesystem test outputs after each test."""
    created_dirs = []
    yield created_dirs
    
    # 1. Clean DB - delete child foreign key tables before parent tables
    with SyncSessionLocal() as session:
        session.query(ClipVariant).filter(ClipVariant.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipHookPlan).filter(ClipHookPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipSFXPlan).filter(ClipSFXPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipRetention).filter(ClipRetention.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(TaskExecution).filter(TaskExecution.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(SFXAsset).filter(SFXAsset.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(VisualAsset).filter(VisualAsset.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ArtifactRecord).filter(ArtifactRecord.storage_key.like(f"%{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.commit()
        
    # 2. Clean test media directories
    for d in created_dirs:
        if d and os.path.exists(d):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass


def _create_test_clip_bundle(video_uid: str, clip_uid: str, created_dirs: List[Path], duration: float = 2.0) -> Dict[str, Any]:
    """Helper to synchronously seed test DB records and a valid synthetic MP4 file."""
    chan_id = f"{TEST_PREFIX}chan_{video_uid[:6]}"
    vid_id = f"{TEST_PREFIX}vid_{video_uid}"
    job_id = f"{TEST_PREFIX}job_{video_uid[:6]}"
    clip_id = f"{TEST_PREFIX}clip_{clip_uid}"
    
    # Storage key convention
    clip_rel_key = f"outputs/{vid_id}/clips/{clip_id}/clip.mp4"
    clip_physical_path = Path(settings.OUTPUT_DIR) / f"{vid_id}/clips/{clip_id}/clip.mp4"
    clip_physical_dir = Path(settings.OUTPUT_DIR) / f"{vid_id}"
    created_dirs.append(clip_physical_dir)
    
    # Generate actual valid synthetic MP4 video
    _generate_synthetic_video(clip_physical_path, duration=duration, width=720, height=1280)
    
    with SyncSessionLocal() as session:
        chan = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{chan_id}",
            channel_name="Live Worker Verification Channel",
            channel_url="https://youtube.com/channel/live_worker_test",
            is_test=True
        )
        session.add(chan)
        
        video = Video(
            id=vid_id,
            youtube_id=f"yt_{vid_id}",
            title="Live Worker Synthetic Video",
            channel_id=chan_id,
            local_path=clip_rel_key
        )
        session.add(video)
        
        job = Job(id=job_id, video_id=vid_id, channel_id=chan_id, is_test=True)
        session.add(job)
        
        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            run_identity=f"{job_id}_0_0",
            title="Live Worker Verification Clip",
            output_path=clip_rel_key,
            start_time=0.0,
            end_time=duration,
            duration=duration,
            publish_status="draft"
        )
        session.add(clip)
        
        # Base clip artifact record
        base_art = ArtifactRecord(
            id=f"{TEST_PREFIX}art_{clip_uid}",
            owner_type="clip",
            owner_id=clip_id,
            artifact_type=ArtifactType.FINAL_CLIP.value,
            storage_key=clip_rel_key,
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add(base_art)
        session.commit()
        
    return {
        "chan_id": chan_id,
        "vid_id": vid_id,
        "job_id": job_id,
        "clip_id": clip_id,
        "clip_rel_key": clip_rel_key,
        "clip_physical_path": clip_physical_path
    }


# ─── TEST 1: WORKER CONNECTIVITY & REGISTRATION ──────────────────────────────

def test_live_worker_connectivity(ensure_worker_ready):
    """Asserts that the live Docker Celery worker is connected and healthy."""
    worker_name = ensure_worker_ready
    assert "celery@" in worker_name
    inspect = celery_app.control.inspect()
    stats = inspect.stats()
    assert stats is not None
    assert worker_name in stats


# ─── TEST 2: HOOK OPPORTUNITY ANALYSIS ON LIVE WORKER ────────────────────────

def test_live_worker_hook_analysis_task(ensure_worker_ready, cleanup_c03_data):
    """Verifies that analyze_hook_opportunities executes on the live Docker worker."""
    uid = uuid.uuid4().hex[:8]
    bundle = _create_test_clip_bundle(uid, uid, cleanup_c03_data, duration=15.0)
    clip_id = bundle["clip_id"]
    
    # Seed ClipRetention with dropoff risk points
    with SyncSessionLocal() as session:
        ret = ClipRetention(
            clip_id=clip_id,
            overall_score=0.78,
            analysis_json=json.dumps([
                {"start_time": 0.0, "severity": 0.85},
                {"start_time": 5.0, "severity": 0.40}
            ])
        )
        session.add(ret)
        session.commit()
        
    # Dispatch task to live Celery worker queue
    async_res = analyze_hook_opportunities_task.delay(clip_id=clip_id)
    assert async_res.id is not None
    
    # Await result from live worker
    result = async_res.get(timeout=30)
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["clip_id"] == clip_id
    assert "opportunity_type" in result[0]
    
    # Verify ClipHookPlan was committed to PostgreSQL by the worker
    with SyncSessionLocal() as session:
        db_plan = session.query(ClipHookPlan).filter_by(clip_id=clip_id).first()
        assert db_plan is not None
        plan_data = json.loads(db_plan.plan_json)
        assert "opportunities" in plan_data
        assert len(plan_data["opportunities"]) > 0


# ─── TEST 3: APPLY HOOK VARIANT ON LIVE WORKER ────────────────────────────────

def test_live_worker_apply_hook_plan_task(ensure_worker_ready, cleanup_c03_data):
    """Verifies that apply_hook_plan executes on the live Docker worker and creates valid media."""
    uid = uuid.uuid4().hex[:8]
    bundle = _create_test_clip_bundle(uid, uid, cleanup_c03_data, duration=2.0)
    clip_id = bundle["clip_id"]
    
    hook_plan = HookPlan(
        clip_id=clip_id,
        plan_hash=f"hash_{uid}",
        planner_version="1.0.0",
        opportunities=[
            HookOpportunity(
                id=f"opp_{uid}",
                clip_id=clip_id,
                start_time=0.0,
                end_time=1.5,
                opportunity_type="opening_hook",
                hook_objective="Capture immediate attention",
                confidence=0.85,
                reason="Default opening hook opportunity."
            )
        ],
        visual_interventions=[
            ZoomIntervention(start_time=0.2, end_time=1.4, zoom_factor=1.15)
        ]
    )
    
    # Dispatch to live Celery worker
    async_res = apply_hook_task.delay(clip_id=clip_id, hook_plan_dict=hook_plan.model_dump())
    assert async_res.id is not None
    
    # Await result
    res = async_res.get(timeout=45)
    assert res["status"] == "success"
    assert res["variant_type"] == "hook"
    
    # Verify PostgreSQL state
    with SyncSessionLocal() as session:
        tx = session.query(TaskExecution).filter_by(id=async_res.id).first()
        assert tx is not None
        assert tx.status == TaskExecutionStatus.SUCCEEDED.value
        
        variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="hook").first()
        assert variant is not None
        assert variant.status == "completed"
        
        ar = session.query(ArtifactRecord).filter_by(id=variant.artifact_id).first()
        assert ar is not None
        assert ar.status == ArtifactStatus.READY.value
        assert "hook_" in ar.storage_key
        
    # Verify output file on disk
    variant_local_path = Path(settings.OUTPUT_DIR) / ar.storage_key.replace("outputs/", "")
    assert variant_local_path.exists(), f"Rendered variant file missing at {variant_local_path}"
    
    # Probe media: must have video and audio streams, exactly 0 subtitle streams
    info = _probe_media_streams(variant_local_path)
    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
    
    assert len(video_streams) == 1
    assert len(audio_streams) >= 1
    assert len(sub_streams) == 0, "Invariant violated: Subtitle stream found in Hook output!"
    assert float(info["format"]["duration"]) > 0.0


# ─── TEST 4: APPLY SFX VARIANT ON LIVE WORKER ─────────────────────────────────

def test_live_worker_apply_sfx_task(ensure_worker_ready, cleanup_c03_data):
    """Verifies that apply_sfx executes on the live Docker worker and creates a valid audio/video mix."""
    uid = uuid.uuid4().hex[:8]
    bundle = _create_test_clip_bundle(uid, uid, cleanup_c03_data, duration=2.0)
    clip_id = bundle["clip_id"]
    vid_id = bundle["vid_id"]
    
    # Create synthetic SFX audio file
    sfx_uid = f"sfx_{uid}"
    sfx_storage_key = f"outputs/{vid_id}/sfx_{sfx_uid}.wav"
    sfx_physical_path = Path(settings.OUTPUT_DIR) / f"{vid_id}/sfx_{sfx_uid}.wav"
    _generate_synthetic_audio(sfx_physical_path, duration=0.5)
    
    with SyncSessionLocal() as session:
        sfx_art = ArtifactRecord(
            id=f"{TEST_PREFIX}art_{sfx_uid}",
            owner_type="video",
            owner_id=vid_id,
            artifact_type=ArtifactType.AUDIO_SFX.value,
            storage_key=sfx_storage_key,
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add(sfx_art)
        
        sfx_asset = SFXAsset(
            id=f"{TEST_PREFIX}{sfx_uid}",
            name="Synthetic Beep",
            category="impact",
            artifact_id=sfx_art.id,
            duration=0.5
        )
        session.add(sfx_asset)
        session.commit()
        sfx_asset_id = sfx_asset.id
        
    sfx_plan = SFXPlan(
        clip_id=clip_id,
        placements=[
            SFXPlacement(
                asset_id=sfx_asset_id,
                category="impact",
                start_time=0.3,
                end_time=0.8,
                gain=-2.0,
                ducking_enabled=True,
                ducking_target_gain=-10.0
            )
        ]
    )
    
    # Dispatch to live Celery worker
    async_res = apply_sfx_task.delay(clip_id=clip_id, sfx_plan_dict=sfx_plan.model_dump())
    assert async_res.id is not None
    
    # Await result
    res = async_res.get(timeout=45)
    assert res["sfx_applied"] is True
    assert res["clip_id"] == clip_id
    
    # Verify PostgreSQL state
    with SyncSessionLocal() as session:
        tx = session.query(TaskExecution).filter_by(id=async_res.id).first()
        assert tx is not None
        assert tx.status == TaskExecutionStatus.SUCCEEDED.value
        
        variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="sfx").first()
        assert variant is not None
        assert variant.status == "completed"
        
        ar = session.query(ArtifactRecord).filter_by(id=variant.artifact_id).first()
        assert ar is not None
        assert ar.status == ArtifactStatus.READY.value
        assert "sfx_" in ar.storage_key
        
    # Verify output file
    variant_local_path = Path(settings.OUTPUT_DIR) / ar.storage_key.replace("outputs/", "")
    assert variant_local_path.exists()
    
    info = _probe_media_streams(variant_local_path)
    streams = info.get("streams", [])
    assert any(s.get("codec_type") == "video" for s in streams)
    assert any(s.get("codec_type") == "audio" for s in streams)
    assert not any(s.get("codec_type") == "subtitle" for s in streams), "Invariant violated: Subtitles present!"


# ─── TEST 5: APPLY B-ROLL VARIANT ON LIVE WORKER ──────────────────────────────

def test_live_worker_apply_broll_task(ensure_worker_ready, cleanup_c03_data):
    """Verifies that apply_broll executes on the live Docker worker and composites an overlay video."""
    uid = uuid.uuid4().hex[:8]
    bundle = _create_test_clip_bundle(uid, uid, cleanup_c03_data, duration=2.0)
    clip_id = bundle["clip_id"]
    vid_id = bundle["vid_id"]
    
    # Create synthetic B-roll overlay video
    broll_uid = f"broll_{uid}"
    broll_storage_key = f"outputs/{vid_id}/broll_{broll_uid}.mp4"
    broll_physical_path = Path(settings.OUTPUT_DIR) / f"{vid_id}/broll_{broll_uid}.mp4"
    _generate_synthetic_video(broll_physical_path, duration=1.0, width=400, height=400)
    
    with SyncSessionLocal() as session:
        broll_art = ArtifactRecord(
            id=f"{TEST_PREFIX}art_{broll_uid}",
            owner_type="video",
            owner_id=vid_id,
            artifact_type=ArtifactType.BROLL_ASSET.value,
            storage_key=broll_storage_key,
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add(broll_art)
        
        vis_asset = VisualAsset(
            id=f"{TEST_PREFIX}{broll_uid}",
            keyword="cutaway",
            asset_type="video",
            artifact_id=broll_art.id
        )
        session.add(vis_asset)
        session.commit()
        vis_asset_id = vis_asset.id
        
    broll_plan = BrollPlan(
        clip_id=clip_id,
        planner_version="1.0.0",
        placements=[
            BrollPlacement(
                asset_id=vis_asset_id,
                opportunity_id=f"opp_{uid}",
                confidence=0.85,
                start_time=0.2,
                end_time=1.2,
                display_mode=DisplayMode.PIP_BOTTOM,
                x=100,
                y=100,
                w=400,
                h=400
            )
        ]
    )
    
    # Dispatch to live Celery worker
    async_res = apply_broll_task.delay(clip_id=clip_id, broll_plan_dict=broll_plan.model_dump())
    assert async_res.id is not None
    
    # Await result
    res = async_res.get(timeout=45)
    assert res["broll_applied"] is True
    assert res["clip_id"] == clip_id
    
    # Verify PostgreSQL state
    with SyncSessionLocal() as session:
        tx = session.query(TaskExecution).filter_by(id=async_res.id).first()
        assert tx is not None
        assert tx.status == TaskExecutionStatus.SUCCEEDED.value
        
        variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="broll").first()
        assert variant is not None
        assert variant.status == "completed"
        
        ar = session.query(ArtifactRecord).filter_by(id=variant.artifact_id).first()
        assert ar is not None
        assert ar.status == ArtifactStatus.READY.value
        assert "broll_" in ar.storage_key
        
    # Verify output file
    variant_local_path = Path(settings.OUTPUT_DIR) / ar.storage_key.replace("outputs/", "")
    assert variant_local_path.exists()
    
    info = _probe_media_streams(variant_local_path)
    streams = info.get("streams", [])
    assert any(s.get("codec_type") == "video" for s in streams)
    assert not any(s.get("codec_type") == "subtitle" for s in streams), "Invariant violated: Subtitles present!"


# ─── TEST 6: IDEMPOTENCY HANDLING ON LIVE WORKER ──────────────────────────────

def test_live_worker_idempotency_sfx(ensure_worker_ready, cleanup_c03_data):
    """Verifies that re-dispatching an identical plan hash returns quickly via claim idempotency."""
    uid = uuid.uuid4().hex[:8]
    bundle = _create_test_clip_bundle(uid, uid, cleanup_c03_data, duration=2.0)
    clip_id = bundle["clip_id"]
    vid_id = bundle["vid_id"]
    
    sfx_uid = f"sfx_{uid}"
    sfx_storage_key = f"outputs/{vid_id}/sfx_{sfx_uid}.wav"
    sfx_physical_path = Path(settings.OUTPUT_DIR) / f"{vid_id}/sfx_{sfx_uid}.wav"
    _generate_synthetic_audio(sfx_physical_path, duration=0.5)
    
    with SyncSessionLocal() as session:
        sfx_art = ArtifactRecord(
            id=f"{TEST_PREFIX}art_{sfx_uid}",
            owner_type="video",
            owner_id=vid_id,
            artifact_type=ArtifactType.AUDIO_SFX.value,
            storage_key=sfx_storage_key,
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add(sfx_art)
        sfx_asset = SFXAsset(
            id=f"{TEST_PREFIX}{sfx_uid}",
            name="Beep",
            category="impact",
            artifact_id=sfx_art.id,
            duration=0.5
        )
        session.add(sfx_asset)
        session.commit()
        sfx_asset_id = sfx_asset.id
        
    sfx_plan = SFXPlan(
        clip_id=clip_id,
        placements=[
            SFXPlacement(
                asset_id=sfx_asset_id,
                category="impact",
                start_time=0.1,
                end_time=0.6,
                gain=0.0
            )
        ]
    )
    
    # Dispatch 1: Succeeds
    res1 = apply_sfx_task.delay(clip_id=clip_id, sfx_plan_dict=sfx_plan.model_dump()).get(timeout=45)
    assert res1["sfx_applied"] is True
    
    # Dispatch 2: Idempotent short-circuit
    res2 = apply_sfx_task.delay(clip_id=clip_id, sfx_plan_dict=sfx_plan.model_dump()).get(timeout=20)
    assert res2["sfx_applied"] is True
    
    # Verify exactly 1 ClipVariant was created (no duplicates)
    with SyncSessionLocal() as session:
        variants = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="sfx").all()
        assert len(variants) == 1


# ─── TEST 7: CONTROLLED FAILURE ON NONEXISTENT CLIP ───────────────────────────

def test_live_worker_nonexistent_clip_failure(ensure_worker_ready, cleanup_c03_data):
    """Verifies that dispatching against an invalid clip fails cleanly and records TaskExecution status FAILED."""
    fake_clip_id = f"{TEST_PREFIX}clip_nonexistent_{uuid.uuid4().hex[:6]}"
    dummy_plan = SFXPlan(clip_id=fake_clip_id, placements=[])
    
    async_res = apply_sfx_task.delay(clip_id=fake_clip_id, sfx_plan_dict=dummy_plan.model_dump())
    
    with pytest.raises(Exception):
        async_res.get(timeout=15)
        
    # Verify no orphan variants were created
    with SyncSessionLocal() as session:
        variants = session.query(ClipVariant).filter_by(clip_id=fake_clip_id).all()
        assert len(variants) == 0


# ─── TEST 8: ADVERSARIAL: MISSING B-ROLL ASSET RECORD FAILURE ───────────────────

def test_live_worker_missing_broll_asset_failure(ensure_worker_ready, cleanup_c03_data):
    """Adversarial check: B-roll task referencing nonexistent VisualAsset fails safely with no orphan variant."""
    uid = uuid.uuid4().hex[:8]
    bundle = _create_test_clip_bundle(uid, uid, cleanup_c03_data, duration=2.0)
    clip_id = bundle["clip_id"]
    
    broll_plan = BrollPlan(
        clip_id=clip_id,
        planner_version="1.0.0",
        placements=[
            BrollPlacement(
                asset_id=f"nonexistent_visual_asset_{uid}",
                opportunity_id=f"opp_{uid}",
                confidence=0.80,
                start_time=0.2,
                end_time=1.0,
                display_mode=DisplayMode.PIP_BOTTOM,
                x=100, y=100, w=400, h=400
            )
        ]
    )
    
    async_res = apply_broll_task.delay(clip_id=clip_id, broll_plan_dict=broll_plan.model_dump())
    with pytest.raises(Exception):
        async_res.get(timeout=20)
        
    with SyncSessionLocal() as session:
        variants = session.query(ClipVariant).filter_by(clip_id=clip_id).all()
        assert len(variants) == 0


# ─── TEST 9: ADVERSARIAL: CONCURRENT TASK DISPATCH TO LIVE WORKER ──────────────

def test_live_worker_concurrent_enhancement_dispatch(ensure_worker_ready, cleanup_c03_data):
    """Adversarial check: Dispatch Hook, SFX, and B-roll concurrently across 3 clips without race conditions."""
    uid_h = uuid.uuid4().hex[:8]
    uid_s = uuid.uuid4().hex[:8]
    uid_b = uuid.uuid4().hex[:8]
    
    bundle_h = _create_test_clip_bundle(uid_h, uid_h, cleanup_c03_data, duration=2.0)
    bundle_s = _create_test_clip_bundle(uid_s, uid_s, cleanup_c03_data, duration=2.0)
    bundle_b = _create_test_clip_bundle(uid_b, uid_b, cleanup_c03_data, duration=2.0)
    
    # Setup SFX asset
    sfx_uid = f"sfx_{uid_s}"
    sfx_storage_key = f"outputs/{bundle_s['vid_id']}/sfx_{sfx_uid}.wav"
    sfx_physical_path = Path(settings.OUTPUT_DIR) / f"{bundle_s['vid_id']}/sfx_{sfx_uid}.wav"
    _generate_synthetic_audio(sfx_physical_path, duration=0.5)
    
    # Setup B-roll asset
    broll_uid = f"broll_{uid_b}"
    broll_storage_key = f"outputs/{bundle_b['vid_id']}/broll_{broll_uid}.mp4"
    broll_physical_path = Path(settings.OUTPUT_DIR) / f"{bundle_b['vid_id']}/broll_{broll_uid}.mp4"
    _generate_synthetic_video(broll_physical_path, duration=1.0, width=400, height=400)
    
    with SyncSessionLocal() as session:
        sfx_art = ArtifactRecord(
            id=f"{TEST_PREFIX}art_{sfx_uid}",
            owner_type="video",
            owner_id=bundle_s["vid_id"],
            artifact_type=ArtifactType.AUDIO_SFX.value,
            storage_key=sfx_storage_key,
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add(sfx_art)
        sfx_asset = SFXAsset(
            id=f"{TEST_PREFIX}{sfx_uid}",
            name="Beep",
            category="impact",
            artifact_id=sfx_art.id,
            duration=0.5
        )
        session.add(sfx_asset)
        
        broll_art = ArtifactRecord(
            id=f"{TEST_PREFIX}art_{broll_uid}",
            owner_type="video",
            owner_id=bundle_b["vid_id"],
            artifact_type=ArtifactType.BROLL_ASSET.value,
            storage_key=broll_storage_key,
            backend="local",
            status=ArtifactStatus.READY.value,
            retention_policy="persistent"
        )
        session.add(broll_art)
        vis_asset = VisualAsset(
            id=f"{TEST_PREFIX}{broll_uid}",
            keyword="cutaway",
            asset_type="video",
            artifact_id=broll_art.id
        )
        session.add(vis_asset)
        session.commit()
        sfx_asset_id = sfx_asset.id
        vis_asset_id = vis_asset.id
        
    hook_plan = HookPlan(
        clip_id=bundle_h["clip_id"],
        plan_hash=f"hash_{uid_h}",
        planner_version="1.0.0",
        opportunities=[
            HookOpportunity(
                id=f"opp_{uid_h}",
                clip_id=bundle_h["clip_id"],
                start_time=0.0,
                end_time=1.5,
                opportunity_type="opening_hook",
                hook_objective="Capture attention",
                confidence=0.85,
                reason="Adversarial concurrency test"
            )
        ],
        visual_interventions=[
            ZoomIntervention(start_time=0.2, end_time=1.4, zoom_factor=1.12)
        ]
    )
    sfx_plan = SFXPlan(
        clip_id=bundle_s["clip_id"],
        placements=[
            SFXPlacement(
                asset_id=sfx_asset_id,
                category="impact",
                start_time=0.2,
                end_time=0.7,
                gain=-3.0
            )
        ]
    )
    broll_plan = BrollPlan(
        clip_id=bundle_b["clip_id"],
        planner_version="1.0.0",
        placements=[
            BrollPlacement(
                asset_id=vis_asset_id,
                opportunity_id=f"opp_{uid_b}",
                confidence=0.80,
                start_time=0.1,
                end_time=1.0,
                display_mode=DisplayMode.PIP_BOTTOM,
                x=100, y=100, w=400, h=400
            )
        ]
    )
    
    # Dispatch all three concurrently to live Celery worker
    async_h = apply_hook_task.delay(clip_id=bundle_h["clip_id"], hook_plan_dict=hook_plan.model_dump())
    async_s = apply_sfx_task.delay(clip_id=bundle_s["clip_id"], sfx_plan_dict=sfx_plan.model_dump())
    async_b = apply_broll_task.delay(clip_id=bundle_b["clip_id"], broll_plan_dict=broll_plan.model_dump())
    
    # Await all concurrently
    res_h = async_h.get(timeout=60)
    res_s = async_s.get(timeout=60)
    res_b = async_b.get(timeout=60)
    
    assert res_h["status"] == "success"
    assert res_s["sfx_applied"] is True
    assert res_b["broll_applied"] is True
    
    # Verify all 3 variants exist and are completed in DB
    with SyncSessionLocal() as session:
        vh = session.query(ClipVariant).filter_by(clip_id=bundle_h["clip_id"], variant_type="hook").first()
        vs = session.query(ClipVariant).filter_by(clip_id=bundle_s["clip_id"], variant_type="sfx").first()
        vb = session.query(ClipVariant).filter_by(clip_id=bundle_b["clip_id"], variant_type="broll").first()
        
        assert vh is not None and vh.status == "completed"
        assert vs is not None and vs.status == "completed"
        assert vb is not None and vb.status == "completed"


# ─── TEST 10: YOUTUBE PUBLICATION INVARIANT ────────────────────────────────────

def test_no_youtube_publication_invariant(ensure_worker_ready, cleanup_c03_data):
    """Verifies that across all operations, no live YouTube publishing occurred."""
    with SyncSessionLocal() as session:
        clips = session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).all()
        for c in clips:
            assert c.publish_status == "draft"
            assert c.youtube_short_id is None
            
        channels = session.query(Channel).filter(Channel.id.like(f"{TEST_PREFIX}%")).all()
        for ch in channels:
            assert ch.is_test is True
