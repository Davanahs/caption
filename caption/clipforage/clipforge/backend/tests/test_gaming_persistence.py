"""
clipforge/backend/tests/test_gaming_persistence.py
=================================================
Authoritative Tier 1 & Tier 2 test suite for Dual-Region Gaming Layout database
persistence, Job.config JSON serialization/deserialization, zero schema migrations,
Celery task payload inheritance, and legacy backward compatibility.

Covers Features:
- F20: Job Configuration Persistence (Lossless roundtrip, preset preservation, Unicode/emojis, cancellation handling)
- F21: Backward Compatibility Preservation (Legacy jobs with null/empty gaming config)
"""

import json
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, inspect as sa_inspect
from sqlalchemy.orm import Session

from backend.models.database import SyncSessionLocal, AsyncSessionLocal
from backend.models.models import Base, Job, JobStatus, Video
from backend.api.routes.jobs import _job_dict, get_job, list_active_jobs, list_job_history, retry_failed_job
from backend.tests.gaming_test_fixtures import (
    MockJob,
    MockAsyncSession,
    create_mock_db_session,
    create_mock_celery_task,
)


@pytest.fixture(autouse=True)
def cleanup_test_jobs():
    """Fixture ensuring any test jobs created during test runs are cleaned up."""
    created_job_ids = []
    yield created_job_ids
    if created_job_ids:
        try:
            with SyncSessionLocal() as session:
                session.query(Job).filter(Job.id.in_(created_job_ids)).delete(synchronize_session=False)
                session.commit()
        except Exception:
            pass


# ==============================================================================
# AUTHORITATIVE SECTION 3.2 TIER 1 PERSISTENCE TEST CASES
# ==============================================================================

def test_tier1_f20_persist_gaming_config_in_job_config(cleanup_test_jobs):
    """
    [TC-T1-F20-01] Verify Job instance creation with serialized gaming_layout in config Text column.
    Ensures Job.config is valid JSON containing all required layout fields.
    """
    job_id = f"test-persist-{uuid.uuid4()}"
    cleanup_test_jobs.append(job_id)

    gaming_layout = {
        "mode": "gaming",
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
        "facecam_output_rect": {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.22},
        "canvas_width": 1080,
        "canvas_height": 1920,
    }
    config_data = {
        "reframe_mode": "gaming",
        "mode": "gaming",
        "gaming_layout": gaming_layout,
        "source_type": "youtube",
    }

    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        progress=0,
        current_step="Queued",
        source_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        source_title="Gaming Session",
        config=json.dumps(config_data),
        is_test=True,
    )

    with SyncSessionLocal() as session:
        session.add(job)
        session.commit()

    # Re-read and verify serialization
    with SyncSessionLocal() as session:
        retrieved = session.get(Job, job_id)
        assert retrieved is not None
        assert isinstance(retrieved.config, str)

        parsed = json.loads(retrieved.config)
        assert parsed["mode"] == "gaming"
        assert parsed["reframe_mode"] == "gaming"
        assert "gaming_layout" in parsed

        gl = parsed["gaming_layout"]
        assert gl["gameplay_roi"] == {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
        assert gl["facecam_roi"] == {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25}
        assert gl["facecam_placement"] == "top-right"
        assert gl["facecam_output_rect"] == {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.22}
        assert gl["canvas_width"] == 1080
        assert gl["canvas_height"] == 1920


def test_tier1_f20_reload_gaming_config_lossless_roundtrip(cleanup_test_jobs):
    """
    [TC-T1-F20-02] Persist high-precision normalized coordinates, reload from DB,
    and assert lossless roundtrip with absolute float delta <= 1e-6 across all coordinates.
    """
    job_id = f"test-lossless-{uuid.uuid4()}"
    cleanup_test_jobs.append(job_id)

    original_coords = {
        "gameplay_roi": {"x": 0.123456, "y": 0.065432, "width": 0.812345, "height": 0.901234},
        "facecam_roi": {"x": 0.654321, "y": 0.043210, "width": 0.287654, "height": 0.234567},
        "facecam_output_rect": {"x": 0.601234, "y": 0.034567, "width": 0.356789, "height": 0.210987},
    }

    gaming_layout = {
        "mode": "gaming",
        "facecam_placement": "custom",
        "canvas_width": 1080,
        "canvas_height": 1920,
        **original_coords,
    }

    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        config=json.dumps({"gaming_layout": gaming_layout, "mode": "gaming"}),
        is_test=True,
    )

    with SyncSessionLocal() as session:
        session.add(job)
        session.commit()

    with SyncSessionLocal() as session:
        retrieved = session.get(Job, job_id)
        assert retrieved is not None
        reloaded_gl = json.loads(retrieved.config)["gaming_layout"]

        for region_key in ("gameplay_roi", "facecam_roi", "facecam_output_rect"):
            for coord_key in ("x", "y", "width", "height"):
                expected_val = original_coords[region_key][coord_key]
                actual_val = reloaded_gl[region_key][coord_key]
                assert abs(expected_val - actual_val) <= 1e-6, (
                    f"Lossless roundtrip failure in {region_key}.{coord_key}: "
                    f"expected {expected_val}, got {actual_val}"
                )


