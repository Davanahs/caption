"""
Section 13 Controlled Private YouTube Upload Acceptance Verification
Preconditions and safety rules:
1. Destination channel: UCH90024qrJHA4amGRxnTldw (clipse)
2. Visibility: strictly 'private'
3. Idempotency key: clipforge_acceptance_private_upload_20261025
4. Non-sensitive test clip: dummy.mp4
5. Post-upload verification: query YouTube API to confirm privacyStatus == 'private'
6. Never print tokens or credentials to stdout/logs
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, ".")

def main():
    print("=" * 70)
    print("CLIPFORGE SECTION 13: CONTROLLED PRIVATE YOUTUBE ACCEPTANCE TEST")
    print("=" * 70)

    # Precondition 1: Check destination channel in DB
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Channel, Clip, PublishStatus, PublishRecord, VideoTrackingQueue

    destination_channel_id = "518b3118-2367-4f84-898f-ff97a61df306"
    expected_yt_channel_id = "UCH90024qrJHA4amGRxnTldw"

    with SyncSessionLocal() as session:
        ch = session.query(Channel).filter_by(id=destination_channel_id).first()
        if not ch:
            print("BLOCKED: Destination channel not found in database.")
            return
        if ch.youtube_channel_id != expected_yt_channel_id:
            print(f"BLOCKED: Channel ID mismatch: expected {expected_yt_channel_id}, got {ch.youtube_channel_id}")
            return
        if not ch.is_destination:
            print("BLOCKED: Channel is not configured as an authorized destination.")
            return
        print(f"Precondition 1 PASSED: Destination channel '{ch.channel_name}' ({ch.youtube_channel_id}) verified.")

    # Precondition 2: Check token file & client authentication
    from backend.services.publisher import get_youtube_client, _resolve_token_file
    token_file = _resolve_token_file(expected_yt_channel_id)
    if not token_file.exists():
        print(f"BLOCKED: Token file {token_file} does not exist.")
        return

    try:
        yt_client = get_youtube_client(expected_yt_channel_id)
        ch_resp = yt_client.channels().list(part="id,snippet", mine=True).execute()
        if not ch_resp.get("items"):
            print("BLOCKED: Could not list channels for authenticated credentials.")
            return
        auth_id = ch_resp["items"][0]["id"]
        auth_title = ch_resp["items"][0]["snippet"]["title"]
        if auth_id != expected_yt_channel_id:
            print(f"BLOCKED: Credential mismatch: authenticated as {auth_id}, expected {expected_yt_channel_id}")
            return
        print(f"Precondition 2 PASSED: Authenticated client verified for '{auth_title}' ({auth_id}).")
    except Exception as exc:
        print(f"BLOCKED: YouTube client authentication error: {exc}")
        return

    # Precondition 3: Test clip file
    test_video_path = Path("dummy.mp4").resolve()
    if not test_video_path.exists():
        print(f"BLOCKED: Test media file {test_video_path} not found.")
        return
    print(f"Precondition 3 PASSED: Non-sensitive test clip verified ({test_video_path}, size={test_video_path.stat().st_size} bytes).")

    # Precondition 4: Setup or locate test clip record in DB
    clip_id = "clip-section13-acceptance-private-001"
    idempotency_key = "clipforge_acceptance_private_upload_20261025"

    with SyncSessionLocal() as session:
        # Check if already published with external ID
        existing_rec = session.query(PublishRecord).filter_by(idempotency_key=idempotency_key).first()
        if existing_rec and existing_rec.external_id:
            print(f"NOTE: Already uploaded under idempotency key {idempotency_key}: YouTube ID {existing_rec.external_id}")
            # Verify status on YouTube
            verify_remote_video(yt_client, existing_rec.external_id)
            return

        clip = session.query(Clip).filter_by(id=clip_id).first()
        if not clip:
            clip = Clip(
                id=clip_id,
                video_id="video-acceptance-section13",
                title="ClipForge Acceptance Test Clip [Private]",
                description="Controlled acceptance test for ClipForge private upload verification.",
                output_path=str(test_video_path),
                start_time=0.0,
                end_time=10.0,
                duration=10.0,
                score=0.0,
                privacy="private",
                made_for_kids=False,
                category="22",
                license="youtube",
                publish_destination_id=destination_channel_id,
                publish_status=PublishStatus.DRAFT.value,
                publish_idempotency_key=idempotency_key,
                created_at=datetime.now(timezone.utc),
            )
            session.add(clip)
        else:
            clip.output_path = str(test_video_path)
            clip.privacy = "private"
            clip.publish_destination_id = destination_channel_id
            clip.publish_idempotency_key = idempotency_key
            clip.publish_status = PublishStatus.DRAFT.value
        session.commit()
    print("Precondition 4 PASSED: DB clip record initialized with privacy='private'.")

    # Precondition 5: Execute upload with privacy strictly 'private'
    print("\nExecuting controlled Private upload...")
    from backend.core.config import settings
    original_publish_mode = getattr(settings, "PUBLISH_MODE", "test")

    try:
        # Temporarily enable prod upload for this single controlled test
        settings.PUBLISH_MODE = "prod"
        from backend.services.publisher import upload_short

        upload_result = upload_short(
            video_path=test_video_path,
            title="ClipForge Acceptance Test [Private]",
            description="Autonomous UI Acceptance Test Verification #Shorts",
            privacy="private",
            made_for_kids=False,
            category="22",
            license_type="youtube",
            idempotency_key=idempotency_key,
            channel_id=expected_yt_channel_id,
            clip_id=clip_id,
        )

        video_id = upload_result.get("id")
        video_url = upload_result.get("url")
        print(f"\nUPLOAD SUCCESSFUL!")
        print(f"YouTube Video ID: {video_id}")
        print(f"YouTube URL: {video_url}")

        # Post-upload Verification: Query YouTube API to confirm privacyStatus == 'private'
        verify_remote_video(yt_client, video_id, clip_id=clip_id)

    except Exception as exc:
        print(f"\nUPLOAD ATTEMPT TERMINATED: {exc}")
        print("Safety Stop Condition evaluated.")
    finally:
        # Restore original PUBLISH_MODE
        settings.PUBLISH_MODE = original_publish_mode
        print(f"\nPUBLISH_MODE restored to: {settings.PUBLISH_MODE}")

def verify_remote_video(yt_client, video_id, clip_id=None):
    print("\nVerifying uploaded video metadata on YouTube API...")
    v_resp = yt_client.videos().list(part="snippet,status", id=video_id).execute()
    items = v_resp.get("items", [])
    if not items:
        print(f"WARNING: Video {video_id} not found in YouTube query response.")
        return

    item = items[0]
    status = item.get("status", {})
    snippet = item.get("snippet", {})
    actual_privacy = status.get("privacyStatus")
    title = snippet.get("title")
    channel_id = snippet.get("channelId")

    print(f"Verified Title: {title}")
    print(f"Verified Channel ID: {channel_id}")
    print(f"Verified Privacy Status: {actual_privacy}")

    assert actual_privacy == "private", f"CRITICAL SECURITY FAILURE: Video is {actual_privacy}, NOT private!"
    print("\nVERIFICATION PASS: Video is confirmed PRIVATE on YouTube.")

    # Update DB state
    if clip_id:
        from backend.models.database import SyncSessionLocal
        from backend.models.models import Clip, PublishStatus, PublishRecord
        with SyncSessionLocal() as session:
            c = session.query(Clip).filter_by(id=clip_id).first()
            if c:
                c.youtube_short_id = video_id
                c.publish_status = PublishStatus.PUBLISHED.value
                c.publish_stage = "published"
                c.publish_progress = 100
                c.published_at = datetime.now(timezone.utc)
                c.publish_completed_at = datetime.now(timezone.utc)
            pr = session.query(PublishRecord).filter_by(idempotency_key="clipforge_acceptance_private_upload_20261025").first()
            if not pr:
                pr = PublishRecord(
                    idempotency_key="clipforge_acceptance_private_upload_20261025",
                    job_id="acceptance-job-001",
                    clip_id=clip_id,
                    target="youtube",
                    external_id=video_id,
                    status="completed"
                )
                session.add(pr)
            else:
                pr.external_id = video_id
                pr.status = "completed"
            session.commit()
            print("Database state updated to 'published' with confirmed external ID.")

if __name__ == "__main__":
    main()
