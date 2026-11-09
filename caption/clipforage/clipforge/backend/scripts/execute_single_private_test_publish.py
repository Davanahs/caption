"""
Execute exactly ONE private test publish for the newly generated test Short
and verify live YouTube readback, privacy, and DB reconciliation.
"""
import urllib.request
import json
import time
import sys

def execute_private_test():
    sys.stdout.reconfigure(encoding="utf-8")
    clip_id = "3717a40a-2238-4d55-a7cd-14882378d121"
    dest_id = "518b3118-2367-4f84-898f-ff97a61df306"

    payload = {
        "clip_id": clip_id,
        "destination_channel_id": dest_id,
        "privacy": "private",
        "title": "ClipForge Test Short (Private Verification)",
        "description": "ClipForge automated verification test Short - strictly private.",
        "tags": "Shorts,test,clipforge",
        "category": "22",
        "made_for_kids": False,
        "age_restricted": False
    }

    print(f"Dispatching single private test upload for clip {clip_id} to destination {dest_id}...")
    req = urllib.request.Request(
        "http://localhost:8000/api/publish/publish-now",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req) as resp:
        code = resp.getcode()
        body = json.loads(resp.read().decode("utf-8"))

    print(f"Publish-Now Endpoint Response: HTTP {code}")
    print("Response Body:", json.dumps(body, indent=2))

    # Monitor clip status in DB until published or failed
    print("Monitoring publishing progression in ClipForge database...")
    start_time = time.time()
    last_stage = None

    while time.time() - start_time < 120:
        with urllib.request.urlopen(f"http://localhost:8000/api/clips/{clip_id}") as resp:
            c = json.loads(resp.read().decode("utf-8"))

        pub_status = c.get("publish_status")
        stage = c.get("publish_stage")
        yt_id = c.get("youtube_short_id")
        err = c.get("publish_error")

        if stage != last_stage or pub_status in ("published", "failed"):
            print(f"[{int(time.time() - start_time)}s] PublishStatus: {pub_status} | Stage: {stage} | YouTube Short ID: {yt_id}")
            last_stage = stage

        if pub_status == "published" and yt_id:
            print("\n✅ Clip successfully PUBLISHED!")
            print(f"Remote YouTube Short ID: {yt_id}")
            print(f"Observed Local Privacy: {c.get('privacy')}")
            print(f"Published URL: https://www.youtube.com/shorts/{yt_id}")

            # Verify directly via YouTube API
            from backend.services.publisher import get_youtube_client
            yt = get_youtube_client(channel_id="UCH90024qrJHA4amGRxnTldw")
            resp_yt = yt.videos().list(part="snippet,status", id=yt_id).execute()
            if resp_yt.get("items"):
                item = resp_yt["items"][0]
                remote_privacy = item.get("status", {}).get("privacyStatus")
                remote_channel = item.get("snippet", {}).get("channelId")
                remote_title = item.get("snippet", {}).get("title")
                print("\n--- Live YouTube API Readback Verification ---")
                print(f"Remote Video ID: {yt_id}")
                print(f"Remote Channel ID: {remote_channel} (Expected: UCH90024qrJHA4amGRxnTldw)")
                print(f"Remote Title: {remote_title}")
                print(f"Remote Privacy Status: {remote_privacy} (CRITICAL: Must be 'private')")
                assert remote_privacy == "private", f"PRIVACY INVARIANT VIOLATION: expected private, got {remote_privacy}"
                assert remote_channel == "UCH90024qrJHA4amGRxnTldw", f"CHANNEL MISMATCH: expected UCH90024qrJHA4amGRxnTldw, got {remote_channel}"
                print("✅ 100% VERIFIED: Video is confirmed PRIVATE on the authorized destination channel!")
            else:
                print(f"WARNING: Video {yt_id} not found in immediate API readback.")
            return

        elif pub_status == "failed":
            print(f"❌ Publishing FAILED: {err}")
            return

        time.sleep(3)

    print("Publishing monitoring timed out!")


if __name__ == "__main__":
    execute_private_test()