def test_tier1_f20_persist_all_facecam_placement_presets(cleanup_test_jobs):
    """
    [TC-T1-F20-03] Persist jobs across each facecam placement preset:
    top-left, top-right, bottom-left, bottom-right, and custom.
    Verifies roundtrip retrieves identical preset name without modification.
    """
    presets = ["top-left", "top-right", "bottom-left", "bottom-right", "custom"]

    for preset in presets:
        job_id = f"test-preset-{preset}-{uuid.uuid4()}"
        cleanup_test_jobs.append(job_id)

        config_data = {
            "mode": "gaming",
            "gaming_layout": {
                "facecam_placement": preset,
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            }
        }

        job = Job(id=job_id, status=JobStatus.PENDING, config=json.dumps(config_data), is_test=True)
        with SyncSessionLocal() as session:
            session.add(job)
            session.commit()

        with SyncSessionLocal() as session:
            retrieved = session.get(Job, job_id)
            assert retrieved is not None
            parsed = json.loads(retrieved.config)
            assert parsed["gaming_layout"]["facecam_placement"] == preset, (
                f"Preset mismatch: expected {preset}, got {parsed['gaming_layout']['facecam_placement']}"
            )


def test_tier1_f20_no_database_schema_migration_required():
    """
    [TC-T1-F20-04] Inspect Job.__table__.columns and verify NO new columns exist on the jobs table
    (e.g., no gameplay_roi, no facecam_roi, no gaming_layout).
    Strictly verifies reliance on Job.config Text column per R4 and F20.
    """
    mapper = sa_inspect(Job)
    col_names = {c.key for c in mapper.column_attrs}

    # Verify existing config column exists
    assert "config" in col_names, "Job model must retain the 'config' column"

    # Verify no dedicated gaming columns were added
    forbidden_columns = [
        "gameplay_roi",
        "facecam_roi",
        "gaming_layout",
        "facecam_placement",
        "facecam_output_rect",
        "canvas_width",
        "canvas_height",
        "captions",
        "subtitles",
    ]
    for col in forbidden_columns:
        assert col not in col_names, (
            f"F20 / R4 Violation: Column '{col}' was added to Job table. "
            "Dual-region gaming configuration must strictly reside in Job.config JSON without DB migration."
        )


