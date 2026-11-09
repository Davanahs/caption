"""
Phase 3 Comprehensive Test Suite:
- PREREQ-011: Real Media Preflight Validation
- PREREQ-003: Prevent Self-Ingestion in Channel Monitor & Output Provenance
- PREREQ-005: Safe Scheduling (Non-null, future ISO timestamp & verified artifact)
- PREREQ-009: Dubbing Preflight (Render-complete & base file check before TTS)
- PREREQ-010: Correct Retry by Source Type (YouTube downloader vs local filesystem)
"""
import pytest
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from backend.tasks.video_tasks import validate_media_task
from backend.services.channel_monitor import run_channel_monitor
from backend.api.routes.publish import schedule_publish, PublishRequest
from backend.api.routes.dubbing import trigger_dubbing
from backend.models.dubbing import DubbingRequest
from backend.tasks.dubbing_tasks import generate_dubbing_variant_task
from backend.api.routes.jobs import retry_failed_job
from backend.models.models import Channel, Video, Clip, Job, JobStatus


def _mock_async_session_for_scalar(scalar_returns):
    """Helper to mock an AsyncSession where each await db.execute(...) returns a scalar from scalar_returns."""
    mock_db = AsyncMock()
    if not isinstance(scalar_returns, list):
        scalar_returns = [scalar_returns]

    mock_results = []
    for val in scalar_returns:
        res = MagicMock()
        res.scalar_one_or_none.return_value = val
        res.scalar_one.return_value = val
        res.scalars.return_value.first.return_value = val
        res.scalars.return_value.all.return_value = [val] if val is not None else []
        mock_results.append(res)

    mock_db.execute = AsyncMock(side_effect=mock_results)
    return mock_db


class TestPhase3MediaValidation:
    """PREREQ-011: Media preflight validation in validate_media_task."""

    @patch("backend.models.database.SyncSessionLocal")
    @patch("backend.models.artifact_sync.managed_download_sync")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    def test_validate_media_task_success(self, mock_stat, mock_exists, mock_run, mock_managed_dl, mock_session_cls):
        mock_stat.return_value = MagicMock(st_size=50000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "format": {"duration": "120.5"},
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080},
                    {"codec_type": "audio"}
                ]
            })
        )
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = "/tmp/fake_video.mp4"
        mock_managed_dl.return_value = mock_ctx

        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        fake_video = MagicMock(id="v1", local_path="uploads/v1/source.mp4", duration=0.0)
        mock_session.query.return_value.filter_by.return_value.first.return_value = fake_video

        mock_task = MagicMock()
        result_in = {"video_id": "v1", "job_id": "j1", "is_test": True}

        with patch("backend.tasks.video_tasks.update_job_sync"):
            out = validate_media_task(result_in)
            assert out["video_id"] == "v1"
            assert fake_video.duration == 120.5

    @patch("backend.models.database.SyncSessionLocal")
    @patch("backend.models.artifact_sync.managed_download_sync")
    @patch("pathlib.Path.exists", return_value=False)
    def test_validate_media_task_fails_missing_file(self, mock_exists, mock_managed_dl, mock_session_cls):
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = "/tmp/missing.mp4"
        mock_managed_dl.return_value = mock_ctx

        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        fake_video = MagicMock(id="v2", local_path="uploads/v2/source.mp4", duration=0.0)
        mock_session.query.return_value.filter_by.return_value.first.return_value = fake_video

        mock_task = MagicMock()
        result_in = {"video_id": "v2", "job_id": "j2"}

        with patch("backend.tasks.video_tasks.update_job_sync"):
            with pytest.raises(RuntimeError) as exc_info:
                validate_media_task(result_in)
            assert "missing or 0 bytes" in str(exc_info.value)

    @patch("backend.models.database.SyncSessionLocal")
    @patch("backend.models.artifact_sync.managed_download_sync")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    def test_validate_media_task_fails_no_video_stream(self, mock_stat, mock_exists, mock_run, mock_managed_dl, mock_session_cls):
        mock_stat.return_value = MagicMock(st_size=50000)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "format": {"duration": "120.5"},
                "streams": [
                    {"codec_type": "audio"}
                ]
            })
        )
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = "/tmp/audio_only.mp4"
        mock_managed_dl.return_value = mock_ctx

        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        fake_video = MagicMock(id="v3", local_path="uploads/v3/source.mp4", duration=0.0)
        mock_session.query.return_value.filter_by.return_value.first.return_value = fake_video

        mock_task = MagicMock()
        result_in = {"video_id": "v3", "job_id": "j3"}

        with patch("backend.tasks.video_tasks.update_job_sync"):
            with pytest.raises(RuntimeError) as exc_info:
                validate_media_task(result_in)
            assert "Invalid or missing video stream" in str(exc_info.value)


