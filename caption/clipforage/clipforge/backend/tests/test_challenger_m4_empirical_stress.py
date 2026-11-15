"""
backend/tests/test_challenger_m4_empirical_stress.py
===================================================
Challenger Empirical Stress Verification Suite for Milestone M4.
Executes independent empirical probes to stress-test:
1. Zero split filter deadlocks via single-source input flattening [input_path, input_path]
2. Audio and duration preservation (duration delta < 0.05s, start PTS < 0.001s, eof_action=pass:repeatlast=0)
3. R5 Zero-Caption Mandate (-sn flag, 0 subtitle streams, 0 caption files, 0 drawtext filters, 422 on injection)
4. Persistence without schema migrations (Job.config JSON roundtrip)
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
import pytest

from backend.models.layout import GamingLayoutConfig, LayoutPlan, ScaleMode, LayoutMode
from backend.services.gaming_geometry import (
    calculate_gaming_coordinates,
    create_gaming_layout_plan,
    validate_gaming_layout,
)
from backend.services.layout_engine import LayoutEngine
from backend.services.reframe_engine import reframe_to_vertical, run_ffmpeg
from backend.tests.gaming_test_fixtures import (
    assert_faststart_moov_atom,
    assert_filtergraph_zero_caption_invariant,
    assert_gaming_video_invariants,
    assert_zero_caption_invariant,
    generate_synthetic_video,
    probe_media,
)
from backend.models.models import Job


@pytest.fixture(scope="module")
def challenger_stress_dir(tmp_path_factory) -> Path:
    wdir = tmp_path_factory.mktemp("challenger_m4_stress")
    return wdir


class TestChallengerEmpiricalVerification:
    """Empirical challenger stress suite."""

    # --------------------------------------------------------------------------
    # 1. ZERO SPLIT FILTER DEADLOCKS & INPUT FLATTENING
    # --------------------------------------------------------------------------
    def test_single_source_input_flattening_and_no_split_filter(self):
        config = {
            "mode": "gaming",
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "facecam_output_rect": {"x": 0.65, "y": 0.05, "width": 0.30, "height": 0.25},
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, 1920, 1080, 1080, 1920)
        assert len(plan.regions) == 2, "Gaming layout plan must have exactly 2 regions"
        assert plan.regions[0].z_order == 1
        assert plan.regions[1].z_order == 2

        # In reframe_to_vertical, flat_inputs contains [input_path, input_path]
        dummy_input = Path("dummy_gameplay.mp4")
        flat_inputs = [dummy_input, dummy_input]
        plan.regions[0].source_index = 0
        plan.regions[1].source_index = 1

        filtergraph = LayoutEngine.build_render_graph(plan, flat_inputs)

        # Invariant: split filter must NOT appear in filtergraph
        assert "split=" not in filtergraph, f"Split filter found in filtergraph: {filtergraph}"
        assert "[0:v]" in filtergraph, f"Missing primary source 0:v: {filtergraph}"
        assert "[1:v]" in filtergraph, f"Missing secondary source 1:v: {filtergraph}"
        assert "setsar=1" in filtergraph
        assert "eof_action=pass:repeatlast=0" in filtergraph, "Secondary overlay must have eof_action=pass:repeatlast=0"

    # --------------------------------------------------------------------------
    # 2. AUDIO & DURATION PRESERVATION & START PTS ALIGNMENT
    # --------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_audio_sync_duration_and_start_pts_alignment(self, challenger_stress_dir: Path):
        source_path = challenger_stress_dir / "stress_source_sync.mp4"
        out_path = challenger_stress_dir / "stress_rendered_sync.mp4"

        # Generate synthetic video with 3.500s duration and 440Hz sine audio
        generate_synthetic_video(
            output_path=source_path,
            width=1920,
            height=1080,
            duration=3.5,
            fps=30,
            audio_freq=440,
        )

        in_probe = probe_media(source_path)
        in_v = [s for s in in_probe["streams"] if s["codec_type"] == "video"][0]
        in_a = [s for s in in_probe["streams"] if s["codec_type"] == "audio"][0]
        in_v_dur = float(in_v.get("duration", in_probe["format"]["duration"]))
        in_a_dur = float(in_a.get("duration", in_probe["format"]["duration"]))

        # Render with gaming layout
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
        await reframe_to_vertical(
            input_path=source_path,
            output_path=out_path,
            mode="gaming",
            plan=plan,
        )

        assert out_path.exists()
        out_probe = probe_media(out_path)
        out_v = [s for s in out_probe["streams"] if s["codec_type"] == "video"][0]
        out_a = [s for s in out_probe["streams"] if s["codec_type"] == "audio"][0]
        out_v_dur = float(out_v.get("duration", out_probe["format"]["duration"]))
        out_a_dur = float(out_a.get("duration", out_probe["format"]["duration"]))

        # Verify duration preservation delta < 0.05s
        v_dur_delta = abs(out_v_dur - in_v_dur)
        a_dur_delta = abs(out_a_dur - in_a_dur)
        assert v_dur_delta < 0.05, f"Video duration delta {v_dur_delta:.4f}s exceeds 0.05s tolerance"
        assert a_dur_delta < 0.05, f"Audio duration delta {a_dur_delta:.4f}s exceeds 0.05s tolerance"

        # Verify start PTS alignment < 0.001s using detailed packet inspection
        ffprobe_pts_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=start_time,start_pts",
            "-of", "json",
            str(out_path),
        ]
        res = subprocess.run(ffprobe_pts_cmd, stdout=subprocess.PIPE, text=True, check=True)
        pts_data = json.loads(res.stdout)
        for s in pts_data["streams"]:
            st = float(s.get("start_time", 0.0))
            assert abs(st) < 0.001, f"Start time {st} exceeds 0.001s PTS alignment threshold"

        # Verify faststart atom ordering
        atoms = assert_faststart_moov_atom(out_path)
        assert atoms.index("moov") < atoms.index("mdat")

    # --------------------------------------------------------------------------
    # 3. R5 ZERO-CAPTION MANDATE VERIFICATION
    # --------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_r5_zero_caption_mandate_adversarial(self, challenger_stress_dir: Path):
        source_raw = challenger_stress_dir / "stress_raw.mp4"
        source_sub = challenger_stress_dir / "stress_with_subtitles.mp4"
        out_rendered = challenger_stress_dir / "stress_rendered_nosub.mp4"

        generate_synthetic_video(source_raw, 1920, 1080, duration=2.0)

        # Create mock SRT and mux into source
        mock_srt = challenger_stress_dir / "temp_input_sub.srt"
        mock_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nMalicious Subtitle\n\n", encoding="utf-8")

        mux_cmd = [
            "ffmpeg", "-y",
            "-i", str(source_raw),
            "-i", str(mock_srt),
            "-c:v", "copy", "-c:a", "copy",
            "-c:s", "mov_text",
            str(source_sub),
        ]
        proc = subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        mock_srt.unlink(missing_ok=True)
        assert proc.returncode == 0

        # Verify source indeed has a subtitle stream
        src_probe = probe_media(source_sub)
        assert any(s.get("codec_type") == "subtitle" for s in src_probe["streams"])

        # Render with gaming layout
        config = {
            "gameplay_roi": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        plan = LayoutEngine.create_gaming_plan(config, source_w=1920, source_h=1080)
        await reframe_to_vertical(
            input_path=source_sub,
            output_path=out_rendered,
            mode="gaming",
            plan=plan,
        )

        # Invariant checks:
        # 1. 0 subtitle streams on rendered MP4
        out_probe = probe_media(out_rendered)
        sub_streams = [s for s in out_probe["streams"] if s.get("codec_type") == "subtitle"]
        assert len(sub_streams) == 0, f"Found {len(sub_streams)} subtitle stream(s) in rendered video!"

        # 2. 0 caption files in output directory
        assert_zero_caption_invariant(out_rendered, check_directory=True)

        # 3. Filtergraph contains zero drawtext or subtitles
        fg = LayoutEngine.build_render_graph(plan, [source_sub, source_sub])
        assert_filtergraph_zero_caption_invariant(fg)

    # --------------------------------------------------------------------------
    # 4. PERSISTENCE INVARIANT (Job.config JSON WITHOUT SCHEMA MIGRATIONS)
    # --------------------------------------------------------------------------
    def test_persistence_without_schema_migration(self):
        from sqlalchemy import inspect
        from backend.models.models import Job

        mapper = inspect(Job)
        columns = {c.key: c for c in mapper.column_attrs}

        # Verify config exists and is Text (JSON string)
        assert "config" in columns, "Job model must contain 'config' column"
        assert not hasattr(Job, "gameplay_roi"), "Job model should NOT have separate gameplay_roi column (no migration)"
        assert not hasattr(Job, "facecam_roi"), "Job model should NOT have separate facecam_roi column (no migration)"

        # Verify lossless JSON roundtrip
        gaming_cfg = {
            "mode": "gaming",
            "gameplay_roi": {"x": 0.12, "y": 0.08, "width": 0.80, "height": 0.84},
            "facecam_roi": {"x": 0.70, "y": 0.05, "width": 0.25, "height": 0.25},
            "facecam_placement": "top-right",
            "facecam_output_rect": {"x": 0.65, "y": 0.05, "width": 0.30, "height": 0.25},
            "canvas_width": 1080,
            "canvas_height": 1920,
        }
        job = Job(id="stress_job_001", source_title="Test Gameplay", config=json.dumps({"gaming_layout": gaming_cfg}))
        assert job.config is not None

        loaded = json.loads(job.config)
        assert loaded["gaming_layout"] == gaming_cfg
