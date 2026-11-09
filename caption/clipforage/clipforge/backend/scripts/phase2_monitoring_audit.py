"""
backend/scripts/phase2_monitoring_audit.py
=========================================
Bounded read-only discovery pass and monitoring invariants audit on:
Source Channel: Nishant Chahar (ID: b4bb167b-429f-4c52-b78f-a52cc9f03980)
"""
import sys
import io
import json
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Video, VideoDecision, Clip
from backend.services.downloader import get_channel_videos
from backend.services.provenance import check_is_clipforge_short_sync

def audit_phase2():
    print("=" * 70)
    print("PHASE 2: CHANNEL CONFIGURATION & MONITORING AUDIT")
    print("=" * 70)

    src_channel_id = "b4bb167b-429f-4c52-b78f-a52cc9f03980"

    with SyncSessionLocal() as session:
        # A. Inspect Source Channel Configuration
        src = session.query(Channel).filter_by(id=src_channel_id).first()
        assert src is not None, "Source channel Nishant Chahar not found!"
        print(f"\n[A] Source Channel Verification:")
        print(f"  Channel ID:            {src.id}")
        print(f"  Channel Name:          {src.channel_name}")
        print(f"  YouTube Channel ID:    {src.youtube_channel_id}")
        print(f"  Auto Monitor (active): {src.is_active}")
        print(f"  Auto Clip:             {src.auto_clip}")
        print(f"  Auto Publish:          {src.auto_publish}")
        print(f"  Publish Destination:   {src.publish_destination_id}")

        assert src.auto_clip is True
        assert src.auto_publish is True
        assert src.publish_destination_id is not None

        # Destination channel check
        dest = session.query(Channel).filter_by(id=src.publish_destination_id).first()
        assert dest is not None and dest.is_destination is True
        print(f"  -> Destination Linked: {dest.channel_name} (YT: {dest.youtube_channel_id}, Active: {dest.is_active})")

        # B. Destination Channel Exclusion Invariant
        print(f"\n[B] Destination Channel Exclusion Audit:")
        dest_channels = session.query(Channel).filter(Channel.is_destination == True).all()
        dest_ids = {d.id for d in dest_channels}
        dest_yt_ids = {d.youtube_channel_id for d in dest_channels}
        print(f"  Total Destination Channels: {len(dest_channels)} -> {list(dest_yt_ids)}")

        # Query all active monitored sources
        sources = session.query(Channel).filter(
            (Channel.is_destination == False) | (Channel.is_destination == None),
            Channel.is_active == True
        ).all()
        print(f"  Total Active Monitored Sources: {len(sources)}")
        for s in sources:
            assert s.id not in dest_ids, f"Destination channel {s.channel_name} leaked into sources query!"
            assert s.youtube_channel_id not in dest_yt_ids, f"Destination YouTube ID {s.youtube_channel_id} in sources query!"
        print("  -> Invariant PASSED: Zero destination channels in source monitoring query.")

        # C. Bounded Read-Only Discovery Pass
        print(f"\n[C] Bounded Read-Only Discovery Pass on {src.channel_name} (Scan Depth: 5):")
        channel_url = f"https://www.youtube.com/channel/{src.youtube_channel_id}"
        import asyncio
        discovered = asyncio.run(get_channel_videos(channel_url, max_results=5))
        print(f"  Discovered Items Count: {len(discovered)}")
        assert len(discovered) > 0, "No videos returned from bounded discovery!"

        for i, item in enumerate(discovered, 1):
            yt_id = item.get("id") or item.get("youtube_id")
            title = item.get("title", "")[:50]
            dur = item.get("duration")
            # Check duplicate in DB
            db_vid = session.query(Video).filter_by(youtube_id=yt_id).first()
            in_db = "YES (Duplicate Protected)" if db_vid else "NO (New candidate)"
            # Check provenance self-ingestion
            is_cf_short, _, _ = check_is_clipforge_short_sync(session, yt_id)
            print(f"    {i}. [{yt_id}] {title} | Dur: {dur}s | In DB: {in_db} | ClipForge Short: {is_cf_short}")
            assert not is_cf_short, f"Self-ingestion violation: ClipForge short {yt_id} returned as source!"

        print("  -> Discovery Pass PASSED: Duplicate detection verified; zero self-ingestion.")

    print("\n" + "=" * 70)
    print("ALL PHASE 2 MONITORING CHECKS PASSED (100%)")
    print("=" * 70)

if __name__ == "__main__":
    audit_phase2()
