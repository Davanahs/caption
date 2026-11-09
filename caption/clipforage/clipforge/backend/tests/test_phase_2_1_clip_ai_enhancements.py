"""
test_phase_2_1_clip_ai_enhancements.py
======================================
Isolated Acceptance and Regression Test Suite for Phase 2.1:
Clip Preview AI Enhancements Wiring (CF-DEF-004)

Verifies:
1. Hook Opportunity Planning & Overlay Endpoints:
   - GET /api/clips/{id}/hook (404 and 200 responses)
   - POST /api/clips/{id}/hook/plan (task dispatch & ClipHookPlan DB persistence)
   - POST /api/clips/{id}/hook/apply (422 validation, task dispatch)
2. B-roll Cutaway Planning & Compositing Endpoints:
   - GET /api/clips/{id}/broll-plan (404 and 200 responses, fallback asset resilience)
   - POST /api/clips/{id}/broll-apply (422 validation, task dispatch)
3. SFX Audio Retention Planning & Mixing Endpoints:
   - GET /api/clips/{id}/sfx-plan (404 and 200 responses, fallback sine wave synthesis)
   - POST /api/clips/{id}/sfx-apply (422 validation, task dispatch)
4. Isolated Planner Services:
   - HookPlanner & analyze_hook_opportunities_task persistence
   - BrollPlanner create_plan resilience
   - SFXPlanner generate_plan resilience
"""

import os
import json
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import (
    Clip, Video, Channel, Job, ClipHookPlan, ClipRetention, SFXAsset, VisualAsset, ArtifactRecord,
    ClipVisualPlan, ClipSFXPlan
)
from backend.models.broll import BrollPlan, BrollPlacement
from backend.models.sfx import SFXPlan, SFXPlacement
from backend.models.hook import HookPlan, HookOpportunity, HookConcept
from backend.services.sfx_planner import SFXPlanner
from backend.services.broll_planner import BrollPlanner
from backend.tasks.hook_tasks import analyze_hook_opportunities_task

TEST_PREFIX = "p21_test_"


