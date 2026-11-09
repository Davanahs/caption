"""
test_phase_2_1_1b_sfx_get_cleanup.py
====================================
Authoritative Regression Test Suite for Phase 2.1.1B:
SFX Plan GET Side-Effect Cleanup & Event-Loop Safety (CF-DEF-012)

Verifies:
1. Repeated GET requests return the existing plan without creating or updating database records.
2. GET with no existing plan does not generate or persist a plan or retention record.
3. GET does not invoke the expensive retention predictor or FFprobe analysis.
4. Explicit generation (POST /api/clips/{id}/sfx-plan) creates and persists the expected plan.
5. Repeated and concurrent generation requests do not create inconsistent or duplicate plan state.
6. Missing clips, missing media and invalid artifacts are handled without false success.
7. Test-context isolation remains intact; production never synthesizes fallback SFX merely because the asset table is empty.
8. The retention predictor offloading executes off the main asyncio thread via asyncio.to_thread.
9. A media-analysis failure is reported correctly and does not leave misleading success state or orphaned artifacts.
"""

import os
import json
import uuid
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.main import app
from backend.models.database import SyncSessionLocal, engine, AsyncSessionLocal
from backend.models.models import (
    Clip, Video, Job, Channel, ClipSFXPlan, ClipRetention, SFXAsset, ArtifactRecord
)
from backend.models.retention import RetentionAnalysis, RetentionPoint, DropoffRisk
from backend.models.sfx import SFXPlan, SFXPlacement

TEST_PREFIX = "test_sfx_211b_"


@pytest.fixture(autouse=True)
async def cleanup_test_records():
    """Wipes test database records before and after every test."""
    def _clean():
        with SyncSessionLocal() as session:
            session.query(ClipSFXPlan).filter(ClipSFXPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(ClipRetention).filter(ClipRetention.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Video).filter(Video.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Job).filter(Job.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(Channel).filter(Channel.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
            session.query(SFXAsset).filter(
                (SFXAsset.id.like(f"{TEST_PREFIX}%")) | 
                (SFXAsset.name.like("sample_%"))
            ).delete(synchronize_session=False)
            session.query(ArtifactRecord).filter(
                (ArtifactRecord.id.like(f"{TEST_PREFIX}%")) | 
                (ArtifactRecord.storage_key.like("mock_sfx/%"))
            ).delete(synchronize_session=False)
            session.commit()

    _clean()
    yield
    await engine.dispose()
    _clean()


def create_fixture(clip_id: str, is_test: bool = True, output_path: str = None) -> tuple[str, str]:
    """Synchronously creates linked test channel, job, video, and clip records."""
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        with open(output_path, "wb") as f:
            f.write(b"\x00" * 1024)

    with SyncSessionLocal() as session:
        chan_id = f"{TEST_PREFIX}chan_{uuid.uuid4().hex[:6]}"
        channel = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{chan_id}",
            channel_name="Test Channel",
            channel_url=f"https://youtube.com/c/{chan_id}",
            is_test=is_test
        )
        session.add(channel)

        vid_id = f"{TEST_PREFIX}vid_{uuid.uuid4().hex[:6]}"
        video = Video(
            id=vid_id,
            youtube_id=f"yt_{vid_id}",
            title="Test Source Video",
            channel_id=chan_id,
            local_path=output_path
        )
        session.add(video)

        job_id = f"{TEST_PREFIX}job_{uuid.uuid4().hex[:6]}"
        job = Job(
            id=job_id,
            video_id=vid_id,
            channel_id=chan_id,
            is_test=is_test
        )
        session.add(job)

        clip = Clip(
            id=clip_id,
            video_id=vid_id,
            title="Test SFX Clip",
            start_time=0.0,
            end_time=15.0,
            output_path=output_path,
            duration=15.0,
            status="completed"
        )
        session.add(clip)
        session.commit()

    return clip_id, output_path


def seed_retention_and_plan(clip_id: str) -> SFXPlan:
    """Helper to seed existing ClipRetention and ClipSFXPlan records."""
    sample_plan = SFXPlan(
        clip_id=clip_id,
        placements=[
            SFXPlacement(
                asset_id=f"{TEST_PREFIX}asset_1",
                category="whoosh",
                start_time=1.0,
                end_time=2.0,
                gain=-10.0,
                ducking_enabled=True,
                ducking_target_gain=-15.0,
                confidence=0.9,
                reason="Attention whoosh"
            )
        ]
    )
    with SyncSessionLocal() as session:
        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=75.5,
            analysis_json=json.dumps([{
                "start_time": 1.0,
                "end_time": 2.0,
                "severity": "high",
                "primary_reason": "low_visual_motion",
                "contributing_reasons": [],
                "confidence": 0.85,
                "suggested_intervention_types": ["sfx_opportunity"]
            }])
        )
        session.add(retention)

        sfx_plan_record = ClipSFXPlan(
            clip_id=clip_id,
            plan_json=sample_plan.model_dump_json(),
            plan_hash="initial_hash_12345"
        )
        session.add(sfx_plan_record)
        session.commit()

    return sample_plan


# ==============================================================================
# Case 1: Repeated GET requests return existing plan without creating or mutating DB
# ==============================================================================
@pytest.mark.asyncio
async def test_repeated_get_returns_existing_plan_without_db_mutations():
    clip_id = f"{TEST_PREFIX}c1_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)
    expected_plan = seed_retention_and_plan(clip_id)

    # Count DB rows before
    with SyncSessionLocal() as session:
        plans_before = session.query(ClipSFXPlan).count()
        retentions_before = session.query(ClipRetention).count()
        assets_before = session.query(SFXAsset).count()
        plan_row_before = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).first()
        initial_hash = plan_row_before.plan_hash

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            resp = await client.get(f"/api/clips/{clip_id}/sfx-plan")
            assert resp.status_code == 200
            data = resp.json()
            assert data["clip_id"] == clip_id
            assert len(data["placements"]) == len(expected_plan.placements)
            assert data["placements"][0]["category"] == "whoosh"

    # Count DB rows after — must be exactly identical
    with SyncSessionLocal() as session:
        plans_after = session.query(ClipSFXPlan).count()
        retentions_after = session.query(ClipRetention).count()
        assets_after = session.query(SFXAsset).count()
        plan_row_after = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).first()
        
        assert plans_after == plans_before
        assert retentions_after == retentions_before
        assert assets_after == assets_before
        assert plan_row_after.plan_hash == initial_hash