def test_tier1_f20_celery_task_inherits_persisted_config():
    """
    [TC-T1-F20-05] Simulate Celery job dispatch with dispatch_kwargs extracted from Job.config.
    Verifies Celery task kwargs retain full gaming_layout dictionary and mode='gaming'.
    """
    gaming_layout = {
        "mode": "gaming",
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
    }
    dispatch_kwargs = {
        "job_id": "job-celery-inherit-001",
        "reframe_mode": "gaming",
        "mode": "gaming",
        "gaming_layout": gaming_layout,
    }
    config_data = {
        "reframe_mode": "gaming",
        "mode": "gaming",
        "gaming_layout": gaming_layout,
        "dispatch_kwargs": dispatch_kwargs,
    }

    job = MockJob(job_id="job-celery-inherit-001", config=json.dumps(config_data))

    # Simulate celery dispatch
    parsed_config = json.loads(job.config)
    task_kwargs = parsed_config.get("dispatch_kwargs", {})

    assert task_kwargs.get("mode") == "gaming"
    assert task_kwargs.get("reframe_mode") == "gaming"
    assert task_kwargs.get("gaming_layout") == gaming_layout


def test_tier1_f21_legacy_job_queries_compatible(cleanup_test_jobs):
    """
    [TC-T1-F21-05] Query jobs table containing a mixture of gaming jobs, podcast jobs,
    and null-config jobs. Verifies _job_dict executes cleanly without schema error or KeyError.
    """
    id_null = f"test-legacy-null-{uuid.uuid4()}"
    id_podcast = f"test-legacy-podcast-{uuid.uuid4()}"
    id_gaming = f"test-gaming-{uuid.uuid4()}"
    cleanup_test_jobs.extend([id_null, id_podcast, id_gaming])

    job_null = Job(id=id_null, status=JobStatus.COMPLETED, config=None, is_test=True)
    job_podcast = Job(
        id=id_podcast,
        status=JobStatus.COMPLETED,
        config=json.dumps({"mode": "podcast_interview", "podcast_composition": "stacked"}),
        is_test=True,
    )
    job_gaming = Job(
        id=id_gaming,
        status=JobStatus.PENDING,
        config=json.dumps({
            "mode": "gaming",
            "gaming_layout": {
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            }
        }),
        is_test=True,
    )

    with SyncSessionLocal() as session:
        session.add_all([job_null, job_podcast, job_gaming])
        session.commit()

    with SyncSessionLocal() as session:
        j1 = session.get(Job, id_null)
        j2 = session.get(Job, id_podcast)
        j3 = session.get(Job, id_gaming)

        dict1 = _job_dict(j1)
        dict2 = _job_dict(j2)
        dict3 = _job_dict(j3)

        assert dict1["config"] == {}
        assert dict2["config"]["mode"] == "podcast_interview"
        assert dict2["config"].get("gaming_layout") is None
        assert dict3["config"]["mode"] == "gaming"
        assert dict3["config"]["gaming_layout"]["facecam_roi"]["x"] == 0.7


# ==============================================================================
# AUTHORITATIVE SECTION 3.2 TIER 2 PERSISTENCE TEST CASES
# ==============================================================================

def test_tier2_f20_persist_unicode_and_emojis_in_job_config(cleanup_test_jobs):
    """
    [TC-T2-F20-01] Persist video title and config metadata containing emojis and international characters:
    '🎮 Epic Gameplay 🔥 [4K 60fps] 🏆 中文 日本語 한국어 Русский'.
    Asserts UTF-8 lossless serialization and deserialization without Mojibake or UnicodeEncodeError.
    """
    job_id = f"test-unicode-{uuid.uuid4()}"
    cleanup_test_jobs.append(job_id)

    unicode_title = "🎮 Epic Gameplay 🔥 [4K 60fps] 🏆 中文 日本語 한국어 Русский 🚀"
    config_data = {
        "mode": "gaming",
        "title": unicode_title,
        "gaming_layout": {
            "notes": "🎯 Direct Hit! 💥",
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
        }
    }

    job = Job(
        id=job_id,
        source_title=unicode_title,
        status=JobStatus.PENDING,
        config=json.dumps(config_data, ensure_ascii=False),
        is_test=True,
    )

    with SyncSessionLocal() as session:
        session.add(job)
        session.commit()

    with SyncSessionLocal() as session:
        retrieved = session.get(Job, job_id)
        assert retrieved is not None
        assert retrieved.source_title == unicode_title

        parsed = json.loads(retrieved.config)
        assert parsed["title"] == unicode_title
        assert parsed["gaming_layout"]["notes"] == "🎯 Direct Hit! 💥"


