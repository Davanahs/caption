"""
test_podcast_layout_pipeline.py
===============================
Unit and integration tests for the Podcast & Interview Manual Area Selection layout feature.
Verifies API ingestion, coordinate validation, LayoutPlan generation, and reframe_task routing.
"""
import pytest
import json
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from backend.models.layout import LayoutPlan, LayoutMode, ScaleMode, BackgroundPolicy
from backend.services.layout_engine import LayoutEngine


# ==========================================
# 1. API INTAKE & VALIDATION TESTS
# ==========================================

class TestPodcastApiValidation:

    @pytest.fixture(autouse=True)
    def mock_ai_provider(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            yield

    @pytest.mark.asyncio
    async def test_valid_podcast_regions_accepted(self):
        """Verify valid regions JSON string is accepted and correctly stored in job configuration."""
        from backend.api.routes.videos import process_youtube_url

        valid_regions = [
            {"id": "area-1", "label": "Speaker 1", "x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8},
            {"id": "area-2", "label": "Speaker 2", "x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8},
        ]
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)), \
             patch("backend.services.llm_router.is_ai_provider_configured", return_value=True), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "celery-task-123"
            mock_apply.return_value = mock_task

            res = await process_youtube_url(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=json.dumps(valid_regions),
                podcast_composition="stacked",
                db=mock_db
            )

            assert "job_id" in res
            assert res["message"] == "Processing started"

            # Check that Job added to db has config containing regions and mode
            added_job = mock_db.add.call_args[0][0]
            config = json.loads(added_job.config)
            assert config["mode"] == "podcast_interview"
            assert config["podcast_composition"] == "stacked"
            assert len(config["regions"]) == 2
            assert config["regions"][0]["label"] == "Speaker 1"
            assert config["regions"][1]["label"] == "Speaker 2"

            # Check celery task kwargs
            kwargs = mock_apply.call_args[1]["kwargs"]
            assert kwargs["regions"] == config["regions"]
            assert kwargs["podcast_composition"] == "stacked"

    @pytest.mark.asyncio
    async def test_invalid_regions_json_rejected(self):
        """Verify malformed JSON in regions raises HTTP 400 before queuing."""
        from backend.api.routes.videos import process_youtube_url

        mock_db = AsyncMock()
        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)):
            with pytest.raises(HTTPException) as exc:
                await process_youtube_url(
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    regions="not-valid-json",
                    db=mock_db
                )
            assert exc.value.status_code == 400
            assert "Invalid regions configuration" in exc.value.detail

    @pytest.mark.asyncio
    async def test_negative_coordinates_rejected(self):
        """Verify negative coordinates are rejected with HTTP 400."""
        from backend.api.routes.videos import process_youtube_url

        invalid_regions = [
            {"id": "area-1", "x": -0.1, "y": 0.2, "width": 0.4, "height": 0.6}
        ]
        mock_db = AsyncMock()
        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)):
            with pytest.raises(HTTPException) as exc:
                await process_youtube_url(
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    regions=json.dumps(invalid_regions),
                    db=mock_db
                )
            assert exc.value.status_code == 400
            assert "out of [0, 1] range" in exc.value.detail

    @pytest.mark.asyncio
    async def test_zero_dimension_region_rejected(self):
        """Verify zero width or height is rejected with HTTP 400."""
        from backend.api.routes.videos import process_youtube_url

        invalid_regions = [
            {"id": "area-1", "x": 0.1, "y": 0.2, "width": 0.0, "height": 0.6}
        ]
        mock_db = AsyncMock()
        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)):
            with pytest.raises(HTTPException) as exc:
                await process_youtube_url(
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    regions=json.dumps(invalid_regions),
                    db=mock_db
                )
            assert exc.value.status_code == 400
            assert "must be positive" in exc.value.detail

    @pytest.mark.asyncio
    async def test_standard_url_processing_preserved(self):
        """Verify submitting URL without regions keeps standard mode intact."""
        from backend.api.routes.videos import process_youtube_url

        mock_db = AsyncMock()
        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
            mock_apply.return_value = MagicMock(id="task-standard-1")

            res = await process_youtube_url(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                db=mock_db
            )
            added_job = mock_db.add.call_args[0][0]
            config = json.loads(added_job.config)
            assert config["mode"] == "standard"
            assert config["regions"] is None


# ==========================================
# 2. LAYOUT ENGINE PODCAST PLAN TESTS
# ==========================================