@pytest.fixture(autouse=True)
async def cleanup_p21_records():
    """Wipes test database records after every test."""
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(ClipVisualPlan).filter(ClipVisualPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipSFXPlan).filter(ClipSFXPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipHookPlan).filter(ClipHookPlan.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ClipRetention).filter(ClipRetention.clip_id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Clip).filter(Clip.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(SFXAsset).filter(SFXAsset.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(VisualAsset).filter(VisualAsset.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.query(ArtifactRecord).filter(ArtifactRecord.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.commit()


def create_test_clip_record(clip_id: str, title: str = "Test AI Clip", output_path: str = None) -> Clip:
    """Helper to synchronously seed a test channel, job, video, and clip record."""
    with SyncSessionLocal() as session:
        chan_id = f"{TEST_PREFIX}chan"
        channel = session.query(Channel).filter_by(id=chan_id).first()
        if not channel:
            channel = Channel(
                id=chan_id,
                youtube_channel_id=f"UC_{TEST_PREFIX}chan_{uuid.uuid4().hex[:6]}",
                channel_name="Test AI Channel",
                channel_url="https://youtube.com/channel/test_ai",
                is_test=True
            )
            session.add(channel)

        vid_id = f"{TEST_PREFIX}vid_{uuid.uuid4().hex[:8]}"
        video = Video(
            id=vid_id,
            youtube_id=f"yt_{uuid.uuid4().hex[:8]}",
            title="Source Video For AI Enhancements",
            channel_id=chan_id,
            local_path=output_path or "/tmp/dummy.mp4"
        )
        session.add(video)

        job = Job(
            id=f"{TEST_PREFIX}job_{uuid.uuid4().hex[:8]}",
            video_id=vid_id,
            channel_id=chan_id,
            is_test=True
        )
        session.add(job)

        clip = Clip(
            id=clip_id,
            video_id=video.id,
            title=title,
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            score=8.7,
            publish_status="draft",
            output_path=output_path or "/tmp/dummy.mp4",
            transcript_segment="Wait until you see how this insane technology changes everything you knew.",
            description="Short teaser description"
        )
        session.add(clip)
        session.commit()
        return clip


@pytest.mark.asyncio
async def test_get_hook_plan_not_found_returns_404():
    """GET /api/clips/{id}/hook returns 404 when no plan exists."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/clips/{TEST_PREFIX}nonexistent/hook")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_hook_plan_not_found_returns_404():
    """POST /api/clips/{id}/hook/plan returns 404 when clip does not exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/api/clips/{TEST_PREFIX}nonexistent/hook/plan")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_and_get_hook_plan_success():
    """Verifies analyze_hook_opportunities_task persists ClipHookPlan and GET retrieves it."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    # 1. Trigger POST endpoint with mocked Celery task
    with patch("backend.tasks.hook_tasks.analyze_hook_opportunities_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock_hook_task_12345"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/hook/plan")
            assert resp.status_code == 200
            data = resp.json()
            assert data["task_id"] == "mock_hook_task_12345"
            assert data["clip_id"] == clip_id

    # 2. Execute analyze_hook_opportunities_task directly to test plan generation & DB persistence
    task_result = analyze_hook_opportunities_task(clip_id=clip_id)
    assert isinstance(task_result, list)
    assert len(task_result) >= 1
    assert "id" in task_result[0]

    # 3. Retrieve plan via GET endpoint
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        get_resp = await client.get(f"/api/clips/{clip_id}/hook")
        assert get_resp.status_code == 200
        plan = get_resp.json()
        assert plan["clip_id"] == clip_id
        assert "opportunities" in plan
        assert len(plan["opportunities"]) >= 1
        assert "concepts" in plan
        assert len(plan["concepts"]) >= 1
        assert plan["concepts"][0]["target_duration"] > 0


@pytest.mark.asyncio
async def test_apply_hook_plan_invalid_schema_returns_422():
    """POST /api/clips/{id}/hook/apply returns 422 on invalid payload schema."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/clips/{clip_id}/hook/apply", json={"invalid_field": 999})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_apply_hook_plan_success():
    """POST /api/clips/{id}/hook/apply dispatches apply_hook_task with valid payload."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    valid_payload = {
        "clip_id": clip_id,
        "planner_version": "1.0.0",
        "opportunities": [{
            "id": "opp_1",
            "clip_id": clip_id,
            "start_time": 0.0,
            "end_time": 3.0,
            "opportunity_type": "curiosity_gap",
            "hook_objective": "Increase initial 3s retention",
            "confidence": 0.9,
            "reason": "Strong provocative opening statement",
            "priority": 1
        }],
        "concepts": [{
            "opportunity_id": "opp_1",
            "hook_style": "curiosity",
            "hook_text": "This Changes Everything!",
            "target_duration": 3.0,
            "delivery_mode": "voiceover_only",
            "confidence": 0.92,
            "planner_version": "1.0.0"
        }]
    }

    with patch("backend.tasks.hook_tasks.apply_hook_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock_apply_hook_67890"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/hook/apply", json=valid_payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["task_id"] == "mock_apply_hook_67890"
            assert data["clip_id"] == clip_id


@pytest.mark.asyncio
async def test_get_broll_plan_not_found_returns_404():
    """GET /api/clips/{id}/broll-plan returns 404 when clip does not exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/clips/{TEST_PREFIX}missing/broll-plan")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_broll_plan_success():
    """GET /api/clips/{id}/broll-plan successfully creates and returns a BrollPlan."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/clips/{clip_id}/broll-plan")
        assert resp.status_code == 200
        plan = resp.json()
        assert plan["clip_id"] == clip_id
        assert "placements" in plan
        assert isinstance(plan["placements"], list)
        assert len(plan["placements"]) >= 1
        first_placement = plan["placements"][0]
        assert "display_mode" in first_placement
        assert first_placement["start_time"] >= 0.0


@pytest.mark.asyncio
async def test_apply_broll_plan_invalid_schema_returns_422():
    """POST /api/clips/{id}/broll-apply returns 422 on invalid schema."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/clips/{clip_id}/broll-apply", json={"bad_data": True})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_apply_broll_plan_success():
    """POST /api/clips/{id}/broll-apply dispatches apply_broll_task with valid payload."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    valid_plan = {
        "clip_id": clip_id,
        "placements": [{
            "asset_id": f"{TEST_PREFIX}asset_broll",
            "opportunity_id": "opp_1",
            "start_time": 2.0,
            "end_time": 5.0,
            "display_mode": "full_cutaway",
            "confidence": 0.88
        }]
    }

    with patch("backend.tasks.clip_tasks.apply_broll_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock_apply_broll_54321"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/broll-apply", json=valid_plan)
            assert resp.status_code == 200
            data = resp.json()
            assert data["task_id"] == "mock_apply_broll_54321"
            assert data["clip_id"] == clip_id


@pytest.mark.asyncio
async def test_get_sfx_plan_not_found_returns_404():
    """GET /api/clips/{id}/sfx-plan returns 404 when clip does not exist."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/clips/{TEST_PREFIX}missing/sfx-plan")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_sfx_plan_success():
    """Verifies POST /api/clips/{id}/sfx-plan generates plan and read-only GET retrieves it."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    # Seed an isolated ClipRetention record for this clip
    with SyncSessionLocal() as session:
        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=7.8,
            analysis_json=json.dumps([{
                "start_time": 0.0,
                "end_time": 2.5,
                "severity": "high",
                "primary_reason": "low_audio_energy",
                "contributing_reasons": ["silence"],
                "confidence": 0.85,
                "suggested_intervention_types": ["sfx_opportunity"]
            }])
        )
        session.add(retention)
        session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Before generation, read-only GET returns 404 (no plan created as side effect)
        get_before = await client.get(f"/api/clips/{clip_id}/sfx-plan")
        assert get_before.status_code == 404

        # 2. Explicit POST generates and persists plan
        post_resp = await client.post(f"/api/clips/{clip_id}/sfx-plan")
        assert post_resp.status_code == 200
        plan = post_resp.json()
        assert plan["clip_id"] == clip_id
        assert "placements" in plan
        assert len(plan["placements"]) >= 1

        # 3. Read-only GET retrieves persisted plan
        get_after = await client.get(f"/api/clips/{clip_id}/sfx-plan")
        assert get_after.status_code == 200
        retrieved_plan = get_after.json()
        assert retrieved_plan["clip_id"] == clip_id
        assert len(retrieved_plan["placements"]) == len(plan["placements"])
        cue = retrieved_plan["placements"][0]
        assert "category" in cue
        assert "ducking_enabled" in cue
        assert cue["start_time"] >= 0.0



@pytest.mark.asyncio
async def test_apply_sfx_plan_invalid_schema_returns_422():
    """POST /api/clips/{id}/sfx-apply returns 422 on invalid schema."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/clips/{clip_id}/sfx-apply", json={"wrong_format": 1})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_apply_sfx_plan_success():
    """POST /api/clips/{id}/sfx-apply dispatches apply_sfx_task with valid payload."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    valid_sfx = {
        "clip_id": clip_id,
        "placements": [{
            "asset_id": f"{TEST_PREFIX}asset_sfx",
            "category": "whoosh",
            "start_time": 0.0,
            "end_time": 1.2,
            "gain": 0.8,
            "ducking_enabled": True,
            "ducking_target_gain": -12.0,
            "confidence": 0.95,
            "reason": "Opening attention hook"
        }]
    }

    with patch("backend.tasks.clip_tasks.apply_sfx_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "mock_apply_sfx_99887"
        mock_delay.return_value = mock_task

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/clips/{clip_id}/sfx-apply", json=valid_sfx)
            assert resp.status_code == 200
            data = resp.json()
            assert data["task_id"] == "mock_apply_sfx_99887"
            assert data["clip_id"] == clip_id


@pytest.mark.asyncio
async def test_sfx_planner_isolated_mock_fallback():
    """Verifies SFXPlanner generates a plan even when sfx_assets table is completely empty."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    with SyncSessionLocal() as session:
        # Seed an isolated ClipRetention record for this clip so planner can read it
        retention = ClipRetention(
            clip_id=clip_id,
            overall_score=7.8,
            analysis_json=json.dumps([{
                "start_time": 0.0,
                "end_time": 2.5,
                "severity": "high",
                "primary_reason": "low_audio_energy",
                "contributing_reasons": ["silence"],
                "confidence": 0.85,
                "suggested_intervention_types": ["sfx_opportunity"]
            }])
        )
        session.add(retention)
        session.commit()

        planner = SFXPlanner()
        # Ensure 0 assets
        session.query(SFXAsset).filter(SFXAsset.id.like(f"{TEST_PREFIX}%")).delete(synchronize_session=False)
        session.commit()

        # Generate plan asynchronously
        from backend.models.database import AsyncSessionLocal
        async with AsyncSessionLocal() as async_session:
            plan = await planner.generate_plan(clip_id=clip_id, db=async_session)
            assert isinstance(plan, SFXPlan)
            assert plan.clip_id == clip_id
            assert len(plan.placements) >= 1
            assert plan.placements[0].category in ["whoosh", "impact", "riser"]


@pytest.mark.asyncio
async def test_broll_planner_isolated_mock_fallback():
    """Verifies BrollPlanner creates cutaway placements without crashing when no visual assets exist."""
    clip_id = f"{TEST_PREFIX}clip_{uuid.uuid4().hex[:8]}"
    create_test_clip_record(clip_id)

    from backend.models.database import AsyncSessionLocal
    async with AsyncSessionLocal() as async_session:
        planner = BrollPlanner()
        transcript = [
            {"word": "amazing", "start": 0.0, "end": 0.8},
            {"word": "technology", "start": 0.9, "end": 1.6},
            {"word": "future", "start": 1.7, "end": 2.5}
        ]
        plan = await planner.create_plan(
            db=async_session,
            clip_id=clip_id,
            transcript=transcript,
            clip_start_time=0.0,
            clip_end_time=10.0
        )
        assert isinstance(plan, BrollPlan)
        assert plan.clip_id == clip_id
        assert len(plan.placements) >= 1
        assert plan.placements[0].display_mode in ["full_cutaway", "pip_top", "pip_bottom"]
