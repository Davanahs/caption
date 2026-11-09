import sys
from pathlib import Path
from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Video, Clip, PublishRecord, PublishTarget, ChannelDestination

with SyncSessionLocal() as s:
    print("=== CHANNELS ===")
    channels = s.query(Channel).all()
    for c in channels:
        print(f"ID: {c.id}")
        print(f"  Name: {c.channel_name}")
        print(f"  YT ID: {c.youtube_channel_id}")
        print(f"  is_active (Auto Monitor): {c.is_active}, auto_publish: {c.auto_publish}, auto_clip: {c.auto_clip}")
        print(f"  publish_destination_id: {c.publish_destination_id}")
        print(f"  is_destination: {c.is_destination}, is_default_dest: {c.is_default_destination}")
        print(f"  publishing_settings: {c.publishing_settings}")
        print()

    print("=== CHANNEL DESTINATIONS ===")
    dests = s.query(ChannelDestination).all()
    for d in dests:
        print(f"Source: {d.source_channel_id} -> Dest: {d.destination_channel_id} (default: {d.is_default})")

    print("\n=== CANDIDATE VIDEOS & CLIPS ===")
    candidate_yt_ids = [
        "UBHOWXL4Apg", "Cm45rJ_ayA4", "MjDUTSOsUMg", # Batch A
        "-rPzGJH1acU", "bBlahWRZ2Yw", "m5hidzW-_i0"  # Batch B
    ]
    for ytid in candidate_yt_ids:
        v = s.query(Video).filter_by(youtube_id=ytid).first()
        if not v:
            print(f"Video {ytid}: NOT FOUND IN DB")
            continue
        print(f"\nVideo: {v.youtube_id} | Title: {v.title[:50]} | DB ID: {v.id}")
        clips = s.query(Clip).filter_by(video_id=v.id).order_by(Clip.created_at.asc()).all()
        print(f"  Clips count: {len(clips)}")
        for cl in clips:
            p = Path(cl.output_path) if cl.output_path else None
            exists = p.exists() if p else False
            th = Path(cl.thumbnail_path) if cl.thumbnail_path else None
            th_exists = th.exists() if th else False
            print(f"    Clip ID: {cl.id} | Status: {cl.status} | PubStatus: {cl.publish_status} | Duration: {cl.duration}s | YT_Short_ID: {cl.youtube_short_id} | FileExists: {exists} | ThumbExists: {th_exists}")
            print(f"      Title: {cl.title}")
            print(f"      Path: {cl.output_path}")

    print("\n=== RECENT PUBLISH RECORDS ===")
    records = s.query(PublishRecord).order_by(PublishRecord.created_at.desc()).limit(10).all()
    for r in records:
        print(f"Record: key={r.idempotency_key}, status={r.status}, ext_id={r.external_id}, created_at={r.created_at}, updated_at={r.updated_at}")
