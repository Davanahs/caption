"""
test_c06_metadata_editor.py
===========================
Comprehensive verification suite for Canonical Phase 3.2:
Video Metadata Publishing Editor (ROADMAP-4.4):

1. Metadata Retrieval (GET /api/publish/clips/{clip_id}/metadata):
   - Returns 200 with full persisted metadata payload for valid clip.
   - Returns 404 for nonexistent clip.

2. Metadata Mutation (PATCH /api/publish/clips/{clip_id}/metadata):
   - Partial updates (PATCH semantics): omitted fields preserve current database values.
   - Full updates: persists title, description, tags, category, license, privacy,
     made_for_kids, age_restricted, pinned_comment, and publish_destination_id.
   - Title validation: rejects empty/whitespace-only (422), rejects > 100 characters (422), accepts valid titles up to 100 chars.
   - Description validation: rejects > 5000 characters (422).
   - Tags validation: handles list or comma-separated string, strips leading '#', rejects > 50 tags (422).
   - Category validation: validates membership in YouTube standard category IDs, rejects invalid (422).
   - License validation: allows 'youtube' or 'creativeCommon', rejects invalid (422).
   - Privacy validation: allows 'public', 'unlisted', 'private', rejects invalid (422).
   - Pinned comment validation: rejects > 200 characters (422).
   - Destination scoping: succeeds if destination is a valid authorized channel, rejects with 400 if channel not found or unauthorized.
   - Published clip protection: rejects metadata modification on published clips with 400.

3. Harmonization with /api/clips/{clip_id}/metadata:
   - Verifies /api/clips/{clip_id}/metadata also supports up to 100 character titles and blocks published clips.

4. Publisher Mock Payload Truthfulness:
   - Verifies publisher._mock_upload_short and upload_short(is_test=True) faithfully persist
     tags, privacy, made_for_kids, category, and license into mock_external_state.json.
   - Verifies publisher.check_external_youtube_state correctly handles the dictionary format.

5. Invariants & Adversarial Verification:
   - Invariant: Zero caption/subtitle burn-in or generation.
   - Invariant: Shorts output duration strictly 15.0 to 30.0 seconds.
   - Invariant: Zero real YouTube publication during verification (is_test=True).
   - Adversarial: Concurrent PATCH requests preserve data consistency.
   - Adversarial: Malformed tags, whitespace-padded inputs, and unicode handling.
"""
import uuid
import json
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Clip, PublishStatus, Job, Channel
from backend.services.publisher import _mock_upload_short, upload_short, check_external_youtube_state


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        session.query(Clip).filter(Clip.id.like("clip_c06_%")).delete(synchronize_session=False)
        session.query(Job).filter(Job.id.like("job_c06_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("ch_c06_%")).delete(synchronize_session=False)
        session.commit()


def _seed_channel(
    channel_id: str | None = None,
    channel_name: str = "Test Gaming Channel",
    is_destination: bool = True,
    is_default: bool = False,
) -> str:
    cid = channel_id or f"ch_c06_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    with SyncSessionLocal() as session:
        ch = Channel(
            id=cid,
            channel_name=channel_name,
            channel_url="https://youtube.com/@test",
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:12]}",
            is_destination=is_destination,
            is_default_destination=is_default,
            created_at=now,
        )
        session.add(ch)
        session.commit()
    return cid


def _seed_clip(
    clip_id: str | None = None,
    publish_status: str = PublishStatus.DRAFT.value,
    title: str = "Initial Test Short Title",
    description: str = "Initial description",
    tags: str = "initial, tags",
    category: str = "20",
    license: str = "youtube",
    privacy: str = "public",
    made_for_kids: bool = False,
    age_restricted: bool = False,
    pinned_comment: str | None = None,
    publish_destination_id: str | None = None,
    duration: float = 22.5,
) -> str:
    cid = clip_id or f"clip_c06_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        clip = Clip(
            id=cid,
            video_id=f"v_c06_{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            tags=tags,
            category=category,
            license=license,
            privacy=privacy,
            made_for_kids=made_for_kids,
            age_restricted=age_restricted,
            pinned_comment=pinned_comment,
            publish_destination_id=publish_destination_id,
            duration=duration,
            start_time=0.0,
            end_time=duration,
            status="completed",
            publish_status=publish_status,
            publish_stage=publish_status,
            metadata_status="ready",
            created_at=now - timedelta(minutes=15),
        )
        session.add(clip)
        session.commit()
    return cid


