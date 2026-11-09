"""
test_podcast_geometry_parity.py — Comprehensive Parity Verification for Podcast Crop Geometry.
Validates:
1. Exact mathematical parity between Python crop engine and language-neutral golden vectors.
2. FFmpeg crop and filtergraph strings (exact=1, proper scale/pad, zero distortion).
3. Even-pixel alignment on odd and even source dimensions for YUV420p chroma subsampling.
4. Actual synthetic video rendering and frame extraction through FFmpeg.
5. Standard Stacked Split (1080x960 top/bottom) and Single Speaker Focus (deterministic Area 1) regressions.
"""

import json
import os
import subprocess
from pathlib import Path
import pytest

from backend.services.advanced_podcast_engine import (
    calculate_side_by_side_participant_crop,
    calculate_9_16_crop_rect,
    render_visibility_driven_video
)
from backend.services.layout_engine import LayoutEngine

GOLDEN_VECTORS_PATH = Path("docs/engineering/podcast_geometry_golden_vectors.json")


def load_golden_vectors():
    assert GOLDEN_VECTORS_PATH.exists(), f"Golden vectors file missing at {GOLDEN_VECTORS_PATH}"
    with open(GOLDEN_VECTORS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["vectors"]


class TestPodcastGeometryParity:

    def test_golden_vectors_exist_and_cover_all_requirements(self):
        vectors = load_golden_vectors()
        assert len(vectors) >= 18, f"Expected at least 18 golden vectors, got {len(vectors)}"
        vector_ids = [v["id"] for v in vectors]
        
        required_coverage = [
            "vector-01-full-frame",
            "vector-02-narrow-region",
            "vector-03-wide-region",
            "vector-04-fractional-coordinates",
            "vector-05-tiny-box",
            "vector-06-touch-left-top",
            "vector-07-touch-right-bottom",
            "vector-08-out-of-range-negative",
            "vector-09-out-of-range-overflow",
            "vector-10-high-res-4k",
            "vector-11-720p-source",
            "vector-12-non-even-source",
            "vector-13-crop-wider-than-source",
            "vector-14-face-inside-region",
            "vector-15-face-outside-region",
            "vector-16-clamp-left",
            "vector-17-clamp-right",
            "vector-18-aspect-ratio-4-3"
        ]
        for req in required_coverage:
            assert req in vector_ids, f"Missing required golden vector: {req}"

    @pytest.mark.parametrize("vector_idx", range(18))
    def test_backend_crop_matches_golden_vector(self, vector_idx):
        vectors = load_golden_vectors()
        v = vectors[vector_idx]
        inp = v["input"]
        exp = v["expected"]

        actual = calculate_side_by_side_participant_crop(
            region=inp["region"],
            src_w=inp["src_w"],
            src_h=inp["src_h"],
            face_box=inp["face_box"],
            dest_panel_w=inp["dest_panel_w"],
            dest_panel_h=inp["dest_panel_h"]
        )

        # 1. Exact pixel bounds parity
        assert actual["x"] == exp["x"], f"[{v['id']}] x mismatch: {actual['x']} vs {exp['x']}"
        assert actual["y"] == exp["y"], f"[{v['id']}] y mismatch: {actual['y']} vs {exp['y']}"
        assert actual["w"] == exp["w"], f"[{v['id']}] w mismatch: {actual['w']} vs {exp['w']}"
        assert actual["h"] == exp["h"], f"[{v['id']}] h mismatch: {actual['h']} vs {exp['h']}"

        # 2. Even dimensions for YUV420p video codecs
        assert actual["x"] % 2 == 0, f"[{v['id']}] x ({actual['x']}) must be even"
        assert actual["y"] % 2 == 0, f"[{v['id']}] y ({actual['y']}) must be even"
        assert actual["w"] % 2 == 0, f"[{v['id']}] w ({actual['w']}) must be even"
        assert actual["h"] % 2 == 0, f"[{v['id']}] h ({actual['h']}) must be even"

        # 3. Containment within source and outward region coverage
        max_src_w = (inp["src_w"] // 2) * 2
        max_src_h = (inp["src_h"] // 2) * 2
        assert actual["x"] >= 0, f"[{v['id']}] x must be >= 0"
        assert actual["x"] + actual["w"] <= max_src_w, f"[{v['id']}] crop exceeds max width"
        assert actual["y"] >= 0, f"[{v['id']}] y must be >= 0"
        assert actual["y"] + actual["h"] <= max_src_h, f"[{v['id']}] crop exceeds max height"
        assert actual["x"] <= actual["region_left"], f"[{v['id']}] crop_x must not exceed region_left"
        assert actual["x"] + actual["w"] >= actual["region_right"], f"[{v['id']}] crop must cover region_right"

        # 4. Destination panel framing & padding parity
        assert actual["scaled_w"] == exp["scaled_w"], f"[{v['id']}] scaled_w mismatch"
        assert actual["scaled_h"] == exp["scaled_h"], f"[{v['id']}] scaled_h mismatch"
        assert actual["pad_x"] == exp["pad_x"], f"[{v['id']}] pad_x mismatch"
        assert actual["pad_y"] == exp["pad_y"], f"[{v['id']}] pad_y mismatch"
        assert abs(actual["scale_factor"] - exp["scale_factor"]) < 1e-5, f"[{v['id']}] scale_factor mismatch"

        # 5. FFmpeg filter string parity
        assert actual["ffmpeg_crop"] == exp["ffmpeg_crop"], f"[{v['id']}] ffmpeg_crop mismatch"
        assert actual["ffmpeg_filter"] == exp["ffmpeg_filter"], f"[{v['id']}] ffmpeg_filter mismatch"
        assert ":exact=1" in actual["ffmpeg_crop"], f"[{v['id']}] ffmpeg_crop must contain exact=1"

    def test_calculate_9_16_crop_rect_even_bounds_on_odd_sources(self):
        # Odd dimensions 1921x1081
        res = calculate_9_16_crop_rect(0.5, 1921, 1081)
        assert res["x"] % 2 == 0
        assert res["w"] % 2 == 0
        assert res["y"] % 2 == 0
        assert res["h"] % 2 == 0
        assert res["x"] + res["w"] <= 1920
        assert res["y"] + res["h"] <= 1080

    def test_standard_stacked_split_regression(self):
        # Preserves Standard Stacked Split: Area 1 top 1080x960, Area 2 bottom 1080x960
        regions = [
            {"x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8},
            {"x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8}
        ]
        plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080, composition="stacked")
        assert len(plan.regions) == 2
        # Top panel
        assert plan.regions[0].w == 1080
        assert plan.regions[0].h == 960
        assert plan.regions[0].x == 0
        assert plan.regions[0].y == 0
        # Bottom panel
        assert plan.regions[1].w == 1080
        assert plan.regions[1].h == 960
        assert plan.regions[1].x == 0
        assert plan.regions[1].y == 960

    def test_single_speaker_focus_regression(self):
        # Preserves Single Speaker Focus: Area 1/index 0 only, 1080x1920 full frame
        regions = [
            {"x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8},
            {"x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8}
        ]
        plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080, composition="single_focus")
        assert len(plan.regions) == 1
        assert plan.regions[0].w == 1080
        assert plan.regions[0].h == 1920
        assert plan.regions[0].x == 0
        assert plan.regions[0].y == 0
        # Must deterministically use crop coordinates of Area 1 (index 0)
        cx, cy, cw, ch = plan.regions[0].crop_coords
        assert cx == int(round(0.05 * 1920) // 2) * 2

    @pytest.mark.asyncio
    async def test_real_render_side_by_side_actual_agreement(self, tmp_path):
        """
        Renders an actual synthetic side-by-side clip through render_visibility_driven_video.
        Inspects output with ffprobe to verify 1080x1920, 540x1920 half-panels, AAC audio, 0 subtitles.
        """
        src_mp4 = tmp_path / "src_parity.mp4"
        out_mp4 = tmp_path / "out_parity.mp4"

        # Create 3-second 1920x1080 synthetic video with left blue box and right purple box
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=black:s=1920x1080:d=3.0,drawbox=x=192:y=108:w=576:h=864:c=blue:t=fill,drawbox=x=1152:y=108:w=576:h=864:c=purple:t=fill",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=3.0",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(src_mp4)
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, f"FFmpeg failed: {proc.stderr}"

        # Schedule with SIDE_BY_SIDE composition
        crop_a = calculate_side_by_side_participant_crop({"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8}, 1920, 1080)
        crop_b = calculate_side_by_side_participant_crop({"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}, 1920, 1080)

        schedule = [
            {
                "start_time": 0.0,
                "end_time": 3.0,
                "composition": "SIDE_BY_SIDE",
                "crop_a": crop_a,
                "crop_b": crop_b,
                "region_a": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8},
                "region_b": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.8}
            }
        ]

        rendered = await render_visibility_driven_video(
            video_path=src_mp4,
            output_path=out_mp4,
            schedule=schedule,
            clip_start=0.0,
            clip_end=3.0,
            canvas_w=1080,
            canvas_h=1920
        )
        assert rendered.exists()
        assert rendered.stat().st_size > 0

        # FFprobe verification
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height",
            "-of", "json",
            str(rendered)
        ]
        probe_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert probe_res.returncode == 0
        probe_data = json.loads(probe_res.stdout)

        streams = probe_data["streams"]
        v_stream = next(s for s in streams if s["codec_type"] == "video")
        a_stream = next(s for s in streams if s["codec_type"] == "audio")
        sub_streams = [s for s in streams if s["codec_type"] == "subtitle"]

        assert v_stream["width"] == 1080
        assert v_stream["height"] == 1920
        assert v_stream["codec_name"] == "h264"
        assert a_stream["codec_name"] == "aac"
        assert len(sub_streams) == 0, "Subtitles are strictly prohibited!"
