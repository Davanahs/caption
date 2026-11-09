"""
test_automation_repairs.py
===========================
Verification tests for forensic automation repairs:
1. Defect 2 Fix: Single video process creates Job, sets source_title, returns real job_id (not None).
2. Defect 2 Stranded Decision Fix: Stranded decisions with status in (resolved_custom, resolved_defaults)
   and job_id=None are recovered by resolve_video_decision_sync rather than stranded.
3. Defect 1 Fix: Multi-video batch processing endpoint (/api/channels/{channel_id}/process-videos-batch)
   validates items, dispatches sequential Celery tasks, creates durable Job records with titles,
   and prevents duplicate jobs when already processing.
"""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.models.database import SyncSessionLocal, engine
from backend.models.models import Channel, VideoDecision, VideoDecisionStatus, Job
from backend.tasks.orchestration import resolve_video_decision_sync


@pytest.fixture(autouse=True)
async def cleanup_repair_test_data():
    yield
    await engine.dispose()
    with SyncSessionLocal() as session:
        test_ch_ids = [
            ch[0] for ch in session.query(Channel.id).filter(
                Channel.id.like("test_repair_%")
            ).all()
        ]
        if test_ch_ids:
            session.query(Job).filter(Job.channel_id.in_(test_ch_ids)).delete(synchronize_session=False)
            session.query(VideoDecision).filter(VideoDecision.channel_id.in_(test_ch_ids)).delete(synchronize_session=False)
            session.query(Channel).filter(Channel.id.in_(test_ch_ids)).delete(synchronize_session=False)
            session.commit()


@pytest.mark.asyncio
async def test_process_channel_video_creates_job_and_returns_job_id():
    """Verify Defect 2 fix: process_channel_video creates durable Job and returns valid job_id."""
    ch_id = f"test_repair_ch_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_url="https://www.youtube.com/@RepairChannel",
            channel_name="Repair Channel",
            is_active=True,
            auto_clip=True,
            is_test=True,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_task:
            mock_task.return_value = MagicMock(id=f"celery_{uuid.uuid4().hex[:8]}")
            res = await client.post(
                f"/api/channels/{ch_id}/process-video",
                json={
                    "video_id": "yt_repair_vid_01",
                    "video_title": "Forensic Repair Test Video",
                    "video_url": "https://www.youtube.com/watch?v=yt_repair_vid_01",
                }
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["status"] == "queued"
            assert data["job_id"] is not None
            assert len(data["job_id"]) > 0

            # Verify Job was persisted in database with correct source_title
            with SyncSessionLocal() as session:
                job = session.query(Job).filter(Job.id == data["job_id"]).first()
                assert job is not None
                assert job.source_title == "Forensic Repair Test Video"
                assert str(job.status) in ("pending", "queued")
                assert job.channel_id == ch_id


def test_stranded_decision_without_job_id_is_recovered():
    """Verify Defect 2 fix: Stranded decision with job_id=None is recovered by resolve_video_decision_sync."""
    from datetime import datetime, timezone
    ch_id = f"test_repair_ch_{uuid.uuid4().hex[:8]}"
    dec_id = f"test_repair_dec_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_url="https://www.youtube.com/@StrandedChannel",
            channel_name="Stranded Channel",
            is_active=True,
            is_test=True,
        )
        session.add(ch)

        # Create stranded decision (status resolved_custom, but job_id is None)
        dec = VideoDecision(
            id=dec_id,
            channel_id=ch_id,
            youtube_id="yt_stranded_01",
            video_title="Stranded Recovery Video",
            youtube_url="https://www.youtube.com/watch?v=yt_stranded_01",
            status=VideoDecisionStatus.RESOLVED_CUSTOM.value,
            decision_deadline=datetime.now(timezone.utc),
            channel_profile_snapshot={"duration_mode": "adaptive"},
            job_id=None,  # Stranded!
        )
        session.add(dec)
        session.commit()

    with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_task:
        mock_task.return_value = MagicMock(id=f"celery_{uuid.uuid4().hex[:8]}")
        res = resolve_video_decision_sync(dec_id, action="custom", custom_overrides={"clip_mode": "ai_highlights"})
        assert res.get("already_resolved") is not True
        assert res["job_id"] is not None

        # Verify DB updated
        with SyncSessionLocal() as session:
            dec = session.query(VideoDecision).filter(VideoDecision.id == dec_id).first()
            assert dec.job_id == res["job_id"]


