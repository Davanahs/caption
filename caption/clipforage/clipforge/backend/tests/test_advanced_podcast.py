"""
test_advanced_podcast.py
========================
Unit and integration tests for the Advanced Podcast Engine:
Camera-Following, Speaker-Aware Vertical Reframing.

Verifies:
1. compute_normalized_hsv_hist: HSV histogram extraction and normalization
2. detect_camera_cuts: Cut detection and interval generation
3. extract_reference_signatures: Appearance signature generation for participants
4. calculate_9_16_crop_rect: 9:16 vertical crop bounds, even pixel alignment, clamping
5. classify_shot_interval: Speaker 1, Speaker 2, Two-shot, Unassigned classification
6. build_shot_schedule: End-to-end schedule building with review flags
7. render_camera_following_video: Filtergraph generation with continuous audio, no stacked panels, -sn flag
8. API validation: POST /api/videos/podcast/analyze-shots & POST /api/videos/url with shot_schedule
"""

import pytest
import sys
import json
import uuid
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.advanced_podcast_engine import (
    compute_normalized_hsv_hist,
    detect_camera_cuts,
    extract_reference_signatures,
    calculate_9_16_crop_rect,
    classify_shot_interval,
    build_shot_schedule,
    render_camera_following_video
)


# ==========================================
# 1. MATHEMATICAL & ALGORITHM UNIT TESTS
# ==========================================

class TestAdvancedPodcastCropMath:

    def test_calculate_9_16_crop_rect_center(self):
        """1080p source (1920x1080), center speaker at x=0.5."""
        rect = calculate_9_16_crop_rect(0.5, src_w=1920, src_h=1080)
        assert rect["h"] == 1080
        # 1080 * 9 / 16 = 607.5 -> rounded to 608 -> even: 606 or 608
        assert rect["w"] % 2 == 0
        assert rect["h"] % 2 == 0
        assert rect["x"] % 2 == 0
        # Centered: (1920 - rect['w']) // 2
        assert rect["x"] > 600 and rect["x"] < 700
        assert rect["x"] + rect["w"] <= 1920
        assert rect["y"] == 0

    def test_calculate_9_16_crop_rect_left_boundary_clamped(self):
        """Speaker on extreme left (x=0.0). Must clamp to x=0 and remain inside bounds."""
        rect = calculate_9_16_crop_rect(0.0, src_w=1920, src_h=1080)
        assert rect["x"] == 0
        assert rect["w"] % 2 == 0
        assert rect["x"] + rect["w"] <= 1920

    def test_calculate_9_16_crop_rect_right_boundary_clamped(self):
        """Speaker on extreme right (x=1.0). Must clamp to max x and remain inside bounds."""
        rect = calculate_9_16_crop_rect(1.0, src_w=1920, src_h=1080)
        assert rect["x"] + rect["w"] <= 1920
        assert rect["x"] == (1920 - rect["w"]) // 2 * 2  # Max clamped offset
        assert rect["w"] % 2 == 0

    def test_calculate_9_16_crop_rect_normalized_values(self):
        """Normalized values must be strictly in [0.0, 1.0]."""
        rect = calculate_9_16_crop_rect(0.35, src_w=1280, src_h=720)
        assert 0.0 <= rect["norm_x"] <= 1.0
        assert 0.0 <= rect["norm_y"] <= 1.0
        assert 0.0 < rect["norm_w"] <= 1.0
        assert 0.0 < rect["norm_h"] <= 1.0
        assert rect["norm_x"] + rect["norm_w"] <= 1.001


class TestAdvancedPodcastHistogram:

    def test_compute_normalized_hsv_hist_valid_bgr(self):
        """Valid BGR image produces normalized 2D HSV histogram."""
        synthetic_img = np.zeros((100, 100, 3), dtype=np.uint8)
        synthetic_img[:, :] = [255, 128, 0]  # solid blue-ish color
        hist = compute_normalized_hsv_hist(synthetic_img, h_bins=16, s_bins=16)
        assert hist is not None
        assert hist.shape == (16, 16)
        assert hist.max() <= 1.0

    def test_compute_normalized_hsv_hist_empty_or_none(self):
        """Empty or None image returns None."""
        assert compute_normalized_hsv_hist(None) is None
        empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
        assert compute_normalized_hsv_hist(empty_img) is None


# ==========================================
# 2. SHOT DETECTION & CLASSIFICATION TESTS
# ==========================================

