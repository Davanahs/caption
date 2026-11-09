import os
import sys
import time
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Video, Clip, PublishRecord, PublishTarget
from backend.tasks.clip_tasks import publish_clip_task
from backend.services.publisher import get_youtube_client

def verify_destination_channel():
    print("=== Step 1: Verify Destination Channel ===")
    with SyncSessionLocal() as s:
        dest = s.query(Channel).filter_by(id="518b3118-2367-4f84-898f-ff97a61df306").first()
        if not dest:
            raise ValueError("Destination channel not found in DB")
        print(f"Destination Channel: {dest.channel_name} ({dest.youtube_channel_id})")
        
        # Verify OAuth client
        yt = get_youtube_client(dest.youtube_channel_id)
        resp = yt.channels().list(part="snippet,status", mine=True).execute()
        auth_title = resp["items"][0]["snippet"]["title"]
        auth_id = resp["items"][0]["id"]
        print(f"Verified live OAuth credentials: {auth_title} (ID: {auth_id})")
        if auth_id != dest.youtube_channel_id:
            raise ValueError(f"Channel ID mismatch: expected {dest.youtube_channel_id}, got {auth_id}")
    return dest.youtube_channel_id


def execute_batch(batch_name: str, items: list[dict], yt_channel_id: str):
    print(f"\n{'='*70}\nStarting {batch_name}\n{'='*70}")
    results = []

    for idx, item in enumerate(items, 1):
        clip_id = item["clip_id"]
        source_ytid = item["source_ytid"]
        print(f"\n--- [{batch_name} #{idx}] Source Video: {source_ytid} | Clip: {clip_id} ---")
        
        with SyncSessionLocal() as s:
            c = s.query(Clip).filter_by(id=clip_id).first()
            v = s.query(Video).filter_by(id=c.video_id).first()
            if c.publish_status == "published" and c.youtube_short_id and not c.youtube_short_id.startswith("mock_"):
                print(f"ALREADY PUBLISHED: Clip {clip_id} is already published on YouTube as {c.youtube_short_id}. Reusing verified result.")
                results.append({
                    "batch": batch_name,
                    "source_ytid": source_ytid,
                    "clip_id": clip_id,
                    "title": c.title,
                    "status": "published",
                    "youtube_id": c.youtube_short_id,
                    "url": f"https://www.youtube.com/shorts/{c.youtube_short_id}",
                    "published_at": c.published_at.isoformat() if c.published_at else None,
                    "note": "Reused verified publication"
                })
                continue

            print(f"Source Title: {v.title}")
            print(f"Clip Title:   {c.title}")
            print(f"Duration:     {c.duration:.1f}s | Path: {c.output_path}")
            
            # Verify file exists
            p = Path(c.output_path)
            if not p.exists():
                print(f"ERROR: Media artifact does not exist: {p}")
                results.append({
                    "batch": batch_name,
                    "source_ytid": source_ytid,
                    "clip_id": clip_id,
                    "title": c.title,
                    "status": "failed",
                    "error": f"Artifact not found: {p}"
                })
                continue

        # Execute upload through publish_clip_task with explicit private visibility
        start_time = datetime.now(timezone.utc)
        print(f"Initiating upload to ClipSee ({yt_channel_id}) with visibility=PRIVATE at {start_time.isoformat()}...")
        try:
            pub_res = publish_clip_task(
                clip_id=clip_id,
                channel_id=yt_channel_id,
                privacy="private"
            )
            yt_id = pub_res.get("youtube_id")
            end_time = datetime.now(timezone.utc)
            duration_s = (end_time - start_time).total_seconds()
            print(f"SUCCESS! Published privately to ClipSee.")
            print(f"   YouTube Short ID: {yt_id}")
            print(f"   URL: https://www.youtube.com/shorts/{yt_id}")
            print(f"   Upload execution time: {duration_s:.1f}s")
            
            # Verify in DB
            with SyncSessionLocal() as s:
                c = s.query(Clip).filter_by(id=clip_id).first()
                print(f"   DB Record: status={c.publish_status}, yt_id={c.youtube_short_id}, pub_at={c.published_at}")

            results.append({
                "batch": batch_name,
                "source_ytid": source_ytid,
                "clip_id": clip_id,
                "title": c.title,
                "status": "published",
                "youtube_id": yt_id,
                "url": f"https://www.youtube.com/shorts/{yt_id}",
                "published_at": end_time.isoformat(),
                "duration_seconds": duration_s
            })
        except Exception as e:
            print(f"FAILED upload for clip {clip_id}: {e}")
            results.append({
                "batch": batch_name,
                "source_ytid": source_ytid,
                "clip_id": clip_id,
                "status": "failed",
                "error": str(e)
            })

    return results


def main():
    yt_channel_id = verify_destination_channel()

    batch_a_items = [
        {
            "source_ytid": "UBHOWXL4Apg",
            "clip_id": "ab96872a-e81f-482d-98eb-2024919e3bbb", # Why the number 4 key breaks everything
        },
        {
            "source_ytid": "Cm45rJ_ayA4",
            "clip_id": "988b9d0d-1244-4e57-9771-f3d0b1d552d9", # Software Engineer Salary vs Cost of Living
        },
        {
            "source_ytid": "MjDUTSOsUMg",
            "clip_id": "a0dfbe13-bb91-4a60-bb7a-dcbdf02c1466", # Adobe's Moat Just Died?
        },
    ]

    batch_b_items = [
        {
            "source_ytid": "-rPzGJH1acU",
            "clip_id": "b1b8af97-d7b9-4873-baf0-e0013f2660a1", # Ben Affleck Paid $587M For AI?
        },
        {
            "source_ytid": "bBlahWRZ2Yw",
            "clip_id": "f9bedd47-4eb4-411d-ab9d-6fff5205ce5a", # Why Your AI Content Fails
        },
        {
            "source_ytid": "m5hidzW-_i0",
            "clip_id": "295a2da3-7a04-4a85-90d8-1e981d84b534", # Is $200 AI Worth It? Free vs Paid
        },
    ]

    all_results = []
    
    # Execute Batch A
    res_a = execute_batch("Batch A (Latest 3)", batch_a_items, yt_channel_id)
    all_results.extend(res_a)

    # Execute Batch B
    res_b = execute_batch("Batch B (3 Most-Viewed)", batch_b_items, yt_channel_id)
    all_results.extend(res_b)

    # Save results to json for report generation
    out_file = Path("backend/scripts/monitoring_publishing_results.json")
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*70}\nAll batches executed. Summary saved to {out_file}\n{'='*70}")
    for r in all_results:
        print(f"[{r['batch']}] {r['source_ytid']} -> {r['status']} | YT_ID: {r.get('youtube_id')} | URL: {r.get('url')}")

if __name__ == "__main__":
    main()
