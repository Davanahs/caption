"""
reconcile_and_fix_three_privacies.py
====================================
Corrects the remote YouTube privacy status of the three Batch B YouTube Shorts:
  - 39w4TLjreFU
  - L3ihlJVo_3A
  - FoNMm4F9qIM
from 'public' to 'private', preserving snippet, title, tags, and descriptions.
Follows with a subsequent read-only verification query and DB reconciliation.
"""

import sys
import io
import json
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.services.publisher import get_youtube_client
from backend.models.database import SyncSessionLocal
from backend.models.models import Clip, PublishRecord, Video

DESTINATION_CHANNEL_ID = "UCH90024qrJHA4amGRxnTldw"
TARGET_IDS = ["39w4TLjreFU", "L3ihlJVo_3A", "FoNMm4F9qIM"]

def main():
    print("=" * 70)
    print("PHASE 1: CORRECTING REMOTE PRIVACY FOR THE 3 YOUTUBE SHORTS")
    print("=" * 70)

    # 1. Authenticate YouTube client
    yt = get_youtube_client(DESTINATION_CHANNEL_ID)
    
    # 2. Query YouTube Data API (Pre-update check)
    print("\n[Step 1] Querying current status on YouTube...")
    resp = yt.videos().list(part="snippet,status", id=",".join(TARGET_IDS)).execute()
    items = resp.get("items", [])
    if len(items) != 3:
        raise RuntimeError(f"Expected 3 items from YouTube, got {len(items)}")

    # Verify ownership and status
    for item in items:
        vid_id = item["id"]
        ch_id = item["snippet"].get("channelId")
        title = item["snippet"].get("title")
        cur_privacy = item["status"].get("privacyStatus")
        print(f" -> Found Video: {vid_id} | Channel: {ch_id} | Privacy: {cur_privacy} | Title: {title}")
        if ch_id != DESTINATION_CHANNEL_ID:
            raise RuntimeError(f"Video {vid_id} channelId mismatch: {ch_id} != {DESTINATION_CHANNEL_ID}")

    # 3. Update remote privacy to 'private' while preserving all snippet fields
    print("\n[Step 2] Updating remote privacy to 'private'...")
    for item in items:
        vid_id = item["id"]
        snippet = item["snippet"]
        status = item["status"]

        update_body = {
            "id": vid_id,
            "snippet": {
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "categoryId": snippet.get("categoryId", "22"),
                "defaultLanguage": snippet.get("defaultLanguage", "en"),
                "defaultAudioLanguage": snippet.get("defaultAudioLanguage", "hi")
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": status.get("selfDeclaredMadeForKids", False),
                "embeddable": status.get("embeddable", True)
            }
        }
        
        print(f" -> Sending update for {vid_id} (Title: '{snippet['title']}') to private...")
        up_resp = yt.videos().update(part="snippet,status", body=update_body).execute()
        new_status = up_resp.get("status", {}).get("privacyStatus")
        print(f"    API Update Response Privacy: {new_status}")

    # 4. Subsequent read-only verification query
    print("\n[Step 3] Subsequent read-only verification query...")
    verify_resp = yt.videos().list(part="snippet,status", id=",".join(TARGET_IDS)).execute()
    verified_items = verify_resp.get("items", [])
    all_private = True
    for item in verified_items:
        vid_id = item["id"]
        title = item["snippet"]["title"]
        priv = item["status"]["privacyStatus"]
        print(f" -> Verified YouTube Video: {vid_id} | Privacy: {priv} | Title: {title}")
        if priv != "private":
            all_private = False
            print(f"    ERROR: {vid_id} is still {priv}!")

    if not all_private:
        raise RuntimeError("One or more videos failed to transition to private!")

    print("\n[SUCCESS] All 3 videos verified REMOTE PRIVATE on YouTube Data API.")

    # 5. Database reconciliation
    print("\n[Step 4] Reconciling local database records...")
    with SyncSessionLocal() as s:
        for vid_id in TARGET_IDS:
            c = s.query(Clip).filter(Clip.youtube_short_id == vid_id).first()
            if c:
                c.privacy = "private"
                print(f" -> Reconciled Clip {c.id}: privacy set to '{c.privacy}', publish_status='{c.publish_status}'")
            else:
                print(f" -> WARNING: Clip record for {vid_id} not found in DB!")

            # Reconcile PublishRecord if exists
            prs = s.query(PublishRecord).filter(PublishRecord.external_id == vid_id).all()
            for pr in prs:
                print(f"    PublishRecord {pr.idempotency_key}: status={pr.status}, external_id={pr.external_id}")

        s.commit()
    print("\n[SUCCESS] Local database reconciled.")

if __name__ == "__main__":
    main()