class TestAdvancedPodcastClassification:

    def test_detect_camera_cuts_missing_file_raises(self, tmp_path):
        """Non-existent video file raises FileNotFoundError."""
        non_existent = tmp_path / "missing.mp4"
        with pytest.raises(FileNotFoundError):
            detect_camera_cuts(non_existent)

    def test_build_shot_schedule_empty_regions_raises(self, tmp_path):
        """Empty participant regions raises ValueError."""
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.touch()
        with pytest.raises(ValueError, match="At least one participant reference region is required"):
            build_shot_schedule(dummy_video, [])

    def test_classify_shot_interval_speaker_1_dominates(self, tmp_path):
        """When Speaker 1 matches frame best, shot is classified as speaker_1."""
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.touch()

        # Mock frame and comparison
        signatures = [
            {
                "track_id": "speaker_1",
                "label": "Speaker 1",
                "ref_rect": {"x": 0.1, "y": 0.2, "width": 0.35, "height": 0.6},
                "center_x_norm": 0.275,
                "hist": np.ones((24, 24), dtype=np.float32)
            },
            {
                "track_id": "speaker_2",
                "label": "Speaker 2",
                "ref_rect": {"x": 0.55, "y": 0.2, "width": 0.35, "height": 0.6},
                "center_x_norm": 0.725,
                "hist": np.zeros((24, 24), dtype=np.float32)
            }
        ]

        with patch("cv2.VideoCapture") as mock_cap_cls, \
             patch("cv2.compareHist", side_effect=[0.85, 0.20]):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.return_value = 30.0
            mock_frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128
            mock_cap.read.return_value = (True, mock_frame)
            mock_cap_cls.return_value = mock_cap

            res = classify_shot_interval(dummy_video, (0.0, 3.5), signatures, src_w=1280, src_h=720)

            assert res["active_track_id"] == "speaker_1"
            assert res["confidence"] == 0.85
            assert res["review_needed"] is False
            assert res["duration"] == 3.5
            assert "crop_rect" in res
            assert res["crop_rect"]["w"] % 2 == 0

    def test_classify_shot_interval_two_shot(self, tmp_path):
        """When both participants score high correlation, classifies as two_shot with center framing."""
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.touch()

        signatures = [
            {"track_id": "speaker_1", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.6}, "hist": np.ones((24, 24))},
            {"track_id": "speaker_2", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.6}, "hist": np.ones((24, 24))}
        ]

        with patch("cv2.VideoCapture") as mock_cap_cls, \
             patch("cv2.compareHist", side_effect=[0.72, 0.68]):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.return_value = 30.0
            mock_cap.read.return_value = (True, np.ones((720, 1280, 3), dtype=np.uint8))
            mock_cap_cls.return_value = mock_cap

            res = classify_shot_interval(dummy_video, (3.5, 7.0), signatures, src_w=1280, src_h=720)

            assert res["active_track_id"] == "two_shot"
            assert res["fallback_policy"] == "fit"
            assert res["confidence"] == pytest.approx(0.70, rel=1e-2)

    def test_classify_shot_interval_unassigned_cutaway(self, tmp_path):
        """When neither participant matches (cutaway shot), flags review_needed and unassigned."""
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.touch()

        signatures = [
            {"track_id": "speaker_1", "center_x_norm": 0.25, "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.6}, "hist": np.ones((24, 24))},
            {"track_id": "speaker_2", "center_x_norm": 0.75, "ref_rect": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.6}, "hist": np.ones((24, 24))}
        ]

        with patch("cv2.VideoCapture") as mock_cap_cls, \
             patch("cv2.compareHist", side_effect=[0.15, 0.12]):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.return_value = 30.0
            mock_cap.read.return_value = (True, np.ones((720, 1280, 3), dtype=np.uint8))
            mock_cap_cls.return_value = mock_cap

            res = classify_shot_interval(dummy_video, (7.0, 9.0), signatures, src_w=1280, src_h=720)

            assert res["active_track_id"] == "unassigned"
            assert res["review_needed"] is True


# ==========================================
# 3. RENDERING & FILTERGRAPH INVARIANTS
# ==========================================