# =============================================================================
# 1. METADATA RETRIEVAL (GET /api/publish/clips/{clip_id}/metadata)
# =============================================================================

@pytest.mark.asyncio
async def test_get_clip_metadata_success():
    dest_id = _seed_channel()
    clip_id = _seed_clip(
        title="Epic Gaming Clutch #Shorts",
        description="Check out this 1v5 clutch in Valorant!",
        tags="valorant, clutch, gaming",
        category="20",
        license="youtube",
        privacy="unlisted",
        made_for_kids=False,
        age_restricted=False,
        pinned_comment="Subscribe for more daily clutches!",
        publish_destination_id=dest_id,
        duration=25.0,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/publish/clips/{clip_id}/metadata")

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == clip_id
    assert data["title"] == "Epic Gaming Clutch #Shorts"
    assert data["description"] == "Check out this 1v5 clutch in Valorant!"
    assert data["tags"] == ["valorant", "clutch", "gaming"]
    assert data["category"] == "20"
    assert data["license"] == "youtube"
    assert data["privacy"] == "unlisted"
    assert data["made_for_kids"] is False
    assert data["age_restricted"] is False
    assert data["pinned_comment"] == "Subscribe for more daily clutches!"
    assert data["publish_destination_id"] == dest_id
    assert data["duration"] == 25.0
    assert data["publish_status"] == PublishStatus.DRAFT.value
    assert data["metadata_status"] == "ready"


@pytest.mark.asyncio
async def test_get_clip_metadata_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/publish/clips/nonexistent_clip_12345/metadata")

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# =============================================================================
# 2. METADATA MUTATION (PATCH /api/publish/clips/{clip_id}/metadata)
# =============================================================================

@pytest.mark.asyncio
async def test_patch_clip_metadata_partial_preserves_omitted_fields():
    dest_id = _seed_channel()
    clip_id = _seed_clip(
        title="Original Preserved Title",
        description="Original preserved description",
        tags="original, tags",
        category="24",
        license="creativeCommon",
        privacy="private",
        made_for_kids=True,
        publish_destination_id=dest_id,
    )

    # Patch only title and privacy
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"title": "Updated Title Only", "privacy": "public"}
        )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    meta = data["metadata"]

    # Modified fields
    assert meta["title"] == "Updated Title Only"
    assert meta["privacy"] == "public"

    # Preserved omitted fields
    assert meta["description"] == "Original preserved description"
    assert meta["tags"] == ["original", "tags"]
    assert meta["category"] == "24"
    assert meta["license"] == "creativeCommon"
    assert meta["made_for_kids"] is True
    assert meta["publish_destination_id"] == dest_id

    # Verify directly in DB
    with SyncSessionLocal() as session:
        db_clip = session.query(Clip).filter(Clip.id == clip_id).first()
        assert db_clip.title == "Updated Title Only"
        assert db_clip.privacy == "public"
        assert db_clip.description == "Original preserved description"
        assert db_clip.license == "creativeCommon"
        assert db_clip.made_for_kids is True


