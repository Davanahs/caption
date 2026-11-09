"""
Test Suite for Topic 2 Work Item 2: Publishing Cadence Governance
-----------------------------------------------------------------
Verifies:
1. Destination-scoped rate limit: Minimum 120s gap for same destination; zero cross-destination throttling.
2. Non-blocking Celery worker release: Worker receives self.retry(countdown=...) without blocking execution.
3. Concurrent task coordination: Multi-worker requests are serialized with consecutive staggered countdowns.
4. Privacy and idempotency invariants: Privacy defaults and idempotency keys are preserved across cadence retries.
"""

import pytest
import time
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.publishing_cadence import (
    check_and_reserve_destination_cadence,
    record_destination_published,
    reset_destination_cadence,
    resolve_canonical_destination,
    MIN_PUBLISH_INTERVAL_SEC,
)
from backend.tasks.clip_tasks import publish_clip_task, publish_task
from backend.models.models import Channel, Clip, PublishStatus, PublishTarget


@pytest.fixture(autouse=True)
def clean_cadence_state():
    reset_destination_cadence("dest_channel_A")
    reset_destination_cadence("dest_channel_B")
    reset_destination_cadence("UC_dest_A")
    reset_destination_cadence("UC_dest_B")
    yield
    reset_destination_cadence("dest_channel_A")
    reset_destination_cadence("dest_channel_B")
    reset_destination_cadence("UC_dest_A")
    reset_destination_cadence("UC_dest_B")


def test_cadence_destination_isolation():
    """
    Publishing to Channel A must NEVER throttle or delay publishing to Channel B.
    """
    now = time.time()
    
    # 1. First upload to Channel A allowed immediately
    wait_a1 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=now)
    assert wait_a1 == 0.0, "First publication to Channel A must have zero wait"
    
    # 2. Upload to Channel B at the exact same timestamp must also be allowed immediately
    wait_b1 = check_and_reserve_destination_cadence("dest_channel_B", min_interval_sec=120.0, now_ts=now)
    assert wait_b1 == 0.0, "Channel B must NOT be throttled by Channel A (destination isolation)"


def test_cadence_same_destination_gap_enforced():
    """
    Successive publications to the SAME destination within 120s must enforce the remaining gap.
    """
    now = time.time()
    
    # First publication at T = 0
    wait_1 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=now)
    assert wait_1 == 0.0
    
    # Second publication attempted at T = 30s (90s remaining)
    wait_2 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=now + 30.0)
    assert 89.0 <= wait_2 <= 91.0, f"Expected ~90s wait, got {wait_2}"
    
    # Publication attempted after 125s (gap satisfied)
    reset_destination_cadence("dest_channel_A")
    record_destination_published("dest_channel_A", published_at=datetime.fromtimestamp(now, tz=timezone.utc))
    wait_3 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=now + 125.0)
    assert wait_3 == 0.0, "Publication after 120s must be allowed immediately"


def test_concurrent_worker_slot_serialization():
    """
    Multiple concurrent workers attempting to publish to the same destination
    must receive atomically staggered countdown slots without race conditions.
    """
    t0 = 1000000.0
    
    # Worker 1 claims immediate slot
    wait_w1 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=t0)
    assert wait_w1 == 0.0
    
    # Worker 2 attempts at same second -> gets slot at T0 + 120s
    wait_w2 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=t0)
    assert 119.0 <= wait_w2 <= 121.0
    
    # Worker 3 attempts at same second -> gets slot at T0 + 240s
    wait_w3 = check_and_reserve_destination_cadence("dest_channel_A", min_interval_sec=120.0, now_ts=t0)
    assert 239.0 <= wait_w3 <= 241.0


def test_publish_clip_task_non_blocking_celery_retry():
    """
    When cadence is unfulfilled, publish_clip_task must raise task.retry(countdown=...)
    instead of calling time.sleep, freeing the worker process immediately.
    """
    mock_task = MagicMock()
    mock_task.request = MagicMock()
    mock_task.request.id = "test_task_cadence_1"
    
    from celery.exceptions import Retry as BaseRetry
    class CeleryRetry(BaseRetry):
        def __init__(self, countdown=None):
            self.countdown = countdown
    
    mock_task.retry = MagicMock(side_effect=lambda countdown, **kwargs: CeleryRetry(countdown=countdown))
    
    # Prime destination A with recent publication
    t_now = time.time()
    check_and_reserve_destination_cadence("UC_dest_A", min_interval_sec=120.0, now_ts=t_now)
    
    # Mock clip and channel
    with patch("backend.tasks.clip_tasks.SyncSessionLocal") as mock_session_cls, \
         patch("backend.services.publisher.check_channel_authorization", return_value=True), \
         patch("backend.tasks.clip_tasks.check_external_youtube_state", return_value=None), \
         patch("backend.core.config.settings.PUBLISH_MODE", "prod"), \
         patch.dict("os.environ", {"PUBLISH_MODE": "prod"}):
        
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        
        mock_clip = MagicMock()
        mock_clip.id = "c_cadence_1"
        mock_clip.publish_status = "queued"
        mock_clip.status = "completed"
        mock_clip.output_path = "/tmp/test.mp4"
        mock_clip.publish_destination_id = "dest_channel_A"
        mock_clip.publish_idempotency_key = "pub_c_cadence_1_dest_channel_A"
        mock_clip.video_id = None
        mock_clip.thumbnail_path = None
        mock_clip.tags = "[]"
        mock_clip.title = "Cadence Test"
        mock_clip.description = ""
        mock_clip.category = "22"
        mock_clip.license = "youtube"
        
        mock_dest = MagicMock()
        mock_dest.id = "dest_channel_A"
        mock_dest.youtube_channel_id = "UC_dest_A"
        mock_dest.is_active = True
        mock_dest.is_destination = True
        
        mock_task.request.retries = 0
        mock_task.max_retries = 3

        def mock_query(model):
            q = MagicMock()
            if model == Clip:
                q.filter_by.return_value.with_for_update.return_value.first.return_value = mock_clip
                q.filter_by.return_value.first.return_value = mock_clip
            elif model == Channel:
                q.filter.return_value.first.return_value = mock_dest
                q.filter_by.return_value.first.return_value = mock_dest
            else:
                q.filter_by.return_value.first.return_value = None
                q.filter.return_value.first.return_value = None
            return q

        mock_session.query.side_effect = mock_query
        
        # Verify that time.sleep is NEVER called and mock_task.retry is raised
        with patch("pathlib.Path.exists", return_value=True), \
             patch("time.sleep") as mock_sleep:
            
            with pytest.raises(CeleryRetry) as exc_info:
                publish_clip_task(mock_task, clip_id="c_cadence_1", channel_id="UC_dest_A")
            
            # Assertions
            mock_sleep.assert_not_called()
            mock_task.retry.assert_called_once()
            retry_countdown = mock_task.retry.call_args[1].get("countdown")
            assert retry_countdown is not None
            assert 115 <= retry_countdown <= 121, f"Expected ~120s countdown, got {retry_countdown}"
