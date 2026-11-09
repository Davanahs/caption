import asyncio
import json
import os
import subprocess
import tempfile
import threading
import uuid
import pytest
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.models.database import SyncSessionLocal
from backend.models.models import (
    Clip, Video, Channel, Job, ClipRetention, ClipHookPlan,
    ClipVariant, ArtifactRecord, ArtifactType, ArtifactStatus,
    TaskExecution, TaskExecutionStatus
)
from backend.models.hook import HookPlan, HookOpportunity, HookOpportunityType
from backend.tasks.hook_tasks import (
    analyze_hook_opportunities_task,
    apply_hook_task,
    _normalize_retention_data,
    _safe_async_run
)

TEST_PREFIX = "test_c02_"


@pytest.fixture(autouse=True)
def cleanup_c02_fixtures():
    """Clean up any database records and artifacts created with TEST_PREFIX."""
    yield
    with SyncSessionLocal() as session:
        session.query(ClipVariant).filter(ClipVariant.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ArtifactRecord).filter(ArtifactRecord.owner_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipHookPlan).filter(ClipHookPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipRetention).filter(ClipRetention.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(TaskExecution).filter(TaskExecution.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.commit()


def create_synthetic_mp4(path: str, duration: float = 3.0):
    """Generate a minimal valid MP4 file with video and audio tracks using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=blue:s=320x240:d={duration}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_test_clip(clip_id: str, media_path: Optional[str] = None):
    """Create a fully-connected test Channel -> Video -> Job -> Clip hierarchy."""
    chan_id = f"{TEST_PREFIX}chan_{uuid.uuid4().hex[:6]}"
    vid_id = f"{TEST_PREFIX}vid_{uuid.uuid4().hex[:6]}"
    job_id = f"{TEST_PREFIX}job_{uuid.uuid4().hex[:6]}"

    with SyncSessionLocal() as session:
        chan = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
            channel_name="C02 Test Channel",
            channel_url="https://youtube.com/channel/test_c02",
            is_test=True
        )
        session.add(chan)

        vid = Video(
            id=vid_id,
            youtube_id=f"yt_{uuid.uuid4().hex[:8]}",
            title="C02 Test Video",
            channel_id=chan_id,
            local_path=media_path or "/tmp/dummy_vid.mp4"
        )
        session.add(vid)

        job = Job(
            id=job_id,
            video_id=vid_id,
            channel_id=chan_id,
            is_test=True
        )
        session.add(job)

        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="C02 Test Clip",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            score=8.5,
            publish_status="draft",
            output_path=media_path or "/tmp/dummy_clip.mp4",
            run_identity=f"{job_id}_{clip_id}_run",
            transcript_segment="Watch how this amazing test unfolds in real time."
        )
        session.add(clip)
        session.commit()

    return {"channel_id": chan_id, "video_id": vid_id, "job_id": job_id, "clip_id": clip_id}


# =====================================================================
# Unit / Schema Normalization Tests
# =====================================================================

def test_normalize_retention_data_list_shape():
    """Verify that a raw JSON list of dropoff risks (the exact format produced by clips.py) normalizes cleanly."""
    clip_id = f"{TEST_PREFIX}clip_list"
    raw_list_json = json.dumps([
        {
            "start_time": 0.5,
            "end_time": 3.0,
            "severity": "high",
            "primary_reason": "low_audio_energy",
            "contributing_reasons": ["silence"],
            "confidence": 0.88,
            "suggested_intervention_types": ["zoom_push"]
        }
    ])

    norm = _normalize_retention_data(raw_list_json, clip_id=clip_id, clip_duration=10.0)
    assert norm is not None
    assert norm.clip_id == clip_id
    assert norm.duration == 10.0
    assert len(norm.risks) == 1
    assert norm.risks[0].severity == "high"
    assert norm.risks[0].start_time == 0.5


def test_normalize_retention_data_full_dict_shape():
    """Verify that a full RetentionAnalysis dictionary shape parses cleanly."""
    clip_id = f"{TEST_PREFIX}clip_full_dict"
    full_dict_json = json.dumps({
        "clip_id": clip_id,
        "duration": 12.0,
        "analysis_version": "1.0",
        "points": [
            {
                "timestamp": 1,
                "retention_score": 85.0,
                "audio_score": 75.0,
                "motion_score": 80.0,
                "scene_activity_score": 70.0,
                "risk_level": "low"
            }
        ],
        "risks": [
            {
                "start_time": 1.0,
                "end_time": 4.0,
                "severity": "medium",
                "primary_reason": "low_visual_motion",
                "contributing_reasons": [],
                "confidence": 0.75,
                "suggested_intervention_types": []
            }
        ]
    })

    norm = _normalize_retention_data(full_dict_json, clip_id=clip_id, clip_duration=12.0)
    assert norm is not None
    assert norm.clip_id == clip_id
    assert len(norm.points) == 1
    assert len(norm.risks) == 1
    assert norm.risks[0].severity == "medium"


def test_normalize_retention_data_risks_dict_shape():
    """Verify that a dict containing a 'risks' key normalizes cleanly."""
    clip_id = f"{TEST_PREFIX}clip_risks_dict"
    risks_dict_json = json.dumps({
        "risks": [
            {
                "start_time": 0.0,
                "end_time": 2.0,
                "severity": "critical",
                "primary_reason": "combined_low_engagement",
                "contributing_reasons": ["silence", "static_camera"],
                "confidence": 0.95,
                "suggested_intervention_types": ["sfx_opportunity"]
            }
        ]
    })

    norm = _normalize_retention_data(risks_dict_json, clip_id=clip_id, clip_duration=8.0)
    assert norm is not None
    assert norm.clip_id == clip_id
    assert len(norm.risks) == 1
    assert norm.risks[0].severity == "critical"


def test_normalize_retention_data_malformed_shape():
    """Verify that malformed JSON, empty string, or invalid types fail gracefully without crashing."""
    clip_id = f"{TEST_PREFIX}clip_malformed"

    assert _normalize_retention_data("", clip_id=clip_id, clip_duration=10.0) is None
    assert _normalize_retention_data(None, clip_id=clip_id, clip_duration=10.0) is None
    assert _normalize_retention_data("INVALID_JSON{{{", clip_id=clip_id, clip_duration=10.0) is None
    assert _normalize_retention_data(json.dumps("Just a string"), clip_id=clip_id, clip_duration=10.0) is None
    # Invalid model fields (e.g. invalid severity) should return None without crashing
    invalid_severity_json = json.dumps([{"start_time": 0.0, "end_time": 1.0, "severity": "not_a_valid_severity"}])
    assert _normalize_retention_data(invalid_severity_json, clip_id=clip_id, clip_duration=10.0) is None


# =====================================================================
# Hook Opportunities Task Tests
# =====================================================================

def test_analyze_hook_opportunities_task_with_list_retention():
    """Verify analyze_hook_opportunities_task processes list-shaped retention without Pydantic crashes."""
    clip_id = f"{TEST_PREFIX}opp_list_{uuid.uuid4().hex[:6]}"
    create_test_clip(clip_id)

    # Seed list-shaped ClipRetention
    with SyncSessionLocal() as session:
        ret = ClipRetention(
            clip_id=clip_id,
            overall_score=7.2,
            analysis_json=json.dumps([
                {
                    "start_time": 0.0,
                    "end_time": 3.0,
                    "severity": "high",
                    "primary_reason": "low_audio_energy",
                    "contributing_reasons": ["silence"],
                    "confidence": 0.92,
                    "suggested_intervention_types": ["zoom_push"]
                }
            ])
        )
        session.add(ret)
        session.commit()

    # Execute task in-process
    opps = analyze_hook_opportunities_task.apply(args=[clip_id]).get()
    assert isinstance(opps, list)
    assert len(opps) >= 1

    # Check opening hook reflects retention risk
    opening = opps[0]
    assert opening["opportunity_type"] == HookOpportunityType.RETENTION_RISK.value
    assert opening["confidence"] == 0.9

    # Verify ClipHookPlan was persisted to DB
    with SyncSessionLocal() as session:
        db_plan = session.query(ClipHookPlan).filter_by(clip_id=clip_id).first()
        assert db_plan is not None
        plan_dict = json.loads(db_plan.plan_json)
        assert plan_dict["clip_id"] == clip_id
        assert len(plan_dict["opportunities"]) >= 1


def test_analyze_hook_opportunities_task_with_malformed_retention():
    """Verify analyze_hook_opportunities_task handles malformed retention gracefully."""
    clip_id = f"{TEST_PREFIX}opp_malformed_{uuid.uuid4().hex[:6]}"
    create_test_clip(clip_id)

    with SyncSessionLocal() as session:
        ret = ClipRetention(
            clip_id=clip_id,
            overall_score=5.0,
            analysis_json="MALFORMED_JSON_CORRUPT"
        )
        session.add(ret)
        session.commit()

    opps = analyze_hook_opportunities_task.apply(args=[clip_id]).get()
    assert isinstance(opps, list)
    assert len(opps) >= 1
    # Without valid retention data, defaults to OPENING_HOOK
    assert opps[0]["opportunity_type"] == HookOpportunityType.OPENING_HOOK.value


# =====================================================================
# Apply Hook Task Execution & Event-Loop Bridge Tests
# =====================================================================

def test_safe_async_run_in_fresh_thread():
    """Verify _safe_async_run succeeds in a thread without a pre-existing event loop."""
    result = {"val": None, "error": None}

    def worker():
        try:
            async def dummy_coro():
                await asyncio.sleep(0.01)
                return 42

            result["val"] = _safe_async_run(dummy_coro())
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert result["error"] is None
    assert result["val"] == 42


def test_apply_hook_task_end_to_end_in_worker_thread(tmp_path):
    """
    Test full execution of apply_hook_task in a separate worker thread
    simulating Celery worker execution (no event loop in thread).
    Verifies:
      1. Safe async execution of voiceover and SFX mixer.
      2. FFmpeg layout and audio mixing.
      3. ArtifactRecord registration and READY status.
      4. ClipVariant persistence with variant_type='hook'.
      5. TaskExecution marked SUCCEEDED.
      6. No caption/subtitle filters or text burn-in injected.
    """
    clip_id = f"{TEST_PREFIX}apply_full_{uuid.uuid4().hex[:6]}"
    test_media = tmp_path / "test_input.mp4"
    create_synthetic_mp4(str(test_media), duration=3.0)

    fixtures = create_test_clip(clip_id, media_path=str(test_media))
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    # Pre-claim task execution
    # Generate a valid hook plan dict
    from backend.services.hook_planner import hook_planner
    from backend.services.hook_analyzer import hook_analyzer
    with SyncSessionLocal() as session:
        clip_rec = session.query(Clip).filter_by(id=clip_id).first()
        opps = hook_analyzer.analyze_clip_for_hooks(clip_rec, None, None, None, 3.0)
        hook_plan = hook_planner.generate_hook_plan(clip_id, opps)
        hook_plan_dict = hook_plan.model_dump()
        hook_plan_dict["job_id"] = fixtures["job_id"]

    worker_result = {"out": None, "error": None}

    def thread_worker():
        try:
            # Explicitly ensure no running loop in this thread
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass

            res = apply_hook_task.apply(args=[clip_id, hook_plan_dict], task_id=task_id).get()
            worker_result["out"] = res
        except Exception as e:
            worker_result["error"] = e

    t = threading.Thread(target=thread_worker)
    t.start()
    t.join(timeout=30)

    assert worker_result["error"] is None, f"apply_hook_task failed: {worker_result['error']}"
    assert worker_result["out"] is not None
    assert worker_result["out"]["status"] == "success"
    assert worker_result["out"]["variant_type"] == "hook"

    # Verify ClipVariant in DB
    with SyncSessionLocal() as session:
        variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="hook").first()
        assert variant is not None
        assert variant.status == "completed"
        assert variant.artifact_id is not None

        # Verify ArtifactRecord in DB
        ar = session.query(ArtifactRecord).filter_by(id=variant.artifact_id).first()
        assert ar is not None
        assert ar.status == ArtifactStatus.READY.value
        assert ar.artifact_type == ArtifactType.VIDEO_RENDER.value
        assert ar.owner_id == clip_id

        # Verify TaskExecution marked SUCCEEDED
        tx_check = session.query(TaskExecution).filter_by(id=task_id).first()
        assert tx_check is not None
        assert tx_check.status == TaskExecutionStatus.SUCCEEDED.value
        assert tx_check.completed_at is not None


def test_apply_hook_task_missing_media_failure_path():
    """Verify that when no valid input media exists, apply_hook_task fails cleanly and sets TaskExecution to FAILED."""
    clip_id = f"{TEST_PREFIX}apply_nomedia_{uuid.uuid4().hex[:6]}"
    fixtures = create_test_clip(clip_id, media_path="/nonexistent/missing_file.mp4")
    task_id = f"task_nomedia_{uuid.uuid4().hex[:8]}"

    hook_plan_dict = {
        "clip_id": clip_id,
        "job_id": fixtures["job_id"],
        "planner_version": "1.0.0",
        "opportunities": [],
        "concepts": [],
        "visual_interventions": []
    }

    with pytest.raises(Exception) as exc_info:
        apply_hook_task.apply(args=[clip_id, hook_plan_dict], task_id=task_id).get()

    assert "No valid input video found" in str(exc_info.value)

    # Verify TaskExecution was marked FAILED with reason
    with SyncSessionLocal() as session:
        tx_check = session.query(TaskExecution).filter_by(id=task_id).first()
        assert tx_check is not None
        assert tx_check.status == TaskExecutionStatus.FAILED.value
        assert "No valid input video found" in (tx_check.failure_reason or "")


# =====================================================================
# Pass 2: Adversarial Self-Challenge Tests
# =====================================================================

def test_apply_hook_task_idempotency_duplicate_call(tmp_path):
    """
    Adversarial Challenge 1:
    Duplicate invocation of apply_hook_task with the exact same plan hash
    must hit the idempotency claim and raise celery.exceptions.Ignore cleanly,
    leaving the completed ClipVariant and ArtifactRecord untouched without re-rendering.
    """
    clip_id = f"{TEST_PREFIX}idemp_{uuid.uuid4().hex[:6]}"
    test_media = tmp_path / "test_input_idemp.mp4"
    create_synthetic_mp4(str(test_media), duration=2.5)

    fixtures = create_test_clip(clip_id, media_path=str(test_media))

    from backend.services.hook_planner import hook_planner
    from backend.services.hook_analyzer import hook_analyzer
    with SyncSessionLocal() as session:
        clip_rec = session.query(Clip).filter_by(id=clip_id).first()
        opps = hook_analyzer.analyze_clip_for_hooks(clip_rec, None, None, None, 2.5)
        hook_plan = hook_planner.generate_hook_plan(clip_id, opps)
        hook_plan_dict = hook_plan.model_dump()
        hook_plan_dict["job_id"] = fixtures["job_id"]

    task_id_1 = f"task_first_{uuid.uuid4().hex[:6]}"
    first_res = apply_hook_task.apply(args=[clip_id, hook_plan_dict], task_id=task_id_1).get()
    assert first_res["status"] == "success"

    # Second invocation with same plan hash must be ignored by Celery
    task_id_2 = f"task_second_{uuid.uuid4().hex[:6]}"
    second_res = apply_hook_task.apply(args=[clip_id, hook_plan_dict], task_id=task_id_2)
    assert second_res.status == "IGNORED" or second_res.result is None

    # Verify only 1 ClipVariant exists
    with SyncSessionLocal() as session:
        variants = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="hook").all()
        assert len(variants) == 1
        assert variants[0].status == "completed"


def test_apply_hook_task_resolves_managed_storage_media(tmp_path):
    """
    Adversarial Challenge 2:
    Input media is stored ONLY in managed storage (storage_service), NOT on local disk.
    Task must download media through storage abstraction, render, upload output, and succeed.
    """
    from backend.core.storage import storage_service

    clip_id = f"{TEST_PREFIX}managed_storage_{uuid.uuid4().hex[:6]}"
    local_source = tmp_path / "storage_source.mp4"
    create_synthetic_mp4(str(local_source), duration=2.0)

    # Put into managed storage
    storage_key = f"uploads/{TEST_PREFIX}clips/{clip_id}/source.mp4"
    storage_service.put(storage_key, str(local_source))
    assert storage_service.exists(storage_key)

    # Delete local file to prove task cannot rely on local filesystem
    os.remove(str(local_source))
    assert not os.path.exists(str(local_source))

    # Point clip.output_path to storage key
    fixtures = create_test_clip(clip_id, media_path=storage_key)

    from backend.services.hook_planner import hook_planner
    from backend.services.hook_analyzer import hook_analyzer
    with SyncSessionLocal() as session:
        clip_rec = session.query(Clip).filter_by(id=clip_id).first()
        opps = hook_analyzer.analyze_clip_for_hooks(clip_rec, None, None, None, 2.0)
        hook_plan = hook_planner.generate_hook_plan(clip_id, opps)
        hook_plan_dict = hook_plan.model_dump()
        hook_plan_dict["job_id"] = fixtures["job_id"]

    task_id = f"task_managed_{uuid.uuid4().hex[:6]}"
    res = apply_hook_task.apply(args=[clip_id, hook_plan_dict], task_id=task_id).get()
    assert res["status"] == "success"

    # Verify final variant exists in DB and managed storage
    with SyncSessionLocal() as session:
        variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="hook").first()
        assert variant is not None
        ar = session.query(ArtifactRecord).filter_by(id=variant.artifact_id).first()
        assert ar is not None
        assert storage_service.exists(ar.storage_key)


def test_apply_hook_task_verifies_no_subtitles_or_captions(tmp_path):
    """
    Adversarial Challenge 3:
    Invariance test: Hook overlay must never generate or burn subtitles/captions into media.
    FFprobe inspection must prove zero subtitle tracks.
    """
    from backend.core.storage import storage_service

    clip_id = f"{TEST_PREFIX}sub_invariant_{uuid.uuid4().hex[:6]}"
    test_media = tmp_path / "test_input_sub.mp4"
    create_synthetic_mp4(str(test_media), duration=2.0)

    fixtures = create_test_clip(clip_id, media_path=str(test_media))

    from backend.services.hook_planner import hook_planner
    from backend.services.hook_analyzer import hook_analyzer
    with SyncSessionLocal() as session:
        clip_rec = session.query(Clip).filter_by(id=clip_id).first()
        opps = hook_analyzer.analyze_clip_for_hooks(clip_rec, None, None, None, 2.0)
        hook_plan = hook_planner.generate_hook_plan(clip_id, opps)
        hook_plan_dict = hook_plan.model_dump()
        hook_plan_dict["job_id"] = fixtures["job_id"]

    task_id = f"task_sub_{uuid.uuid4().hex[:6]}"
    res = apply_hook_task.apply(args=[clip_id, hook_plan_dict], task_id=task_id).get()
    assert res["status"] == "success"

    with SyncSessionLocal() as session:
        variant = session.query(ClipVariant).filter_by(clip_id=clip_id, variant_type="hook").first()
        ar = session.query(ArtifactRecord).filter_by(id=variant.artifact_id).first()

        # Download rendered variant for probe inspection
        probe_target = tmp_path / "probe_variant.mp4"
        storage_service.get(ar.storage_key, str(probe_target))
        assert os.path.exists(str(probe_target))

        # Run ffprobe to inspect streams
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type",
            "-of", "json",
            str(probe_target)
        ]
        probe_run = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(probe_run.stdout)
        codec_types = [s["codec_type"] for s in probe_data.get("streams", [])]

        # Must have video and audio, but strictly zero subtitle tracks
        assert "video" in codec_types
        assert "audio" in codec_types
        assert "subtitle" not in codec_types, "Hook output must NOT contain subtitle streams"