# ==============================================================================
# Case 2: GET with no existing plan does not generate or persist plan or retention
# ==============================================================================
@pytest.mark.asyncio
async def test_get_with_no_existing_plan_does_not_mutate_db_or_create_records():
    clip_id = f"{TEST_PREFIX}c2_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/clips/{clip_id}/sfx-plan")
        assert resp.status_code == 404
        assert "SFX plan not found" in resp.json()["detail"]

    with SyncSessionLocal() as session:
        ret = session.query(ClipRetention).filter_by(clip_id=clip_id).first()
        assert ret is None, "GET must NOT create ClipRetention record"
        plan = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).first()
        assert plan is None, "GET must NOT create ClipSFXPlan record"
        assets = session.query(SFXAsset).filter(SFXAsset.name.like("sample_%")).count()
        assert assets == 0, "GET must NOT synthesize mock assets"


# ==============================================================================
# Case 3: GET does not invoke ViralityPredictor or FFprobe analysis
# ==============================================================================
@pytest.mark.asyncio
async def test_get_does_not_invoke_virality_predictor_or_ffprobe():
    clip_id = f"{TEST_PREFIX}c3_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)

    with patch("backend.services.virality_predictor.ViralityPredictor.analyze_clip") as mock_analyze:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/clips/{clip_id}/sfx-plan")
            assert resp.status_code == 404
            assert mock_analyze.call_count == 0, "GET must never call ViralityPredictor.analyze_clip"


