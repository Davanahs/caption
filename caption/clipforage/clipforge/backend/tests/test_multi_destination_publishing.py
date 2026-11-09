"""
Unit & Integration tests for multi-destination v3 publishing architecture:
- Destination validation & error handling
- Destination resolution semantics (explicit, defaults, explicit empty blocking)
- Orphan destination isolation (6 legacy clips remain only in legacy column)
- PublishTarget creation & status transitions
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, ChannelDestination, PublishTarget, Clip, Video
from backend.services.publisher import validate_destination_ids, resolve_publish_destinations
from backend.models.db_sync import save_clip_record


@pytest.fixture
def test_channels():
    """Sets up isolated test channels in the DB."""
    source_id = f"test_src_{uuid.uuid4().hex[:8]}"
    dest_id = f"test_dest_{uuid.uuid4().hex[:8]}"
    inactive_id = f"test_inact_{uuid.uuid4().hex[:8]}"
    
    with SyncSessionLocal() as session:
        src = Channel(
            id=source_id,
            channel_name="Test Source",
            channel_url="https://youtube.com/@source",
            youtube_channel_id=f"UC_{source_id}",
            is_active=True,
            is_destination=False,
            is_test=True
        )
        dest = Channel(
            id=dest_id,
            channel_name="Test Destination",
            channel_url="https://youtube.com/@dest",
            youtube_channel_id=f"UC_{dest_id}",
            is_active=True,
            is_destination=True,
            is_default_destination=False,
            is_test=True
        )
        inact = Channel(
            id=inactive_id,
            channel_name="Test Inactive Dest",
            channel_url="https://youtube.com/@inactive",
            youtube_channel_id=f"UC_{inactive_id}",
            is_active=False,
            is_destination=True,
            is_test=True
        )
        session.add_all([src, dest, inact])
        session.commit()

    yield {
        "source_id": source_id,
        "dest_id": dest_id,
        "inactive_id": inactive_id
    }

    # Teardown
    with SyncSessionLocal() as session:
        session.query(PublishTarget).filter(PublishTarget.destination_id.in_([dest_id, inactive_id])).delete(synchronize_session=False)
        session.query(ChannelDestination).filter(ChannelDestination.source_channel_id == source_id).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.in_([source_id, dest_id, inactive_id])).delete(synchronize_session=False)
        session.commit()


def test_validate_destination_nonexistent():
    """Validating non-existent destination ID raises ValueError."""
    with SyncSessionLocal() as session:
        with pytest.raises(ValueError, match="does not exist"):
            validate_destination_ids(["non_existent_uuid"], session)


def test_validate_destination_not_destination_channel(test_channels):
    """Validating channel where is_destination=False raises ValueError."""
    with SyncSessionLocal() as session:
        with pytest.raises(ValueError, match="not configured as a publishing destination"):
            validate_destination_ids([test_channels["source_id"]], session)


def test_validate_destination_inactive(test_channels):
    """Validating inactive channel raises ValueError."""
    with SyncSessionLocal() as session:
        with pytest.raises(ValueError, match="is inactive"):
            validate_destination_ids([test_channels["inactive_id"]], session)


def test_resolve_destinations_explicit_empty_blocks(test_channels):
    """Explicit destination_ids: [] BLOCKS publishing and never falls back to defaults."""
    with SyncSessionLocal() as session:
        # Configure a default relationship
        cd = ChannelDestination(
            id=str(uuid.uuid4()),
            source_channel_id=test_channels["source_id"],
            destination_channel_id=test_channels["dest_id"],
            is_default=True
        )
        session.add(cd)
        session.commit()

        # Config with explicit empty list
        config = {"destination_ids": []}
        resolved = resolve_publish_destinations(config, test_channels["source_id"], session)
        assert resolved == []


def test_resolve_destinations_absent_uses_channel_destination_defaults(test_channels):
    """When destination_ids is absent from config, source channel defaults are resolved."""
    with SyncSessionLocal() as session:
        # Create active relationship
        cd = ChannelDestination(
            id=str(uuid.uuid4()),
            source_channel_id=test_channels["source_id"],
            destination_channel_id=test_channels["dest_id"],
            is_default=True
        )
        session.add(cd)
        session.commit()

        # Config without destination_ids key
        config = {"reframe_mode": "center_crop"}
        # Mock file check in validate_destination_ids by mocking Path.exists
        from unittest.mock import patch
        with patch("pathlib.Path.exists", return_value=True):
            resolved = resolve_publish_destinations(config, test_channels["source_id"], session)
            assert resolved == [test_channels["dest_id"]]


def test_save_clip_record_isolates_orphan_destination():
    """
    6 legacy clips have publish_destination_id = 'test-destination-uuid' which is not a channel.
    save_clip_record must save the legacy string on Clip, but NOT create any PublishTarget rows.
    """
    clip_id = f"test_clip_{uuid.uuid4().hex[:8]}"
    video_id = f"test_vid_{uuid.uuid4().hex[:8]}"
    orphan_dest = "test-destination-uuid"

    with SyncSessionLocal() as session:
        vid = Video(id=video_id, title="Test Video", youtube_url="https://youtube.com/watch?v=123")
        session.add(vid)
        session.commit()

    try:
        save_clip_record(
            clip_id=clip_id,
            video_id=video_id,
            title="Test Orphan Isolation Clip",
            start=0.0,
            end=15.0,
            duration=15.0,
            score=1.0,
            output_path="",
            thumbnail_path="",
            transcript_segment="",
            publish_destination_id=orphan_dest
        )

        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            assert clip is not None
            assert clip.publish_destination_id == orphan_dest

            # Verify NO PublishTarget created for orphaned destination
            targets = session.query(PublishTarget).filter_by(clip_id=clip_id).all()
            assert len(targets) == 0

    finally:
        with SyncSessionLocal() as session:
            session.query(Clip).filter_by(id=clip_id).delete()
            session.query(Video).filter_by(id=video_id).delete()
            session.commit()


def test_save_clip_record_creates_valid_publish_targets(test_channels):
    """When valid destinations are provided, PublishTarget rows are created atomically."""
    clip_id = f"test_clip_{uuid.uuid4().hex[:8]}"
    video_id = f"test_vid_{uuid.uuid4().hex[:8]}"
    dest_id = test_channels["dest_id"]

    with SyncSessionLocal() as session:
        vid = Video(id=video_id, title="Test Video", youtube_url="https://youtube.com/watch?v=456")
        session.add(vid)
        session.commit()

    try:
        save_clip_record(
            clip_id=clip_id,
            video_id=video_id,
            title="Test Valid Targets Clip",
            start=0.0,
            end=20.0,
            duration=20.0,
            score=1.0,
            output_path="",
            thumbnail_path="",
            transcript_segment="",
            destination_ids=[dest_id]
        )

        with SyncSessionLocal() as session:
            targets = session.query(PublishTarget).filter_by(clip_id=clip_id).all()
            assert len(targets) == 1
            assert targets[0].destination_id == dest_id
            assert targets[0].status == "pending"

    finally:
        with SyncSessionLocal() as session:
            session.query(PublishTarget).filter_by(clip_id=clip_id).delete()
            session.query(Clip).filter_by(id=clip_id).delete()
            session.query(Video).filter_by(id=video_id).delete()
            session.commit()
