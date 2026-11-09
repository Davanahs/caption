"""
Comprehensive End-to-End Automated Pipeline Verifier
Tests all 15 phases by processing a test video through the live FastAPI & Celery backend.
"""
import os
import sys
import time
import json
import uuid
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://localhost:8000"

def create_sample_video(output_path: str) -> str:
    """Creates a 15-second synthetic test video with audio track using FFmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-vf", "drawtext=text='ClipForge AI E2E Test Video':fontcolor=white:fontsize=48:x=(w-tw)/2:y=(h-th)/2",
        "-t", "15",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[OK] Created test video: {output_path} ({os.path.getsize(output_path)} bytes)")
    return output_path


def run_e2e_verification():
    print("=" * 60)
    print("[E2E] ClipForge Automated E2E Pipeline Verification (Phases 1-15)")
    print("=" * 60)

    # 1. Create sample video file
    sample_file = os.path.abspath("uploads/e2e_verification_test.mp4")
    create_sample_video(sample_file)

    # 2. Submit via multipart/form-data to POST /api/videos/upload
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = []

    def add_field(name, val):
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        body.append(b"")
        body.append(str(val).encode())

    add_field("hook_type", "controversial")
    add_field("num_clips", "2")
    add_field("enable_broll", "true")
    add_field("enable_hook", "true")
    add_field("target_language", "es")

    # Add file field
    with open(sample_file, "rb") as f:
        file_bytes = f.read()

    body.append(f"--{boundary}".encode())
    body.append(f'Content-Disposition: form-data; name="file"; filename="e2e_verification_test.mp4"'.encode())
    body.append(b"Content-Type: video/mp4")
    body.append(b"")
    body.append(file_bytes)
    body.append(f"--{boundary}--".encode())
    body.append(b"")

    payload = b"\r\n".join(body)

    req = urllib.request.Request(
        f"{BASE_URL}/api/videos/upload",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    print("\n[1/4] Submitting job to FastAPI `/api/videos/upload`...")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            job_id = data.get("job_id")
            print(f"[OK] Job queued successfully! Job ID: {job_id}")
    except Exception as e:
        print(f"[ERR] Upload failed: {e}")
        return

    # 3. Poll job progress via GET /api/jobs/{job_id}
    print("\n[2/4] Polling Celery pipeline processing...")
    start_time = time.time()
    last_step = ""

    while True:
        time.sleep(3)
        elapsed = int(time.time() - start_time)
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/jobs/{job_id}") as jresp:
                jdata = json.loads(jresp.read().decode())
                status = jdata.get("status")
                progress = jdata.get("progress", 0)
                step = jdata.get("current_step", "Processing")

                if step != last_step or elapsed % 15 == 0:
                    print(f"  [{elapsed}s] Status: {status.upper()} | Progress: {progress}% | Step: {step}")
                    last_step = step

                if status in ("completed", "done", "failed"):
                    print(f"\n[3/4] Processing finished in {elapsed}s with status: {status.upper()}")
                    if status == "failed":
                        print(f"[ERR] Error details: {jdata.get('error_message')}")
                    break
        except Exception as poll_err:
            print(f"  Polling note: {poll_err}")

    # 4. Verify DB Records & Artifacts
    print("\n[4/4] Verifying pipeline artifacts in PostgreSQL database...")

    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, ContentAnalysis, SEOAnalysis

    try:
        with SyncSessionLocal() as session:
            clips = session.query(Clip).order_by(Clip.created_at.desc()).limit(5).all()
            content_analyses = session.query(ContentAnalysis).order_by(ContentAnalysis.created_at.desc()).limit(5).all()
            seo_analyses = session.query(SEOAnalysis).order_by(SEOAnalysis.created_at.desc()).limit(5).all()

            print(f"\n[SUMMARY] Verification Summary:")
            print(f"  - Total Clips Generated: {len(clips)}")
            for c in clips:
                exists = os.path.exists(c.output_path) if c.output_path else False
                size = os.path.getsize(c.output_path) if exists else 0
                print(f"  * Clip ID {c.id[:8]}: title='{c.title}' duration={c.duration}s output_exists={exists} size={size} bytes")

            print(f"  - Content Understanding Records: {len(content_analyses)}")
            for ca in content_analyses:
                print(f"  * Analysis for Clip {ca.clip_id[:8]}: niche='{ca.niche}' topic='{ca.topic}' hook='{ca.hook_type}' sentiment={ca.sentiment_score}")

            print(f"  - SEO Index Records: {len(seo_analyses)}")
            for sa in seo_analyses:
                print(f"  * SEO for Clip {sa.clip_id[:8]}: seo_score={sa.seo_score} ctr_score={sa.ctr_score} discoverability={sa.discoverability_score}")
    except Exception as db_err:
        print(f"[ERR] DB verification failed: {db_err}")

if __name__ == "__main__":
    run_e2e_verification()