@pytest.mark.asyncio
async def test_process_videos_batch_endpoint_multi_selection():
    """Verify Defect 1 fix: Batch process multiple videos creates distinct jobs and prevents duplicates."""
    ch_id = f"test_repair_ch_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_url="https://www.youtube.com/@BatchChannel",
            channel_name="Batch Channel",
            is_active=True,
            is_test=True,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_task:
            mock_task.return_value = MagicMock(id=f"celery_{uuid.uuid4().hex[:8]}")

            # Batch 1: Two videos
            batch_payload = {
                "videos": [
                    {
                        "video_id": "yt_batch_01",
                        "video_title": "Batch Video One",
                        "video_url": "https://www.youtube.com/watch?v=yt_batch_01",
                    },
                    {
                        "video_id": "yt_batch_02",
                        "video_title": "Batch Video Two",
                        "video_url": "https://www.youtube.com/watch?v=yt_batch_02",
                    }
                ]
            }

            res = await client.post(
                f"/api/channels/{ch_id}/process-videos-batch",
                json=batch_payload
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["queued_count"] == 2
            assert data["already_processing_count"] == 0
            assert data["rejected_count"] == 0
            assert len(data["items"]) == 2
            assert data["items"][0]["status"] == "queued"
            assert data["items"][1]["status"] == "queued"
            assert data["items"][0]["job_id"] is not None
            assert data["items"][1]["job_id"] is not None
            assert data["items"][0]["job_id"] != data["items"][1]["job_id"]

            # Verify in DB
            with SyncSessionLocal() as session:
                jobs = session.query(Job).filter(Job.channel_id == ch_id).all()
                assert len(jobs) == 2
                titles = {j.source_title for j in jobs}
                assert "Batch Video One" in titles
                assert "Batch Video Two" in titles

            # Batch 2: Resubmit same batch -> Idempotency check: should report already_processing
            res2 = await client.post(
                f"/api/channels/{ch_id}/process-videos-batch",
                json=batch_payload
            )
            assert res2.status_code == 200, res2.text
            data2 = res2.json()
            assert data2["queued_count"] == 0
            assert data2["already_processing_count"] == 2
            assert data2["rejected_count"] == 0


@pytest.mark.asyncio
async def test_process_videos_batch_empty_selection_rejected():
    """Verify that an empty videos list returns 422 Unprocessable Entity."""
    ch_id = f"test_repair_ch_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_url="https://www.youtube.com/@EmptyBatchChannel",
            channel_name="Empty Batch Channel",
            is_active=True,
            is_test=True,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/channels/{ch_id}/process-videos-batch",
            json={"videos": []}
        )
        assert res.status_code == 422, f"Expected 422 for empty list, got {res.status_code}"


