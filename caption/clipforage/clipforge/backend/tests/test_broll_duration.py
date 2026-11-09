import os
import subprocess
import json
import pytest
from pathlib import Path
from backend.services.layout_engine import LayoutEngine
from backend.models.layout import LayoutPlan, RegionModel, ScaleMode, BackgroundPolicy, AudioPolicy
from backend.models.broll import DisplayMode

def probe_stream_durations(file_path: str):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,duration",
        "-of", "json", file_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    video_dur = None
    audio_dur = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and "duration" in s:
            video_dur = float(s["duration"])
        elif s.get("codec_type") == "audio" and "duration" in s:
            audio_dur = float(s["duration"])
    format_dur = float(data.get("format", {}).get("duration", 0))
    return {"video_duration": video_dur or format_dur, "audio_duration": audio_dur or format_dur, "format_duration": format_dur}

def test_broll_overlay_does_not_truncate_base_video(tmp_path: Path):
    """
    Verifies that a short B-roll overlay (e.g. 1.0s or 2.0s) onto a longer base video (5.0s)
    does NOT truncate the final video stream to the overlay duration.
    """
    base_video = tmp_path / "base_video.mp4"
    overlay_video = tmp_path / "overlay_broll.mp4"
    output_video = tmp_path / "output_broll.mp4"

    # Create 5s base video with audio tone
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=5:size=1080x1920:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-c:a", "aac",
        str(base_video)
    ], check=True, capture_output=True)

    # Create 1s overlay video
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=1080x1920:rate=30",
        "-c:v", "libx264",
        str(overlay_video)
    ], check=True, capture_output=True)

    # Verify input durations
    base_info = probe_stream_durations(str(base_video))
    overlay_info = probe_stream_durations(str(overlay_video))
    assert 4.8 <= base_info["video_duration"] <= 5.2
    assert 0.8 <= overlay_info["video_duration"] <= 1.2

    # Construct LayoutPlan matching apply_broll_task
    regions = [
        RegionModel(
            source_index=0,
            x=0, y=0, w=1080, h=1920,
            scale_mode=ScaleMode.CONTAIN,
            z_order=0
        ),
        RegionModel(
            source_index=1,
            start_time=1.0,
            end_time=3.0,
            fade_duration=0.2,
            z_order=1,
            x=0, y=0, w=1080, h=1920,
            scale_mode=ScaleMode.CROP
        )
    ]
    layout_plan = LayoutPlan(
        canvas_width=1080,
        canvas_height=1920,
        regions=regions,
        background_policy=BackgroundPolicy.NONE,
        audio_policy=AudioPolicy.PRIMARY_ONLY
    )

    inputs = [base_video, overlay_video]
    filtergraph = LayoutEngine.build_render_graph(layout_plan, inputs)

    cmd = ["ffmpeg", "-y"]
    for inp in inputs:
        cmd.extend(["-i", str(inp)])
    cmd.extend([
        "-filter_complex", filtergraph,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-f", "mp4",
        str(output_video)
    ])

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"

    out_info = probe_stream_durations(str(output_video))

    # Crucial assertion: Video duration must preserve the full 5s base clip duration,
    # NOT truncate to 1s overlay!
    assert out_info["video_duration"] >= 4.8, (
        f"Video stream truncated! Expected ~5.0s, got {out_info['video_duration']}s"
    )
    assert out_info["format_duration"] >= 4.8, (
        f"Container truncated! Expected ~5.0s, got {out_info['format_duration']}s"
    )
    assert out_info["audio_duration"] >= 4.8, (
        f"Audio truncated! Expected ~5.0s, got {out_info['audio_duration']}s"
    )


