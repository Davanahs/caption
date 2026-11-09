"""
Regression test suite for pipeline publishing adapter and task dispatch defense.
Verifies:
1. Distinct task registration: 'publish_clip' (pipeline adapter) vs 'publish_clip_task' (Studio manual/queue).
2. Defense against dictionary payload: Output validator dict payload cannot crash database query with psycopg2 'can't adapt type dict'.
3. Type guard validation: Non-string or nested dict IDs return clean failure dictionaries without driver crash.
4. User-facing error sanitization: Technical driver errors (psycopg2, sql, parameter dumps) are replaced with clean notices while domain errors are preserved.
"""
import pytest
import uuid
from unittest.mock import MagicMock, patch
from pathlib import Path

from backend.tasks.process_video import celery_app
from backend.tasks.clip_tasks import publish_task, publish_clip_task
from backend.core.sanitizer import sanitize_user_facing_error, DEFAULT_SANITIZED_ERROR
from backend.models.models import Clip, Job, PublishStatus
from backend.models.database import SyncSessionLocal


def test_task_registry_distinct_identifiers():
    """Verify publish_clip and publish_clip_task have separate, un-collided registrations in Celery."""
    tasks = celery_app.tasks
    assert "publish_clip" in tasks, "Pipeline task 'publish_clip' must be registered in Celery"
    assert "publish_clip_task" in tasks, "Studio task 'publish_clip_task' must be registered in Celery"

    task_pipeline = tasks["publish_clip"]
    task_studio = tasks["publish_clip_task"]

    assert task_pipeline.name == "publish_clip"
    assert task_studio.name == "publish_clip_task"
    assert task_pipeline != task_studio, "Tasks must not reference the same underlying callable"


def test_publish_task_accepts_output_validation_dict_payload():
    """
    Verify publish_task correctly unpacks the dictionary result from output_validation_task
    without passing the dictionary to SQLAlchemy or psycopg2.
    """
    test_clip_id = str(uuid.uuid4())
    test_job_id = str(uuid.uuid4())
    
    dict_payload = {
        "clip_id": test_clip_id,
        "job_id": test_job_id,
        "final_storage_key": f"clips/{test_clip_id}.mp4",
        "status": "completed"
    }

    mock_self = MagicMock()
    mock_self.request.id = "mock_task_exec_123"

    with patch("backend.tasks.clip_tasks.SyncSessionLocal") as mock_sync_db, \
         patch("backend.tasks.clip_tasks.update_clip_status_sync") as mock_update_status, \
         patch("backend.tasks.clip_tasks.check_and_claim_execution", return_value=True), \
         patch("backend.tasks.clip_tasks.update_clip_publish_sync"), \
         patch("backend.tasks.clip_tasks.upload_short", return_value={"id": "mock_yt_vid", "url": "https://youtu.be/mock_yt_vid", "status": "published"}):
        
        # Mock session to verify filter_by query
        mock_session = MagicMock()
        mock_sync_db.return_value.__enter__.return_value = mock_session
        mock_clip = MagicMock()
        mock_clip.id = test_clip_id
        mock_clip.output_path = "/tmp/test.mp4"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_clip

        result = publish_task(mock_self, dict_payload)

        # Confirm update_clip_status_sync was called with string clip_id, NOT a dict
        mock_update_status.assert_any_call(test_clip_id, "publishing")
        for call_args in mock_update_status.call_args_list:
            assert isinstance(call_args[0][0], str)
            assert not isinstance(call_args[0][0], dict)


def test_publish_clip_task_defensive_dict_unpacking():
    """
    Verify publish_clip_task safely unpacks a dictionary passed accidentally as pos_args[0]
    and extracts string clip_id without crashing with psycopg2 'can't adapt type dict'.
    """
    test_clip_id = str(uuid.uuid4())
    nested_dict_arg = {
        "clip_id": test_clip_id,
        "reframed_storage_key": "storage/reframed.mp4",
        "thumb_a_storage_key": "storage/thumb_a.png",
        "thumb_b_storage_key": "storage/thumb_b.png"
    }

    mock_self = MagicMock()
    mock_self.request.id = "mock_task_exec_456"
    mock_self.request.retries = 0

    with patch("backend.tasks.clip_tasks.SyncSessionLocal") as mock_sync_db:
        mock_session = MagicMock()
        mock_sync_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = None

        # Call with dict as pos_arg (the exact historical failure mode)
        res = publish_clip_task(mock_self, nested_dict_arg)

        # Must safely return a failure dict and NOT crash with ProgrammingError
        assert res["status"] == "failed"
        assert res["clip_id"] == test_clip_id
        assert res["error"] == "Clip not found"

        # Verify filter_by received the STRING clip_id, NOT the dict
        filter_kwargs = mock_session.query.return_value.filter_by.call_args[1]
        assert filter_kwargs["id"] == test_clip_id
        assert isinstance(filter_kwargs["id"], str)


def test_publish_tasks_reject_invalid_non_string_ids():
    """Verify that completely invalid non-string IDs return a clean error without touching the DB."""
    mock_self = MagicMock()
    mock_self.request.id = "mock_invalid_task"

    # Malformed payload missing clip_id
    bad_payload = {"unknown_key": 12345}

    res_pipeline = publish_task(mock_self, bad_payload)
    assert res_pipeline["status"] == "failed"
    assert "Invalid clip_id" in res_pipeline["error"]

    res_studio = publish_clip_task(mock_self, bad_payload)
    assert res_studio["status"] == "failed"
    assert "Invalid clip_id" in res_studio["error"]


def test_error_sanitizer_masks_technical_driver_leaks():
    """Verify sanitizer masks driver errors and preserves safe domain errors."""
    raw_psycopg2_err = (
        "ProgrammingError: (psycopg2.ProgrammingError) can't adapt type 'dict' "
        "[SQL: SELECT clips.id AS clips_id FROM clips WHERE clips.id = %(id_1)s LIMIT %(param_1)s FOR UPDATE] "
        "[parameters: {'id_1': {'clip_id': 'dfbfbf16-3e75-4089-a5e3-4f1e0394c8e7'}, 'param_1': 1}]"
    )
    sanitized = sanitize_user_facing_error(raw_psycopg2_err)
    assert sanitized == DEFAULT_SANITIZED_ERROR
    assert "psycopg2" not in sanitized
    assert "can't adapt type" not in sanitized
    assert "[SQL:" not in sanitized
    assert "SELECT" not in sanitized

    raw_partial = "ProgrammingError: (psycopg2.ProgrammingError) can't adapt type 'dict'"
    assert sanitize_user_facing_error(raw_partial) == DEFAULT_SANITIZED_ERROR

    # Safe domain error must be preserved
    domain_err = "OutputValidatorError: Duration 30.2s exceeds maximum Shorts duration limit of 30.0s"
    assert sanitize_user_facing_error(domain_err) == domain_err

    user_cancel = "Cancelled by user"
    assert sanitize_user_facing_error(user_cancel) == user_cancel
