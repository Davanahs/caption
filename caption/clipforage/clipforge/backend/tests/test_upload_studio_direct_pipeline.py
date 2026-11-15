"""
ClipForge - Upload Studio Dedicated Direct Processing & Publishing Test Suite
Verifies:
1. Video media validation with FFprobe
2. Audio transcription with Whisper
3. AI metadata generation (Title, Description, SEO tags, Pinned comment)
4. Destination outro concatenation (-sn invariant)
5. YouTube upload with privacy='private'
6. Multi-destination PublishTarget tracking
7. Sequential batch dispatch isolation
"""
import os
import sys
import uuid
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.models.models import (
    UploadBatch,
    Video,
    Job,
    Clip,
    Channel,
    DestinationOutro,
    PublishTarget,
    PublishStatus,
    ClipStatus,
    JobStatus,
    UploadBatchStatus,
    VideoUploadStatus,
    VideoProcessingStatus,
)
from backend.tasks.studio_tasks import (
    process_studio_direct_video_task,
    process_studio_batch_sequential_task,
)
from backend.services.queue_manager import dispatch_celery_job


@pytest.fixture
def disposable_db(tmp_path):
    """Provides an isolated sqlite in-memory or file database for fast deterministic unit tests."""
    db_file = tmp_path / f"test_studio_direct_{uuid.uuid4().hex[:8]}.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    from backend.models.database import Base
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with patch("backend.tasks.studio_tasks.SyncSessionLocal", TestingSession), \
         patch("backend.models.database.SyncSessionLocal", TestingSession):
        yield {"session_factory": TestingSession, "engine": engine}

    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_video_file(tmp_path):
    """Creates a small valid mp4 test file."""
    f = tmp_path / "test_short.mp4"
    # Write a tiny valid MP4 header/dummy bytes or copy synthetic fixture if exists
    synth = Path(settings.UPLOAD_DIR) / "synthetic_test_fixture.mp4"
    if synth.exists() and synth.stat().st_size > 0:
        f.write_bytes(synth.read_bytes())
    else:
        # Minimal dummy container bytes
        f.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08mdat")
    return f


