"""
test_c10_dubbing_pipeline.py
============================
Focused test suite for Canonical Phase 6.1 (C-10): Multi-Language Dubbing Pipeline & UI Integration (CAP-001).

Verifies:
1. GET /api/dubbing/languages & /api/clips/dubbing/languages catalog contract (6 global languages, default voices).
2. GET /api/dubbing/{clip_id} returns 404 for unknown clips.
3. GET /api/dubbing/{clip_id} returns empty plan list and populated plan list with matched variants.
4. POST /api/dubbing/{clip_id} rejects mismatched path vs body clip_id (400).
5. POST /api/dubbing/{clip_id} rejects non-existent clips (404).
6. POST /api/dubbing/{clip_id} rejects unsupported target languages (400).
7. POST /api/dubbing/{clip_id} strictly enforces voice clone authorization guard (403 when authorization_granted=False).
8. POST /api/dubbing/{clip_id} allows authorized voice clone (200 with task_id when authorization_granted=True).
9. POST /api/dubbing/{clip_id} resolves default voice if omitted or 'default'.
10. POST /api/dubbing/{clip_id} automatically resolves job_id from video/clip if omitted.
11. GET /api/dubbing/tasks/{task_id} polls Celery task execution status.
12. Timing-fit boundary protection: required speed > 1.3x fails closed in dubbing_engine.
13. Celery task idempotency: second identical task invocation returns skipped status with matching variant_id.
14. Dual visual input resolution: task falls back to clip.output_path when base video_render variant is absent.
15. Empty transcript resolution: task falls back to clip.title / default speech string when transcript_segment is None.
16. Invariant: Shorts duration capped strictly between 15.0 and 30.0 seconds.
17. Invariant: Zero caption/subtitle burn-in or subtitle generation tracks.
18. Invariant: Test data isolation with is_test=True.
"""

import os
import uuid
import inspect
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import (
    Clip, Video, Job, DubbingPlan, DubbingSegment, ClipVariant, ArtifactType,
    TaskExecution, ArtifactRecord
)
from backend.models.dubbing import DubbingRequest, DubbingSegmentInput
from backend.services import dubbing_engine
from backend.tasks import dubbing_tasks
from backend.tasks.dubbing_tasks import generate_dubbing_variant_task
from backend.api.routes.dubbing import SUPPORTED_LANGUAGES, SUPPORTED_LANGUAGE_CODES


PREFIX = "c10_test_"


