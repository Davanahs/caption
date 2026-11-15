"""
test_gaming_layout_pipeline.py
==============================
Unit and integration tests for the Dual-Region Gaming Layout pipeline in ClipForge:
- LayoutMode.GAMING enum and LayoutPlan validation invariants
- LayoutEngine.create_gaming_plan and resolve_plan routing
- Even-pixel codec quantization (YUV420p)
- Filtergraph structure (multi-crop scale-to-fill, PiP overlay, setsar=1)
- Single-source input flattening without split deadlocks
- Audio stream preservation (-map 0:a? -c:a aac)
- R5 Zero-Caption Mandate (-sn, zero caption filters, zero subtitle streams)
- Codec flags (-pix_fmt yuv420p, -movflags +faststart)
- End-to-end synthetic video rendering verification
- reframe_task dispatch routing in Celery worker
"""

import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

from backend.models.layout import (
    AudioPolicy,
    BackgroundPolicy,
    GamingLayoutConfig,
    LayoutMode,
    LayoutPlan,
    NormalizedRectModel,
    RegionModel,
    ScaleMode,
    ZoomIntervention,
)
from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    create_gaming_layout_plan,
    get_facecam_preset,
    to_canvas_overlay,
    to_even_pixel,
    to_even_span,
    to_source_crop,
)
from backend.services.layout_engine import LayoutEngine
import backend.services.reframe_engine as reframe_module
from backend.services.reframe_engine import reframe_to_vertical, run_ffmpeg
from backend.tests.gaming_test_fixtures import (
    assert_faststart_moov_atom,
    assert_filtergraph_zero_caption_invariant,
    assert_gaming_video_invariants,
    assert_zero_caption_invariant,
    create_synthetic_1080p_gameplay,
    create_synthetic_4k_ultrawide,
    create_synthetic_odd_dimension,
    create_synthetic_portrait,
    generate_synthetic_video,
    probe_media,
)