class TestPhase3SelfIngestionPrevention:
    """PREREQ-003: Prevent self-ingestion in channel monitor."""

    @pytest.mark.asyncio
    async def test_run_channel_monitor_excludes_destinations(self):
        mock_db = AsyncMock()
        mock_source_ch = MagicMock(id="src_1", channel_name="Source Channel", is_active=True, is_destination=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_source_ch]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("backend.services.channel_monitor.check_channel_for_new_videos", AsyncMock(return_value=[])) as mock_check:
            await run_channel_monitor(mock_db)
            executed_stmt = mock_db.execute.call_args[0][0]
            stmt_str = str(executed_stmt).lower()
            assert "is_destination" in stmt_str
            mock_check.assert_called_once_with(mock_source_ch, mock_db)


class TestPhase3SafeScheduling:
    """PREREQ-005: Safe scheduling boundary validation."""

    @pytest.mark.asyncio
    async def test_schedule_rejects_missing_or_empty_timestamp(self):
        mock_clip = MagicMock(id="c1", status="completed", output_path="/tmp/c1.mp4", publish_destination_id="d1")
        mock_dest = MagicMock(id="d1", youtube_channel_id="UC_dest", is_destination=True, is_active=True)
        mock_db = _mock_async_session_for_scalar([mock_clip, mock_dest])

        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            req = PublishRequest(clip_id="c1", scheduled_at=None, destination_channel_id="d1")
            with pytest.raises(HTTPException) as exc_info:
                await schedule_publish(req, mock_db)
            assert exc_info.value.status_code == 400
            assert "scheduled_at is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_schedule_rejects_past_timestamp(self):
        mock_clip = MagicMock(id="c1", status="completed", output_path="/tmp/c1.mp4", publish_destination_id="d1")
        mock_dest = MagicMock(id="d1", youtube_channel_id="UC_dest", is_destination=True, is_active=True)
        mock_db = _mock_async_session_for_scalar([mock_clip, mock_dest])

        past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            req = PublishRequest(clip_id="c1", scheduled_at=past_iso, destination_channel_id="d1")
            with pytest.raises(HTTPException) as exc_info:
                await schedule_publish(req, mock_db)
            assert exc_info.value.status_code == 400
            assert "in the future" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_schedule_rejects_unrendered_clip(self):
        mock_clip = MagicMock(id="c1", status="reframing", output_path=None, publish_destination_id="d1")
        mock_dest = MagicMock(id="d1", youtube_channel_id="UC_dest", is_destination=True, is_active=True)
        mock_db = _mock_async_session_for_scalar([mock_clip, mock_dest])

        future_iso = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            req = PublishRequest(clip_id="c1", scheduled_at=future_iso, destination_channel_id="d1")
            with pytest.raises(HTTPException) as exc_info:
                await schedule_publish(req, mock_db)
            assert exc_info.value.status_code == 400
            assert "rendering is not complete" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    async def test_schedule_accepts_valid_future_timestamp_with_artifact(self, mock_stat, mock_exists):
        mock_stat.return_value = MagicMock(st_size=1024)
        mock_clip = MagicMock(id="c1", status="completed", output_path="/tmp/c1.mp4", publish_destination_id="d1")
        mock_dest = MagicMock(id="d1", youtube_channel_id="UC_dest", is_destination=True, is_active=True)
        mock_db = _mock_async_session_for_scalar([mock_clip, mock_dest])

        future_iso = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            req = PublishRequest(clip_id="c1", scheduled_at=future_iso, destination_channel_id="d1")
            res = await schedule_publish(req, mock_db)
            assert res["message"] == "Clip scheduled"
            assert mock_clip.publish_status == "queued"
            assert mock_clip.scheduled_at is not None