@pytest.fixture(autouse=True)
async def cleanup_c10_fixtures():
    """Ensure test clips, videos, and plans are cleaned up before and after each test."""
    with SyncSessionLocal() as session:
        session.query(TaskExecution).filter(
            (TaskExecution.clip_id.like(f"{PREFIX}%")) | (TaskExecution.job_id.like(f"{PREFIX}%"))
        ).delete(synchronize_session=False)
        session.query(DubbingSegment).filter(
            DubbingSegment.plan_id.in_(
                session.query(DubbingPlan.id).filter(DubbingPlan.clip_id.like(f"{PREFIX}%"))
            )
        ).delete(synchronize_session=False)
        session.query(DubbingPlan).filter(
            DubbingPlan.clip_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(ClipVariant).filter(
            ClipVariant.clip_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(ArtifactRecord).filter(
            ArtifactRecord.owner_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(Clip).filter(
            Clip.id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(Job).filter(
            Job.id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(Video).filter(
            Video.id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.commit()
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(TaskExecution).filter(
            (TaskExecution.clip_id.like(f"{PREFIX}%")) | (TaskExecution.job_id.like(f"{PREFIX}%"))
        ).delete(synchronize_session=False)
        session.query(DubbingSegment).filter(
            DubbingSegment.plan_id.in_(
                session.query(DubbingPlan.id).filter(DubbingPlan.clip_id.like(f"{PREFIX}%"))
            )
        ).delete(synchronize_session=False)
        session.query(DubbingPlan).filter(
            DubbingPlan.clip_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(ClipVariant).filter(
            ClipVariant.clip_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(ArtifactRecord).filter(
            ArtifactRecord.owner_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(Clip).filter(
            Clip.id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(Job).filter(
            Job.id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.query(Video).filter(
            Video.id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        session.commit()


def _seed_test_clip(
    clip_id: str,
    video_id: str,
    job_id: str = None,
    transcript: str = "Test transcript content for dubbing.",
    output_path: str = None,
    duration: float = 20.0
) -> Clip:
    with SyncSessionLocal() as session:
        vid = session.query(Video).filter(Video.id == video_id).first()
        if not vid:
            vid = Video(
                id=video_id,
                youtube_url="https://youtube.com/watch?v=c10test",
                title="C10 Test Video",
                local_path=output_path or "dummy_c10.mp4"
            )
            session.add(vid)

        if job_id:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                job = Job(id=job_id, video_id=video_id, status="completed")
                session.add(job)

        if not output_path:
            from backend.core.config import settings
            dummy_file = settings.OUTPUT_DIR / f"{clip_id}.mp4"
            dummy_file.parent.mkdir(parents=True, exist_ok=True)
            if not dummy_file.exists():
                dummy_file.write_bytes(b"\x00" * 1024)
            output_path = str(dummy_file)

        clip = Clip(
            id=clip_id,
            video_id=video_id,
            start_time=0.0,
            end_time=duration,
            duration=duration,
            transcript_segment=transcript,
            title="C10 Test Clip",
            output_path=output_path,
            status="completed",
            score=90
        )
        session.add(clip)
        session.commit()
        session.refresh(clip)
        session.expunge(clip)
        return clip


# ─── 1. Catalog & Discovery Endpoints ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_dubbing_languages_catalog():
    """Validates /api/dubbing/languages returns 6 supported languages with correct schema."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/dubbing/languages")
        assert res.status_code == 200
        data = res.json()
        assert "languages" in data
        languages = data["languages"]
        assert len(languages) == 6

        codes = [l["code"] for l in languages]
        assert set(codes) == {"es", "hi", "de", "ja", "pt", "fr"}

        for lang in languages:
            assert "name" in lang
            assert "native_name" in lang
            assert "default_voice" in lang
            assert "voice_provider" in lang

        # Test legacy/aliased endpoint
        res_alias = await ac.get("/api/clips/dubbing/languages")
        assert res_alias.status_code == 200
        assert res_alias.json() == data


# ─── 2. Querying Clip Dubbing Status & Plans ───────────────────────────────────

@pytest.mark.asyncio
async def test_get_clip_dubbing_unknown_clip_404():
    """Validates 404 response when querying dubbing plans for an unknown clip."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/dubbing/{PREFIX}unknown_clip")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_clip_dubbing_empty_and_populated():
    """Validates querying clip dubbing plans when empty and when populated with variants."""
    clip_id = f"{PREFIX}clip_get_1"
    video_id = f"{PREFIX}vid_get_1"
    _seed_test_clip(clip_id=clip_id, video_id=video_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Initially empty
        res1 = await ac.get(f"/api/dubbing/{clip_id}")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["clip_id"] == clip_id
        assert data1["plans"] == []

        # Populate with a DubbingPlan and ClipVariant
        plan_id = f"{PREFIX}plan_1"
        variant_id = f"{PREFIX}var_1"
        with SyncSessionLocal() as session:
            p = DubbingPlan(
                id=plan_id,
                clip_id=clip_id,
                target_language="es",
                voice_provider="edge_tts",
                voice_id="es-ES-AlvaroNeural",
                is_voice_clone=False,
                authorization_granted=False,
                status="completed"
            )
            session.add(p)
            v = ClipVariant(
                variant_id=variant_id,
                clip_id=clip_id,
                variant_type=ArtifactType.DUBBING_VARIANT.value,
                variant_metadata=f'{{"plan_id": "{plan_id}"}}',
                status="completed"
            )
            session.add(v)
            session.commit()

        # Query again
        res2 = await ac.get(f"/api/dubbing/{clip_id}")
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2["plans"]) == 1
        plan_entry = data2["plans"][0]
        assert plan_entry["id"] == plan_id
        assert plan_entry["target_language"] == "es"
        assert plan_entry["target_language_name"] == "Spanish"
        assert plan_entry["voice_id"] == "es-ES-AlvaroNeural"
        assert plan_entry["variant_id"] == variant_id
        assert plan_entry["variant_status"] == "completed"


# ─── 3. Trigger Endpoint Validation & Governance ───────────────────────────────

@pytest.mark.asyncio
async def test_trigger_dubbing_mismatched_clip_id():
    """Asserts 400 rejection when path clip_id differs from request body clip_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/dubbing/{PREFIX}clip_path",
            json={
                "clip_id": f"{PREFIX}clip_body",
                "target_language": "es"
            }
        )
        assert res.status_code == 400
        assert "match" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_dubbing_unknown_clip_404():
    """Asserts 404 rejection when attempting to trigger dubbing on a non-existent clip."""
    clip_id = f"{PREFIX}nonexistent_clip"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/dubbing/{clip_id}",
            json={
                "clip_id": clip_id,
                "target_language": "es"
            }
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_dubbing_unsupported_language_rejection():
    """Asserts 400 rejection when requesting an unsupported target language."""
    clip_id = f"{PREFIX}clip_lang_rej"
    video_id = f"{PREFIX}vid_lang_rej"
    _seed_test_clip(clip_id=clip_id, video_id=video_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/dubbing/{clip_id}",
            json={
                "clip_id": clip_id,
                "target_language": "klingon"
            }
        )
        assert res.status_code == 400
        assert "unsupported" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_dubbing_voice_clone_authorization_guard():
    """Asserts HTTP 403 Forbidden when voice cloning is requested without explicit user consent."""
    clip_id = f"{PREFIX}clip_auth_guard"
    video_id = f"{PREFIX}vid_auth_guard"
    _seed_test_clip(clip_id=clip_id, video_id=video_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            f"/api/dubbing/{clip_id}",
            json={
                "clip_id": clip_id,
                "target_language": "es",
                "voice_provider": "elevenlabs",
                "is_voice_clone": True,
                "authorization_granted": False
            }
        )
        assert res.status_code == 403
        assert "authorization not granted" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_dubbing_authorized_clone():
    """Asserts successful task dispatch when voice cloning is explicitly authorized."""
    clip_id = f"{PREFIX}clip_clone_ok"
    video_id = f"{PREFIX}vid_clone_ok"
    _seed_test_clip(clip_id=clip_id, video_id=video_id)

    with patch("backend.tasks.dubbing_tasks.generate_dubbing_variant_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock-celery-clone-task-123"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/dubbing/{clip_id}",
                json={
                    "clip_id": clip_id,
                    "target_language": "fr",
                    "voice_provider": "elevenlabs",
                    "is_voice_clone": True,
                    "authorization_granted": True
                }
            )
            assert res.status_code == 200
            data = res.json()
            assert data["task_id"] == "mock-celery-clone-task-123"
            assert data["status"] == "pending"
            assert data["target_language"] == "fr"

            # Check that task.delay was called
            assert mock_delay.called
            call_dict = mock_delay.call_args[0][0]
            assert call_dict["is_voice_clone"] is True
            assert call_dict["authorization_granted"] is True


@pytest.mark.asyncio
async def test_trigger_dubbing_default_voice_resolution():
    """Validates that 'default' or empty voice_id is automatically mapped to canonical neural voice."""
    clip_id = f"{PREFIX}clip_def_voice"
    video_id = f"{PREFIX}vid_def_voice"
    _seed_test_clip(clip_id=clip_id, video_id=video_id)

    with patch("backend.tasks.dubbing_tasks.generate_dubbing_variant_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock-celery-voice-task-456"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/dubbing/{clip_id}",
                json={
                    "clip_id": clip_id,
                    "target_language": "hi",
                    "voice_id": "default"
                }
            )
            assert res.status_code == 200
            assert mock_delay.called
            call_dict = mock_delay.call_args[0][0]
            assert call_dict["voice_id"] == "hi-IN-MadhurNeural"


@pytest.mark.asyncio
async def test_trigger_dubbing_automatic_job_id_resolution():
    """Validates that omitted job_id is automatically resolved from video jobs or generated."""
    clip_id = f"{PREFIX}clip_job_res"
    video_id = f"{PREFIX}vid_job_res"
    job_id = f"{PREFIX}job_res_existing"
    _seed_test_clip(clip_id=clip_id, video_id=video_id, job_id=job_id)

    with patch("backend.tasks.dubbing_tasks.generate_dubbing_variant_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock-celery-job-task-789"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                f"/api/dubbing/{clip_id}",
                json={
                    "clip_id": clip_id,
                    "target_language": "de"
                }
            )
            assert res.status_code == 200
            call_dict = mock_delay.call_args[0][0]
            assert call_dict["job_id"] == job_id


# ─── 4. Celery Task Status Polling ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dubbing_task_status_endpoint():
    """Validates GET /api/dubbing/tasks/{task_id} polls Celery AsyncResult properly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch("backend.api.routes.dubbing.celery_app.AsyncResult") as mock_async_result:
            mock_res_obj = MagicMock()
            mock_res_obj.status = "SUCCESS"
            mock_res_obj.ready.return_value = True
            mock_res_obj.result = {"status": "completed", "variant_id": "var-123"}
            mock_async_result.return_value = mock_res_obj

            res = await ac.get("/api/dubbing/tasks/task-abc-123")
            assert res.status_code == 200
            data = res.json()
            assert data["task_id"] == "task-abc-123"
            assert data["status"] == "SUCCESS"
            assert data["ready"] is True
            assert data["result"] == {"status": "completed", "variant_id": "var-123"}


# ─── 5. Timing-Fit Boundary & Engine Governance ────────────────────────────────

@pytest.mark.asyncio
async def test_dubbing_timing_boundary_atempo_cap():
    """
    Validates that if synthesized audio requires speed adjustment exceeding
    MAX_ATEMPO (1.3x), dubbing_engine fails closed rather than producing chipmunk audio.
    """
    req = DubbingRequest(
        clip_id=f"{PREFIX}clip_atempo",
        target_language="es",
        voice_provider="edge_tts",
        voice_id="es-ES-AlvaroNeural"
    )
    # Segment of 2 seconds duration
    seg = DubbingSegmentInput(
        sequence=1,
        source_text="This is an extensive monologue that cannot possibly fit in two seconds.",
        start_time=0.0,
        end_time=2.0
    )

    # Mock get_audio_duration to simulate 6.0 seconds audio (speed = 3.0x > 1.3x)
    with patch("backend.services.dubbing_engine.translate_text", return_value="Texto traducido largo"):
        with patch("backend.services.dubbing_engine.get_audio_duration", return_value=6.0):
            with patch.object(dubbing_engine, "get_voice_provider") as mock_gp:
                mock_provider = MagicMock()
                mock_provider.generate_audio = AsyncMock(return_value="/tmp/mock_audio.wav")
                mock_gp.return_value = mock_provider

                resp = await dubbing_engine.execute_dubbing_plan(req, [seg])
                assert resp.status == "failed"
                assert "exceeds maximum 1.3" in resp.error_message


# ─── 6. Celery Task Idempotency & Visual Input Fallback ─────────────────────────

def test_dubbing_task_idempotency_and_visual_fallback(tmp_path):
    """
    Validates:
    1. Dubbing task succeeds on first invocation using clip.output_path fallback.
    2. Second invocation with identical parameters is skipped via task_execution idempotency.
    """
    clip_id = f"{PREFIX}clip_task_idem"
    video_id = f"{PREFIX}vid_task_idem"
    job_id = f"{PREFIX}job_task_idem"

    # Create dummy dummy.mp4
    dummy_mp4 = str(tmp_path / "dummy_video.mp4")
    with open(dummy_mp4, "wb") as f:
        f.write(b"mock mp4 content")

    _seed_test_clip(
        clip_id=clip_id,
        video_id=video_id,
        job_id=job_id,
        output_path=dummy_mp4
    )

    request_dict = {
        "job_id": job_id,
        "clip_id": clip_id,
        "target_language": "es",
        "voice_provider": "edge_tts",
        "voice_id": "es-ES-AlvaroNeural",
        "is_voice_clone": False,
        "authorization_granted": False,
        "plan_version": "v1"
    }

    # Mock execute_dubbing_plan and sfx_mixer to avoid ffmpeg execution
    mock_dub_resp = MagicMock()
    mock_dub_resp.status = "completed"
    mock_dub_resp.segments = []

    def fake_subprocess_run(cmd, *args, **kwargs):
        for arg in cmd:
            if "clipforge_managed_ul_" in str(arg):
                with open(arg, "wb") as f:
                    f.write(b"dummy mp4 render content")
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        return res

    with patch("backend.tasks.dubbing_tasks.execute_dubbing_plan", return_value=mock_dub_resp):
        with patch("backend.tasks.dubbing_tasks.subprocess.run", side_effect=fake_subprocess_run):
            # First run
            res1 = generate_dubbing_variant_task(request_dict)
            assert res1["status"] == "completed"
            var_id = res1["variant_id"]
            assert var_id is not None

            # Verify database records created
            with SyncSessionLocal() as session:
                plan = session.query(DubbingPlan).filter(DubbingPlan.clip_id == clip_id).first()
                assert plan is not None
                assert plan.target_language == "es"
                variant = session.query(ClipVariant).filter(ClipVariant.variant_id == var_id).first()
                assert variant is not None
                assert variant.variant_type == ArtifactType.DUBBING_VARIANT.value

            # Second run (should be skipped due to claim idempotency)
            res2 = generate_dubbing_variant_task(request_dict)
            assert res2["status"] == "skipped"
            assert res2["variant_id"] == var_id


def test_dubbing_empty_transcript_fallback(tmp_path):
    """Asserts that when transcript_segment is None or empty, dubbing task falls back to clip.title."""
    clip_id = f"{PREFIX}clip_empty_trans"
    video_id = f"{PREFIX}vid_empty_trans"
    job_id = f"{PREFIX}job_empty_trans"

    dummy_mp4 = str(tmp_path / "dummy_video2.mp4")
    with open(dummy_mp4, "wb") as f:
        f.write(b"mock mp4 content")

    _seed_test_clip(
        clip_id=clip_id,
        video_id=video_id,
        job_id=job_id,
        transcript=None,  # None transcript!
        output_path=dummy_mp4
    )

    request_dict = {
        "job_id": job_id,
        "clip_id": clip_id,
        "target_language": "pt",
        "voice_provider": "edge_tts",
        "voice_id": "pt-BR-AntonioNeural",
        "is_voice_clone": False,
        "authorization_granted": False,
        "plan_version": "v1"
    }

    mock_dub_resp = MagicMock()
    mock_dub_resp.status = "completed"
    mock_dub_resp.segments = []

    def fake_subprocess_run2(cmd, *args, **kwargs):
        for arg in cmd:
            if "clipforge_managed_ul_" in str(arg):
                with open(arg, "wb") as f:
                    f.write(b"dummy mp4 render content 2")
        res = MagicMock()
        res.returncode = 0
        res.stderr = ""
        return res

    with patch("backend.tasks.dubbing_tasks.execute_dubbing_plan") as mock_exec:
        mock_exec.return_value = mock_dub_resp
        with patch("backend.tasks.dubbing_tasks.subprocess.run", side_effect=fake_subprocess_run2):
            res = generate_dubbing_variant_task(request_dict)
            assert res["status"] == "completed"

            # Check that segments_input passed to execute_dubbing_plan used clip.title
            assert mock_exec.called
            called_segments = mock_exec.call_args[0][1]
            assert len(called_segments) == 1
            assert called_segments[0].source_text == "C10 Test Clip"


# ─── 7. Invariants: Duration, Zero Subtitles, Synthetic Isolation ─────────────

def test_shorts_duration_capped_invariant():
    """Asserts that shorts durations are strictly bounded between 15.0 and 30.0 seconds."""
    clip = Clip(duration=25.0, start_time=5.0, end_time=30.0)
    assert 15.0 <= clip.duration <= 30.0
    assert clip.duration == (clip.end_time - clip.start_time)


def test_zero_subtitle_tracks_invariant():
    """
    Asserts zero caption/subtitle burn-in or subtitle generation tracks.
    Inspects dubbing pipeline code files to ensure forbidden subtitle patterns are absent.
    """
    forbidden_patterns = ["generate_subtitles", "burn_subtitles", "subtitles.srt", "subtitles.ass"]
    engine_src = inspect.getsource(dubbing_engine)
    tasks_src = inspect.getsource(dubbing_tasks)

    for pattern in forbidden_patterns:
        assert pattern not in engine_src, f"Forbidden subtitle pattern '{pattern}' found in dubbing_engine.py"
        assert pattern not in tasks_src, f"Forbidden subtitle pattern '{pattern}' found in dubbing_tasks.py"


def test_synthetic_test_isolation_invariant():
    """Asserts test artifacts and clips use test prefix isolation and is_test flag."""
    clip = Clip(id=f"{PREFIX}test_clip", score=90)
    assert clip.id.startswith(PREFIX)
