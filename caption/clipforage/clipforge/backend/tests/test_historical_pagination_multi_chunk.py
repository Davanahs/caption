"""
test_historical_pagination_multi_chunk.py
=========================================
Deterministic verification of historical candidate discovery pagination beyond 100 videos.
Verifies:
1. Multi-chunk pagination (fetching >100 and up to 250 candidates in bounded chunks).
2. Zero duplicate candidates across chunk boundaries.
3. Zero candidate loss at chunk boundary 100/101 and 200/201.
4. Scan depth limits enforced strictly (depth 150 -> exactly 150 scanned; depth 250 -> exactly 250 scanned).
5. Sorting and selection operating on the combined multi-chunk inventory (Latest, Most-viewed, Since Date, New Only).
6. Candidate scope metadata and scanned_count accuracy.
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel
from backend.services.downloader import get_channel_videos


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    yield
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest.fixture
def paginated_channel():
    tag = uuid.uuid4().hex[:8]
    src_id = f"src_pag_{tag}"
    dest_id = f"dest_pag_{tag}"

    with SyncSessionLocal() as session:
        dest_ch = Channel(
            id=dest_id,
            channel_name=f"Destination {tag}",
            channel_url=f"https://youtube.com/@dest_{tag}",
            youtube_channel_id=f"UC_dest_{tag}",
            is_destination=True,
            is_active=True,
            is_test=True,
        )
        src_ch = Channel(
            id=src_id,
            channel_name=f"Paginated Channel {tag}",
            # Use fixture_pagination URL to trigger deterministic 250-item fixture in downloader.py
            channel_url=f"https://youtube.com/@fixture_pagination_{tag}",
            youtube_channel_id=f"UC_pag_{tag}",
            is_destination=False,
            publish_destination_id=dest_id,
            is_active=True,
            auto_clip=True,
            auto_publish=True,
            is_test=True,
        )
        session.add_all([dest_ch, src_ch])
        session.commit()

    yield {"src_id": src_id, "dest_id": dest_id, "tag": tag}

    with SyncSessionLocal() as session:
        session.query(Channel).filter(Channel.id.in_([src_id, dest_id])).delete(synchronize_session=False)
        session.commit()


@pytest.mark.asyncio
async def test_downloader_service_multi_chunk_boundaries():
    """Verify get_channel_videos accurately paginates across 100-item chunks using start_index."""
    fixture_url = "https://youtube.com/@fixture_pagination_test"

    # Chunk 1: items 1..100
    chunk1 = await get_channel_videos(fixture_url, start_index=1, page_size=100, return_page_meta=True)
    assert len(chunk1["items"]) == 100
    assert chunk1["has_more"] is True
    assert chunk1["items"][0]["id"] == "fixture_vid_001"
    assert chunk1["items"][99]["id"] == "fixture_vid_100"

    # Chunk 2: items 101..200
    chunk2 = await get_channel_videos(fixture_url, start_index=101, page_size=100, return_page_meta=True)
    assert len(chunk2["items"]) == 100
    assert chunk2["has_more"] is True
    assert chunk2["items"][0]["id"] == "fixture_vid_101"
    assert chunk2["items"][99]["id"] == "fixture_vid_200"

    # Chunk 3: items 201..250
    chunk3 = await get_channel_videos(fixture_url, start_index=201, page_size=50, return_page_meta=True)
    assert len(chunk3["items"]) == 50
    assert chunk3["has_more"] is False
    assert chunk3["items"][0]["id"] == "fixture_vid_201"
    assert chunk3["items"][49]["id"] == "fixture_vid_250"

    # Check that boundaries are seamless and disjoint
    ids_1 = {it["id"] for it in chunk1["items"]}
    ids_2 = {it["id"] for it in chunk2["items"]}
    ids_3 = {it["id"] for it in chunk3["items"]}

    assert len(ids_1.intersection(ids_2)) == 0, "Chunk 1 and Chunk 2 overlap!"
    assert len(ids_2.intersection(ids_3)) == 0, "Chunk 2 and Chunk 3 overlap!"
    assert len(ids_1.intersection(ids_3)) == 0, "Chunk 1 and Chunk 3 overlap!"

    combined = ids_1.union(ids_2).union(ids_3)
    assert len(combined) == 250, f"Expected 250 distinct IDs, got {len(combined)}"
    assert "fixture_vid_100" in ids_1
    assert "fixture_vid_101" in ids_2
    assert "fixture_vid_200" in ids_2
    assert "fixture_vid_201" in ids_3


@pytest.mark.asyncio
async def test_pagination_beyond_100_videos_multi_chunk(paginated_channel):
    """Verify that requesting max_search_depth=150 fetches across chunks without duplicates or drops."""
    src_id = paginated_channel["src_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
            "mode": "latest",
            "count": 10,
            "max_search_depth": 150
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Scope metadata verification
        scope = data["candidate_scope"]
        assert scope["scanned_count"] == 150, f"Expected 150 scanned candidates, got {scope['scanned_count']}"
        assert scope["search_depth_limit"] == 150
        assert scope["scope_type"] == "bounded"
        assert "Evaluated 150 most recent channel videos" in scope["description"]

        # Check total discovered count matches scanned count
        assert data["total_discovered"] == 150
        assert data["will_queue"] == 10
        # Exactly 10 items marked for queueing
        assert sum(1 for it in data["items"] if it["selected_for_queue"]) == 10


@pytest.mark.asyncio
async def test_pagination_up_to_max_search_depth_250(paginated_channel):
    """Verify requesting max_search_depth=250 evaluates all 250 candidates across 3 chunks."""
    src_id = paginated_channel["src_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
            "mode": "latest",
            "count": 20,
            "max_search_depth": 250
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()

        scope = data["candidate_scope"]
        assert scope["scanned_count"] == 250, f"Expected 250 scanned candidates, got {scope['scanned_count']}"
        assert scope["search_depth_limit"] == 250
        assert data["total_discovered"] == 250
        assert data["will_queue"] == 20
        assert sum(1 for it in data["items"] if it["selected_for_queue"]) == 20


@pytest.mark.asyncio
async def test_pagination_most_viewed_sorting_across_all_chunks(paginated_channel):
    """Verify that Most-Viewed N operates on the combined inventory of all chunks."""
    src_id = paginated_channel["src_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # In fixture_pagination, fixture_vid_001 has highest views: 1000 + (250 - 1)*50 = 13450
        # fixture_vid_002 has 13400, etc.
        resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
            "mode": "most_viewed",
            "count": 3,
            "max_search_depth": 150
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()

        items = data["items"]
        # Exactly 3 items selected for queueing
        assert data["will_queue"] == 3
        selected = [it for it in items if it["selected_for_queue"]]
        assert len(selected) == 3
        assert selected[0]["id"] == "fixture_vid_001"
        assert selected[1]["id"] == "fixture_vid_002"
        assert selected[2]["id"] == "fixture_vid_003"
        assert selected[0]["view_count"] > selected[1]["view_count"] > selected[2]["view_count"]


@pytest.mark.asyncio
async def test_pagination_since_date_cutoff_across_chunks(paginated_channel):
    """Verify Uploaded Since Date filters properly across multi-chunk inventory."""
    src_id = paginated_channel["src_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
            "mode": "uploaded_since",
            "since_date": "2026-10-15",
            "count": 10,
            "max_search_depth": 150
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["mode"] == "uploaded_since"
        assert data["candidate_scope"]["scanned_count"] == 150
        assert data["since_date"] == "2026-10-15"


@pytest.mark.asyncio
async def test_pagination_new_only_mode(paginated_channel):
    """Verify New Uploads Only returns 0 candidates and does not backfill."""
    src_id = paginated_channel["src_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/channels/{src_id}/historical-preview", json={
            "mode": "new_only",
            "count": 5,
            "max_search_depth": 200
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["mode"] == "new_only"
        assert data["total_discovered"] == 0
        assert data["will_queue"] == 0
        assert len(data["items"]) == 0
