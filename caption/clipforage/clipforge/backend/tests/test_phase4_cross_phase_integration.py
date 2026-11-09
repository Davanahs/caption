"""
Phase 4 Cross-Phase Integration and Operational Consistency Test Suite

Validates integration contracts across API, worker, database, scheduler, AI router, and publisher:
1. Celery task registry integrity and distinct task registrations.
2. AI provider intake validation and failover handling without heuristic fallback.
3. Media preflight gating preventing downstream transcription/rendering.
4. Execution-time destination credential validation and defense against global token fallback.
5. Missing artifact checks for scheduling, dubbing, and publishing.
6. Source-type aware retry routing (YouTube URL vs local filesystem).
"""
import pytest
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from backend.tasks.process_video import celery_app
from backend.models.models import Channel, Video, Clip, Job, JobStatus
from backend.services.llm_router import is_ai_provider_configured, get_configured_providers
from backend.services.clip_scorer import ai_score_candidates
from backend.tasks.video_tasks import validate_media_task
from backend.tasks.clip_tasks import publish_clip_task, publish_task
from backend.tasks.dubbing_tasks import generate_dubbing_variant_task
from backend.api.routes.publish import schedule_publish, PublishRequest
from backend.api.routes.jobs import retry_failed_job
from backend.api.routes.videos import validate_clip_mode_and_duration


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


class TestPhase4TaskRegistryContracts:
    """Verify Celery task registry contains all required tasks with correct signatures."""

    def test_all_core_tasks_registered(self):
        registered = celery_app.tasks
        required_tasks = [
            "validate_media_task",
            "download_task",
            "transcription_task",
            "reframe_clip",
            "render_clip",
            "validate_output",
            "publish_clip",
            "publish_clip_task",
            "backend.tasks.dubbing_tasks.generate_dubbing_variant_task",
        ]
        for task_name in required_tasks:
            matching = [t for t in registered.keys() if t == task_name or t.endswith(f".{task_name}")]
            assert len(matching) > 0, f"Missing registered task: {task_name} in {list(registered.keys())}"

    def test_pipeline_and_studio_publishing_tasks_distinct(self):
        tasks = celery_app.tasks
        assert "publish_clip" in tasks
        assert "publish_clip_task" in tasks
        assert tasks["publish_clip"] != tasks["publish_clip_task"]