def test_studio_direct_processing_happy_path_with_outro_and_private_upload(disposable_db, sample_video_file):
    """
    Verifies full direct pipeline:
    Probe -> Whisper -> AI Metadata -> Outro Concatenation -> Private YouTube Upload -> Advance
    """
    Session = disposable_db["session_factory"]
    now = datetime.now(timezone.utc)
    batch_id = f"b_{uuid.uuid4().hex[:12]}"
    video_id = f"v_{uuid.uuid4().hex[:12]}"
    job_id = f"job_studio_{uuid.uuid4().hex[:12]}"
    dest_id = f"ch_dest_{uuid.uuid4().hex[:8]}"
    outro_id = f"outro_{uuid.uuid4().hex[:8]}"

    with Session() as session:
        # Create destination channel with an active outro
        ch = Channel(
            id=dest_id,
            youtube_channel_id="UC_TEST_DESTINATION_123",
            channel_name="Test Rhymee",
            channel_url="https://youtube.com/channel/UC_TEST_DESTINATION_123",
            is_active=True,
            is_destination=True,
            active_outro_id=outro_id,
        )
        session.add(ch)

        outro = DestinationOutro(
            id=outro_id,
            channel_id=dest_id,
            file_path="uploads/outros/test/outro.png",
            original_filename="outro.png",
            file_size_bytes=1024,
            outro_type="image",
            duration_seconds=1.0,
            is_active=True,
        )
        session.add(outro)

        batch = UploadBatch(
            id=batch_id,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            total_files=1,
            status=UploadBatchStatus.PROCESSING.value,
            config={"destination_ids": [dest_id]},
        )
        session.add(batch)

        video = Video(
            id=video_id,
            upload_batch_id=batch_id,
            title="Cool Staged Short.mp4",
            source_filename="Cool Staged Short.mp4",
            local_path=str(sample_video_file),
            upload_status=VideoUploadStatus.UPLOADED.value,
            processing_status=VideoProcessingStatus.PROCESSING.value,
            queue_position=0,
        )
        session.add(video)

        job = Job(
            id=job_id,
            video_id=video_id,
            source_url=str(sample_video_file),
            source_title="Cool Staged Short",
            status=JobStatus.PENDING.value,
            progress=5,
        )
        session.add(job)
        session.commit()

    # Mocks
    mock_probe = {
        "streams": [
            {"codec_type": "video", "width": 1080, "height": 1920, "duration": "12.5"},
            {"codec_type": "audio", "channels": 2, "sample_rate": "44100"}
        ],
        "format": {"duration": "12.5"}
    }
    mock_transcription = {"text": "Learn how to code AI agents in 10 seconds!"}
    mock_meta = {
        "title": "AI Agents in 10 Seconds! 🚀",
        "description": "Here is how you build agentic systems.\n\n#Shorts #viral #trending #ai #coding",
        "tags": ["AI", "agents", "coding", "Shorts", "viral"],
        "pinned_comment": "Subscribe for more AI tutorials! 👇",
    }
    mock_render_res = {
        "variant_file_path": str(sample_video_file),
        "duration": 13.5,
        "width": 1080,
        "height": 1920,
        "file_size": 2048,
    }
    mock_upload_res = {
        "id": "yt_short_xyz987",
        "url": "https://www.youtube.com/shorts/yt_short_xyz987",
        "title": "AI Agents in 10 Seconds! 🚀 #Shorts",
        "privacy": "private",
        "status": "uploaded",
    }

    with patch("backend.services.outro_service.probe_media_with_ffprobe", return_value=mock_probe), \
         patch("backend.services.transcriber.transcribe_video", return_value=mock_transcription) as mock_trans, \
         patch("backend.services.metadata_generator.generate_metadata", return_value=mock_meta) as mock_gen, \
         patch("backend.services.outro_service.render_clip_with_outro", return_value=mock_render_res) as mock_render, \
         patch("backend.services.publisher.upload_short", return_value=mock_upload_res) as mock_upload, \
         patch("backend.tasks.studio_tasks.on_studio_video_finished_task.delay") as mock_finished:

        res = process_studio_direct_video_task(
            job_id=job_id,
            video_id=video_id,
            local_path=str(sample_video_file),
            studio_batch_id=batch_id,
            destination_ids=[dest_id],
        )

        assert res["status"] == "success"

        # Assertions
        mock_trans.assert_called_once()
        mock_render.assert_called_once()
        mock_upload.assert_called_once()

        # Check upload parameters: MUST be private and target correct channel
        upload_kwargs = mock_upload.call_args[1]
        assert upload_kwargs["privacy"] == "private"
        assert upload_kwargs["channel_id"] == "UC_TEST_DESTINATION_123"
        assert upload_kwargs["title"] == "AI Agents in 10 Seconds! 🚀"

        # Check DB updates
        with Session() as session:
            v = session.query(Video).filter_by(id=video_id).first()
            assert v.processing_status == VideoProcessingStatus.COMPLETED.value
            assert v.processing_progress == 100
            assert "Published to YouTube (Private)" in v.processing_step
            assert v.title == "AI Agents in 10 Seconds! 🚀"

            j = session.query(Job).filter_by(id=job_id).first()
            assert j.status == JobStatus.COMPLETED.value
            assert j.progress == 100

            clip = session.query(Clip).filter_by(video_id=video_id).first()
            assert clip is not None
            assert clip.title == "AI Agents in 10 Seconds! 🚀"
            assert clip.youtube_short_id == "yt_short_xyz987"
            assert clip.publish_status == PublishStatus.PUBLISHED.value
            assert clip.privacy == "private"

            pt = session.query(PublishTarget).filter_by(clip_id=clip.id, destination_id=dest_id).first()
            assert pt is not None
            assert pt.status == "completed"
            assert pt.publish_stage == "published"
            assert pt.youtube_video_id == "yt_short_xyz987"
            assert pt.privacy == "private"
            assert pt.outro_applied_id == outro_id

        # Verify sequential callback was triggered
        mock_finished.assert_called_once_with(
            batch_id=batch_id,
            video_id=video_id,
            job_id=job_id,
        )


