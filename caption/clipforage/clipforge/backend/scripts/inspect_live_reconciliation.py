"""
inspect_live_reconciliation.py
==============================
Reconciles the 6 target private YouTube Shorts, their source videos, channels,
generated clips, and remaining clips in the database.
"""
import sys
import io
from collections import Counter
from datetime import timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Video, Clip, Job, VideoDecision, PublishRecord

def reconcile():
    six_ids = ['YpHobheDpk8', 'kkXWbXZI_iM', '0OfOivc-tpU', '39w4TLjreFU', 'L3ihlJVo_3A', 'FoNMm4F9qIM']
    
    with SyncSessionLocal() as s:
        print("=" * 60)
        print("1. RECONCILING THE 6 TARGET LIVE YOUTUBE SHORTS")
        print("=" * 60)
        
        found_count = 0
        video_ids_for_six = []
        for yt_id in six_ids:
            c = s.query(Clip).filter(Clip.youtube_short_id == yt_id).first()
            if c:
                found_count += 1
                v = s.query(Video).filter(Video.id == c.video_id).first()
                ch = s.query(Channel).filter(Channel.id == c.publish_destination_id).first()
                if v:
                    video_ids_for_six.append(v.id)
                v_yt = v.youtube_id if v else "None"
                v_title = v.title[:35] if v else "Unknown"
                dest_name = ch.channel_name if ch else str(c.publish_destination_id)
                print(f"  [FOUND] Short: {yt_id} | Clip: {c.id} | Video YT: {v_yt} ({v_title}) | Dest: {dest_name} | Status: {c.publish_status} | Priv: {c.privacy}")
            else:
                print(f"  [MISSING] Short: {yt_id} NOT found in Clip table!")

        print(f"\nTotal Target Shorts Reconciled in DB: {found_count} / 6")

        print("\n" + "=" * 60)
        print("2. ALL GENERATED CLIPS FOR THESE 6 SOURCE VIDEOS")
        print("=" * 60)
        all_clips_for_six = s.query(Clip).filter(Clip.video_id.in_(video_ids_for_six)).all()
        print(f"Total clips generated for these 6 source videos: {len(all_clips_for_six)}")
        
        # Group by video
        by_vid = {}
        for c in all_clips_for_six:
            by_vid.setdefault(c.video_id, []).append(c)
            
        for vid, clips in by_vid.items():
            v = s.query(Video).filter(Video.id == vid).first()
            v_yt = v.youtube_id if v else "Unknown"
            v_title = v.title[:35] if v else "Unknown"
            print(f"\nSource Video: {v_yt} ({v_title}) - Total Clips: {len(clips)}")
            for c in clips:
                is_pub = "YES -> " + str(c.youtube_short_id) if c.youtube_short_id in six_ids else ("MOCK -> " + str(c.youtube_short_id) if c.youtube_short_id else "NO (Unpublished)")
                print(f"    Clip {c.id[:8]}.. | Score: {c.score} | Duration: {c.duration}s | Status: {c.status} | PubStatus: {c.publish_status} | Published: {is_pub}")

        print("\n" + "=" * 60)
        print("3. CHANNELS OVERVIEW")
        print("=" * 60)
        channels = s.query(Channel).all()
        for ch in channels:
            print(f"  Channel: {ch.id} | Name: {ch.channel_name} | YT_ID: {ch.youtube_channel_id} | Dest: {ch.is_destination} | Active: {ch.is_active} | AutoClip: {ch.auto_clip} | AutoPub: {ch.auto_publish} | DestLink: {ch.publish_destination_id}")

        print("\n" + "=" * 60)
        print("4. SUMMARY METRICS ACROSS REPOSITORY DATABASE")
        print("=" * 60)
        all_clips = s.query(Clip).all()
        print(f"Total Clips in DB: {len(all_clips)}")
        print(f"Clips by status: {dict(Counter(c.status for c in all_clips))}")
        print(f"Clips by publish_status: {dict(Counter(c.publish_status for c in all_clips))}")
        live_yt_clips = [c for c in all_clips if c.youtube_short_id and not c.youtube_short_id.startswith('mock_')]
        print(f"Live (non-mock) YouTube Shorts in DB: {len(live_yt_clips)}")
        for c in live_yt_clips:
            print(f"    Live Short: {c.youtube_short_id} (Clip: {c.id}, Privacy: {c.privacy})")

if __name__ == "__main__":
    reconcile()