class TestPhase3DubbingPreflight:
    """PREREQ-009: Dubbing preflight validation."""

    @pytest.mark.asyncio
    async def test_trigger_dubbing_rejects_unrendered_clip(self):
        mock_clip = MagicMock(id="c_unrendered", status="reframing", output_path=None)
        mock_db = _mock_async_session_for_scalar([mock_clip])

        req = DubbingRequest(clip_id="c_unrendered", target_language="es")
        with pytest.raises(HTTPException) as exc_info:
            await trigger_dubbing("c_unrendered", req, mock_db)
        assert exc_info.value.status_code == 400
        assert "not render-complete" in exc_info.value.detail

    def test_dubbing_task_preflight_fails_missing_base_file_before_tts(self):
        """Worker task must reject missing base video before invoking TTS or paid services."""
        with patch("backend.tasks.dubbing_tasks.SyncSessionLocal") as mock_session_cls, \
             patch("backend.tasks.dubbing_tasks.check_and_claim_execution", return_value=MagicMock()), \
             patch("backend.services.dubbing_engine.execute_dubbing_plan") as mock_tts_plan, \
             patch("pathlib.Path.exists", return_value=False):

            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session
            fake_clip = MagicMock(id="c_base_missing", status="completed", output_path="/tmp/nonexistent.mp4")
            mock_session.query.return_value.filter.return_value.first.return_value = fake_clip

            req_dict = {
                "clip_id": "c_base_missing",
                "target_language": "es",
                "voice_provider": "edge_tts",
                "voice_id": "es-ES-AlvaroNeural"
            }
            with pytest.raises(ValueError) as exc_info:
                generate_dubbing_variant_task(req_dict)
            assert "does not exist or is empty on disk" in str(exc_info.value)
            mock_tts_plan.assert_not_called()


class TestPhase3SourceTypeAwareRetry:
    """PREREQ-010: Correct retry by source type."""

    @pytest.mark.asyncio
    async def test_retry_youtube_job_dispatches_with_youtube_url(self):
        job = MagicMock(
            id="j_yt",
            status=JobStatus.FAILED.value,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            source_title="YouTube Video",
            config=json.dumps({"source_type": "youtube", "clip_mode": "ai_highlights"}),
            video_id=None
        )
        mock_db = _mock_async_session_for_scalar([job])

        with patch("backend.services.provenance.check_is_clipforge_short", AsyncMock(return_value=(False, None, None))), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:

            mock_apply.return_value = MagicMock(id="celery_yt_task")
            res = await retry_failed_job("j_yt", mock_db)
            assert res["status"] == "retried"
            assert res["source_type"] == "youtube"

            kwargs = mock_apply.call_args[1]["kwargs"]
            assert "youtube_url" in kwargs
            assert kwargs["youtube_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            assert "local_path" not in kwargs

    @pytest.mark.asyncio
    async def test_retry_local_job_fails_if_file_missing_on_disk(self):
        job = MagicMock(
            id="j_local_expired",
            status=JobStatus.FAILED.value,
            source_url="my_upload.mp4",
            source_title="my_upload.mp4",
            config=json.dumps({"source_type": "local", "local_path": "/tmp/expired.mp4"}),
            video_id=None
        )
        mock_db = _mock_async_session_for_scalar([job])

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await retry_failed_job("j_local_expired", mock_db)
            assert exc_info.value.status_code == 400
            assert "retained original file has expired or was removed" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("pathlib.Path.stat")
    async def test_retry_local_job_dispatches_with_local_path(self, mock_stat, mock_isfile, mock_exists):
        mock_stat.return_value = MagicMock(st_size=50000)
        job = MagicMock(
            id="j_local_ok",
            status=JobStatus.FAILED.value,
            source_url="local_video.mp4",
            source_title="local_video.mp4",
            config=json.dumps({"source_type": "local", "local_path": "/tmp/valid_local.mp4"}),
            video_id=None
        )
        mock_db = _mock_async_session_for_scalar([job])

        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
            mock_apply.return_value = MagicMock(id="celery_local_task")
            res = await retry_failed_job("j_local_ok", mock_db)
            assert res["status"] == "retried"
            assert res["source_type"] == "local"

            kwargs = mock_apply.call_args[1]["kwargs"]
            assert "local_path" in kwargs
            assert "youtube_url" not in kwargs