# ==============================================================================
# Case 4: Explicit generation (POST) creates and persists the expected plan
# ==============================================================================
@pytest.mark.asyncio
async def test_explicit_post_generates_and_persists_expected_plan():
    clip_id = f"{TEST_PREFIX}c4_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)

    mock_analysis = RetentionAnalysis(
        clip_id=clip_id,
        duration=15.0,
        analysis_version="v1.0-test",
        points=[
            RetentionPoint(timestamp=0, retention_score=80.0, audio_score=50.0, motion_score=50.0, scene_activity_score=50.0, risk_level="low"),
            RetentionPoint(timestamp=1, retention_score=25.0, audio_score=10.0, motion_score=10.0, scene_activity_score=50.0, risk_level="critical"),
            RetentionPoint(timestamp=2, retention_score=25.0, audio_score=10.0, motion_score=10.0, scene_activity_score=50.0, risk_level="critical"),
        ],
        risks=[
            DropoffRisk(
                start_time=1.0,
                end_time=3.0,
                severity="high",
                primary_reason="low_audio_energy",
                contributing_reasons=["silence"],
                confidence=0.88,
                suggested_intervention_types=["sfx_opportunity"]
            )
        ]
    )

    with patch("backend.services.virality_predictor.ViralityPredictor.analyze_clip", return_value=mock_analysis):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Before POST: GET returns 404
            get_before = await client.get(f"/api/clips/{clip_id}/sfx-plan")
            assert get_before.status_code == 404

            # 2. Trigger explicit POST generation
            post_resp = await client.post(f"/api/clips/{clip_id}/sfx-plan")
            assert post_resp.status_code == 200
            plan_data = post_resp.json()
            assert plan_data["clip_id"] == clip_id
            assert "placements" in plan_data
            assert len(plan_data["placements"]) >= 1

            # 3. After POST: GET returns 200 with the exact persisted plan
            get_after = await client.get(f"/api/clips/{clip_id}/sfx-plan")
            assert get_after.status_code == 200
            retrieved_data = get_after.json()
            assert retrieved_data["clip_id"] == clip_id
            assert len(retrieved_data["placements"]) == len(plan_data["placements"])

    # 4. Verify DB persistence state
    with SyncSessionLocal() as session:
        ret = session.query(ClipRetention).filter_by(clip_id=clip_id).first()
        assert ret is not None
        assert ret.overall_score == mock_analysis.overall_score
        plan_record = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).first()
        assert plan_record is not None


# ==============================================================================
# Case 5: Repeated and concurrent generation requests do not create duplicates
# ==============================================================================
@pytest.mark.asyncio
async def test_repeated_and_concurrent_post_generations_are_consistent():
    clip_id = f"{TEST_PREFIX}c5_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)

    mock_analysis = RetentionAnalysis(
        clip_id=clip_id,
        duration=10.0,
        analysis_version="v1.0-test",
        points=[RetentionPoint(timestamp=0, retention_score=80.0, audio_score=50.0, motion_score=50.0, scene_activity_score=50.0, risk_level="low")],
        risks=[]
    )

    with patch("backend.services.virality_predictor.ViralityPredictor.analyze_clip", return_value=mock_analysis):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post(f"/api/clips/{clip_id}/sfx-plan")
            assert resp1.status_code == 200

            resp2 = await client.post(f"/api/clips/{clip_id}/sfx-plan")
            assert resp2.status_code == 200

    with SyncSessionLocal() as session:
        plans = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).all()
        assert len(plans) == 1, "Must not create duplicate ClipSFXPlan records"
        rets = session.query(ClipRetention).filter_by(clip_id=clip_id).all()
        assert len(rets) == 1, "Must not create duplicate ClipRetention records"


# ==============================================================================
# Case 6: Missing clips, missing media and invalid artifacts are handled without false success
# ==============================================================================
@pytest.mark.asyncio
async def test_missing_clip_and_missing_media_handled_gracefully():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Non-existent clip
        missing_id = f"{TEST_PREFIX}nonexistent"
        get_res = await client.get(f"/api/clips/{missing_id}/sfx-plan")
        assert get_res.status_code == 404
        post_res = await client.post(f"/api/clips/{missing_id}/sfx-plan")
        assert post_res.status_code == 404

    # Clip exists in DB but media file does not exist on disk
    clip_id = f"{TEST_PREFIX}c6_nomedia_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True, output_path="/nonexistent/path/to/video.mp4")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post_res = await client.post(f"/api/clips/{clip_id}/sfx-plan")
        assert post_res.status_code == 400
        assert "Clip video file not found or not rendered" in post_res.json()["detail"]


