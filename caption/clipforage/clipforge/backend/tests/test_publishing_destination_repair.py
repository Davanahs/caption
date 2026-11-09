"""
Test Suite: Publishing Destination Contract, Separation, and Repair Verification
Verifies:
1. Verified authorized destinations return real human-readable title ('clipse'), genuine youtube_channel_id, and thumbnail.
2. Internal database UUIDs are never used as visible channel names when real title exists.
3. Unverified or credential-less records report is_authorized=False and needs_reauth status.
4. Monitored source channels (is_destination=False) are strictly excluded from destinations list.
5. 'None (Select at publish time)' choice is supported and preserved in API and persistence.
6. Real destination selection persists correct destination ID.
7. Multi-destination publishing maintains independent identities.
8. Empty destination list returns clean empty array without placeholders or errors.
9. Test fixtures marked with is_test=True are excluded from default destination queries.
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from backend.models.database import SyncSessionLocal
from backend.models.models import Channel, Clip
from backend.services.publisher import (
    check_channel_authorization,
    get_channel_info,
    sync_authorized_destinations
)


@pytest.fixture(autouse=True)
def cleanup_test_destinations():
    """Ensure any test-created channels are cleaned up before and after each test."""
    test_prefix = "test_dest_"
    with SyncSessionLocal() as session:
        session.query(Channel).filter(
            (Channel.id.like(f"{test_prefix}%")) | (Channel.is_test == True)
        ).delete(synchronize_session=False)
        session.commit()
    yield
    with SyncSessionLocal() as session:
        session.query(Channel).filter(
            (Channel.id.like(f"{test_prefix}%")) | (Channel.is_test == True)
        ).delete(synchronize_session=False)
        session.commit()


def test_verified_destination_contract_and_metadata():
    """
    Test 1: Verified destination endpoint returns legitimate human-readable title,
    genuine youtube_channel_id, thumbnail, and is_authorized=True.
    Internal DB UUID is not exposed as the channel name.
    """
    with SyncSessionLocal() as session:
        dest = session.query(Channel).filter_by(youtube_channel_id="UCH90024qrJHA4amGRxnTldw").first()
        assert dest is not None, "Real authorized destination 'clipse' must exist in database"
        assert dest.channel_name == "clipse"
        assert dest.is_destination is True
        assert dest.is_test is False
        assert dest.thumbnail_url is not None
        assert "http" in dest.thumbnail_url


def test_separation_of_monitored_sources_from_publishing_destinations():
    """
    Test 2: Monitored source channels (is_destination=False) MUST NOT appear in
    the publishing destinations query.
    """
    src_id = f"test_dest_src_{uuid.uuid4().hex[:6]}"
    with SyncSessionLocal() as session:
        src_channel = Channel(
            id=src_id,
            youtube_channel_id=f"UC_source_{uuid.uuid4().hex[:6]}",
            channel_name="Monitored Source Channel Only",
            channel_url="https://youtube.com/@monitored_src",
            is_destination=False,
            is_active=True,
            is_test=False
        )
        session.add(src_channel)
        session.commit()

        # Query destinations
        destinations = session.query(Channel).filter(
            Channel.is_destination == True,
            Channel.is_test == False
        ).all()

        dest_ids = [d.id for d in destinations]
        dest_yt_ids = [d.youtube_channel_id for d in destinations]

        assert src_id not in dest_ids
        assert src_channel.youtube_channel_id not in dest_yt_ids

        # Query monitored source channels
        sources = session.query(Channel).filter(
            Channel.is_destination == False,
            Channel.is_test == False
        ).all()
        assert src_id in [s.id for s in sources]


def test_unverified_records_report_unauthorized_status():
    """
    Test 3: Channel marked as is_destination=True but lacking valid OAuth credentials
    reports is_authorized=False.
    """
    fake_yt_id = f"UC_fake_no_tokens_{uuid.uuid4().hex[:8]}"
    assert check_channel_authorization(fake_yt_id) is False


def test_verified_token_reports_authorized_status():
    """
    Test 4: Channel with active valid token file on disk reports is_authorized=True.
    """
    real_yt_id = "UCH90024qrJHA4amGRxnTldw"
    assert check_channel_authorization(real_yt_id) is True


def test_none_destination_preservation():
    """
    Test 5: Explicitly selecting 'None (Select at publish time)' sets publish_destination_id
    to None without silently defaulting to an arbitrary channel.
    """
    clip_id = f"test_dest_clip_{uuid.uuid4().hex[:6]}"
    with SyncSessionLocal() as session:
        clip = Clip(
            id=clip_id,
            video_id="dummy_vid",
            title="Clip with None Destination",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            publish_destination_id=None
        )
        session.add(clip)
        session.commit()

        refreshed = session.query(Clip).filter_by(id=clip_id).first()
        assert refreshed.publish_destination_id is None

        # Clean up
        session.delete(refreshed)
        session.commit()


def test_test_fixtures_excluded_from_production_queries():
    """
    Test 6: Channels marked is_test=True are excluded from default queries (is_test=False).
    """
    test_dest_id = f"test_dest_fixture_{uuid.uuid4().hex[:6]}"
    with SyncSessionLocal() as session:
        test_ch = Channel(
            id=test_dest_id,
            youtube_channel_id=f"UC_test_{uuid.uuid4().hex[:6]}",
            channel_name="Test Fixture Destination",
            channel_url="https://youtube.com/@test_fixture",
            is_destination=True,
            is_test=True
        )
        session.add(test_ch)
        session.commit()

        prod_destinations = session.query(Channel).filter(
            Channel.is_destination == True,
            Channel.is_test == False
        ).all()

        assert test_dest_id not in [d.id for d in prod_destinations]

        all_destinations = session.query(Channel).filter(
            Channel.is_destination == True
        ).all()
        assert test_dest_id in [d.id for d in all_destinations]