@pytest.mark.asyncio
async def test_process_videos_batch_intra_payload_duplicate_idempotency():
    """Verify that submitting the same video twice in one payload creates only one job and reports already_processing for the duplicate."""
    ch_id = f"test_repair_ch_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_url="https://www.youtube.com/@DuplicatePayloadChannel",
            channel_name="Duplicate Payload Channel",
            is_active=True,
            is_test=True,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_task:
            mock_task.return_value = MagicMock(id=f"celery_{uuid.uuid4().hex[:8]}")

            duplicate_payload = {
                "videos": [
                    {
                        "video_id": "yt_intra_dup_01",
                        "video_title": "Intra Duplicate Video",
                        "video_url": "https://www.youtube.com/watch?v=yt_intra_dup_01",
                    },
                    {
                        "video_id": "yt_intra_dup_01",
                        "video_title": "Intra Duplicate Video Copy",
                        "video_url": "https://www.youtube.com/watch?v=yt_intra_dup_01",
                    }
                ]
            }

            res = await client.post(
                f"/api/channels/{ch_id}/process-videos-batch",
                json=duplicate_payload
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["queued_count"] == 1
            assert data["already_processing_count"] == 1
            assert data["rejected_count"] == 0
            assert len(data["items"]) == 2
            assert data["items"][0]["status"] == "queued"
            assert data["items"][1]["status"] == "already_processing"

            # Verify in DB: exactly 1 Job created
            with SyncSessionLocal() as session:
                jobs = session.query(Job).filter(Job.channel_id == ch_id).all()
                assert len(jobs) == 1


@pytest.mark.asyncio
async def test_process_videos_batch_partial_rejection_missing_fields():
    """Verify that invalid items (missing video_url) are reported as rejected without failing the valid items."""
    ch_id = f"test_repair_ch_{uuid.uuid4().hex[:8]}"
    with SyncSessionLocal() as session:
        ch = Channel(
            id=ch_id,
            youtube_channel_id=f"UC_{ch_id}",
            channel_url="https://www.youtube.com/@PartialRejectionChannel",
            channel_name="Partial Rejection Channel",
            is_active=True,
            is_test=True,
        )
        session.add(ch)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_task:
            mock_task.return_value = MagicMock(id=f"celery_{uuid.uuid4().hex[:8]}")

            mixed_payload = {
                "videos": [
                    {
                        "video_id": "yt_partial_valid_01",
                        "video_title": "Valid Video 01",
                        "video_url": "https://www.youtube.com/watch?v=yt_partial_valid_01",
                    },
                    {
                        "video_id": "yt_partial_invalid_02",
                        "video_title": "Invalid Video 02",
                        "video_url": "",  # Empty URL -> should be rejected
                    }
                ]
            }

            res = await client.post(
                f"/api/channels/{ch_id}/process-videos-batch",
                json=mixed_payload
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["queued_count"] == 1
            assert data["rejected_count"] == 1
            assert data["already_processing_count"] == 0
            assert len(data["items"]) == 2
            assert data["items"][0]["status"] == "queued"
            assert data["items"][1]["status"] == "rejected"
            assert "Missing video_id or video_url" in data["items"][1]["error"]

            # Verify in DB: only the valid video has a Job
            with SyncSessionLocal() as session:
                jobs = session.query(Job).filter(Job.channel_id == ch_id).all()
                assert len(jobs) == 1
                assert jobs[0].source_title == "Valid Video 01"


@pytest.mark.asyncio
async def test_process_videos_batch_channel_identity_isolation():
    """Verify that batch video processing strictly enforces channel ownership and isolation."""
    ch_a = f"test_repair_ch_a_{uuid.uuid4().hex[:8]}"
    ch_b = f"test_repair_ch_b_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        session.add(Channel(
            id=ch_a,
            youtube_channel_id=f"UC_{ch_a}",
            channel_url="https://www.youtube.com/@ChannelA",
            channel_name="Channel A",
            is_active=True,
            is_test=True,
        ))
        session.add(Channel(
            id=ch_b,
            youtube_channel_id=f"UC_{ch_b}",
            channel_url="https://www.youtube.com/@ChannelB",
            channel_name="Channel B",
            is_active=True,
            is_test=True,
        ))
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_task:
            mock_task.return_value = MagicMock(id=f"celery_{uuid.uuid4().hex[:8]}")

            # Send batch to Channel A
            res_a = await client.post(
                f"/api/channels/{ch_a}/process-videos-batch",
                json={
                    "videos": [
                        {
                            "video_id": "yt_iso_vid_01",
                            "video_title": "Channel A Video",
                            "video_url": "https://www.youtube.com/watch?v=yt_iso_vid_01",
                        }
                    ]
                }
            )
            assert res_a.status_code == 200
            data_a = res_a.json()
            assert data_a["queued_count"] == 1

            # Send batch to Channel B
            res_b = await client.post(
                f"/api/channels/{ch_b}/process-videos-batch",
                json={
                    "videos": [
                        {
                            "video_id": "yt_iso_vid_02",
                            "video_title": "Channel B Video",
                            "video_url": "https://www.youtube.com/watch?v=yt_iso_vid_02",
                        }
                    ]
                }
            )
            assert res_b.status_code == 200
            data_b = res_b.json()
            assert data_b["queued_count"] == 1

            # Verify in DB: jobs are isolated by channel_id
            with SyncSessionLocal() as session:
                jobs_a = session.query(Job).filter(Job.channel_id == ch_a).all()
                jobs_b = session.query(Job).filter(Job.channel_id == ch_b).all()
                assert len(jobs_a) == 1
                assert jobs_a[0].source_title == "Channel A Video"
                assert len(jobs_b) == 1
                assert jobs_b[0].source_title == "Channel B Video"

