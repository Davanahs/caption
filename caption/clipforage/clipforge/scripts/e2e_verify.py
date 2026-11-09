import requests
import time
import json
import os

API_URL = "http://localhost:8000/api/videos/upload"

def run_test():
    file_path = r"C:\Users\Chinmaygouda\.gemini\antigravity-ide\brain\bd8ba98f-b065-4627-aa9f-197f9b7c7248\base_with_audio.mp4"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found!")
        return
        
    print("Uploading file to API...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path, f, "video/mp4")}
        data = {
            "reframe_mode": "multi_split",
            "clips_count": 1,
            "clip_mode": "ai_highlights"
        }
        resp = requests.post(API_URL, files=files, data=data)
        
    if resp.status_code != 200:
        print(f"Failed to upload: {resp.status_code} {resp.text}")
        return
        
    res_data = resp.json()
    job_id = res_data["job_id"]
    print(f"Job created: {job_id}")
    
    print("Waiting for job to finish...")
    for _ in range(60):
        # We can check DB via API or direct DB connection.
        # Let's check API for job status.
        # Oh, do we have a /api/jobs/{job_id} endpoint?
        job_resp = requests.get(f"http://localhost:8000/api/jobs/{job_id}")
        if job_resp.status_code == 200:
            job = job_resp.json()
            print(f"Status: {job['status']}, Progress: {job['progress']}%, Step: {job['current_step']}")
            
            # Check config persistence via API response
            if "config" in job:
                config = job["config"]
                if config.get("reframe_mode") != "multi_split":
                    print(f"ERROR: API config does not have multi_split! Config: {config}")
                    return
                else:
                    print("SUCCESS: API config has reframe_mode = multi_split")
            else:
                print("ERROR: API response missing 'config' field!")
                return
                
            if job["status"] in ["completed", "failed"]:
                print(f"Job finished with status: {job['status']}")
                break
        time.sleep(5)
        
if __name__ == "__main__":
    run_test()