class TestPodcastLayoutPlan:

    def test_single_speaker_focus_plan(self):
        """Verify single region frames to 1080x1920 with exact crop coords."""
        regions = [{"id": "speaker1", "x": 0.2, "y": 0.1, "width": 0.5, "height": 0.8}]
        plan = LayoutEngine.create_podcast_plan(
            regions_normalized=regions,
            source_w=1920,
            source_h=1080,
            composition="single_region",
            canvas_w=1080,
            canvas_h=1920
        )
        assert plan.mode == LayoutMode.CENTER_CROP
        assert len(plan.regions) == 1
        r = plan.regions[0]
        assert r.w == 1080 and r.h == 1920
        assert r.scale_mode == ScaleMode.CONTAIN
        cx, cy, cw, ch = r.crop_coords
        assert cx == 384
        assert cy == 108
        assert cw == 960
        assert ch == 864
        # Even coordinates check
        assert all(v % 2 == 0 for v in (cx, cy, cw, ch))

    def test_two_speaker_stacked_plan(self):
        """Verify two regions split vertical canvas into 1080x960 upper and lower frames."""
        regions = [
            {"id": "spk1", "label": "Guest", "x": 0.05, "y": 0.15, "width": 0.42, "height": 0.75},
            {"id": "spk2", "label": "Host", "x": 0.53, "y": 0.15, "width": 0.42, "height": 0.75},
        ]
        plan = LayoutEngine.create_podcast_plan(
            regions_normalized=regions,
            source_w=1920,
            source_h=1080,
            composition="stacked",
            canvas_w=1080,
            canvas_h=1920
        )
        assert plan.mode == LayoutMode.STACKED_16_9
        assert len(plan.regions) == 2
        r1, r2 = plan.regions[0], plan.regions[1]
        assert r1.x == 0 and r1.y == 0 and r1.w == 1080 and r1.h == 960
        assert r2.x == 0 and r2.y == 960 and r2.w == 1080 and r2.h == 960
        assert r1.crop_coords is not None
        assert r2.crop_coords is not None
        assert r1.crop_coords != r2.crop_coords

    def test_ffmpeg_filtergraph_contains_both_crops_and_overlays(self):
        """Verify FFmpeg filter graph builds with 2 inputs, crops, scales, and stacked overlays."""
        from pathlib import Path
        regions = [
            {"id": "spk1", "x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8},
            {"id": "spk2", "x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8},
        ]
        plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080, composition="stacked")
        fg = LayoutEngine.build_render_graph(plan, [Path("in1.mp4"), Path("in2.mp4")])

        # Verify background initialization
        assert "color=c=black:s=1080x1920[bg]" in fg
        # Verify first region crop & scale to 1080x960
        assert "[0:v]crop=" in fg
        assert "scale=1080:960" in fg
        assert "overlay=x=0:y=0:shortest=1" in fg
        # Verify second region crop & scale to 1080x960 overlaid at y=960
        assert "[1:v]crop=" in fg
        assert "overlay=x=0:y=960:eof_action=pass" in fg
        # Verify final output setsar=1
        assert "setsar=1[outv]" in fg


# ==========================================
# 3. WORKER REFRAME TASK ROUTING TESTS
# ==========================================

class TestPodcastWorkerReframeRouting:

    def test_reframe_task_builds_podcast_plan_when_regions_present(self):
        """Verify reframe_task detects Job.config regions and invokes create_podcast_plan."""
        from backend.tasks.clip_tasks import reframe_task

        regions = [
            {"id": "r1", "label": "Host", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7},
            {"id": "r2", "label": "Guest", "x": 0.55, "y": 0.1, "width": 0.35, "height": 0.7},
        ]
        config_data = {
            "mode": "podcast_interview",
            "podcast_composition": "stacked",
            "regions": regions
        }

        mock_job = MagicMock()
        mock_job.id = "job-podcast-test"
        mock_job.config = json.dumps(config_data)
        mock_job.status = "processing"

        mock_clip = MagicMock()
        mock_clip.id = "clip-123"
        mock_clip.video_id = "video-456"
        mock_clip.start_time = 10.0
        mock_clip.end_time = 40.0

        mock_video = MagicMock()
        mock_video.id = "video-456"
        mock_video.local_path = "uploads/video-456/source.mp4"

        from backend.models.models import Clip, Video, Job
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        def mock_query(model):
            m = MagicMock()
            m_name = getattr(model, "__name__", "")
            if m_name == "Clip" or model == Clip:
                m.filter_by.return_value.first.return_value = mock_clip
            elif m_name == "Video" or model == Video:
                m.filter_by.return_value.first.return_value = mock_video
            elif m_name == "Job" or model == Job:
                m.filter_by.return_value.first.return_value = mock_job
                m.filter_by.return_value.order_by.return_value.first.return_value = mock_job
            return m
        mock_session.query.side_effect = mock_query

        with patch("backend.models.database.SyncSessionLocal", return_value=mock_session), \
             patch("backend.models.db_sync.update_clip_status_sync"), \
             patch("backend.core.task_execution.check_and_claim_execution"), \
             patch("backend.models.artifact_sync.check_artifact_exists_sync", return_value=False), \
             patch("backend.models.artifact_sync.managed_download_sync") as mock_dl, \
             patch("backend.models.artifact_sync.managed_upload_sync") as mock_ul, \
             patch("backend.services.clip_cutter.cut_clip", new_callable=AsyncMock), \
             patch("backend.services.clip_cutter.get_video_dimensions", new_callable=AsyncMock, return_value=(1920, 1080)), \
             patch("backend.services.reframe_engine.reframe_to_vertical", new_callable=AsyncMock) as mock_reframe, \
             patch("backend.services.layout_engine.LayoutEngine.create_podcast_plan", wraps=LayoutEngine.create_podcast_plan) as mock_create_plan:

            mock_dl.return_value.__enter__.return_value = "C:/tmp/mock_source.mp4"
            mock_ul.return_value.__enter__.return_value = "C:/tmp/mock_reframed.mp4"

            # Execute reframe_task directly
            mock_self = MagicMock()
            mock_self.request.id = "task-reframe-1"
            mock_self.request.hostname = "worker-1"

            result = reframe_task._orig_run(clip_id="clip-123", job_id="job-podcast-test")

            # Assert create_podcast_plan was called with parsed regions
            mock_create_plan.assert_called_once()
            call_kwargs = mock_create_plan.call_args[1]
            assert call_kwargs["regions_normalized"] == regions
            assert call_kwargs["source_w"] == 1920
            assert call_kwargs["source_h"] == 1080

            # Assert reframe_to_vertical was invoked with the generated LayoutPlan
            mock_reframe.assert_called_once()
            reframe_plan = mock_reframe.call_args[1]["plan"]
            assert reframe_plan is not None
            assert reframe_plan.mode == LayoutMode.STACKED_16_9
            assert len(reframe_plan.regions) == 2