def test_studio_direct_processing_no_destination_saves_draft(disposable_db, sample_video_file):
    """When no destinations are configured, video is analyzed and saved as draft without upload."""
    Session = disposable_db["session_factory"]
    batch_id = f"b_{uuid.uuid4().hex[:12]}"
    video_id = f"v_{uuid.uuid4().hex[:12]}"
    job_id = f"job_studio_{uuid.uuid4().hex[:12]}"

    with Session() as session:
        batch = UploadBatch(
            id=batch_id,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            total_files=1,
            status=UploadBatchStatus.PROCESSING.value,
            config={},  # No destinations
        )
        session.add(batch)

        video = Video(
            id=video_id,
            upload_batch_id=batch_id,
            title="Draft Short.mp4",
            local_path=str(sample_video_file),
            upload_status=VideoUploadStatus.UPLOADED.value,
            processing_status=VideoProcessingStatus.PROCESSING.value,
            queue_position=0,
        )
        session.add(video)

        job = Job(
            id=job_id,
            video_id=video_id,
            source_url=str(sample_video_file),
            source_title="Draft Short",
            status=JobStatus.PENDING.value,
            progress=5,
        )
        session.add(job)
        session.commit()

    mock_probe = {
        "streams": [{"codec_type": "video", "width": 1080, "height": 1920, "duration": "10.0"}],
        "format": {"duration": "10.0"}
    }
    mock_meta = {
        "title": "Draft Short Video",
        "description": "Short description",
        "tags": ["viral"],
        "pinned_comment": "Subscribe",
    }

    with patch("backend.services.outro_service.probe_media_with_ffprobe", return_value=mock_probe), \
         patch("backend.services.metadata_generator.generate_metadata", return_value=mock_meta), \
         patch("backend.services.publisher.upload_short") as mock_upload, \
         patch("backend.tasks.studio_tasks.on_studio_video_finished_task.delay") as mock_finished:

        res = process_studio_direct_video_task(
            job_id=job_id,
            video_id=video_id,
            local_path=str(sample_video_file),
            studio_batch_id=batch_id,
            destination_ids=None,
        )

        assert res["status"] == "success"
        mock_upload.assert_not_called()

        with Session() as session:
            v = session.query(Video).filter_by(id=video_id).first()
            assert v.processing_status == VideoProcessingStatus.COMPLETED.value
            assert "Draft" in v.processing_step

            clip = session.query(Clip).filter_by(video_id=video_id).first()
            assert clip is not None
            assert clip.publish_status == PublishStatus.DRAFT.value

        mock_finished.assert_called_once()


def test_studio_direct_processing_silent_video(disposable_db, sample_video_file):
    """A silent video (no audio stream) is handled gracefully without transcription failure."""
    Session = disposable_db["session_factory"]
    batch_id = f"b_{uuid.uuid4().hex[:12]}"
    video_id = f"v_{uuid.uuid4().hex[:12]}"
    job_id = f"job_studio_{uuid.uuid4().hex[:12]}"

    with Session() as session:
        batch = UploadBatch(
            id=batch_id,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            total_files=1,
            status=UploadBatchStatus.PROCESSING.value,
            config={},
        )
        session.add(batch)

        video = Video(
            id=video_id,
            upload_batch_id=batch_id,
            title="Silent Loop.mp4",
            local_path=str(sample_video_file),
            upload_status=VideoUploadStatus.UPLOADED.value,
            processing_status=VideoProcessingStatus.PROCESSING.value,
            queue_position=0,
        )
        session.add(video)

        job = Job(
            id=job_id,
            video_id=video_id,
            source_url=str(sample_video_file),
            source_title="Silent Loop",
            status=JobStatus.PENDING.value,
            progress=5,
        )
        session.add(job)
        session.commit()

    mock_probe = {
        "streams": [{"codec_type": "video", "width": 720, "height": 1280, "duration": "5.0"}],
        "format": {"duration": "5.0"}
    }
    mock_meta = {
        "title": "Satisfying Visual Loop ✨",
        "description": "Watch this satisfying loop.\n\n#Shorts #satisfying",
        "tags": ["satisfying", "loop"],
        "pinned_comment": "",
    }

    with patch("backend.services.outro_service.probe_media_with_ffprobe", return_value=mock_probe), \
         patch("backend.services.transcriber.transcribe_video") as mock_trans, \
         patch("backend.services.metadata_generator.generate_metadata", return_value=mock_meta), \
         patch("backend.tasks.studio_tasks.on_studio_video_finished_task.delay"):

        res = process_studio_direct_video_task(
            job_id=job_id,
            video_id=video_id,
            local_path=str(sample_video_file),
            studio_batch_id=batch_id,
            destination_ids=None,
        )

        assert res["status"] == "success"
        # Transcribe should be skipped because there is no audio stream
        mock_trans.assert_not_called()


def test_studio_isolation_dispatches_correct_task():
    """Verify that dispatch_celery_job routes studio_batch_id to direct task and normal jobs to chord orchestrator."""
    with patch("backend.tasks.studio_tasks.process_studio_direct_video_task.apply_async") as mock_studio_task, \
         patch("backend.tasks.orchestration.start_video_processing_task.apply_async") as mock_orchestrator_task:

        mock_studio_task.return_value = MagicMock(id="task_studio_123")
        mock_orchestrator_task.return_value = MagicMock(id="task_orch_456")

        # Studio job with studio_batch_id
        res_studio = dispatch_celery_job(
            job_id="job_studio_1",
            kwargs={"studio_batch_id": "b_123", "video_id": "v_1"}
        )
        assert res_studio == "task_studio_123"
        mock_studio_task.assert_called_once()
        mock_orchestrator_task.assert_not_called()

        # Regular automation/gaming/podcast job without studio_batch_id
        res_regular = dispatch_celery_job(
            job_id="job_reg_2",
            kwargs={"youtube_url": "https://youtube.com/watch?v=abc"}
        )
        assert res_regular == "task_orch_456"
        mock_orchestrator_task.assert_called_once()