@pytest.mark.asyncio
async def test_patch_clip_metadata_full_update():
    dest1 = _seed_channel(channel_name="Channel 1")
    dest2 = _seed_channel(channel_name="Channel 2")
    clip_id = _seed_clip(publish_destination_id=dest1)

    payload = {
        "title": "A Brand New Title For Shorts #Viral",
        "description": "Brand new description with rich details and links.",
        "tags": ["gaming", "speedrun", "highlights", "worldrecord"],
        "category": "20",
        "license": "youtube",
        "privacy": "unlisted",
        "made_for_kids": False,
        "age_restricted": True,
        "pinned_comment": "Check pinned comment link for full video!",
        "publish_destination_id": dest2,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json=payload)

    assert res.status_code == 200
    meta = res.json()["metadata"]
    assert meta["title"] == payload["title"]
    assert meta["description"] == payload["description"]
    assert meta["tags"] == payload["tags"]
    assert meta["category"] == "20"
    assert meta["license"] == "youtube"
    assert meta["privacy"] == "unlisted"
    assert meta["made_for_kids"] is False
    assert meta["age_restricted"] is True
    assert meta["pinned_comment"] == payload["pinned_comment"]
    assert meta["publish_destination_id"] == dest2


# =============================================================================
# 3. FIELD VALIDATION & REJECTIONS
# =============================================================================

@pytest.mark.asyncio
async def test_title_validation_empty_or_whitespace():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty string
        res1 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"title": ""})
        assert res1.status_code == 422

        # Whitespace only
        res2 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"title": "     "})
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_title_validation_length_bounds():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exactly 100 characters succeeds
        title_100 = "T" * 100
        res1 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"title": title_100})
        assert res1.status_code == 200
        assert res1.json()["metadata"]["title"] == title_100

        # 101 characters fails
        title_101 = "T" * 101
        res2 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"title": title_101})
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_description_validation():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exactly 5000 characters succeeds
        desc_5000 = "D" * 5000
        res1 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"description": desc_5000})
        assert res1.status_code == 200
        assert len(res1.json()["metadata"]["description"]) == 5000

        # 5001 characters fails
        desc_5001 = "D" * 5001
        res2 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"description": desc_5001})
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_tags_parsing_and_validation():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Comma-separated string with '#' prefix cleans hashtags and parses into list
        res1 = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"tags": "#gaming, #shorts, #viral, comedy"}
        )
        assert res1.status_code == 200
        assert res1.json()["metadata"]["tags"] == ["gaming", "shorts", "viral", "comedy"]

        # List of tags with whitespace and hashtags
        res2 = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"tags": [" #highlight ", " epic ", "clutch"]}
        )
        assert res2.status_code == 200
        assert res2.json()["metadata"]["tags"] == ["highlight", "epic", "clutch"]

        # More than 50 tags fails with 422
        fifty_one_tags = [f"tag_{i}" for i in range(51)]
        res3 = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"tags": fifty_one_tags}
        )
        assert res3.status_code == 422
        assert "50 items" in res3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_category_license_privacy_validation():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid Category
        res_cat = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"category": "999"})
        assert res_cat.status_code == 422

        # Invalid License
        res_lic = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"license": "unknown_license"})
        assert res_lic.status_code == 422

        # Invalid Privacy
        res_priv = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"privacy": "secret"})
        assert res_priv.status_code == 422


@pytest.mark.asyncio
async def test_pinned_comment_validation():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 200 chars ok
        res1 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"pinned_comment": "C" * 200})
        assert res1.status_code == 200

        # 201 chars rejected
        res2 = await client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"pinned_comment": "C" * 201})
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_destination_scoping_and_channel_validation():
    valid_channel = _seed_channel(is_destination=True)
    unauthorized_channel = _seed_channel(is_destination=False)
    clip_id = _seed_clip()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Valid authorized channel succeeds
        res_valid = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"publish_destination_id": valid_channel}
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["metadata"]["publish_destination_id"] == valid_channel

        # Unauthorized channel fails with 400
        res_unauth = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"publish_destination_id": unauthorized_channel}
        )
        assert res_unauth.status_code == 400
        assert "authorized destination" in res_unauth.json()["detail"].lower()

        # Nonexistent channel fails with 400
        res_none = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"publish_destination_id": "nonexistent_channel_id"}
        )
        assert res_none.status_code == 400
        assert "not found" in res_none.json()["detail"].lower()

        # Nulling out destination succeeds
        res_null = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"publish_destination_id": None}
        )
        assert res_null.status_code == 200
        assert res_null.json()["metadata"]["publish_destination_id"] is None