class TestPhase4AIIntakeAndScoringContract:
    """Verify AI provider configuration check at intake and zero heuristic fallback."""

    def test_ai_highlights_intake_fails_fast_when_unconfigured(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                validate_clip_mode_and_duration("ai_highlights", max_clip_duration=30, target_duration=None)
            assert exc_info.value.status_code == 503
            assert "No AI provider configured" in exc_info.value.detail

    def test_equal_split_intake_succeeds_without_ai_provider(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=False):
            mode = validate_clip_mode_and_duration("equal_split", max_clip_duration=None, target_duration=45.0)
            assert mode == "equal_split"

    @pytest.mark.asyncio
    async def test_clip_scorer_raises_runtime_error_on_empty_ai_response(self):
        mock_candidates = [{"start": 0, "end": 30, "duration": 30, "text": "hello"}]
        with patch("backend.services.clip_scorer.route_and_generate", return_value=""):
            with pytest.raises(RuntimeError) as exc_info:
                await ai_score_candidates(mock_candidates, top_n=1)
            assert "Heuristic scoring fallback is strictly forbidden" in str(exc_info.value)


class TestPhase4PreflightGatingContract:
    """Verify media preflight stops processing before downstream tasks."""

    @patch("backend.models.database.SyncSessionLocal")
    @patch("backend.models.artifact_sync.managed_download_sync")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    @patch("subprocess.run")
    def test_preflight_corrupt_video_fails_and_updates_job(self, mock_run, mock_stat, mock_exists, mock_managed_dl, mock_session_cls):
        mock_stat.return_value = MagicMock(st_size=1024)
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Corrupt moov atom")

        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = "/tmp/corrupt.mp4"
        mock_managed_dl.return_value = mock_ctx

        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        fake_video = MagicMock(id="v_corrupt", local_path="uploads/corrupt.mp4")
        mock_session.query.return_value.filter_by.return_value.first.return_value = fake_video

        with patch("backend.tasks.video_tasks.update_job_sync") as mock_update:
            with pytest.raises(RuntimeError) as exc:
                validate_media_task({"video_id": "v_corrupt", "job_id": "j_corrupt"})
            assert "FFprobe failed" in str(exc.value)
            # Verify update_job_sync was called with 'failed'
            failed_calls = [c for c in mock_update.call_args_list if len(c[0]) > 1 and c[0][1] == "failed"]
            assert len(failed_calls) > 0


class TestPhase4PublishingSafetyIntegration:
    """Verify destination validation at execution time, credential validation, and no token fallback."""

    @patch("backend.models.database.SyncSessionLocal")
    def test_publish_fails_fast_when_destination_disconnected_before_exec(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session

        fake_clip = MagicMock(id="c_pub", publish_destination_id="dest_inactive", output_path="/tmp/f.mp4", status="completed")
        mock_session.query.return_value.filter_by.return_value.first.return_value = fake_clip
        # Channel filter returns None
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch("pathlib.Path.exists", return_value=True):
            res = publish_clip_task(clip_id="c_pub", channel_id="dest_inactive")
            assert res["status"] == "failed"
            assert "not found, inactive, or not registered as destination" in res["error"]

    @patch("backend.models.database.SyncSessionLocal")
    @patch("backend.services.publisher.upload_short")
    def test_publish_fails_without_fallback_when_credentials_invalid(self, mock_upload, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session

        fake_clip = MagicMock(id="c_pub_2", publish_destination_id="dest_bad_creds", output_path="/tmp/f2.mp4", status="completed")
        fake_channel = MagicMock(
            id="dest_bad_creds",
            youtube_channel_id="UC_dest_bad_creds",
            is_active=True,
            is_destination=True,
            credentials_json="invalid json"
        )
        mock_session.query.return_value.filter_by.return_value.first.return_value = fake_clip
        mock_session.query.return_value.filter.return_value.first.return_value = fake_channel

        with patch("pathlib.Path.exists", return_value=True):
            with patch("backend.services.publisher.check_channel_authorization", return_value=False):
                res = publish_clip_task(clip_id="c_pub_2", channel_id="dest_bad_creds")
                assert res["status"] == "failed"
                assert "lacks valid OAuth credentials" in res["error"]
                mock_upload.assert_not_called()


class TestPhase4ArtifactGuardIntegration:
    """Verify lost or missing output artifacts prevent scheduling, dubbing, and publishing."""

    @pytest.mark.asyncio
    @patch("pathlib.Path.exists", return_value=False)
    async def test_schedule_publish_rejects_missing_rendered_artifact(self, mock_exists):
        fake_clip = MagicMock(
            id="c_art",
            status="completed",
            output_path="/tmp/missing.mp4",
            publish_destination_id="ch_dest"
        )
        fake_dest = MagicMock(id="ch_dest", youtube_channel_id="UC_dest", is_active=True, is_destination=True)
        mock_db = _mock_async_session_for_scalar([fake_clip, fake_dest])

        future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        with patch("backend.services.publisher.check_channel_authorization", return_value=True):
            req = PublishRequest(clip_id="c_art", destination_channel_id="ch_dest", scheduled_at=future_time)
            with pytest.raises(HTTPException) as exc:
                await schedule_publish(req, mock_db)
            assert exc.value.status_code == 400
            assert "Rendered video artifact does not exist" in exc.value.detail

    def test_dubbing_task_aborts_immediately_on_missing_artifact(self):
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


class TestPhase4SourceTypeRetryIntegration:
    """Verify source-type routing during job retry."""

    @pytest.mark.asyncio
    async def test_youtube_job_retry_dispatches_with_youtube_url(self):
        job = MagicMock(
            id="j_yt",
            status=JobStatus.FAILED.value,
            source_url="https://youtube.com/watch?v=abc12345",
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
            assert kwargs["youtube_url"] == "https://youtube.com/watch?v=abc12345"
            assert "local_path" not in kwargs

    @pytest.mark.asyncio
    async def test_local_job_retry_dispatches_with_local_path(self):
        job = MagicMock(
            id="j_loc",
            status=JobStatus.FAILED.value,
            source_url="local_upload.mp4",
            source_title="local_upload.mp4",
            config=json.dumps({"source_type": "local", "local_path": "/tmp/valid_local.mp4"}),
            video_id=None
        )
        mock_db = _mock_async_session_for_scalar([job])

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.stat", return_value=MagicMock(st_size=50000)), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:

            mock_apply.return_value = MagicMock(id="celery_loc_task")
            res = await retry_failed_job("j_loc", mock_db)
            assert res["status"] == "retried"
            assert res["source_type"] == "local"

            kwargs = mock_apply.call_args[1]["kwargs"]
            assert "local_path" in kwargs
            assert "valid_local.mp4" in kwargs["local_path"]
            assert "youtube_url" not in kwargs
