"""
verify_podcast_real_render.py
==============================
Executes a real end-to-end render test using FFmpeg and FFprobe:
1. Generates a synthetic 1920x1080 3-second test video with two distinct colored halves (left=blue, right=red) and audio tone.
2. Defines 2 podcast speaker selection regions (Speaker 1 left, Speaker 2 right).
3. Constructs the LayoutPlan via LayoutEngine.create_podcast_plan (composition='stacked').
4. Renders the vertical video via reframe_to_vertical.
5. Runs ffprobe to assert:
   - Output resolution is exactly 1080x1920 (9:16 vertical).
   - Video codec is h264.
   - Audio codec is aac.
   - Subtitle streams count is exactly 0.
"""
import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from backend.services.layout_engine import LayoutEngine
from backend.services.reframe_engine import reframe_to_vertical


async def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        source_video = tmp_path / "source_1080p.mp4"
        output_video = tmp_path / "podcast_stacked_output.mp4"

        print("[Step 1] Generating synthetic 1920x1080 test video with audio tone...")
        # Left half blue, right half red, 3 seconds, 30fps, 440Hz test audio tone
        gen_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "testsrc=size=1920x1080:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=3",
            "-t", "3",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(source_video)
        ]
        res = subprocess.run(gen_cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Failed to generate source video: {res.stderr}"
        assert source_video.exists(), "Source video was not created"
        print(f"  Source created: {source_video} ({source_video.stat().st_size} bytes)")

        print("\n[Step 2] Defining podcast regions and building LayoutPlan...")
        regions = [
            {"id": "spk-1", "label": "Speaker 1 (Left)", "x": 0.05, "y": 0.1, "width": 0.42, "height": 0.8},
            {"id": "spk-2", "label": "Speaker 2 (Right)", "x": 0.53, "y": 0.1, "width": 0.42, "height": 0.8},
        ]
        plan = LayoutEngine.create_podcast_plan(
            regions_normalized=regions,
            source_w=1920,
            source_h=1080,
            composition="stacked",
            canvas_w=1080,
            canvas_h=1920
        )
        print(f"  LayoutPlan Mode: {plan.mode.value}")
        print(f"  Region 0: crop={plan.regions[0].crop_coords}, canvas=(x={plan.regions[0].x}, y={plan.regions[0].y}, w={plan.regions[0].w}, h={plan.regions[0].h})")
        print(f"  Region 1: crop={plan.regions[1].crop_coords}, canvas=(x={plan.regions[1].x}, y={plan.regions[1].y}, w={plan.regions[1].w}, h={plan.regions[1].h})")

        print("\n[Step 3] Rendering stacked vertical video via reframe_to_vertical...")
        rendered_path = await reframe_to_vertical(
            input_path=source_video,
            output_path=output_video,
            plan=plan
        )
        assert rendered_path.exists(), f"Rendered output missing: {rendered_path}"
        output_size = rendered_path.stat().st_size
        print(f"  Rendered output successfully: {rendered_path} ({output_size} bytes)")

        print("\n[Step 4] Running FFprobe verification on rendered output...")
        probe_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(rendered_path)
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        assert probe_res.returncode == 0, f"FFprobe failed: {probe_res.stderr}"

        probe_data = json.loads(probe_res.stdout)
        streams = probe_data.get("streams", [])
        
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

        print(f"  Video streams found: {len(video_streams)}")
        print(f"  Audio streams found: {len(audio_streams)}")
        print(f"  Subtitle streams found: {len(sub_streams)}")

        assert len(video_streams) == 1, f"Expected exactly 1 video stream, got {len(video_streams)}"
        v = video_streams[0]
        width = int(v.get("width"))
        height = int(v.get("height"))
        v_codec = v.get("codec_name")

        print(f"  Dimensions: {width}x{height}")
        print(f"  Video codec: {v_codec}")

        assert width == 1080 and height == 1920, f"Dimensions must be 1080x1920, got {width}x{height}"
        assert v_codec == "h264", f"Video codec must be h264, got {v_codec}"

        assert len(audio_streams) == 1, f"Expected 1 audio stream, got {len(audio_streams)}"
        a_codec = audio_streams[0].get("codec_name")
        print(f"  Audio codec: {a_codec}")
        assert a_codec == "aac", f"Audio codec must be aac, got {a_codec}"

        # Subtitle invariant: Zero subtitle streams
        assert len(sub_streams) == 0, f"Forbidden subtitle streams found: {len(sub_streams)}"
        print("  Subtitle check: 0 subtitle streams (Invariant Verified)")

        print("\n[Step 5] Testing single_region composition rendering and verification...")
        output_single = tmp_path / "podcast_single_output.mp4"
        single_plan = LayoutEngine.create_podcast_plan(
            regions_normalized=[regions[0]],
            source_w=1920,
            source_h=1080,
            composition="single_region",
            canvas_w=1080,
            canvas_h=1920
        )
        rendered_single = await reframe_to_vertical(
            input_path=source_video,
            output_path=output_single,
            plan=single_plan
        )
        assert rendered_single.exists()
        probe_res_single = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(rendered_single)
        ], capture_output=True, text=True)
        probe_single_data = json.loads(probe_res_single.stdout)
        v_single = [s for s in probe_single_data.get("streams", []) if s.get("codec_type") == "video"][0]
        assert int(v_single.get("width")) == 1080 and int(v_single.get("height")) == 1920
        assert v_single.get("codec_name") == "h264"
        print(f"  Single region output: {rendered_single.name} ({rendered_single.stat().st_size} bytes, 1080x1920 h264)")

        print("\n=== ALL REAL VIDEO RENDERING ACCEPTANCE CRITERIA SATISFIED ===")


if __name__ == "__main__":
    asyncio.run(main())