def sample_frame_rgb(video_path: Path, timestamp: float) -> tuple[float, float, float]:
    """Extracts a scaled frame at timestamp and computes average RGB values."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
        "-vf", "scale=64:64",
        "-vframes", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ]
    res = subprocess.run(cmd, capture_output=True, check=True)
    raw = res.stdout
    assert len(raw) > 0, f"No frame returned at timestamp {timestamp}"
    total_pixels = len(raw) // 3
    r = sum(raw[0::3]) / total_pixels
    g = sum(raw[1::3]) / total_pixels
    b = sum(raw[2::3]) / total_pixels
    return r, g, b


def test_broll_overlay_29s_base_clip_full_verification(tmp_path: Path):
    """
    Step 2 Verification:
    - 29-second base video (green, with 440Hz sine audio).
    - 2-second B-roll video (red).
    - Configured overlay interval [10.0, 12.0]s entirely within base clip.
    - Output preserves full intended duration within tolerance (29.0s +/- 0.2s).
    - B-roll is visible in intended interval (t=11s is red).
    - Original video resumes after B-roll finishes (t=15s is green).
    - Audio is not truncated (t >= 28.8s).
    - Output video is decodable.
    - Primary operational final.mp4 is untouched and not overwritten.
    """
    operational_path = Path("outputs/66f293c8-c227-40b7-8180-422d7733787f/clips/f828ab90-cb28-4ab9-9f00-edb3c1ebd4cd/final.mp4")
    assert operational_path.exists(), "Operational clip fixture must exist to verify non-destruction"
    op_stat_before = operational_path.stat()
    assert op_stat_before.st_size == 16649813, f"Unexpected operational fixture size {op_stat_before.st_size}"

    base_video = tmp_path / "base_29s.mp4"
    broll_video = tmp_path / "broll_2s.mp4"
    output_video = tmp_path / "output_29s_broll.mp4"

    # 1. Generate 29s solid green video with 440Hz sine audio
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0x00FF00:s=1080x1920:d=29:r=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=29",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(base_video)
    ], check=True, capture_output=True)

    # 2. Generate 2s solid red B-roll video
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=0xFF0000:s=1080x1920:d=2:r=30",
        "-c:v", "libx264", "-preset", "ultrafast",
        str(broll_video)
    ], check=True, capture_output=True)

    # 3. Build LayoutPlan with B-roll overlay at [10.0, 12.0]
    regions = [
        RegionModel(
            source_index=0,
            x=0, y=0, w=1080, h=1920,
            scale_mode=ScaleMode.CONTAIN,
            z_order=0
        ),
        RegionModel(
            source_index=1,
            start_time=10.0,
            end_time=12.0,
            fade_duration=0.1,
            z_order=1,
            x=0, y=0, w=1080, h=1920,
            scale_mode=ScaleMode.CROP
        )
    ]
    layout_plan = LayoutPlan(
        canvas_width=1080,
        canvas_height=1920,
        regions=regions,
        background_policy=BackgroundPolicy.NONE,
        audio_policy=AudioPolicy.PRIMARY_ONLY
    )

    inputs = [base_video, broll_video]
    filtergraph = LayoutEngine.build_render_graph(layout_plan, inputs)

    # 4. Render with FFmpeg
    cmd = ["ffmpeg", "-y"]
    for inp in inputs:
        cmd.extend(["-i", str(inp)])
    cmd.extend([
        "-filter_complex", filtergraph,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-f", "mp4",
        str(output_video)
    ])

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"

    # 5. Verify duration within documented tolerance (+/- 0.2s of 29.0s)
    out_info = probe_stream_durations(str(output_video))
    assert 28.8 <= out_info["video_duration"] <= 29.2, (
        f"Video duration {out_info['video_duration']}s outside tolerance [28.8, 29.2]s"
    )
    assert 28.8 <= out_info["format_duration"] <= 29.2, (
        f"Format duration {out_info['format_duration']}s outside tolerance [28.8, 29.2]s"
    )
    assert 28.8 <= out_info["audio_duration"] <= 29.2, (
        f"Audio duration {out_info['audio_duration']}s outside tolerance [28.8, 29.2]s"
    )

    # 6. Verify decodability (no FFmpeg decoding errors)
    decode_check = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output_video), "-f", "null", "-"],
        capture_output=True, text=True
    )
    assert decode_check.returncode == 0, f"Output video is not decodable: {decode_check.stderr}"
    assert decode_check.stderr.strip() == "", f"Decoding reported errors: {decode_check.stderr}"

    # 7. Verify visual frame states:
    # At t=5.0s: Base video (green dominant)
    r5, g5, b5 = sample_frame_rgb(output_video, 5.0)
    assert g5 > 150 and r5 < 60 and b5 < 60, f"Expected green base video at t=5s, got R={r5}, G={g5}, B={b5}"

    # At t=11.0s: B-roll active (red dominant)
    r11, g11, b11 = sample_frame_rgb(output_video, 11.0)
    assert r11 > 150 and g11 < 60 and b11 < 60, f"Expected red B-roll at t=11s, got R={r11}, G={g11}, B={b11}"

    # At t=15.0s: Original video resumes (green dominant)
    r15, g15, b15 = sample_frame_rgb(output_video, 15.0)
    assert g15 > 150 and r15 < 60 and b15 < 60, f"Expected green resumption at t=15s, got R={r15}, G={g15}, B={b15}"

    # 8. Verify primary operational final.mp4 is untouched
    op_stat_after = operational_path.stat()
    assert op_stat_before.st_mtime == op_stat_after.st_mtime, "Operational final.mp4 mtime was modified!"
    assert op_stat_before.st_size == op_stat_after.st_size == 16649813, "Operational final.mp4 size was modified!"

