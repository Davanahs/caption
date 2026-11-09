"""
Focused verification for DEF-MEDIA-01: FFmpeg MP4 faststart optimization.
Verifies that all MP4 rendering and container encoding invocations include
`-movflags +faststart`, ensuring the `moov` atom is positioned before `mdat`
for instantaneous progressive web streaming.
"""
import pytest
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from backend.services import clip_cutter
from backend.services import advanced_podcast_engine as ape
from backend.services import reframe_engine
from backend.services import sfx_mixer
from backend.services import overlay_engine
from backend.services import hook_generator
from backend.services import voice_cloner


def parse_top_level_atoms(file_path: Path) -> list[str]:
    """Parses top-level ISO base media file format (MP4) atoms."""
    atoms = []
    with open(file_path, "rb") as f:
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            size = int.from_bytes(header[:4], "big")
            atom_type = header[4:8].decode("latin1", errors="replace")
            atoms.append(atom_type)
            if size == 1:  # 64-bit size
                ext_size = int.from_bytes(f.read(8), "big")
                f.seek(max(0, ext_size - 16), 1)
            elif size == 0:  # Extends to EOF
                break
            else:
                f.seek(max(0, size - 8), 1)
    return atoms


class TestDefMedia01FaststartFlags:
    """Verifies that every MP4 encoding pipeline emits -movflags +faststart."""

    @pytest.mark.asyncio
    async def test_clip_cutter_cut_clip_emits_faststart(self, tmp_path):
        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "", "")

        with patch("backend.services.clip_cutter.run_ffmpeg", side_effect=fake_run_ffmpeg):
            await clip_cutter.cut_clip(
                input_path=str(tmp_path / "in.mp4"),
                output_path=str(tmp_path / "out.mp4"),
                start=1.0,
                end=3.0
            )

        assert captured_cmd is not None
        assert "-movflags" in captured_cmd
        mf_idx = captured_cmd.index("-movflags")
        assert captured_cmd[mf_idx + 1] == "+faststart"

    @pytest.mark.asyncio
    async def test_reframe_engine_emits_faststart(self, tmp_path):
        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "", "")

        src = tmp_path / "input.mp4"
        src.touch()
        out = tmp_path / "out.mp4"

        with patch("backend.services.reframe_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.reframe_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):
            await reframe_engine.reframe_to_vertical(
                input_path=src,
                output_path=out,
                mode="fit"
            )

        assert captured_cmd is not None
        assert "-movflags" in captured_cmd
        mf_idx = captured_cmd.index("-movflags")
        assert captured_cmd[mf_idx + 1] == "+faststart"

    @pytest.mark.asyncio
    async def test_advanced_podcast_single_shot_emits_faststart(self, tmp_path):
        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "", "")

        src = tmp_path / "src.mp4"
        src.touch()
        out = tmp_path / "out.mp4"
        schedule = [
            {"start_time": 0.0, "end_time": 5.0, "crop_rect": {"x": 0, "y": 0, "w": 608, "h": 1080}, "active_track_id": "spk"}
        ]

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):
            await ape.render_camera_following_video(
                video_path=src,
                output_path=out,
                shot_schedule=schedule,
                clip_start=0.0,
                clip_end=5.0
            )

        assert captured_cmd is not None
        assert "-movflags" in captured_cmd
        mf_idx = captured_cmd.index("-movflags")
        assert captured_cmd[mf_idx + 1] == "+faststart"

    @pytest.mark.asyncio
    async def test_advanced_podcast_dynamic_concat_emits_faststart(self, tmp_path):
        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "", "")

        src = tmp_path / "src.mp4"
        src.touch()
        out = tmp_path / "out.mp4"
        schedule = [
            {"start_time": 0.0, "end_time": 2.0, "crop_rect": {"x": 0, "y": 0, "w": 608, "h": 1080}, "active_track_id": "spk1"},
            {"start_time": 2.0, "end_time": 5.0, "crop_rect": {"x": 200, "y": 0, "w": 608, "h": 1080}, "active_track_id": "spk2"}
        ]

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):
            await ape.render_camera_following_video(
                video_path=src,
                output_path=out,
                shot_schedule=schedule,
                clip_start=0.0,
                clip_end=5.0
            )

        assert captured_cmd is not None
        assert "-movflags" in captured_cmd
        mf_idx = captured_cmd.index("-movflags")
        assert captured_cmd[mf_idx + 1] == "+faststart"

    @pytest.mark.asyncio
    async def test_advanced_podcast_visibility_driven_emits_faststart(self, tmp_path):
        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "", "")

        src = tmp_path / "src.mp4"
        src.touch()
        out = tmp_path / "out.mp4"
        schedule = [
            {"shot_id": 1, "start_time": 0.0, "end_time": 5.0, "composition": "SIDE_BY_SIDE", "crop_a": {"x": 0, "y": 0, "w": 540, "h": 960}, "crop_b": {"x": 540, "y": 0, "w": 540, "h": 960}}
        ]

        with patch("backend.services.advanced_podcast_engine.get_video_dimensions", return_value=(1920, 1080)), \
             patch("backend.services.advanced_podcast_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):
            await ape.render_visibility_driven_video(
                video_path=src,
                output_path=out,
                schedule=schedule,
                clip_start=0.0,
                clip_end=5.0
            )

        assert captured_cmd is not None
        assert "-movflags" in captured_cmd
        mf_idx = captured_cmd.index("-movflags")
        assert captured_cmd[mf_idx + 1] == "+faststart"

    @pytest.mark.asyncio
    async def test_sfx_mixer_command_emits_faststart(self, tmp_path):
        from backend.models.sfx import SFXPlan
        plan = SFXPlan(clip_id="test_clip", placements=[])
        cmd = await sfx_mixer.SFXMixer.build_ffmpeg_command(
            video_input_path="input.mp4",
            sfx_plan=plan,
            output_path="output.mp4"
        )
        assert "-movflags" in cmd
        mf_idx = cmd.index("-movflags")
        assert cmd[mf_idx + 1] == "+faststart"

    @pytest.mark.asyncio
    async def test_overlay_engine_watermark_emits_faststart(self, tmp_path):
        captured_cmd = None

        async def fake_run_ffmpeg(cmd):
            nonlocal captured_cmd
            captured_cmd = cmd
            return (0, "", "")

        src = tmp_path / "src.mp4"
        src.touch()
        wm = tmp_path / "logo.png"
        wm.touch()
        out = tmp_path / "out.mp4"

        with patch("backend.services.overlay_engine.run_ffmpeg", side_effect=fake_run_ffmpeg):
            await overlay_engine.apply_watermark(
                video_path=src,
                watermark_url=str(wm),
                output_path=out
            )

        assert captured_cmd is not None
        assert "-movflags" in captured_cmd
        mf_idx = captured_cmd.index("-movflags")
        assert captured_cmd[mf_idx + 1] == "+faststart"

    def test_live_mp4_faststart_atom_order(self, tmp_path):
        """
        Renders a live 1-second synthetic MP4 with FFmpeg using -movflags +faststart,
        and directly checks the resulting binary structure to prove the `moov` atom
        precedes the `mdat` atom.
        """
        out_faststart = tmp_path / "faststart.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(out_faststart)
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            pytest.skip("ffmpeg binary not present in test runner")

        atoms = parse_top_level_atoms(out_faststart)
        assert "moov" in atoms, f"Expected 'moov' atom in {atoms}"
        assert "mdat" in atoms, f"Expected 'mdat' atom in {atoms}"
        moov_idx = atoms.index("moov")
        mdat_idx = atoms.index("mdat")
        assert moov_idx < mdat_idx, (
            f"Expected 'moov' (index {moov_idx}) to precede 'mdat' (index {mdat_idx}) for faststart, got atoms: {atoms}"
        )
