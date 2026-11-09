"""
Submit final verification video and monitor pipeline progress to completion.
"""
import urllib.request
import json
import uuid
import time
from pathlib import Path


def submit_job():
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    lines = []

    def add_field(name, value):
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(str(value).encode("utf-8"))

    def add_file(name, filename, data):
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode("utf-8"))
        lines.append(b"Content-Type: video/mp4")
        lines.append(b"")
        lines.append(data)

    add_field("clip_mode", "ai_highlights")
    add_field("clips_count", 1)
    add_field("max_clip_duration", 30)
    add_field("reframe_mode", "split")
    add_field("publish_destination_id", "518b3118-2367-4f84-898f-ff97a61df306")

    video_path = Path("uploads/final_verification_source.mp4")
    file_bytes = video_path.read_bytes()
    add_file("file", "final_verification_source.mp4", file_bytes)

    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")

    body = b"\r\n".join(lines)
    req = urllib.request.Request("http://localhost:8000/api/videos/upload", data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    print("Upload successful!")
    print(f"Job ID: {result.get('job_id')}")
    return result.get("job_id")


def monitor_job(job_id, timeout_sec=180):
    print(f"Monitoring job {job_id}...")
    start_time = time.time()
    last_step = None

    while time.time() - start_time < timeout_sec:
        url = f"http://localhost:8000/api/jobs/{job_id}"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status")
            progress = data.get("progress")
            step = data.get("current_step") or data.get("error")
            if step != last_step or status in ("completed", "failed"):
                print(f"[{int(time.time() - start_time)}s] Status: {status} | Progress: {progress}% | Step: {step}")
                last_step = step

            if status == "completed":
                print("Job COMPLETED successfully!")
                return data
            elif status == "failed":
                print(f"Job FAILED: {data.get('error')}")
                return data
        except Exception as e:
            print(f"Polling error: {e}")

        time.sleep(3)

    print("Job polling timed out!")
    return None


if __name__ == "__main__":
    jid = submit_job()
    monitor_job(jid)