def test_studio_direct_processing_reframes_landscape_to_vertical_9_16_short(disposable_db, sample_video_file):
    """
    Verifies that when a landscape / horizontal video (e.g. 1280x720) is uploaded in Upload Studio,
    the pipeline automatically reframes it to 1080x1920 vertical format for YouTube Shorts compatibility.
    """
    Session = disposable_db["session_factory"]
    batch_id = f"b_{uuid.uuid4().hex[:12]}"
    video_id = f"v_{uuid.uuid4().hex[:12]}"
    job_id = f"job_studio_{uuid.uuid4().hex[:12]}"
    dest_id = f"ch_dest_{uuid.uuid4().hex[:8]}"

    with Session() as session:
        ch = Channel(
            id=dest_id,
            youtube_channel_id="UC_TEST_DESTINATION_SHORTS",
            channel_name="Test Shorts Channel",
            channel_url="https://youtube.com/channel/UC_TEST_DESTINATION_SHORTS",
            is_active=True,
            is_destination=True,
        )
        session.add(ch)

        batch = UploadBatch(
            id=batch_id,
            idempotency_key=f"idem_{uuid.uuid4().hex[:8]}",
            total_files=1,
            status=UploadBatchStatus.PROCESSING.value,
            config={"destination_ids": [dest_id]},
        )
        session.add(batch)

        video = Video(
            id=video_id,
            upload_batch_id=batch_id,
            title="Landscape Game Clip.mp4",
            source_filename="Landscape Game Clip.mp4",
            local_path=str(sample_video_file),
            upload_status=VideoUploadStatus.UPLOADED.value,
            processing_status=VideoProcessingStatus.PROCESSING.value,
            queue_position=0,
        )
        session.add(video)

        job = Job(
            id=job_id,
            video_id=video_id,
            source_url=str(sample_video_file),
            source_title="Landscape Game Clip",
            status=JobStatus.PENDING.value,
            progress=5,
        )
        session.add(job)
        session.commit()

    # Landscape 16:9 probe: 1280x720
    mock_probe = {
        "streams": [
            {"codec_type": "video", "width": 1280, "height": 720, "duration": "10.0"},
            {"codec_type": "audio", "channels": 2, "sample_rate": "44100"}
        ],
        "format": {"duration": "10.0"}
    }
    mock_transcription = {"text": "Exciting goal scored in the last minute!"}
    mock_meta = {
        "title": "Unbelievable Last Minute Goal! ⚽",
        "description": "Watch this amazing goal.\n\n#Shorts #viral #trending #football",
        "tags": ["football", "goal", "Shorts"],
        "pinned_comment": "What a goal! 👇",
    }
    mock_upload_res = {
        "id": "yt_short_landscape_reframed",
        "url": "https://www.youtube.com/shorts/yt_short_landscape_reframed",
        "title": "Unbelievable Last Minute Goal! ⚽ #Shorts",
        "privacy": "private",
        "status": "uploaded",
    }

    mock_render_proc = MagicMock(returncode=0, stderr=b"")

    with patch("backend.services.outro_service.probe_media_with_ffprobe", return_value=mock_probe), \
         patch("backend.services.transcriber.transcribe_video", return_value=mock_transcription), \
         patch("backend.services.metadata_generator.generate_metadata", return_value=mock_meta), \
         patch("subprocess.run", return_value=mock_render_proc) as mock_subprocess, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat", return_value=MagicMock(st_size=4096)), \
         patch("backend.services.publisher.upload_short", return_value=mock_upload_res) as mock_upload, \
         patch("backend.tasks.studio_tasks.on_studio_video_finished_task.delay"):

        res = process_studio_direct_video_task(
            job_id=job_id,
            video_id=video_id,
            local_path=str(sample_video_file),
            studio_batch_id=batch_id,
            destination_ids=[dest_id],
        )

        assert res["status"] == "success"

        # Verify that subprocess was called to render the 1080x1920 vertical short
        mock_subprocess.assert_called()
        cmd_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in cmd_args
        assert "-filter_complex" in cmd_args
        assert "-sn" in cmd_args

        # Verify that the DB record was updated to 1080x1920
        with Session() as session:
            v_db = session.query(Video).filter_by(id=video_id).first()
            assert v_db.resolution == "1080x1920"