class TestAdvancedPodcastRendering:

    @pytest.mark.asyncio
    async def test_render_camera_following_video_multi_shot_filtergraph(self, tmp_path):
        """
        Verify multi-shot render builds dynamic concat filtergraph:
        - Exactly 1 continuous audio stream: [0:a]atrim=start=...
        - Concat filter: concat=n=2:v=1:a=0[outv]
        - Strictly NO burned-in subtitles (-sn)
        """
        src_video = tmp_path / "src.mp4"
        src_video.touch()
        out_video = tmp_path / "rendered.mp4"

        shot_schedule = [
            {
                "start_time": 0.0,
                "end_time": 5.0,
                "crop_rect": {"x": 100, "y": 0, "w": 608, "h": 1080},
                "active_track_id": "speaker_1"
            },
            {
                "start_time": 5.0,
                "end_time": 10.0,
                "crop_rect": {"x": 800, "y": 0, "w": 608, "h": 1080},
                "active_track_id": "speaker_2"
            }
        ]

        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "success", "")

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):

            res = await render_camera_following_video(
                video_path=src_video,
                output_path=out_video,
                shot_schedule=shot_schedule,
                clip_start=0.0,
                clip_end=10.0
            )

            assert res == out_video
            assert captured_cmd is not None

            # Subtitle suppression invariant
            assert "-sn" in captured_cmd

            # Filter complex inspection
            filter_complex_idx = captured_cmd.index("-filter_complex")
            filtergraph = captured_cmd[filter_complex_idx + 1]

            # Continuous audio invariant
            assert "[0:a]atrim=start=0.0:end=10.0,asetpts=PTS-STARTPTS[outa]" in filtergraph

            # Dynamic visual concat invariant (2 shots -> n=2:v=1:a=0)
            assert "concat=n=2:v=1:a=0[outv]" in filtergraph

            # Both crops present in filtergraph
            assert "crop=608:1080:100:0" in filtergraph
            assert "crop=608:1080:800:0" in filtergraph

            # Single vertical output canvas (1080x1920)
            assert "scale=1080:1920" in filtergraph

    @pytest.mark.asyncio
    async def test_render_camera_following_video_single_shot(self, tmp_path):
        """Verify single shot uses single simple crop filter without concat."""
        src_video = tmp_path / "src.mp4"
        src_video.touch()
        out_video = tmp_path / "rendered.mp4"

        shot_schedule = [
            {
                "start_time": 0.0,
                "end_time": 15.0,
                "crop_rect": {"x": 200, "y": 0, "w": 608, "h": 1080},
                "active_track_id": "speaker_1"
            }
        ]

        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "success", "")

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):

            res = await render_camera_following_video(
                video_path=src_video,
                output_path=out_video,
                shot_schedule=shot_schedule,
                clip_start=0.0,
                clip_end=15.0
            )

            assert res == out_video
            assert "-sn" in captured_cmd
            vf_idx = captured_cmd.index("-vf")
            assert "crop=608:1080:200:0,scale=1080:1920" in captured_cmd[vf_idx + 1]


# ==========================================
# 4. API ENDPOINT & WORKFLOW INTEGRATION
# ==========================================