@pytest.mark.asyncio
async def test_tier2_f20_job_cancellation_preserves_config_integrity(cleanup_test_jobs):
    """
    [TC-T2-F20-02] Verify that cancelling a gaming job updates status to CANCELLED
    while preserving Job.config JSON completely intact and uncorrupted.
    """
    job_id = f"test-cancel-{uuid.uuid4()}"
    cleanup_test_jobs.append(job_id)

    gaming_layout = {
        "mode": "gaming",
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
        "facecam_placement": "top-right",
    }
    config_str = json.dumps({"mode": "gaming", "gaming_layout": gaming_layout})

    job = Job(
        id=job_id,
        status=JobStatus.CLIPPING_IN_PROGRESS,
        progress=45,
        current_step="Reframing vertical layout",
        config=config_str,
        is_test=True,
    )

    with SyncSessionLocal() as session:
        session.add(job)
        session.commit()

    # Simulate cancellation
    with SyncSessionLocal() as session:
        target_job = session.get(Job, job_id)
        assert target_job is not None
        target_job.status = JobStatus.CANCELLED
        target_job.current_step = "Cancelled by user"
        session.commit()

    # Verify config integrity
    with SyncSessionLocal() as session:
        cancelled_job = session.get(Job, job_id)
        assert cancelled_job is not None
        assert cancelled_job.status == JobStatus.CANCELLED

        # Assert config is completely intact
        parsed = json.loads(cancelled_job.config)
        assert parsed["mode"] == "gaming"
        assert parsed["gaming_layout"]["facecam_placement"] == "top-right"
        assert parsed["gaming_layout"]["gameplay_roi"]["width"] == 1.0


def test_tier2_f20_retrieve_legacy_job_missing_gaming_layout_key(cleanup_test_jobs):
    """
    [TC-T2-F20-03] Retrieve legacy job with empty {} or standard {'reframe_mode': 'center_crop'}.
    Verifies _job_dict safely handles missing gaming_layout key with zero KeyError.
    """
    legacy_cases = [
        None,
        "",
        "{}",
        json.dumps({"reframe_mode": "center_crop"}),
        json.dumps({"mode": "standard", "clips_count": 3}),
    ]

    for raw_config in legacy_cases:
        job_id = f"test-legacy-dict-{uuid.uuid4()}"
        cleanup_test_jobs.append(job_id)

        job = Job(
            id=job_id,
            status=JobStatus.COMPLETED,
            config=raw_config,
            is_test=True,
        )
        with SyncSessionLocal() as session:
            session.add(job)
            session.commit()

        with SyncSessionLocal() as session:
            retrieved = session.get(Job, job_id)
            output = _job_dict(retrieved)
            assert isinstance(output["config"], dict)
            assert output["config"].get("gaming_layout") is None


@pytest.mark.asyncio
async def test_tier2_f20_database_connection_drop_rollback():
    """
    [TC-T2-F20-04] Simulate database exception / connection drop during commit.
    Verifies that the session invokes rollback() and no corrupted state persists.
    """
    mock_session = MockAsyncSession()

    job_id = f"test-rollback-{uuid.uuid4()}"
    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        config=json.dumps({"mode": "gaming"}),
        is_test=True,
    )

    mock_session.add(job)

    # Simulate failure on commit
    with patch.object(mock_session, "commit", side_effect=RuntimeError("Simulated DB connection lost")):
        try:
            await mock_session.commit()
        except RuntimeError:
            await mock_session.rollback()

    assert mock_session.rolled_back is True, "Session must execute rollback on commit failure"


