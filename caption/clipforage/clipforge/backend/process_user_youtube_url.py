"""
Process user-provided YouTube URL through full ClipForge pipeline (Phases 1-15)
URL: https://youtu.be/lmqzBkjydyE?si=qx02slM50xULp90V
"""
import os
import sys
import time
import json
import urllib.request
import urllib.parse

BASE_URL = "http://localhost:8000"
YT_URL = "https://youtu.be/lmqzBkjydyE?si=qx02slM50xULp90V"

def process_youtube_video():
    print("=" * 60)
    print("[E2E] Submitting YouTube Video for Full ClipForge E2E Processing")
    print(f"URL: {YT_URL}")
    print("=" * 60)

    # 1. Submit via form-urlencoded to POST /api/videos/url
    params = {
        "url": YT_URL,
        "num_clips": 2,
        "hook_type": "question",
        "hook_title": "true",
        "enable_broll": "true",
        "enable_hook": "true",
        "target_language": "es"
    }

    data_bytes = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/videos/url",
        data=data_bytes,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )

    print("\n[1/3] Submitting YouTube URL to `/api/videos/url`...")
    try:
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode())
            job_id = res_data.get("job_id")
            print(f"[OK] Processing job queued successfully! Job ID: {job_id}")
    except Exception as err:
        print(f"[ERR] Failed to submit YouTube URL: {err}")
        return

    print("\n[2/3] Polling Celery pipeline progress...")
    
    # Needs absolute import from repo root
    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
        
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Job, Clip, ContentAnalysis

    start_time = time.time()
    last_step = ""

    while True:
        time.sleep(4)
        elapsed = int(time.time() - start_time)
        try:
            with SyncSessionLocal() as session:
                job = session.query(Job).filter_by(id=job_id).first()
                if job:
                    if job.current_step != last_step or elapsed % 12 == 0:
                        print(f"  [{elapsed}s] Status: {job.status.upper()} | Progress: {job.progress}% | Step: {job.current_step}")
                        last_step = job.current_step

                    if job.status.lower() in ("completed", "done", "failed"):
                        print(f"\n[3/3] Job finished in {elapsed}s with status: {job.status.upper()}")
                        if job.status.lower() == "failed":
                            print(f"[ERR] Failure reason: {job.error_message}")
                        break
                else:
                    print(f"  [{elapsed}s] Waiting for job record in DB...")
        except Exception as db_err:
            print(f"  Polling error: {db_err}")

    # 3. Report DB Results
    print("\n[RESULT] Verification Report for YouTube Clip Generation:")
    try:
        with SyncSessionLocal() as session:
            clips = session.query(Clip).order_by(Clip.created_at.desc()).limit(5).all()
            print(f"  - Generated Clips in DB: {len(clips)}")
            for c in clips:
                exists = os.path.exists(c.output_path) if c.output_path else False
                size = os.path.getsize(c.output_path) if exists else 0
                title = c.title or ""
                print(f"  * Clip '{title[:40]}' ({c.duration}s, score={c.score}): exists={exists}, size={size} bytes")
                print(f"    - Output Path: {c.output_path}")

            ca_records = session.query(ContentAnalysis).order_by(ContentAnalysis.created_at.desc()).limit(5).all()
            print(f"\n  - Content Analysis Records: {len(ca_records)}")
            for ca in ca_records:
                print(f"  * Niche: {ca.niche} | Topic: {ca.topic} | Hook: {ca.hook_type}")

    except Exception as r_err:
        print(f"[ERR] Report generation error: {r_err}")

if __name__ == "__main__":
    process_youtube_video()
