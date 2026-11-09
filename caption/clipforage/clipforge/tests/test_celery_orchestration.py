import pytest
from unittest.mock import patch, MagicMock
from backend.models.db_sync import update_clip_status_sync, update_job_sync
from backend.models.models import Job, Clip, ClipStatus, JobStatus
from backend.tasks.orchestration import job_completion_aggregation_task

# Pytest fixtures and mocks
@pytest.fixture
def mock_db_session():
    # Mock SyncSessionLocal where it is used
    with patch("backend.models.db_sync.SyncSessionLocal") as mock_session_cls, \
         patch("backend.models.database.SyncSessionLocal") as mock_db_cls:
        
        mock_session = mock_session_cls.return_value.__enter__.return_value
        mock_db_session = mock_db_cls.return_value.__enter__.return_value
        
        yield mock_session, mock_db_session

def test_clip_status_valid_transition(mock_db_session):
    mock_sync_session, _ = mock_db_session
    mock_clip = Clip(id="c1", status=ClipStatus.PENDING.value)
    mock_sync_session.query.return_value.filter_by.return_value.first.return_value = mock_clip
    
    # pending -> reframing is valid
    assert update_clip_status_sync("c1", ClipStatus.REFRAMING.value) is True
    assert mock_clip.status == ClipStatus.REFRAMING.value

def test_clip_status_invalid_transition(mock_db_session):
    mock_sync_session, _ = mock_db_session
    mock_clip = Clip(id="c1", status=ClipStatus.COMPLETED.value)
    mock_sync_session.query.return_value.filter_by.return_value.first.return_value = mock_clip
    
    # completed -> rendering is invalid
    assert update_clip_status_sync("c1", ClipStatus.RENDERING.value) is False
    assert mock_clip.status == ClipStatus.COMPLETED.value

def test_clip_status_failure_transition(mock_db_session):
    mock_sync_session, _ = mock_db_session
    mock_clip = Clip(id="c1", status=ClipStatus.RENDERING.value)
    mock_sync_session.query.return_value.filter_by.return_value.first.return_value = mock_clip
    
    # rendering -> failed is valid
    assert update_clip_status_sync("c1", ClipStatus.FAILED.value) is True
    assert mock_clip.status == ClipStatus.FAILED.value

@patch("backend.tasks.orchestration.update_job_sync")
def test_job_completion_aggregation_all_success(mock_update_job, mock_db_session):
    _, mock_orch_session = mock_db_session
    
    # 3 completed clips
    mock_orch_session.query.return_value.filter_by.return_value.all.return_value = [
        Clip(status=ClipStatus.COMPLETED.value),
        Clip(status=ClipStatus.COMPLETED.value),
        Clip(status=ClipStatus.COMPLETED.value),
    ]
    
    job_completion_aggregation_task([], "j1")
    
    mock_update_job.assert_called_once_with("j1", "completed", 100, "All clips processed successfully")

@patch("backend.tasks.orchestration.update_job_sync")
def test_job_completion_aggregation_partial_failure(mock_update_job, mock_db_session):
    _, mock_orch_session = mock_db_session
    
    # 2 completed, 1 failed
    mock_orch_session.query.return_value.filter_by.return_value.all.return_value = [
        Clip(status=ClipStatus.COMPLETED.value),
        Clip(status=ClipStatus.FAILED.value),
        Clip(status=ClipStatus.COMPLETED.value),
    ]
    
    job_completion_aggregation_task([], "j1")
    
    mock_update_job.assert_called_once_with("j1", "completed_with_failures", 100, "1/3 clips failed")

@patch("backend.tasks.orchestration.update_job_sync")
def test_job_completion_aggregation_all_failure(mock_update_job, mock_db_session):
    _, mock_orch_session = mock_db_session
    
    # All failed
    mock_orch_session.query.return_value.filter_by.return_value.all.return_value = [
        Clip(status=ClipStatus.FAILED.value),
        Clip(status=ClipStatus.FAILED.value),
    ]
    
    job_completion_aggregation_task([], "j1")
    
    mock_update_job.assert_called_once_with("j1", "failed", 100, "All 2 clips failed")