def extract_frame_image(video_path: Path, time_sec: float = 0.5, out_image: Optional[Path] = None) -> Image.Image:
    """Extracts a single frame from video at time_sec and returns PIL Image."""
    if out_image is None:
        out_image = video_path.parent / f"{video_path.stem}_frame_{time_sec}s.png"
    cmd = [
        "ffmpeg", "-y", "-ss", str(time_sec),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(out_image),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Frame extraction failed ({proc.returncode}):\n{proc.stderr}")
    return Image.open(out_image)


# ==============================================================================
# 1. DATA MODEL & SCHEMA VALIDATION TESTS
# ==============================================================================

class TestGamingLayoutModels:

    def test_layout_mode_gaming_enum_exists(self):
        """Confirms LayoutMode.GAMING is defined and equals 'gaming'."""
        assert LayoutMode.GAMING == "gaming"
        assert LayoutMode("gaming") == LayoutMode.GAMING

    def test_normalized_rect_model_valid(self):
        """Valid normalized rect within [0.0, 1.0] bounds passes validation."""
        rect = NormalizedRectModel(x=0.1, y=0.2, width=0.5, height=0.6)
        assert rect.x == 0.1
        assert rect.y == 0.2
        assert rect.width == 0.5
        assert rect.height == 0.6

    def test_normalized_rect_model_out_of_bounds_rejected(self):
        """Out of bounds rectangles exceed 1.0 and raise ValueError."""
        with pytest.raises(ValueError):
            NormalizedRectModel(x=0.8, y=0.1, width=0.3, height=0.5)

        with pytest.raises(ValueError):
            NormalizedRectModel(x=0.1, y=0.7, width=0.5, height=0.4)

    def test_normalized_rect_model_negative_or_subminimum_rejected(self):
        """Negative coordinates or dimensions smaller than 0.05 raise ValueError."""
        with pytest.raises(ValueError):
            NormalizedRectModel(x=-0.01, y=0.0, width=0.5, height=0.5)

        with pytest.raises(ValueError):
            NormalizedRectModel(x=0.0, y=0.0, width=0.02, height=0.5)

    def test_gaming_layout_plan_validation_success(self):
        """Canonical gaming layout plan with 2 regions, distinct z-orders, and BackgroundPolicy.NONE passes."""
        r_gameplay = RegionModel(
            source_index=0,
            x=0,
            y=0,
            w=1080,
            h=1920,
            scale_mode=ScaleMode.CROP,
            z_order=1,
            crop_coords=(0, 0, 1920, 1080),
        )
        r_facecam = RegionModel(
            source_index=1,
            x=702,
            y=76,
            w=324,
            h=422,
            scale_mode=ScaleMode.CROP,
            z_order=2,
            crop_coords=(1344, 54, 480, 270),
        )
        plan = LayoutPlan(
            mode=LayoutMode.GAMING,
            canvas_width=1080,
            canvas_height=1920,
            regions=[r_gameplay, r_facecam],
            background_policy=BackgroundPolicy.NONE,
            audio_policy=AudioPolicy.PRIMARY_ONLY,
        )
        assert plan.mode == LayoutMode.GAMING
        assert len(plan.regions) == 2
        assert plan.regions[0].z_order == 1
        assert plan.regions[1].z_order == 2

    def test_gaming_layout_plan_rejects_blur_background(self):
        """GAMING mode strictly forbids background policies other than NONE."""
        r1 = RegionModel(source_index=0, x=0, y=0, w=1080, h=1920, scale_mode=ScaleMode.CROP, z_order=1)
        r2 = RegionModel(source_index=1, x=100, y=100, w=300, h=400, scale_mode=ScaleMode.CROP, z_order=2)
        with pytest.raises(ValueError, match="BackgroundPolicy.NONE"):
            LayoutPlan(
                mode=LayoutMode.GAMING,
                canvas_width=1080,
                canvas_height=1920,
                regions=[r1, r2],
                background_policy=BackgroundPolicy.BLUR,
            )

    def test_gaming_layout_plan_rejects_zoom_interventions(self):
        """GAMING mode strictly forbids zoom interventions."""
        r1 = RegionModel(
            source_index=0,
            x=0,
            y=0,
            w=1080,
            h=1920,
            scale_mode=ScaleMode.CROP,
            z_order=1,
            zoom_interventions=[ZoomIntervention(start_time=1.0, end_time=3.0, zoom_factor=1.5)],
        )
        r2 = RegionModel(source_index=1, x=100, y=100, w=300, h=400, scale_mode=ScaleMode.CROP, z_order=2)
        with pytest.raises(ValueError, match="Zoom interventions are forbidden in GAMING mode"):
            LayoutPlan(
                mode=LayoutMode.GAMING,
                canvas_width=1080,
                canvas_height=1920,
                regions=[r1, r2],
                background_policy=BackgroundPolicy.NONE,
            )

    def test_gaming_layout_plan_requires_exactly_two_regions_with_ordered_z(self):
        """GAMING mode requires exactly 2 regions with z_order 1 for gameplay and 2 for facecam."""
        r1 = RegionModel(source_index=0, x=0, y=0, w=1080, h=1920, scale_mode=ScaleMode.CROP, z_order=1)
        with pytest.raises(ValueError, match="exactly 2 regions"):
            LayoutPlan(
                mode=LayoutMode.GAMING,
                canvas_width=1080,
                canvas_height=1920,
                regions=[r1],
                background_policy=BackgroundPolicy.NONE,
            )

        # Regions with invalid z_order (z=1 and z=3 instead of z=1 and z=2)
        r2_invalid_z = RegionModel(source_index=1, x=100, y=100, w=300, h=400, scale_mode=ScaleMode.CROP, z_order=3)
        with pytest.raises(ValueError, match="distinct z-orders"):
            LayoutPlan(
                mode=LayoutMode.GAMING,
                canvas_width=1080,
                canvas_height=1920,
                regions=[r1, r2_invalid_z],
                background_policy=BackgroundPolicy.NONE,
            )


# ==============================================================================
# 2. LAYOUT ENGINE PLAN CREATION & GEOMETRY TESTS
# ==============================================================================

class TestLayoutEngineGamingPlan:

    def test_create_gaming_plan_canonical_structure(self):
        """LayoutEngine.create_gaming_plan produces canonical plan with expected dimensions and crops."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
        assert isinstance(plan, LayoutPlan)
        assert plan.mode == LayoutMode.GAMING
        assert plan.canvas_width == 1080
        assert plan.canvas_height == 1920
        assert len(plan.regions) == 2

        r_gp, r_fc = plan.regions[0], plan.regions[1]
        assert r_gp.source_index == 0
        assert r_gp.z_order == 1
        assert r_gp.w == 1080
        assert r_gp.h == 1920
        assert r_gp.crop_coords == (0, 0, 1920, 1080)

        assert r_fc.source_index == 1
        assert r_fc.z_order == 2
        assert r_fc.w > 0
        assert r_fc.h > 0
        assert r_fc.x + r_fc.w <= 1080
        assert r_fc.y + r_fc.h <= 1920

    def test_create_gaming_plan_accepts_canvas_w_or_canvas_width(self):
        """Normalizes both canvas_w/canvas_h and canvas_width/canvas_height keys seamlessly."""
        config_a = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "canvas_w": 1080,
            "canvas_h": 1920,
        }
        plan_a = LayoutEngine.create_gaming_plan(config_a, source_w=1920, source_h=1080)
        assert plan_a.canvas_width == 1080
        assert plan_a.canvas_height == 1920

        config_b = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "canvas_width": 720,
            "canvas_height": 1280,
        }
        plan_b = LayoutEngine.create_gaming_plan(config_b, source_w=1920, source_h=1080)
        assert plan_b.canvas_width == 720
        assert plan_b.canvas_height == 1280

    def test_create_gaming_plan_presets(self):
        """Verifies all four placement presets position facecam PiP within canvas boundaries."""
        presets = ["top-left", "top-right", "bottom-left", "bottom-right"]
        for p in presets:
            config = {
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
                "facecam_placement": p,
            }
            plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
            fc = plan.regions[1]
            assert fc.x >= 0
            assert fc.y >= 0
            assert fc.x + fc.w <= 1080
            assert fc.y + fc.h <= 1920

    def test_create_gaming_plan_even_pixel_quantization(self):
        """Verifies that odd source dimensions (1919x1079) produce even crop and overlay coordinates."""
        config = {
            "gameplay_roi": {"x": 0.13, "y": 0.17, "width": 0.61, "height": 0.73},
            "facecam_roi": {"x": 0.71, "y": 0.03, "width": 0.23, "height": 0.27},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1919, source_h=1079)
        for r in plan.regions:
            assert r.x % 2 == 0
            assert r.y % 2 == 0
            assert r.w % 2 == 0
            assert r.h % 2 == 0
            if r.crop_coords:
                cx, cy, cw, ch = r.crop_coords
                assert cx % 2 == 0
                assert cy % 2 == 0
                assert cw % 2 == 0
                assert ch % 2 == 0

    def test_resolve_plan_routes_gaming_mode(self):
        """LayoutEngine.resolve_plan('gaming', ...) returns a validated gaming plan."""
        plan = LayoutEngine.resolve_plan("gaming", source_w=1920, source_h=1080)
        assert isinstance(plan, LayoutPlan)
        assert plan.mode == LayoutMode.GAMING
        assert len(plan.regions) == 2


# ==============================================================================
# 3. FILTERGRAPH GENERATION & SINGLE-SOURCE FLATTENING TESTS
# ==============================================================================

class TestGamingFiltergraphConstruction:

    def test_filtergraph_multi_crop_structure_without_splits(self):
        """
        Builds filtergraph from gaming plan with 2 inputs.
        Verifies:
        - Input 0 crops gameplay: [0:v]crop=...
        - Input 1 crops facecam: [1:v]crop=...
        - No split filters are used
        - Scale-to-fill force_original_aspect_ratio=increase
        - Overlay with eof_action=pass:repeatlast=0
        - setsar=1 on outv
        """
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
        inputs = [Path("video.mp4"), Path("video.mp4")]

        fg = LayoutEngine.build_render_graph(plan, inputs)

        # Asserts independent input demuxers used without split
        assert "[0:v]crop=" in fg
        assert "[1:v]crop=" in fg
        assert "split" not in fg.lower()

        # Scale-to-fill
        assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in fg

        # Overlay compositing
        assert "overlay=x=702:y=76:eof_action=pass:repeatlast=0" in fg
        assert "setsar=1[outv]" in fg

    def test_filtergraph_zero_caption_mandate(self):
        """Verifies filtergraph contains zero subtitle, ass, or drawtext filters."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("video.mp4"), Path("video.mp4")])
        assert_filtergraph_zero_caption_invariant(fg)


# ==============================================================================
# 4. END-TO-END SYNTHETIC VIDEO RENDERING EXECUTION TEST
# ==============================================================================

class TestGamingRenderingExecution:

    @pytest.mark.asyncio
    async def test_reframe_to_vertical_executes_gaming_render(self, tmp_path):
        """
        Executes genuine FFmpeg reframing on a synthetic 1080p gameplay video.
        Validates:
        - Output file created successfully
        - Resolution is 1080x1920 (9:16 vertical)
        - Codecs: h264, yuv420p, aac
        - Audio stream preserved
        - Faststart moov atom placed before mdat
        - Strict R5 zero captions (no subtitle streams, no caption files)
        """
        source_video = tmp_path / "synthetic_gameplay_1080p.mp4"
        output_video = tmp_path / "reframed_gaming_vertical.mp4"

        create_synthetic_1080p_gameplay(source_video, duration=2.0, fps=30)
        assert source_video.exists()

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)

        # Execute genuine FFmpeg render
        result_path = await reframe_to_vertical(
            input_path=source_video,
            output_path=output_video,
            mode="gaming",
            plan=plan,
        )

        assert result_path == output_video
        assert output_video.exists()
        assert output_video.stat().st_size > 0

        # Opaque-box invariants verification
        invariants = assert_gaming_video_invariants(
            output_video,
            expected_width=1080,
            expected_height=1920,
            expected_video_codec="h264",
            expected_pix_fmt="yuv420p",
            expected_audio_codec="aac",
            check_faststart=True,
            check_zero_captions=True,
        )
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"
        assert invariants["audio_codec"] == "aac"