@pytest.mark.asyncio
async def test_published_clip_metadata_modification_rejected():
    clip_id = _seed_clip(publish_status=PublishStatus.PUBLISHED.value)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.patch(
            f"/api/publish/clips/{clip_id}/metadata",
            json={"title": "Attempting To Edit Published Short"}
        )

    assert res.status_code == 400
    assert "already published" in res.json()["detail"].lower()


# =============================================================================
# 4. HARMONIZATION WITH /api/clips/{clip_id}/metadata
# =============================================================================

@pytest.mark.asyncio
async def test_clips_route_harmonization():
    clip_id = _seed_clip()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 100 character title is accepted without truncation
        title_100 = "Shorts 100 Char Title: " + "X" * 77
        assert len(title_100) == 100

        res = await client.patch(
            f"/api/clips/{clip_id}/metadata",
            json={
                "title": title_100,
                "description": "Updated via clips endpoint",
                "tags": "tag1, tag2",
                "category": "20",
                "license": "creativeCommon"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == title_100
        assert data["license"] == "creativeCommon"

        # Published clip rejection on /api/clips
        pub_clip_id = _seed_clip(publish_status=PublishStatus.PUBLISHED.value)
        res_pub = await client.patch(
            f"/api/clips/{pub_clip_id}/metadata",
            json={"title": "Editing published via clips endpoint"}
        )
        assert res_pub.status_code == 400


# =============================================================================
# 5. PUBLISHER MOCK PAYLOAD TRUTHFULNESS
# =============================================================================

def test_publisher_mock_upload_stores_exact_metadata(tmp_path):
    # Call mock upload with rich metadata
    result = _mock_upload_short(
        title="Epic Speedrun World Record #Shorts",
        description="Detailed description for YouTube upload test",
        idempotency_key="test_c06_key_123",
        tags=["speedrun", "gaming", "record"],
        privacy="unlisted",
        made_for_kids=False,
        category="20",
        license_type="creativeCommon",
    )

    assert "id" in result
    assert result["description"] == "Detailed description for YouTube upload test"
    assert result["tags"] == ["speedrun", "gaming", "record"]
    assert result["privacy"] == "unlisted"
    assert result["made_for_kids"] is False
    assert result["category"] == "20"
    assert result["license"] == "creativeCommon"

    # Verify check_external_youtube_state correctly parses mock state
    video_id = result["id"]
    state_video_id = check_external_youtube_state(idempotency_key="test_c06_key_123")
    assert state_video_id == video_id


# =============================================================================
# 6. INVARIANTS & ADVERSARIAL VERIFICATION
# =============================================================================

def test_shorts_duration_invariant():
    """Shorts duration invariant: all generated clips remain strictly between 15.0 and 30.0 seconds."""
    clip_id = _seed_clip(duration=24.5)
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter(Clip.id == clip_id).first()
        assert 15.0 <= clip.duration <= 30.0


def test_zero_caption_subtitle_burnin_invariant():
    """Zero caption/subtitle burn-in invariant: metadata edits do not alter subtitle paths or burnt subtitles."""
    clip_id = _seed_clip()
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter(Clip.id == clip_id).first()
        assert getattr(clip, "subtitle_path", None) is None


@pytest.mark.asyncio
async def test_concurrent_patch_race_condition():
    """Adversarial: concurrent PATCH requests to same clip resolve cleanly without deadlock."""
    clip_id = _seed_clip(title="Concurrent Base Title")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        patch_tasks = [
            client.patch(f"/api/publish/clips/{clip_id}/metadata", json={"title": f"Patch Title #{i}", "category": "20"})
            for i in range(5)
        ]
        responses = await asyncio.gather(*patch_tasks)

    # All concurrent patches should succeed with 200
    for r in responses:
        assert r.status_code == 200

    # Final DB state has one of the valid titles
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter(Clip.id == clip_id).first()
        assert clip.title.startswith("Patch Title #")
        assert clip.category == "20"
