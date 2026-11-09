import asyncio
import subprocess
from pathlib import Path

async def test_sendcmd():
    # Write a dummy sendcmd file
    cmd_file = Path("/app/outputs/test_cmd.txt")
    with open(cmd_file, "w") as f:
        # We will pan from x=0 to x=800 over 5 seconds
        duration = 5.0
        fps = 25
        total_frames = int(duration * fps)
        for i in range(total_frames):
            t = i / fps
            x = int((i / total_frames) * (1280 - 405))
            y = 0
            f.write(f"{t:.4f} crop x {x};\n")
            f.write(f"{t:.4f} crop y {y};\n")

    print(f"Created command file at {cmd_file}")

    # Run ffmpeg with sendcmd and crop
    # Crop size: 405x720 (9:16 aspect ratio inside 1280x720 input)
    # Target output size: 1080x1920
    # Let's test the filter complex:
    # [0:v]sendcmd=f=/app/outputs/test_cmd.txt,crop=w=405:h=720:x=0:y=0,scale=1080:1920[outv]
    cmd = [
        "ffmpeg", "-y",
        "-i", "/app/uploads/dummy_landscape.mp4",
        "-filter_complex", "[0:v]sendcmd=f=/app/outputs/test_cmd.txt,crop=w=405:h=720:x=0:y=0,scale=1080:1920[outv]",
        "-map", "[outv]",
        "-c:v", "libx264",
        "-preset", "fast",
        "/app/outputs/test_panning.mp4"
    ]
    
    print("Running ffmpeg...")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    print("FFmpeg return code:", proc.returncode)
    if proc.returncode != 0:
        print("Error:")
        print(stderr.decode())
    else:
        print("Success! Output saved to /app/outputs/test_panning.mp4")

if __name__ == "__main__":
    asyncio.run(test_sendcmd())