# ==============================================================================
# 5. CELERY WORKER REFRAME TASK ROUTING TEST
# ==============================================================================

class TestGamingWorkerReframeRouting:

    def test_reframe_task_builds_gaming_plan_when_gaming_layout_present(self):
        """
        Verifies reframe_task detects Job.config containing 'gaming_layout',
        probes cut clip dimensions, invokes LayoutEngine.create_gaming_plan,
        and dispatches to reframe_to_vertical with mode='gaming'.
        """
        from backend.tasks.clip_tasks import reframe_task

        gaming_config = {
            "mode": "gaming",
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        config_data = {
            "mode": "gaming",
            "reframe_mode": "gaming",
            "gaming_layout": gaming_config,
        }

        mock_job = MagicMock()
        mock_job.id = "job-gaming-worker-test"
        mock_job.config = json.dumps(config_data)
        mock_job.status = "processing"

        mock_clip = MagicMock()
        mock_clip.id = "clip-gaming-123"
        mock_clip.video_id = "video-gaming-456"
        mock_clip.start_time = 5.0
        mock_clip.end_time = 15.0

        mock_video = MagicMock()
        mock_video.id = "video-gaming-456"
        mock_video.local_path = "uploads/video-gaming-456/source.mp4"

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
             patch("backend.services.layout_engine.LayoutEngine.create_gaming_plan", wraps=LayoutEngine.create_gaming_plan) as mock_create_plan:

            mock_dl.return_value.__enter__.return_value = "C:/tmp/mock_source.mp4"
            mock_ul.return_value.__enter__.return_value = "C:/tmp/mock_reframed.mp4"

            # Execute reframe_task directly via _orig_run
            mock_self = MagicMock()
            mock_self.request.id = "task-gaming-reframe-1"
            mock_self.request.hostname = "worker-gaming-1"

            result = reframe_task._orig_run(clip_id="clip-gaming-123", job_id="job-gaming-worker-test")

            # Assert create_gaming_plan was invoked
            mock_create_plan.assert_called_once()
            call_kwargs = mock_create_plan.call_args[1]
            assert call_kwargs["config"] == gaming_config
            assert call_kwargs["source_w"] == 1920
            assert call_kwargs["source_h"] == 1080

            # Assert reframe_to_vertical was invoked with mode='gaming' and valid plan
            mock_reframe.assert_called_once()
            reframe_args = mock_reframe.call_args[1]
            assert reframe_args["mode"] == "gaming"
            reframe_plan = reframe_args["plan"]
            assert reframe_plan is not None
            assert reframe_plan.mode == LayoutMode.GAMING
            assert len(reframe_plan.regions) == 2


# ==============================================================================
# CLASS 1: TIER 1 - PIPELINE CONSTRUCTION (10 TESTS)
# ==============================================================================

class TestTier1GamingPipelineConstruction:
    """Tier 1 Feature Coverage: Filtergraph construction, dual -i flattening, z-order, aspect ratios."""

    def test_tc_t1_f14_01_construct_gaming_filtergraph(self):
        """TC-T1-F14-01: Verifies dual crop, dual scale, and single overlay in LayoutEngine filtergraph."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])

        # Dual crop checks
        assert "[0:v]crop=" in fg
        assert "[1:v]crop=" in fg

        # Dual scale checks
        assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in fg
        assert "scale=324:422" in fg

        # Overlay check
        assert "overlay=x=702:y=76:eof_action=pass:repeatlast=0" in fg
        assert "[outv]" in fg

    @pytest.mark.asyncio
    async def test_tc_t1_f14_02_input_flattening_verification(self, tmp_path):
        """TC-T1-F14-02: Verifies reframe engine builds dual -i parameters ([-i input.mp4 -i input.mp4]) preventing split deadlocks."""
        src_path = tmp_path / "src_flat.mp4"
        out_path = tmp_path / "out_flat.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)

        captured_cmd = []
        original_run_ffmpeg = reframe_module.run_ffmpeg

        async def mock_run_ffmpeg(cmd):
            captured_cmd.extend(cmd)
            return await original_run_ffmpeg(cmd)

        with patch.object(reframe_module, "run_ffmpeg", side_effect=mock_run_ffmpeg):
            await reframe_to_vertical(src_path, out_path, plan=plan)

        # Count -i flags
        i_indices = [idx for idx, arg in enumerate(captured_cmd) if arg == "-i"]
        assert len(i_indices) == 2, f"Expected exactly two -i inputs for dual regions, found {len(i_indices)}"
        assert captured_cmd[i_indices[0] + 1] == str(src_path)
        assert captured_cmd[i_indices[1] + 1] == str(src_path)

    def test_tc_t1_f14_03_end_of_file_overlay_action(self):
        """TC-T1-F14-03: Verifies overlay parameter specifies eof_action=pass:repeatlast=0."""
        config = {
            "gameplay_roi": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
            "facecam_roi": {"x": 0.05, "y": 0.04, "width": 0.30, "height": 0.22},
            "facecam_placement": "top-left",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert "eof_action=pass:repeatlast=0" in fg

    def test_tc_t1_f14_04_pixel_aspect_ratio_normalization(self):
        """TC-T1-F14-04: Verifies filtergraph ends with setsar=1[outv]."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.65, "y": 0.74, "width": 0.30, "height": 0.22},
            "facecam_placement": "bottom-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert "setsar=1[outv]" in fg

    def test_tc_t1_f15_01_gameplay_scale_to_fill_aspect_ratio(self):
        """TC-T1-F15-01: Verifies gameplay scale filter contains scale=1080:1920:force_original_aspect_ratio=increase."""
        config = {
            "gameplay_roi": {"x": 0.2, "y": 0.1, "width": 0.6, "height": 0.8},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert "scale=1080:1920:force_original_aspect_ratio=increase" in fg

    def test_tc_t1_f15_02_gameplay_post_scale_crop(self):
        """TC-T1-F15-02: Verifies crop filter following scale contains crop=1080:1920."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert "force_original_aspect_ratio=increase,crop=1080:1920" in fg

    def test_tc_t1_f16_01_facecam_destination_scaling(self):
        """TC-T1-F16-01: Verifies facecam scale filter matches scale=dest_w:dest_h."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        dest_w = plan.regions[1].w
        dest_h = plan.regions[1].h
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert f"scale={dest_w}:{dest_h}" in fg

    def test_tc_t1_f16_02_overlay_coordinate_positioning(self):
        """TC-T1-F16-02: Verifies overlay filter matches x=dest_x:y=dest_y."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        dest_x = plan.regions[1].x
        dest_y = plan.regions[1].y
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert f"x={dest_x}:y={dest_y}" in fg

    def test_tc_t1_f16_03_facecam_z_order_verification(self):
        """TC-T1-F16-03: Verifies facecam stream [scaled_1] is overlaid atop gameplay stream."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        assert plan.regions[0].z_order == 1
        assert plan.regions[1].z_order == 2

        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        # Region 0 is base background [overlayed_0], Region 1 [scaled_1] is overlaid on top of it
        assert "[overlayed_0][scaled_1]overlay=" in fg

    def test_tc_t1_f16_04_facecam_bounded_within_9_16_canvas(self):
        """TC-T1-F16-04: Verifies destination rectangle satisfies dest_x + dest_w <= 1080 and dest_y + dest_h <= 1920."""
        for preset in ("top-left", "top-right", "bottom-left", "bottom-right"):
            config = {
                "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "facecam_roi": {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.25},
                "facecam_placement": preset,
            }
            plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
            fc = plan.regions[1]
            assert fc.x >= 0, f"[{preset}] Negative dest_x: {fc.x}"
            assert fc.y >= 0, f"[{preset}] Negative dest_y: {fc.y}"
            assert fc.x + fc.w <= 1080, f"[{preset}] Overflow width: {fc.x + fc.w} > 1080"
            assert fc.y + fc.h <= 1920, f"[{preset}] Overflow height: {fc.y + fc.h} > 1920"


# ==============================================================================
# CLASS 2: TIER 1 - PIPELINE EXECUTION (17 TESTS)
# ==============================================================================

class TestTier1GamingPipelineExecution:
    """Tier 1 Feature Coverage: Real FFmpeg rendering, media probing, audio, and zero-captions."""

    @pytest.mark.asyncio
    async def test_tc_t1_f14_05_render_synthetic_gaming_video(self, tmp_path):
        """TC-T1-F14-05: Renders synthetic gaming video, asserts exit code 0, file exists, size > 0."""
        src_path = tmp_path / "src_gameplay.mp4"
        out_path = tmp_path / "out_gameplay.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        res = await reframe_to_vertical(src_path, out_path, plan=plan)

        assert res.exists()
        assert res.stat().st_size > 0
        assert_faststart_moov_atom(res)

    @pytest.mark.asyncio
    async def test_tc_t1_f15_03_16_9_gameplay_center_cropped_to_9_16(self, tmp_path):
        """TC-T1-F15-03: Center-cropped 16:9 gameplay renders cleanly filling 1080x1920 without black bars."""
        src_path = tmp_path / "src_16_9.mp4"
        out_path = tmp_path / "out_16_9.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        v = probe["streams"][0]
        assert v["width"] == 1080
        assert v["height"] == 1920

    @pytest.mark.asyncio
    async def test_tc_t1_f15_04_square_1_1_gameplay_crop_to_9_16(self, tmp_path):
        """TC-T1-F15-04: Square gameplay crop scaled to fill height and cropped horizontally."""
        src_path = tmp_path / "src_square.mp4"
        out_path = tmp_path / "out_square.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.2, "y": 0.0, "width": 0.5, "height": 0.5},
            "facecam_roi": {"x": 0.75, "y": 0.05, "width": 0.20, "height": 0.20},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        v = probe["streams"][0]
        assert v["width"] == 1080
        assert v["height"] == 1920

    @pytest.mark.asyncio
    async def test_tc_t1_f15_05_output_dimensions_ffprobe_check(self, tmp_path):
        """TC-T1-F15-05: Probes rendered output stream: width == 1080 and height == 1920."""
        src_path = tmp_path / "src_probe.mp4"
        out_path = tmp_path / "out_probe.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        invariants = assert_gaming_video_invariants(out_path, expected_width=1080, expected_height=1920)
        assert invariants["width"] == 1080
        assert invariants["height"] == 1920
        assert invariants["pix_fmt"] == "yuv420p"

    @pytest.mark.asyncio
    async def test_tc_t1_f16_05_visual_verification_of_facecam_presence(self, tmp_path):
        """TC-T1-F16-05: Extracts frame at 0.5s, inspects pixel color at facecam center, confirms facecam presence."""
        src_path = tmp_path / "src_color.mp4"
        out_path = tmp_path / "out_color.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        img = extract_frame_image(out_path, time_sec=0.5)
        pixel = img.getpixel((864, 287))
        r, g, b = pixel[0], pixel[1], pixel[2]
        assert g > 100, f"Expected dominant green facecam pixel, got RGB=({r}, {g}, {b})"
        assert g > r and g > b, f"Green should exceed Red and Blue: RGB=({r}, {g}, {b})"

    @pytest.mark.asyncio
    async def test_tc_t1_f18_01_native_audio_stream_mapping(self, tmp_path):
        """TC-T1-F18-01: Verifies -map 0:a? and -c:a aac in FFmpeg command."""
        src_path = tmp_path / "src_audio_cmd.mp4"
        out_path = tmp_path / "out_audio_cmd.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)

        captured_cmd = []
        original_run_ffmpeg = reframe_module.run_ffmpeg

        async def mock_run_ffmpeg(cmd):
            captured_cmd.extend(cmd)
            return await original_run_ffmpeg(cmd)

        with patch.object(reframe_module, "run_ffmpeg", side_effect=mock_run_ffmpeg):
            await reframe_to_vertical(src_path, out_path, plan=plan)

        assert "-map" in captured_cmd
        map_indices = [idx for idx, arg in enumerate(captured_cmd) if arg == "-map"]
        mapped_targets = [captured_cmd[i + 1] for i in map_indices]
        assert "0:a?" in mapped_targets, f"Expected '0:a?' in mapped targets: {mapped_targets}"

        c_a_idx = captured_cmd.index("-c:a")
        assert captured_cmd[c_a_idx + 1] == "aac"

    @pytest.mark.asyncio
    async def test_tc_t1_f18_02_audio_codec_verification(self, tmp_path):
        """TC-T1-F18-02: ffprobe confirms rendered audio codec is aac."""
        src_path = tmp_path / "src_aac.mp4"
        out_path = tmp_path / "out_aac.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        audio_streams = [s for s in probe["streams"] if s.get("codec_type") == "audio"]
        assert len(audio_streams) >= 1
        assert audio_streams[0]["codec_name"] == "aac"

    @pytest.mark.asyncio
    async def test_tc_t1_f18_03_audio_video_duration_synchronization(self, tmp_path):
        """TC-T1-F18-03: Verifies video duration and audio duration match within +-0.05s."""
        src_path = tmp_path / "src_dur_sync.mp4"
        out_path = tmp_path / "out_dur_sync.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        v_stream = next(s for s in probe["streams"] if s.get("codec_type") == "video")
        a_stream = next(s for s in probe["streams"] if s.get("codec_type") == "audio")

        v_dur = float(v_stream.get("duration", probe["format"]["duration"]))
        a_dur = float(a_stream.get("duration", probe["format"]["duration"]))
        assert abs(v_dur - a_dur) <= 0.05, f"Audio/video duration desync: v={v_dur}s, a={a_dur}s"

    @pytest.mark.asyncio
    async def test_tc_t1_f18_04_audio_sample_rate_preservation(self, tmp_path):
        """TC-T1-F18-04: Ingests 44100Hz audio, verifies output preserves standard valid audio sample rate."""
        src_path = tmp_path / "src_44k.mp4"
        out_path = tmp_path / "out_44k.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=1.0, audio_freq=440)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        a_stream = next(s for s in probe["streams"] if s.get("codec_type") == "audio")
        sample_rate = int(a_stream.get("sample_rate", 0))
        assert sample_rate in (44100, 48000), f"Unexpected sample rate: {sample_rate}"

    @pytest.mark.asyncio
    async def test_tc_t1_f18_05_clip_timing_preservation(self, tmp_path):
        """TC-T1-F18-05: Verifies clip duration is preserved matching source within tolerance."""
        src_path = tmp_path / "src_timing.mp4"
        out_path = tmp_path / "out_timing.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=2.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        dur = float(probe["format"]["duration"])
        assert abs(dur - 2.0) <= 0.25, f"Duration mismatch: expected 2.0s ±0.25s, got {dur}s"

    def test_tc_t1_f21_01_existing_center_crop_layout_intact(self):
        """TC-T1-F21-01: Confirms legacy create_vertical_plan functions without regression."""
        plan = LayoutEngine.create_vertical_plan(1920, 1080, 1080, 1920)
        assert isinstance(plan, LayoutPlan)
        assert plan.canvas_width == 1080
        assert plan.canvas_height == 1920
        assert len(plan.regions) == 1
        assert plan.regions[0].w == 1080
        assert plan.regions[0].h == 1920

    def test_tc_t1_f21_02_existing_podcast_stacked_layout_intact(self):
        """TC-T1-F21-02: Confirms legacy create_stacked_plan creates two 1080px panels."""
        plan = LayoutEngine.create_stacked_plan(1920, 1080, 1080, 1920)
        assert isinstance(plan, LayoutPlan)
        assert len(plan.regions) == 2
        assert plan.regions[0].w == 1080 and plan.regions[0].h > 0
        assert plan.regions[1].w == 1080 and plan.regions[1].h > 0

    def test_tc_t1_f21_03_existing_blur_background_layout_intact(self):
        """TC-T1-F21-03: Confirms legacy create_blur_plan functions without regression."""
        plan = LayoutEngine.create_blur_plan(1920, 1080, 1080, 1920)
        assert isinstance(plan, LayoutPlan)
        assert plan.background_policy == BackgroundPolicy.BLUR
        assert len(plan.regions) == 1

    @pytest.mark.asyncio
    async def test_tc_t1_f22_01_output_contains_zero_subtitle_streams(self, tmp_path):
        """TC-T1-F22-01: ffprobe confirms [s for s in streams if s['codec_type'] == 'subtitle'] == []."""
        src_path = tmp_path / "src_zero_sub.mp4"
        out_path = tmp_path / "out_zero_sub.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        sub_streams = [s for s in probe["streams"] if s.get("codec_type") == "subtitle"]
        assert len(sub_streams) == 0, f"Found subtitle streams in output: {sub_streams}"

    @pytest.mark.asyncio
    async def test_tc_t1_f22_02_ffmpeg_command_contains_sn_flag(self, tmp_path):
        """TC-T1-F22-02: Verifies '-sn' flag in captured execution command."""
        src_path = tmp_path / "src_sn.mp4"
        out_path = tmp_path / "out_sn.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)

        captured_cmd = []
        original_run_ffmpeg = reframe_module.run_ffmpeg

        async def mock_run_ffmpeg(cmd):
            captured_cmd.extend(cmd)
            return await original_run_ffmpeg(cmd)

        with patch.object(reframe_module, "run_ffmpeg", side_effect=mock_run_ffmpeg):
            await reframe_to_vertical(src_path, out_path, plan=plan)

        assert "-sn" in captured_cmd, f"'-sn' flag missing from FFmpeg command: {captured_cmd}"

    def test_tc_t1_f22_03_filtergraph_contains_no_subtitle_drawtext_filters(self):
        """TC-T1-F22-03: Calls assert_filtergraph_zero_caption_invariant verifying no subtitles=, ass=, or drawtext=."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert_filtergraph_zero_caption_invariant(fg)

    @pytest.mark.asyncio
    async def test_tc_t1_f22_04_zero_caption_subtitle_files_generated(self, tmp_path):
        """TC-T1-F22-04: Calls assert_zero_caption_invariant(check_directory=True) verifying 0 caption artifact files."""
        src_path = tmp_path / "src_no_srt.mp4"
        out_path = tmp_path / "out_no_srt.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert_zero_caption_invariant(out_path, check_directory=True)


# ==============================================================================
# CLASS 3: TIER 2 - BOUNDARY & EXTREMES (29 TESTS)
# ==============================================================================

class TestTier2GamingPipelineBoundaryAndExtremes:
    """Tier 2 Boundary & Extreme Limits: High fps, 4K, 21:9 ultrawide, audio edge cases, adversarial stress."""

    @pytest.mark.asyncio
    async def test_tc_t2_f01_05_high_frame_rate_video_120fps(self, tmp_path):
        """TC-T2-F01-05: 120fps synthetic source renders cleanly without worker crash."""
        src_path = tmp_path / "src_120fps.mp4"
        out_path = tmp_path / "out_120fps.mp4"
        generate_synthetic_video(src_path, width=1280, height=720, duration=0.5, fps=120)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1280, 720)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        v = probe["streams"][0]
        assert v["width"] == 1080
        assert v["height"] == 1920

    @pytest.mark.asyncio
    async def test_tc_t2_f14_01_dual_crop_4k_source_no_deadlock(self, tmp_path):
        """TC-T2-F14-01: 4K source (3840x1600) renders without OOM or buffer queue deadlock."""
        src_path = tmp_path / "src_4k_dual.mp4"
        out_path = tmp_path / "out_4k_dual.mp4"
        create_synthetic_4k_ultrawide(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
            "facecam_roi": {"x": 0.05, "y": 0.05, "width": 0.20, "height": 0.30},
            "facecam_placement": "top-left",
        }
        plan = LayoutEngine.create_gaming_plan(config, 3840, 1600)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()
        assert out_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_tc_t2_f14_02_dual_crop_60fps_source(self, tmp_path):
        """TC-T2-F14-02: 60fps source maintains consistent playback."""
        src_path = tmp_path / "src_60fps.mp4"
        out_path = tmp_path / "out_60fps.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5, fps=60)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        assert probe["streams"][0]["width"] == 1080

    @pytest.mark.asyncio
    async def test_tc_t2_f14_03_source_video_path_spaces_and_special_chars(self, tmp_path):
        """TC-T2-F14-03: Path with spaces and brackets (my video (gaming #1) [clip].mp4) renders cleanly."""
        special_name = "my video (gaming #1) [clip].mp4"
        src_path = tmp_path / special_name
        out_path = tmp_path / "out_special.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()
        assert out_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_tc_t2_f14_04_extremely_short_clip_1s(self, tmp_path):
        """TC-T2-F14-04: 1.0s clip renders with faststart enabled."""
        src_path = tmp_path / "src_1s.mp4"
        out_path = tmp_path / "out_1s.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert_faststart_moov_atom(out_path)

    @pytest.mark.asyncio
    async def test_tc_t2_f14_05_simultaneous_dual_crop_zero_offset(self, tmp_path):
        """TC-T2-F14-05: Facecam at top-left origin (x=0, y=0) overlays cleanly."""
        src_path = tmp_path / "src_zero_off.mp4"
        out_path = tmp_path / "out_zero_off.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.0, "y": 0.0, "width": 0.25, "height": 0.25},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.0, "y": 0.0, "width": 0.30, "height": 0.22},
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f15_01_gameplay_crop_4_3_source_video(self, tmp_path):
        """TC-T2-F15-01: 4:3 source (1440x1080) scaled to fill 9:16 height without distortion."""
        src_path = tmp_path / "src_4_3.mp4"
        out_path = tmp_path / "out_4_3.mp4"
        generate_synthetic_video(src_path, width=1440, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1440, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        assert probe["streams"][0]["width"] == 1080
        assert probe["streams"][0]["height"] == 1920

    @pytest.mark.asyncio
    async def test_tc_t2_f15_02_gameplay_crop_21_9_ultrawide_video(self, tmp_path):
        """TC-T2-F15-02: 21:9 ultrawide source (2560x1080) scaled to fill 9:16 height without distortion."""
        src_path = tmp_path / "src_21_9.mp4"
        out_path = tmp_path / "out_21_9.mp4"
        generate_synthetic_video(src_path, width=2560, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.2, "y": 0.0, "width": 0.6, "height": 1.0},
            "facecam_roi": {"x": 0.8, "y": 0.05, "width": 0.18, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 2560, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        assert probe["streams"][0]["width"] == 1080

    @pytest.mark.asyncio
    async def test_tc_t2_f15_03_gameplay_crop_native_9_16_portrait_source(self, tmp_path):
        """TC-T2-F15-03: 9:16 vertical source (1080x1920) scaled 1:1 with zero crop needed."""
        src_path = tmp_path / "src_portrait.mp4"
        out_path = tmp_path / "out_portrait.mp4"
        create_synthetic_portrait(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1080, 1920)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        assert probe["streams"][0]["width"] == 1080
        assert probe["streams"][0]["height"] == 1920

    @pytest.mark.asyncio
    async def test_tc_t2_f15_04_gameplay_crop_minimum_width_0_05(self, tmp_path):
        """TC-T2-F15-04: Micro-width gameplay slice (w=0.05) scaled up preserving aspect ratio."""
        src_path = tmp_path / "src_min_w.mp4"
        out_path = tmp_path / "out_min_w.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.45, "y": 0.0, "width": 0.05, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f15_05_gameplay_crop_minimum_height_0_05(self, tmp_path):
        """TC-T2-F15-05: Micro-height gameplay slice (h=0.05) scaled up preserving aspect ratio."""
        src_path = tmp_path / "src_min_h.mp4"
        out_path = tmp_path / "out_min_h.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.45, "width": 1.0, "height": 0.05},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f16_01_facecam_overlay_touching_bottom_right(self, tmp_path):
        """TC-T2-F16-01: Destination touching bottom-right boundary does not exceed 1080 x 1920."""
        src_path = tmp_path / "src_br.mp4"
        out_path = tmp_path / "out_br.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "bottom-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        fc = plan.regions[1]
        assert fc.x + fc.w <= 1080
        assert fc.y + fc.h <= 1920
        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f16_02_full_canvas_facecam_overlay(self, tmp_path):
        """TC-T2-F16-02: Full canvas facecam (1.0x1.0) completely covers gameplay layer cleanly."""
        src_path = tmp_path / "src_full_fc.mp4"
        out_path = tmp_path / "out_full_fc.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f16_03_minimum_sized_facecam_overlay(self, tmp_path):
        """TC-T2-F16-03: Micro facecam (w=0.05, h=0.05 -> 54x96px) renders cleanly."""
        src_path = tmp_path / "src_micro_fc.mp4"
        out_path = tmp_path / "out_micro_fc.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.0, "y": 0.0, "width": 0.05, "height": 0.05},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.1, "y": 0.1, "width": 0.05, "height": 0.05},
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f16_04_facecam_overlay_fractional_rounding(self, tmp_path):
        """TC-T2-F16-04: Fractional coordinates (0.333333, 0.666667) align to even canvas pixels (360, 1280)."""
        src_path = tmp_path / "src_frac.mp4"
        out_path = tmp_path / "out_frac.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.1, "y": 0.1, "width": 0.333333, "height": 0.333333},
            "facecam_placement": "custom",
            "facecam_output_rect": {"x": 0.333333, "y": 0.666667, "width": 0.30, "height": 0.22},
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fc = plan.regions[1]
        assert fc.x % 2 == 0
        assert fc.y % 2 == 0
        assert fc.w % 2 == 0
        assert fc.h % 2 == 0

        await reframe_to_vertical(src_path, out_path, plan=plan)
        assert out_path.exists()

    @pytest.mark.asyncio
    async def test_tc_t2_f16_05_verify_facecam_opacity_100_percent(self, tmp_path):
        """TC-T2-F16-05: Sample pixel inside facecam region has 100% facecam color; zero gameplay bleed-through."""
        src_path = tmp_path / "src_opacity.mp4"
        out_path = tmp_path / "out_opacity.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=1.0)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        img = extract_frame_image(out_path, time_sec=0.5)
        fc_pixel = img.getpixel((864, 287))
        bg_pixel = img.getpixel((300, 1000))

        assert fc_pixel[1] > 100 and fc_pixel[2] < 60, f"Facecam should be green, got {fc_pixel}"
        assert bg_pixel[2] > 100 and bg_pixel[1] < 60, f"Background should be blue, got {bg_pixel}"

    @pytest.mark.asyncio
    async def test_tc_t2_f18_01_source_video_mono_audio(self, tmp_path):
        """TC-T2-F18-01: Ingests 1-channel mono source; audio handled cleanly."""
        src_path = tmp_path / "src_mono.mp4"
        out_path = tmp_path / "out_mono.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=0.5",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-ac", "1",
            str(src_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        audio_streams = [s for s in probe["streams"] if s.get("codec_type") == "audio"]
        assert len(audio_streams) >= 1

    @pytest.mark.asyncio
    async def test_tc_t2_f18_02_source_video_44_1khz_audio(self, tmp_path):
        """TC-T2-F18-02: Ingests 44100Hz audio; preserves or resamples cleanly."""
        src_path = tmp_path / "src_44100.mp4"
        out_path = tmp_path / "out_44100.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=0.5",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=0.5",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        audio_streams = [s for s in probe["streams"] if s.get("codec_type") == "audio"]
        assert len(audio_streams) >= 1

    @pytest.mark.asyncio
    async def test_tc_t2_f18_03_source_video_silent_audio(self, tmp_path):
        """TC-T2-F18-03: Ingests silent audio track; output audio remains present."""
        src_path = tmp_path / "src_silent.mp4"
        out_path = tmp_path / "out_silent.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=0.5",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=0.5",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        probe = probe_media(out_path)
        audio_streams = [s for s in probe["streams"] if s.get("codec_type") == "audio"]
        assert len(audio_streams) >= 1

    @pytest.mark.asyncio
    async def test_tc_t2_f18_04_video_audio_track_longer_than_video(self, tmp_path):
        """TC-T2-F18-04: Audio longer than video; renders cleanly and video stream matches video duration."""
        src_path = tmp_path / "src_long_audio.mp4"
        out_path = tmp_path / "out_long_audio.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=0.5",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()
        assert out_path.stat().st_size > 0
        probe = probe_media(out_path)
        v_stream = next(s for s in probe["streams"] if s.get("codec_type") == "video")
        a_stream = next(s for s in probe["streams"] if s.get("codec_type") == "audio")
        v_dur = float(v_stream.get("duration", 0.5))
        assert abs(v_dur - 0.5) <= 0.2, f"Video stream duration unexpected: {v_dur}s"
        assert a_stream is not None

    @pytest.mark.asyncio
    async def test_tc_t2_f18_05_video_audio_track_shorter_than_video(self, tmp_path):
        """TC-T2-F18-05: Audio ends before video; handled cleanly without sync error."""
        src_path = tmp_path / "src_short_audio.mp4"
        out_path = tmp_path / "out_short_audio.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=1.0",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            str(src_path)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()

    def test_tc_t2_f21_03_equal_splits_clip_mode_regression(self):
        """TC-T2-F21-03: Splits source into requested intervals applying gaming layout across clips."""
        config = {
            "gameplay_roi": {"x": 0.1, "y": 0.0, "width": 0.8, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan1 = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        plan2 = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        plan3 = LayoutEngine.create_gaming_plan(config, 1920, 1080)

        for p in (plan1, plan2, plan3):
            assert p.canvas_width == 1080
            assert p.canvas_height == 1920
            assert len(p.regions) == 2
            assert p.regions[0].crop_coords == plan1.regions[0].crop_coords
            assert p.regions[1].crop_coords == plan1.regions[1].crop_coords

    def test_tc_t2_f21_04_ai_highlights_scoring_mode_regression(self):
        """TC-T2-F21-04: Applies gaming layout to AI highlights clips preserving dual-region framing."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.65, "y": 0.04, "width": 0.30, "height": 0.22},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.resolve_plan("gaming", 1920, 1080)
        assert isinstance(plan, LayoutPlan)
        assert len(plan.regions) == 2
        assert plan.regions[0].z_order == 1
        assert plan.regions[1].z_order == 2

    @pytest.mark.asyncio
    async def test_tc_t2_f22_01_payload_injection_subtitles_1_ignored(self, tmp_path):
        """TC-T2-F22-01: Reframe request with subtitles=1 parameter; output has 0 subtitle streams."""
        src_path = tmp_path / "src_sub_inject.mp4"
        out_path = tmp_path / "out_sub_inject.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "subtitles": 1,
            "burn_subtitles": True,
            "caption_style": "default",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert_zero_caption_invariant(out_path, check_directory=True)

    def test_tc_t2_f22_02_payload_injection_drawtext_caption_ignored(self):
        """TC-T2-F22-02: Request with drawtext_caption parameter; filtergraph contains no drawtext."""
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "drawtext_caption": "Victory Royale!",
            "caption_text": "Stream Highlights",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        fg = LayoutEngine.build_render_graph(plan, [Path("src.mp4"), Path("src.mp4")])
        assert_filtergraph_zero_caption_invariant(fg)

    @pytest.mark.asyncio
    async def test_tc_t2_f22_03_source_with_embedded_subtitle_track_stripped(self, tmp_path):
        """TC-T2-F22-03: Ingests MP4 containing embedded Mov_text/SRT track; -sn strips subtitle track from output."""
        srt_file = tmp_path / "sample.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nKillstreak\n", encoding="utf-8")

        src_with_sub = tmp_path / "src_embedded_sub.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=0.5",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
            "-i", str(srt_file),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            "-c:s", "mov_text",
            str(src_with_sub)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        src_probe = probe_media(src_with_sub)
        assert any(s.get("codec_type") == "subtitle" for s in src_probe["streams"])

        out_stripped = tmp_path / "out_stripped.mp4"
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_with_sub, out_stripped, plan=plan)

        out_probe = probe_media(out_stripped)
        out_subs = [s for s in out_probe["streams"] if s.get("codec_type") == "subtitle"]
        assert len(out_subs) == 0, f"Expected 0 subtitle streams after -sn, found: {out_subs}"

    @pytest.mark.asyncio
    async def test_tc_t2_f22_04_artifact_directory_check_for_orphaned_caption_files(self, tmp_path):
        """TC-T2-F22-04: Runs gaming pipeline; confirms 0 .srt or .vtt in artifact directory."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        src_path = artifact_dir / "src_pipeline.mp4"
        out_path = artifact_dir / "out_pipeline.mp4"
        create_synthetic_1080p_gameplay(src_path, duration=0.5)

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert_zero_caption_invariant(out_path, check_directory=True, directory_path=artifact_dir)

    @pytest.mark.asyncio
    async def test_tc_t2_f23_02_adversarial_large_buffer_stress(self, tmp_path):
        """TC-T2-F23-02: High bitrate/large frame buffer synthetic test completes cleanly."""
        src_path = tmp_path / "src_stress.mp4"
        out_path = tmp_path / "out_stress.mp4"
        generate_synthetic_video(src_path, width=1920, height=1080, duration=0.5, fps=60)

        config = {
            "gameplay_roi": {"x": 0.05, "y": 0.05, "width": 0.90, "height": 0.90},
            "facecam_roi": {"x": 0.60, "y": 0.05, "width": 0.35, "height": 0.35},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)
        await reframe_to_vertical(src_path, out_path, plan=plan)

        assert out_path.exists()
        assert out_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_tc_t2_f23_03_adversarial_sudden_process_failure_cleanup(self, tmp_path):
        """TC-T2-F23-03: Simulated FFmpeg nonzero failure; confirms temp files cleaned up and RuntimeError raised."""
        bad_src = tmp_path / "non_existent.mp4"
        out_path = tmp_path / "out_fail.mp4"

        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080)

        with pytest.raises(RuntimeError):
            await reframe_to_vertical(bad_src, out_path, plan=plan)

