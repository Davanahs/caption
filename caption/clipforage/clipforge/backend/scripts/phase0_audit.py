import os, sys, json
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Clip, PublishRecord, VideoTrackingQueue
from backend.services.publisher import get_youtube_client

print("=== PHASE 0 ENVIRONMENT AUDIT ===")
print(f"PUBLISH_MODE: {settings.PUBLISH_MODE}")
print(f"OPENROUTER_API_KEY Configured: {bool(settings.OPENROUTER_API_KEY)}")
print(f"NVIDIA_API_KEY Configured: {bool(getattr(settings, 'NVIDIA_API_KEY', None))}")
print(f"WHISPER_MODEL: {settings.WHISPER_MODEL}")
print(f"OUTPUT_DIR: {settings.OUTPUT_DIR}")
print(f"UPLOAD_DIR: {settings.UPLOAD_DIR}")
print(f"MIN_CLIP_DURATION: {settings.MIN_CLIP_DURATION}")
print(f"MAX_CLIP_DURATION: {settings.MAX_CLIP_DURATION}")
print(f"SCORING_MODE: {settings.SCORING_MODE}")

with SyncSessionLocal() as s:
    dest_channels = s.query(Channel).filter_by(is_destination=True).all()
    print(f"\nConfigured Destination Channels ({len(dest_channels)}):")
    for d in dest_channels:
        token_path = f"tokens/{d.youtube_channel_id}.json"
        token_exists = os.path.exists(token_path)
        print(f"  - {d.channel_name} (ID: {d.id}, YT: {d.youtube_channel_id}, Active: {d.is_active}, Token file exists: {token_exists})")

    test_clip = s.query(Clip).filter_by(youtube_short_id='fxDE7-HJkto').first()
    if test_clip:
        print(f"\nTest Artifact fxDE7-HJkto in DB:")
        print(f"  Clip ID: {test_clip.id}")
        print(f"  Status: {test_clip.status}")
        print(f"  Publish Status: {test_clip.publish_status}")
        print(f"  Duration: {test_clip.duration}s")
        print(f"  Destination ID: {test_clip.publish_destination_id}")
        pr = s.query(PublishRecord).filter_by(external_id='fxDE7-HJkto').first()
        if pr:
            print(f"  PublishRecord Status: {pr.status}, Target: {pr.target}, Key: {pr.idempotency_key}")
        tq = s.query(VideoTrackingQueue).filter_by(youtube_video_id='fxDE7-HJkto').first()
        if tq:
            print(f"  TrackingQueue Status: {tq.status}")

    # Read-only YouTube API verification of fxDE7-HJkto
    yt = get_youtube_client('UCH90024qrJHA4amGRxnTldw')
    resp = yt.videos().list(part='snippet,status', id='fxDE7-HJkto').execute()
    items = resp.get('items', [])
    if items:
        item = items[0]
        print(f"\nLive Read-Only YouTube Data API v3 Readback for fxDE7-HJkto:")
        print(f"  Remote Video ID: {item['id']}")
        print(f"  Remote Channel ID: {item['snippet']['channelId']} (Expected: UCH90024qrJHA4amGRxnTldw)")
        print(f"  Remote Channel Title: {item['snippet']['channelTitle']}")
        print(f"  Remote Title: {item['snippet']['title']}")
        print(f"  Remote Privacy Status: {item['status']['privacyStatus']} (Must be private)")
        print(f"  Remote Upload Status: {item['status']['uploadStatus']}")
