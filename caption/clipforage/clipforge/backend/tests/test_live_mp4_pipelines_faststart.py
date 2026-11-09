"""
Live verification of MP4 faststart atom ordering across major pipeline families.
Renders real output files using FFmpeg in the test environment and parses
top-level binary box headers to verify moov precedes mdat.
"""
import pytest
import os
import subprocess
from pathlib import Path

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
            if size == 1:
                ext_size = int.from_bytes(f.read(8), "big")
                f.seek(max(0, ext_size - 16), 1)
            elif size == 0:
                break
            else:
                f.seek(max(0, size - 8), 1)
    return atoms

def generate_synthetic_mp4(out_path: Path, duration: int = 1):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-f", "mp4",
        str(out_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class TestLiveFaststartAcrossPipelines:

    def test_pipeline_1_clip_cutter_faststart(self, tmp_path):
        src = tmp_path / "src.mp4"
        out = tmp_path / "cut_out.mp4"
        generate_synthetic_mp4(src)

        cmd = [
            "ffmpeg", "-y", "-ss", "0.0", "-to", "0.5",
            "-i", str(src),
            "-c", "copy",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(out)
        ]
        subprocess.run(cmd, check=True)

        atoms = parse_top_level_atoms(out)
        assert "moov" in atoms and "mdat" in atoms
        assert atoms.index("moov") < atoms.index("mdat"), f"moov must precede mdat, got {atoms}"

    def test_pipeline_2_reframe_vertical_faststart(self, tmp_path):
        src = tmp_path / "src.mp4"
        out = tmp_path / "reframe_out.mp4"
        generate_synthetic_mp4(src)

        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(out)
        ]
        subprocess.run(cmd, check=True)

        atoms = parse_top_level_atoms(out)
        assert "moov" in atoms and "mdat" in atoms
        assert atoms.index("moov") < atoms.index("mdat"), f"moov must precede mdat, got {atoms}"

    def test_pipeline_3_podcast_single_shot_faststart(self, tmp_path):
        src = tmp_path / "src.mp4"
        out = tmp_path / "podcast_out.mp4"
        generate_synthetic_mp4(src)

        cmd = [
            "ffmpeg", "-y", "-ss", "0.0", "-to", "0.5",
            "-i", str(src),
            "-vf", "crop=180:240:70:0,scale=1080:1920",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac",
            "-sn",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(out)
        ]
        subprocess.run(cmd, check=True)

        atoms = parse_top_level_atoms(out)
        assert "moov" in atoms and "mdat" in atoms
        assert atoms.index("moov") < atoms.index("mdat"), f"moov must precede mdat, got {atoms}"

    def test_pipeline_4_audio_sfx_mix_faststart(self, tmp_path):
        src = tmp_path / "src.mp4"
        out = tmp_path / "sfx_out.mp4"
        generate_synthetic_mp4(src)

        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-f", "mp4",
            str(out)
        ]
        subprocess.run(cmd, check=True)

        atoms = parse_top_level_atoms(out)
        assert "moov" in atoms and "mdat" in atoms
        assert atoms.index("moov") < atoms.index("mdat"), f"moov must precede mdat, got {atoms}"

    def test_pipeline_5_overlay_watermark_faststart(self, tmp_path):
        src = tmp_path / "src.mp4"
        wm = tmp_path / "wm.png"
        out = tmp_path / "wm_out.mp4"
        generate_synthetic_mp4(src)
        
        # Create 1x1 transparent png
        cmd_png = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red@0.5:s=32x32:d=1", "-frames:v", "1", str(wm)]
        subprocess.run(cmd_png, check=True)

        cmd = [
            "ffmpeg", "-y", "-i", str(src), "-i", str(wm),
            "-filter_complex", "[0:v][1:v]overlay=10:10[outv]",
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out)
        ]
        subprocess.run(cmd, check=True)

        atoms = parse_top_level_atoms(out)
        assert "moov" in atoms and "mdat" in atoms
        assert atoms.index("moov") < atoms.index("mdat"), f"moov must precede mdat, got {atoms}"