class TestAdvancedPodcastApi:

    @pytest.fixture(autouse=True)
    def mock_ai_provider(self):
        with patch("backend.services.llm_router.is_ai_provider_configured", return_value=True):
            yield

    @pytest.mark.asyncio
    async def test_analyze_shots_endpoint_validation(self):
        """analyze-shots endpoint validates required parameters."""
        from backend.api.routes.videos import analyze_podcast_shots
        mock_db = AsyncMock()

        # Missing regions
        with pytest.raises(HTTPException) as exc_info:
            await analyze_podcast_shots(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions="",
                ref_timestamp=0.0,
                db=mock_db
            )
        assert exc_info.value.status_code == 400
        assert "regions parameter is required" in exc_info.value.detail

        # Invalid YouTube URL
        with pytest.raises(HTTPException) as exc_info:
            await analyze_podcast_shots(
                url="invalid-url",
                regions=json.dumps([{"id": "s1", "x": 0.1, "y": 0.1, "w": 0.4, "h": 0.8}]),
                ref_timestamp=0.0,
                db=mock_db
            )
        assert exc_info.value.status_code == 400
        assert "Invalid YouTube URL" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_analyze_shots_endpoint_success(self, tmp_path):
        """analyze-shots endpoint returns valid JSON schedule with review count."""
        from backend.api.routes.videos import analyze_podcast_shots
        mock_db = AsyncMock()

        mock_schedule = [
            {"shot_id": 1, "start_time": 0.0, "end_time": 4.0, "active_track_id": "speaker_1", "confidence": 0.88, "review_needed": False},
            {"shot_id": 2, "start_time": 4.0, "end_time": 8.0, "active_track_id": "unassigned", "confidence": 0.32, "review_needed": True},
        ]

        regions_json = json.dumps([
            {"id": "speaker_1", "label": "Speaker 1", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7},
            {"id": "speaker_2", "label": "Speaker 2", "x": 0.55, "y": 0.1, "width": 0.35, "height": 0.7},
        ])

        fake_video = tmp_path / "fake.mp4"
        fake_video.touch()

        with patch("backend.services.downloader.extract_youtube_id", return_value="dQw4w9WgXcQ"), \
             patch("backend.services.downloader.download_video", return_value=fake_video), \
             patch("backend.services.advanced_podcast_engine.build_shot_schedule", return_value=mock_schedule):

            res = await analyze_podcast_shots(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=regions_json,
                ref_timestamp=2.5,
                db=mock_db
            )

            assert res["status"] == "success"
            assert res["video_id"] == "dQw4w9WgXcQ"
            assert res["total_shots"] == 2
            assert res["review_needed_count"] == 1
            assert res["shots"][0]["active_track_id"] == "speaker_1"
            assert res["shots"][1]["review_needed"] is True

    @pytest.mark.asyncio
    async def test_process_youtube_url_with_advanced_podcast_schedule(self):
        """Verify URL submission with shot_schedule assigns mode='advanced_podcast' and stores schedule."""
        from backend.api.routes.videos import process_youtube_url
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        regions = [
            {"id": "speaker_1", "label": "Speaker 1", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7},
            {"id": "speaker_2", "label": "Speaker 2", "x": 0.55, "y": 0.1, "width": 0.35, "height": 0.7},
        ]
        shot_schedule = [
            {"shot_id": 1, "start_time": 0.0, "end_time": 5.0, "active_track_id": "speaker_1"},
            {"shot_id": 2, "start_time": 5.0, "end_time": 10.0, "active_track_id": "speaker_2"},
        ]

        with patch("backend.services.provenance.check_is_clipforge_short", return_value=(False, None, None)), \
             patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_apply:
            mock_task = MagicMock()
            mock_task.id = "task-adv-123"
            mock_apply.return_value = mock_task

            res = await process_youtube_url(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=json.dumps(regions),
                shot_schedule=json.dumps(shot_schedule),
                podcast_composition="advanced_podcast",
                db=mock_db
            )

            assert "job_id" in res
            assert res["message"] == "Processing started"

            # Check Job configuration stored in DB
            added_job = mock_db.add.call_args[0][0]
            config = json.loads(added_job.config) if isinstance(added_job.config, str) else added_job.config
            assert config["mode"] == "advanced_podcast"
            assert config["podcast_composition"] == "advanced_podcast"
            assert len(config["shot_schedule"]) == 2
            assert config["shot_schedule"][0]["active_track_id"] == "speaker_1"


# ==========================================
# 5. ENHANCED TRACKING, SMOOTHING & ASYNC QUEUE TESTS
# ==========================================

