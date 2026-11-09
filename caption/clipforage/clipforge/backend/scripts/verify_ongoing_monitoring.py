import sys
from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, ChannelDestination, VideoDecision, Video

with SyncSessionLocal() as s:
    src = s.query(Channel).filter_by(id="b4bb167b-429f-4c52-b78f-a52cc9f03980").first()
    dst = s.query(Channel).filter_by(id="518b3118-2367-4f84-898f-ff97a61df306").first()
    link = s.query(ChannelDestination).filter_by(source_channel_id=src.id, destination_channel_id=dst.id).first()

    print("=== ONGOING MONITORING VERIFICATION ===")
    print(f"Source Channel: {src.channel_name} (ID: {src.id}, YT: {src.youtube_channel_id})")
    print(f"  Auto Monitor (is_active): {src.is_active} (EXPECTED: True)")
    print(f"  Auto Publish (auto_publish): {src.auto_publish} (EXPECTED: True)")
    print(f"  Auto Clip (auto_clip): {src.auto_clip} (EXPECTED: True)")
    print(f"  Publish Destination ID: {src.publish_destination_id} (EXPECTED: {dst.id})")
    print(f"  Clips Generated Count: {src.clips_generated}")
    print(f"  Last Checked At: {src.last_checked_at}")
    
    print(f"\nDestination Channel: {dst.channel_name} (ID: {dst.id}, YT: {dst.youtube_channel_id})")
    print(f"  Is Destination: {dst.is_destination} (EXPECTED: True)")
    print(f"  Is Default Destination: {dst.is_default_destination} (EXPECTED: True)")
    print(f"  Auto Publish: {dst.auto_publish} (EXPECTED: True)")
    print(f"  Publishing Settings: {dst.publishing_settings}")
    
    print(f"\nDestination Link in ChannelDestination: {link is not None} (is_default: {getattr(link, 'is_default', None)})")
    
    # Assert all invariants
    assert src.is_active is True, "Auto Monitor must be True"
    assert src.auto_publish is True, "Auto Publish must be True"
    assert src.publish_destination_id == dst.id, "Destination ID must point to ClipSee"
    assert dst.is_destination is True, "Destination must be registered as destination"
    assert dst.publishing_settings.get("default_privacy") == "private", "Default privacy must be private"
    assert link is not None, "ChannelDestination link must exist"
    
    print("\nALL INVARIANTS SATISFIED & VERIFIED!")