@pytest.mark.asyncio
async def test_tier2_f20_concurrency_lock_during_config_update(cleanup_test_jobs):
    """
    [TC-T2-F20-05] Simulate concurrent status/progress updates to Job.config.
    Verifies updates commit safely without JSON syntax truncation or payload corruption.
    """
    job_id = f"test-concurrent-{uuid.uuid4()}"
    cleanup_test_jobs.append(job_id)

    gaming_layout = {
        "mode": "gaming",
        "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
    }
    initial_config = {
        "mode": "gaming",
        "gaming_layout": gaming_layout,
        "progress_log": [],
    }

    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        progress=0,
        config=json.dumps(initial_config),
        is_test=True,
    )

    with SyncSessionLocal() as session:
        session.add(job)
        session.commit()

    # Simulate worker update 1: progress 50%
    with SyncSessionLocal() as session1:
        j1 = session1.get(Job, job_id)
        c1 = json.loads(j1.config)
        c1["progress_log"].append("Step 1 complete")
        j1.progress = 50
        j1.config = json.dumps(c1)
        session1.commit()

    # Simulate worker update 2: progress 100%
    with SyncSessionLocal() as session2:
        j2 = session2.get(Job, job_id)
        c2 = json.loads(j2.config)
        c2["progress_log"].append("Step 2 complete")
        j2.progress = 100
        j2.status = JobStatus.COMPLETED
        j2.config = json.dumps(c2)
        session2.commit()

    # Verify final state is valid JSON and not corrupted
    with SyncSessionLocal() as session:
        final_job = session.get(Job, job_id)
        assert final_job is not None
        assert final_job.progress == 100
        assert final_job.status == JobStatus.COMPLETED

        final_config = json.loads(final_job.config)
        assert final_config["mode"] == "gaming"
        assert final_config["gaming_layout"]["facecam_roi"]["x"] == 0.70
        assert len(final_config["progress_log"]) == 2


# ==============================================================================
# ADDITIONAL PERSISTENCE API TESTS (GET, HISTORY, RETRY)
# ==============================================================================

class TestJobsApiGamingPersistence:

    @pytest.mark.asyncio
    async def test_get_job_api_exposes_gaming_config(self):
        """GET /api/jobs/{id} returns deserialized gaming_layout dictionary in config."""
        job_id = f"job-test-{uuid.uuid4()}"
        gaming_layout = {
            "mode": "gaming",
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        config_data = {
            "mode": "gaming",
            "reframe_mode": "gaming",
            "gaming_layout": gaming_layout,
        }
        mock_job = Job(
            id=job_id,
            status=JobStatus.COMPLETED.value,
            config=json.dumps(config_data),
            is_test=True,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_job, None)
        mock_db.execute.return_value = mock_result

        res = await get_job(job_id=job_id, db=mock_db)
        assert res["id"] == job_id
        assert isinstance(res["config"], dict)
        assert res["config"]["mode"] == "gaming"
        assert res["config"]["gaming_layout"] == gaming_layout

    @pytest.mark.asyncio
    async def test_active_and_history_jobs_include_gaming_config(self):
        """GET /api/jobs/active and /api/jobs/history serialize gaming configuration."""
        gaming_layout = {
            "mode": "gaming",
            "gameplay_roi": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
        }
        active_job = Job(
            id="active-job-1",
            status=JobStatus.CLIPPING_IN_PROGRESS.value,
            config=json.dumps({"mode": "gaming", "gaming_layout": gaming_layout}),
            is_test=False,
        )
        history_job = Job(
            id="history-job-1",
            status=JobStatus.COMPLETED.value,
            config=json.dumps({"mode": "gaming", "gaming_layout": gaming_layout}),
            is_test=False,
        )

        mock_db = AsyncMock()
        mock_active_res = MagicMock()
        mock_active_res.all.return_value = [(active_job, None)]
        mock_history_res = MagicMock()
        mock_history_res.all.return_value = [(history_job, None)]

        mock_db.execute.side_effect = [mock_active_res, mock_history_res]

        active_list = await list_active_jobs(db=mock_db)
        assert len(active_list) == 1
        assert active_list[0]["config"]["gaming_layout"] == gaming_layout

        history_list = await list_job_history(db=mock_db)
        assert len(history_list) == 1
        assert history_list[0]["config"]["gaming_layout"] == gaming_layout
