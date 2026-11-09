"""
Phase 1.2 Primary Real Lifecycle Verification Script
Traces:
  Start Processing (API) -> Job DB Commit -> Celery Dispatch ->
  Worker Execution (Docker clipforge_worker) -> State Transitions ->
  Active Jobs API -> Terminal State -> Job History API
"""
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, VideoDecision, Job, Clip, Video

def setup_test_channel_and_decision():
    from backend.models.models import TaskExecution
    with SyncSessionLocal() as session:
        # Clean up any previous test artifacts
        old_jobs = session.query(Job).filter(Job.source_url.like("%synth_vid01%")).all()
        for oj in old_jobs:
            session.query(TaskExecution).filter_by(job_id=oj.id).delete(synchronize_session=False)
            session.query(Job).filter_by(id=oj.id).delete(synchronize_session=False)
        session.query(VideoDecision).filter_by(channel_id="ch_phase12_e2e").delete(synchronize_session=False)
        session.query(Channel).filter_by(id="ch_phase12_e2e").delete(synchronize_session=False)
        session.commit()

        # Create isolated test channel
        channel = Channel(
            id="ch_phase12_e2e",
            youtube_channel_id="UC_phase12_e2e",
            channel_name="Phase 12 E2E Channel",
            channel_url="https://youtube.com/@phase12_e2e",
            is_active=True,
            is_test=False,
            auto_publish=False,
            processing_profile={
                "clips_count": 1,
                "reframe_mode": "blur",
                "scoring_mode": "test",
                "target_duration": 15
            }
        )
        session.add(channel)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        decision = VideoDecision(
            id="dec_phase12_synth01",
            channel_id="ch_phase12_e2e",
            youtube_id="synth_vid01",
            video_title="Synthetic E2E Video 01",
            youtube_url="https://www.youtube.com/watch?v=synth_vid01",
            status="awaiting_settings",
            decision_deadline=now,
            channel_profile_snapshot={
                "clips_count": 1,
                "reframe_mode": "blur",
                "scoring_mode": "test"
            }
        )
        session.add(decision)
        session.commit()
        print("[Setup] Seeded channel ch_phase12_e2e and decision dec_phase12_synth01 successfully.")

def trigger_start_processing():
    url = "http://localhost:8000/api/channels/ch_phase12_e2e/process-video"
    payload = json.dumps({
        "video_id": "synth_vid01",
        "video_title": "Synthetic E2E Video 01",
        "video_url": "https://www.youtube.com/watch?v=synth_vid01"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print(f"[HTTP POST] Response: {resp.status} -> {body}")
        return body

def trace_lifecycle(job_id: str):
    print(f"\n[Trace] Tracing job {job_id} lifecycle through database, active API, worker, and history API...")
    
    observed_steps = []
    max_wait_seconds = 120
    start_time = time.time()
    
    active_observed = False
    completed = False
    
    while time.time() - start_time < max_wait_seconds:
        # 1. Query Active Jobs API
        try:
            req = urllib.request.Request("http://localhost:8000/api/jobs/active")
            with urllib.request.urlopen(req) as resp:
                active_jobs = json.loads(resp.read().decode("utf-8"))
                matching = [j for j in active_jobs if j["id"] == job_id]
                if matching:
                    active_observed = True
                    print(f"  [Active API] {matching[0]['status']} ({matching[0]['progress']}%) - {matching[0]['current_step']}")
        except Exception as e:
            print(f"  [Active API Error]: {e}")

        # 2. Query Database for exact state
        with SyncSessionLocal() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                state_tuple = (job.status, job.progress, job.current_step)
                if not observed_steps or observed_steps[-1] != state_tuple:
                    observed_steps.append(state_tuple)
                    print(f"  [DB State Transition] status='{job.status}', progress={job.progress}%, step='{job.current_step}', started={job.pipeline_started_at}")
                
                if job.status in ("completed", "completed_with_failures", "failed"):
                    completed = True
                    break

        time.sleep(1.0)

    elapsed = time.time() - start_time
    print(f"\n[Trace Result] Finished after {elapsed:.1f}s. Completed: {completed}")
    print(f"[Trace Sequence] All observed state transitions:")
    for idx, (s, p, step) in enumerate(observed_steps, 1):
        print(f"  {idx}. status='{s}', progress={p}%, step='{step}'")

    # 3. Verify Job History API
    history_observed = False
    try:
        req = urllib.request.Request("http://localhost:8000/api/jobs/history?limit=10")
        with urllib.request.urlopen(req) as resp:
            history_jobs = json.loads(resp.read().decode("utf-8"))
            matching = [j for j in history_jobs if j["id"] == job_id]
            if matching:
                history_observed = True
                print(f"[History API] Found completed job in history: status='{matching[0]['status']}', title='{matching[0]['source_title']}', completed_at='{matching[0]['completed_at']}'")
    except Exception as e:
        print(f"[History API Error]: {e}")

    # 4. Verify clips in DB
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        clips = session.query(Clip).filter_by(video_id=job.video_id).all() if job and job.video_id else []
        print(f"[Clips Generated] Count: {len(clips)}")
        for c in clips:
            print(f"  - Clip {c.id}: status='{c.status}', duration={c.duration}s, publish_status='{c.publish_status}', destination='{c.publish_destination_id}'")

    assert completed, f"Job {job_id} did not reach terminal state within timeout!"
    assert active_observed or len(observed_steps) > 2, "Job was not observed in active states!"
    assert history_observed, "Job did not appear in /api/jobs/history!"
    print("\n[SUCCESS] PRIMARY REAL LIFECYCLE VERIFICATION PASSED!")

if __name__ == "__main__":
    setup_test_channel_and_decision()
    resp = trigger_start_processing()
    job_id = resp["job_id"]
    trace_lifecycle(job_id)
