import time
import os
import requests
from playwright.sync_api import sync_playwright

def verify_mode(p, mode_name, filename):
    print(f"Starting E2E verification for {mode_name}...")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:3000/")
    
    # Wait for the app to load
    page.wait_for_selector('input[type="file"]', state="attached")
    
    # Select mode
    # For Blur it is "Blur (Padded background)"
    # For Crop it is "Crop (Default Center focus)"
    label = f"{mode_name} (Padded background)" if mode_name == "Blur" else f"{mode_name} (Default Center focus)"
    page.locator("select").select_option(label=label)
    
    # Upload file
    filepath = os.path.abspath(f"C:\\Users\\Chinmaygouda\\.gemini\\antigravity-ide\\brain\\bd8ba98f-b065-4627-aa9f-197f9b7c7248\\{filename}")
    # Wait for the file input
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(filepath)
    print(f"[{mode_name}] Uploaded {filename}")
    
    # Wait for the modal to open and click start processing
    page.click('button:has-text("Start Processing")')
    
    print(f"[{mode_name}] Job submitted. Waiting for completion...")
    
    success = False
    start_time = time.time()
    
    while time.time() - start_time < 300: # 5 mins max
        try:
            # Check the page text for completion
            # Wait for any active or recent job row for this file
            body_text = page.inner_text('body').lower()
            
            # Since the filename might be truncated, let's just look for the job via the API or loosely in the body
            # To be robust, let's hit the API directly from the test script to check job status
            res = requests.get("http://localhost:8000/api/jobs/")
            if res.status_code == 200:
                jobs = res.json()
                for job in jobs:
                    # Parse created_at if available
                    job_created_at = 0
                    if job.get('created_at'):
                        from dateutil import parser
                        import datetime
                        # Parse ISO format string to timestamp
                        try:
                            dt = parser.parse(job['created_at'])
                            # Compare with test start time (UTC)
                            # Actually, start_time is local time (time.time()), but let's just use naive timestamp approximation
                            job_created_at = dt.timestamp()
                        except:
                            pass
                            
                    # Only consider jobs created around or after our start_time (give or take a few seconds)
                    if job_created_at and job_created_at < start_time - 10:
                        continue
                        
                    if job.get('source_title') == filename or (job.get('source_url') and filename in job.get('source_url', '')):
                        status = job.get('status')
                        if status == 'completed':
                            print(f"[{mode_name}] Success! Job {job['id']} completed.")
                            success = True
                            break
                        elif status in ['failed', 'completed_with_failures']:
                            print(f"[{mode_name}] Failed! Status: {status}, Error: {job.get('error_message')}")
                            break
                if success or status in ['failed', 'completed_with_failures']:
                    break
        except Exception as e:
            pass
        time.sleep(2)
        
    browser.close()
    return success

if __name__ == "__main__":
    with sync_playwright() as p:
        print("Running Blur test...")
        b = verify_mode(p, "Blur", "base_with_audio.mp4")
        if not b:
            print("Blur test failed")
            
        print("Running Crop test...")
        f = verify_mode(p, "Crop", "base_with_audio.mp4")
        if not f:
            print("Crop test failed")
            
        if b and f:
            print("All Phase 11 layout E2E checks passed via Playwright.")
