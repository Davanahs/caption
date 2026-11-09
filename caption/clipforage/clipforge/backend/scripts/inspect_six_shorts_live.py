import io
import sys
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.services.publisher import get_youtube_client
from backend.models.database import SyncSessionLocal
from backend.models.models import Clip, PublishRecord

DEST_CH = "UCH90024qrJHA4amGRxnTldw"
TARGET_IDS = [
    "YpHobheDpk8",
    "kkXWbXZI_iM",
    "0OfOivc-tpU",
    "39w4TLjreFU",
    "L3ihlJVo_3A",
    "FoNMm4F9qIM"
]

yt = get_youtube_client(DEST_CH)
resp = yt.videos().list(part="status,snippet", id=",".join(TARGET_IDS)).execute()
yt_items = {it["id"]: it for it in resp.get("items", [])}

print("=" * 80)
print("LIVE YOUTUBE DATA API AUDIT FOR THE SIX SHORT IDs")
print("=" * 80)

with SyncSessionLocal() as db:
    for vid_id in TARGET_IDS:
        yt_it = yt_items.get(vid_id)
        clip = db.query(Clip).filter(Clip.youtube_short_id == vid_id).first()
        prs = db.query(PublishRecord).filter(PublishRecord.external_id == vid_id).all()
        
        print(f"\n--- YouTube Short ID: {vid_id} ---")
        if yt_it:
            snip = yt_it["snippet"]
            stat = yt_it["status"]
            print(f"  Remote Channel ID:     {snip.get('channelId')} (Match Destination: {snip.get('channelId') == DEST_CH})")
            print(f"  Remote Privacy Status: {stat.get('privacyStatus')}")
            print(f"  Remote Upload Status:  {stat.get('uploadStatus')}")
            print(f"  Remote Published At:   {snip.get('publishedAt')}")
            print(f"  Remote Title:          {snip.get('title')}")
        else:
            print("  REMOTE ITEM NOT FOUND ON YOUTUBE!")
            
        if clip:
            print(f"  Local Clip ID:         {clip.id}")
            print(f"  Local Clip Video ID:   {clip.video_id}")
            print(f"  Local Clip Privacy:    {clip.privacy}")
            print(f"  Local Publish Status:  {clip.publish_status}")
            print(f"  Local Title:           {clip.title}")
        else:
            print("  LOCAL CLIP RECORD NOT FOUND!")
            
        print(f"  Local Publish Records: {len(prs)}")
        for pr in prs:
            print(f"    - Key: {pr.idempotency_key} | Status: {pr.status} | Target: {pr.target} | Created: {pr.created_at}")