class TestAdvancedPodcastEnhancedCapabilities:

    def test_crop_trajectory_smoother_deadband_suppression(self):
        """Deadband filter completely eliminates micro-jitter below 3% threshold."""
        from backend.services.advanced_podcast_engine import CropTrajectorySmoother
        smoother = CropTrajectorySmoother(deadband_norm=0.03, alpha=0.25)

        base_pos = 0.50
        # Initialize
        assert smoother.smooth(base_pos, "speaker_1", is_cut=True) == 0.50

        # Small micro-movements within deadband (< 0.03) must not move the crop
        noisy_positions = [0.51, 0.49, 0.52, 0.485, 0.505]
        smoothed_outputs = [smoother.smooth(p, "speaker_1", is_cut=False) for p in noisy_positions]

        for out in smoothed_outputs:
            assert out == 0.50, f"Expected deadband suppression, got {out}"

    def test_crop_trajectory_smoother_cut_instant_snap(self):
        """Hard camera cuts snap instantly to the new speaker without lag or delay."""
        from backend.services.advanced_podcast_engine import CropTrajectorySmoother
        smoother = CropTrajectorySmoother(deadband_norm=0.03, alpha=0.25)

        # Speaker 1 on left (0.25)
        pos1 = smoother.smooth(0.25, "speaker_1", is_cut=True)
        assert pos1 == 0.25

        # Cut to Speaker 2 on right (0.75)
        pos2 = smoother.smooth(0.75, "speaker_2", is_cut=True)
        assert pos2 == 0.75, "Camera cut must snap immediately without EMA lag"

    def test_spatial_candidate_search_centered_solo(self, tmp_path):
        """When speaker moves to frame center in a solo shot, spatial search detects centered framing."""
        from backend.services.advanced_podcast_engine import classify_shot_interval
        import cv2

        dummy_video = tmp_path / "dummy_solo.mp4"
        dummy_video.touch()

        # Speaker 1 signature at left (x=0.1)
        signatures = [
            {
                "track_id": "speaker_1",
                "label": "Speaker 1",
                "ref_rect": {"x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7},
                "center_x_norm": 0.275,
                "hist": np.ones((24, 24), dtype=np.float32)
            },
            {
                "track_id": "speaker_2",
                "label": "Speaker 2",
                "ref_rect": {"x": 0.60, "y": 0.1, "width": 0.35, "height": 0.7},
                "center_x_norm": 0.775,
                "hist": np.zeros((24, 24), dtype=np.float32)
            }
        ]

        # In solo shot, person is in center: reference pos is low (0.15), center pos is high (0.92)
        with patch("cv2.VideoCapture") as mock_cap_cls, \
             patch("cv2.compareHist", side_effect=[0.15, 0.92, 0.05, 0.05]):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.return_value = 30.0
            mock_cap.read.return_value = (True, np.ones((720, 1280, 3), dtype=np.uint8))
            mock_cap_cls.return_value = mock_cap

            res = classify_shot_interval(dummy_video, (0.0, 3.0), signatures, src_w=1280, src_h=720)

            assert res["active_track_id"] == "speaker_1"
            assert res["confidence"] == 0.92
            assert res["review_needed"] is False
            # Crop rectangle must be centered around x=0.5
            norm_center = res["crop_rect"]["norm_x"] + res["crop_rect"]["norm_w"] / 2.0
            assert 0.45 <= norm_center <= 0.55

    @pytest.mark.asyncio
    async def test_async_shot_analysis_queue_and_status(self):
        """Verify async_mode=True returns queued task_id and status endpoint queries progress."""
        from backend.api.routes.videos import analyze_podcast_shots, get_podcast_analysis_status
        mock_db = AsyncMock()

        regions_json = json.dumps([{"id": "speaker_1", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7}])

        with patch("backend.tasks.analysis_tasks.analyze_podcast_shots_task.delay") as mock_delay:
            mock_task = MagicMock()
            mock_task.id = "async-task-xyz-789"
            mock_delay.return_value = mock_task

            res = await analyze_podcast_shots(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                regions=regions_json,
                ref_timestamp=0.0,
                async_mode=True,
                db=mock_db
            )

            assert res["status"] == "queued"
            assert res["task_id"] == "async-task-xyz-789"
            assert res["video_id"] == "dQw4w9WgXcQ"

        # Query status endpoint
        with patch("backend.tasks.celery_app.celery_app.AsyncResult") as mock_async_result:
            mock_res_obj = MagicMock()
            mock_res_obj.ready.return_value = False
            mock_res_obj.info = {"progress": 45, "stage": "detecting_cuts", "message": "Detecting cuts..."}
            mock_async_result.return_value = mock_res_obj

            status = await get_podcast_analysis_status("async-task-xyz-789")
            assert status["status"] == "processing"
            assert status["progress"] == 45
            assert status["stage"] == "detecting_cuts"

    def test_celery_task_registration_and_naming(self):
        """Verify analyze_podcast_shots_task is registered in Celery app with matching name."""
        from backend.tasks.celery_app import celery_app
        import backend.tasks.analysis_tasks as analysis_tasks

        # Ensure task is in registry
        assert "analyze_podcast_shots_task" in celery_app.tasks
        task_obj = celery_app.tasks["analyze_podcast_shots_task"]
        assert task_obj.name == "analyze_podcast_shots_task"
        assert task_obj == analysis_tasks.analyze_podcast_shots_task

        # Verify entrypoint process_video also registers the task
        import backend.tasks.process_video as process_video
        assert "analyze_podcast_shots_task" in process_video.celery_app.tasks

    @pytest.mark.asyncio
    async def test_api_dispatches_registered_task_name(self):
        """Verify API route dispatches precisely the registered Celery task."""
        from backend.api.routes.videos import analyze_podcast_shots
        from backend.tasks.analysis_tasks import analyze_podcast_shots_task

        mock_db = AsyncMock()
        regions_json = json.dumps([{"id": "speaker_1", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7}])

        with patch.object(analyze_podcast_shots_task, "delay") as mock_delay:
            mock_task = MagicMock()
            mock_task.id = "dispatched-task-uuid-123"
            mock_delay.return_value = mock_task

            res = await analyze_podcast_shots(
                url="https://www.youtube.com/watch?v=0GjbIOS9Q90",
                regions=regions_json,
                ref_timestamp=0.0,
                composition="advanced_podcast",
                async_mode=True,
                db=mock_db
            )

            assert res["status"] == "queued"
            assert res["task_id"] == "dispatched-task-uuid-123"
            assert mock_delay.called
            call_kwargs = mock_delay.call_args.kwargs
            assert call_kwargs["url"] == "https://www.youtube.com/watch?v=0GjbIOS9Q90"
            assert call_kwargs["composition"] == "advanced_podcast"

    @pytest.mark.asyncio
    async def test_status_endpoint_lifecycle_and_error_serialization(self):
        """Verify get_podcast_analysis_status handles processing, success, and informative worker failures."""
        from backend.api.routes.videos import get_podcast_analysis_status
        from celery.exceptions import NotRegistered

        # 1. Processing status
        with patch("backend.tasks.celery_app.celery_app.AsyncResult") as mock_async_result:
            mock_res_obj = MagicMock()
            mock_res_obj.ready.return_value = False
            mock_res_obj.info = {"progress": 70, "stage": "classifying_speakers", "message": "Classifying..."}
            mock_async_result.return_value = mock_res_obj

            status = await get_podcast_analysis_status("task-123")
            assert status["status"] == "processing"
            assert status["progress"] == 70
            assert status["stage"] == "classifying_speakers"

        # 2. Success status
        with patch("backend.tasks.celery_app.celery_app.AsyncResult") as mock_async_result:
            mock_res_obj = MagicMock()
            mock_res_obj.ready.return_value = True
            mock_res_obj.successful.return_value = True
            mock_res_obj.result = {"status": "success", "total_shots": 3, "shots": []}
            mock_async_result.return_value = mock_res_obj

            status = await get_podcast_analysis_status("task-123")
            assert status["status"] == "success"
            assert status["result"]["total_shots"] == 3

        # 3. Informative worker failure: NotRegistered
        with patch("backend.tasks.celery_app.celery_app.AsyncResult") as mock_async_result:
            mock_res_obj = MagicMock()
            mock_res_obj.ready.return_value = True
            mock_res_obj.successful.return_value = False
            mock_res_obj.result = NotRegistered("analyze_podcast_shots_task")
            mock_async_result.return_value = mock_res_obj

            status = await get_podcast_analysis_status("task-123")
            assert status["status"] == "failed"
            assert "worker reload required" in status["error"]
            assert "NotRegistered" in status["error"]

        # 4. Informative worker failure: generic Exception
        with patch("backend.tasks.celery_app.celery_app.AsyncResult") as mock_async_result:
            mock_res_obj = MagicMock()
            mock_res_obj.ready.return_value = True
            mock_res_obj.successful.return_value = False
            mock_res_obj.result = ValueError("Corrupted video file")
            mock_async_result.return_value = mock_res_obj

            status = await get_podcast_analysis_status("task-123")
            assert status["status"] == "failed"
            assert status["error"] == "ValueError: Corrupted video file"

    def test_eager_task_execution(self):
        """Verify task execution logic produces valid shot schedule in eager execution mode."""
        from backend.tasks.analysis_tasks import analyze_podcast_shots_task

        regions = json.dumps([
            {"id": "speaker_1", "label": "Speaker 1", "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.7},
            {"id": "speaker_2", "label": "Speaker 2", "x": 0.55, "y": 0.1, "width": 0.35, "height": 0.7}
        ])

        # Execute eagerly on synthetic fixture (isolated mock execution)
        res = analyze_podcast_shots_task.apply(kwargs={
            "url": "uploads/synthetic_test_fixture.mp4",
            "regions_json": regions,
            "ref_timestamp": 0.0,
            "composition": "advanced_podcast"
        })

        assert res.state == "SUCCESS"
        result_dict = res.result
        assert result_dict["status"] == "success"
        assert result_dict["total_shots"] >= 1
        assert len(result_dict["shots"]) >= 1
        first_shot = result_dict["shots"][0]
        assert "crop_rect" in first_shot
        assert "active_track_id" in first_shot