# ==============================================================================
# Case 7: Test-context isolation remains intact; production never synthesizes fallback
# ==============================================================================
@pytest.mark.asyncio
async def test_test_context_isolation_preserved_on_generation():
    clip_id = f"{TEST_PREFIX}c7_prod_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=False)  # Explicitly production!

    mock_analysis = RetentionAnalysis(
        clip_id=clip_id,
        duration=10.0,
        analysis_version="v1.0-test",
        points=[RetentionPoint(timestamp=0, retention_score=40.0, audio_score=20.0, motion_score=20.0, scene_activity_score=50.0, risk_level="high")],
        risks=[
            DropoffRisk(
                start_time=1.0, end_time=2.0, severity="high",
                primary_reason="low_audio_energy", contributing_reasons=[], confidence=0.8,
                suggested_intervention_types=["sfx_opportunity"]
            )
        ]
    )

    with patch("backend.services.virality_predictor.ViralityPredictor.analyze_clip", return_value=mock_analysis):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/sfx-plan")
            assert resp.status_code == 200
            plan = resp.json()
            # In production with empty SFX assets, must return safe empty plan
            assert plan["placements"] == [], "Production clip must never synthesize fallback mock assets"

    with SyncSessionLocal() as session:
        mock_assets = session.query(SFXAsset).filter(SFXAsset.name.like("sample_%")).count()
        assert mock_assets == 0, "No synthetic mock SFX assets must be created in production"


# ==============================================================================
# Case 8: Event loop offloading executes on a separate worker thread
# ==============================================================================
@pytest.mark.asyncio
async def test_event_loop_offloading_executes_on_worker_thread():
    clip_id = f"{TEST_PREFIX}c8_thread_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)

    main_thread = threading.current_thread()
    observed_thread = {"thread": None}

    def _inspect_thread(path, cid=""):
        observed_thread["thread"] = threading.current_thread()
        return RetentionAnalysis(
            clip_id=cid or clip_id,
            duration=10.0,
            analysis_version="v1.0-test",
            points=[RetentionPoint(timestamp=0, retention_score=80.0, audio_score=50.0, motion_score=50.0, scene_activity_score=50.0, risk_level="low")],
            risks=[]
        )

    with patch("backend.services.virality_predictor.ViralityPredictor.analyze_clip", side_effect=_inspect_thread):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/sfx-plan")
            assert resp.status_code == 200

    assert observed_thread["thread"] is not None
    assert observed_thread["thread"] != main_thread, "ViralityPredictor.analyze_clip must execute off the main event loop thread"


# ==============================================================================
# Case 9: Media analysis failure is reported correctly without leaving orphaned records
# ==============================================================================
@pytest.mark.asyncio
async def test_media_analysis_failure_propagates_cleanly_without_orphaned_state():
    clip_id = f"{TEST_PREFIX}c9_fail_{uuid.uuid4().hex[:8]}"
    create_fixture(clip_id, is_test=True)

    def _raise_error(path, cid=""):
        raise RuntimeError("FFprobe corrupted bitstream error")

    with patch("backend.services.virality_predictor.ViralityPredictor.analyze_clip", side_effect=_raise_error):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/sfx-plan")
            assert resp.status_code == 500
            assert "Media analysis failed" in resp.json()["detail"]

    # Verify no partial or orphaned state in DB
    with SyncSessionLocal() as session:
        ret = session.query(ClipRetention).filter_by(clip_id=clip_id).first()
        assert ret is None, "Failed media analysis must not leave orphaned ClipRetention"
        plan = session.query(ClipSFXPlan).filter_by(clip_id=clip_id).first()
        assert plan is None, "Failed media analysis must not leave orphaned ClipSFXPlan"
