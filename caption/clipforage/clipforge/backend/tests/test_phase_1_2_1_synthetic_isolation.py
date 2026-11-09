"""
test_phase_1_2_1_synthetic_isolation.py
=========================================
Focused Regression Test Suite for Phase 1.2.1:
Defect Remediation: CF-DEF-009 — Unscoped Synthetic Fixture Interception

Tests:
Test A: Explicitly authorized test job (server-verified is_test=True selects fixture & canned transcript)
Test B: Ordinary input containing synthetic-like text (is_test=False follows normal path without interception)
Test C: Missing or unverified test context (fails closed to normal path)
Test D: Normal media path (standard yt-dlp & transcription path preserved)
Test E: Mock publishing independence (PUBLISH_MODE="test" does not trigger media fixture substitution)
"""
import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import Job, Channel, JobStatus, Video
from backend.services.downloader import get_video_info, download_video
from backend.services.transcriber import transcribe_video
from backend.tasks.video_tasks import download_task, transcription_task


@pytest.fixture(autouse=True)
def cleanup_p121_test_records():
    """Teardown fixture ensuring all test records are wiped after every test."""
    yield
    with SyncSessionLocal() as session:
        session.query(Job).filter(Job.id.like("test_p121_%")).delete(synchronize_session=False)
        session.query(Channel).filter(Channel.id.like("ch_p121_%")).delete(synchronize_session=False)
        session.query(Video).filter(Video.id.like("vid_p121_%")).delete(synchronize_session=False)
        session.commit()


# =========================================================================
# TEST A: Explicitly authorized test job
# =========================================================================
def test_test_a_explicitly_authorized_test_job():
    """
    Test A — Explicitly authorized test job:
    A server-verified test job (is_test=True in DB) using the intended synthetic fixture
    selects the fixture metadata, copies the synthetic fixture file, and returns the
    canned test transcript.
    """
    job_id = f"test_p121_auth_{uuid.uuid4().hex[:8]}"
    chan_id = f"ch_p121_auth_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
            channel_name="Authorized Test Channel",
            channel_url="https://youtube.com/channel/test",
            is_test=True
        )
        job = Job(
            id=job_id,
            status=JobStatus.PENDING.value,
            progress=0,
            channel_id=chan_id,
            is_test=True
        )
        session.add(ch)
        session.add(job)
        session.commit()

    # 1. get_video_info with is_test=True and synthetic fixture ID
    info = asyncio.run(get_video_info("https://www.youtube.com/watch?v=synth_vid01", is_test=True))
    assert info["id"] == "synth_vid01"
    assert info["title"] == "Synthetic Video synth_vid01"
    assert info["duration"] == 20.0
    assert info["uploader"] == "Test Channel"

    # 2. download_video with is_test=True copies synthetic fixture
    fixture_video_id = "synth_vid01"
    dl_path = asyncio.run(download_video("https://www.youtube.com/watch?v=synth_vid01", fixture_video_id, is_test=True))
    assert dl_path.exists()
    assert dl_path.stat().st_size > 0
    # Clean up downloaded temp file
    try:
        dl_path.unlink()
        dl_path.parent.rmdir()
    except Exception:
        pass

    # 3. transcribe_video with is_test=True and synthetic fixture filename
    fixture_path = Path("/app/uploads/synthetic_test_fixture.mp4")
    if not fixture_path.exists():
        fixture_path = Path("uploads/synthetic_test_fixture.mp4")
    
    transcript = transcribe_video(fixture_path, is_test=True)
    assert "synthetic test transcript" in transcript["text"].lower()
    assert len(transcript["segments"]) == 2
    assert transcript["segments"][0]["start"] == 0.0

    # 4. download_task verifies is_test from DB Job/Channel records
    with patch("backend.services.downloader.download_video") as mock_dl, \
         patch("backend.services.downloader.get_video_info") as mock_info:
        
        mock_info.return_value = {"title": "Synthetic Video synth_vid01", "duration": 20.0, "id": "synth_vid01"}
        temp_dir = tempfile.mkdtemp()
        dummy_file = Path(temp_dir) / "video.mp4"
        dummy_file.write_bytes(b"testcontent")
        mock_dl.return_value = dummy_file

        res = download_task(job_id=job_id, youtube_url="https://www.youtube.com/watch?v=synth_vid01")
        
        # Verify is_test=True was passed to get_video_info and download_video
        mock_info.assert_called_once_with("https://www.youtube.com/watch?v=synth_vid01", is_test=True)
        mock_dl.assert_called_once_with("https://www.youtube.com/watch?v=synth_vid01", res["video_id"], is_test=True)
        assert res["is_test"] is True


# =========================================================================
# TEST B: Ordinary input containing synthetic-like text
# =========================================================================
def test_test_b_ordinary_input_containing_synthetic_text():
    """
    Test B — Ordinary input containing synthetic-like text:
    A non-test job (is_test=False) whose URL, identifier, title, or path contains
    'synthetic', 'mock_', or 'test_fixture' does NOT substitute the test fixture
    and does NOT return canned test transcription.
    """
    job_id = f"test_p121_real_{uuid.uuid4().hex[:8]}"
    chan_id = f"ch_p121_real_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
            channel_name="Real Production Channel",
            channel_url="https://youtube.com/channel/real",
            is_test=False
        )
        job = Job(
            id=job_id,
            status=JobStatus.PENDING.value,
            progress=0,
            channel_id=chan_id,
            is_test=False
        )
        session.add(ch)
        session.add(job)
        session.commit()

    synthetic_like_urls = [
        "https://www.youtube.com/watch?v=synthetic_bio",
        "https://www.youtube.com/watch?v=mock_interview_demo",
        "https://www.youtube.com/watch?v=test_fixture_explanation",
    ]

    for url in synthetic_like_urls:
        # 1. get_video_info must NOT intercept and return canned synthetic dict when is_test=False
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b'{"title": "Real Video", "duration": 120.0, "id": "real123"}', b'')
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            info = asyncio.run(get_video_info(url, is_test=False))
            # Must NOT be the canned synthetic fixture info
            assert info.get("uploader") != "Test Channel"
            assert info.get("title") == "Real Video"
            # Must have called yt-dlp subprocess
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "yt-dlp"

        # 2. download_video must NOT copy synthetic fixture when is_test=False
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stderr.readline.side_effect = [b"[download] 100%", b""]
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            with patch("pathlib.Path.exists", return_value=True):
                # When is_test=False, it must attempt yt-dlp, not fixture copy
                out = asyncio.run(download_video(url, "vid_real", is_test=False))
                mock_exec.assert_called_once()
                args = mock_exec.call_args[0]
                assert args[0] == "yt-dlp"

    # 3. transcribe_video on a path containing 'synthetic' or 'mock' when is_test=False
    with patch("backend.services.transcriber.settings.GROQ_API_KEY", ""), \
         patch("backend.services.transcriber.load_model") as mock_load_whisper:
        
        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = {
            "text": "Authentic transcription output from local Whisper engine.",
            "segments": [{"id": 0, "start": 0.0, "end": 5.0, "text": "Authentic transcription", "words": []}]
        }
        mock_load_whisper.return_value = mock_whisper

        # File named synthetic_bio.mp4 but is_test=False
        trans_res = transcribe_video(Path("/tmp/synthetic_bio_lecture.mp4"), is_test=False)
        assert trans_res["text"] == "Authentic transcription output from local Whisper engine."
        assert "synthetic test transcript for testing the full end to end" not in trans_res["text"]


# =========================================================================
# TEST C: Missing or unverified test context
# =========================================================================
def test_test_c_missing_or_unverified_test_context_fails_closed():
    """
    Test C — Missing or unverified test context:
    An input without trusted test-job or channel authorization cannot activate
    fixture interception simply because its identifier resembles a test identifier.
    """
    unverified_url = "https://www.youtube.com/watch?v=synth_vid01"
    
    # 1. Direct call with default is_test=False fails closed to yt-dlp
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b'{"title": "Real Vid", "duration": 50}', b'')
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        info = asyncio.run(get_video_info(unverified_url))
        # Default is_test is False: must call yt-dlp, not fixture
        assert info.get("uploader") != "Test Channel"
        mock_exec.assert_called_once()
        assert mock_exec.call_args[0][0] == "yt-dlp"

    # 2. download_task with non-existent job ID fails closed to is_test=False
    non_existent_job_id = f"test_p121_nonexistent_{uuid.uuid4().hex[:8]}"
    with patch("backend.services.downloader.download_video") as mock_dl, \
         patch("backend.services.downloader.get_video_info") as mock_info:
        
        mock_info.return_value = {"title": "Real Video", "duration": 30.0, "id": "synth_vid01"}
        temp_dir = tempfile.mkdtemp()
        dummy_file = Path(temp_dir) / "video.mp4"
        dummy_file.write_bytes(b"testcontent")
        mock_dl.return_value = dummy_file

        res = download_task(job_id=non_existent_job_id, youtube_url=unverified_url)
        
        # When job context is missing in DB, it fails closed: is_test=False
        mock_info.assert_called_once_with(unverified_url, is_test=False)
        mock_dl.assert_called_once_with(unverified_url, res["video_id"], is_test=False)
        assert res["is_test"] is False


# =========================================================================
# TEST D: Normal media path
# =========================================================================
def test_test_d_normal_media_path():
    """
    Test D — Normal media path:
    A normal job follows the standard download and transcription code paths.
    """
    job_id = f"test_p121_norm_{uuid.uuid4().hex[:8]}"
    chan_id = f"ch_p121_norm_{uuid.uuid4().hex[:8]}"

    with SyncSessionLocal() as session:
        ch = Channel(
            id=chan_id,
            youtube_channel_id=f"UC_{uuid.uuid4().hex[:8]}",
            channel_name="Standard Creator Channel",
            channel_url="https://youtube.com/channel/creator",
            is_test=False
        )
        job = Job(
            id=job_id,
            status=JobStatus.PENDING.value,
            progress=0,
            channel_id=chan_id,
            is_test=False
        )
        session.add(ch)
        session.add(job)
        session.commit()

    standard_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b'{"title": "Never Gonna Give You Up", "duration": 213.0, "id": "dQw4w9WgXcQ"}', b'')
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        info = asyncio.run(get_video_info(standard_url, is_test=False))
        assert info["title"] == "Never Gonna Give You Up"
        assert info["id"] == "dQw4w9WgXcQ"
        mock_exec.assert_called_once()
        cmd = mock_exec.call_args[0]
        assert cmd[0] == "yt-dlp"
        assert standard_url in cmd


# =========================================================================
# TEST E: Mock publishing remains independent
# =========================================================================
def test_test_e_mock_publishing_remains_independent_of_media_fixture():
    """
    Test E — Mock publishing remains independent:
    A test publishing operation (PUBLISH_MODE="test") continues to use the existing
    mock publisher, while normal media processing is NOT silently redirected to a fixture.
    """
    # 1. Verify PUBLISH_MODE="test" activates mock publisher in publisher service
    from backend.services.publisher import upload_short
    
    with patch("backend.services.publisher.settings.PUBLISH_MODE", "test"), \
         patch("time.sleep", return_value=None):
        
        # Test mock publishing succeeds with a mock clip ID
        pub_res = upload_short(
            video_path=Path(__file__),  # dummy existing path
            title="Shorts Test Title",
            description="Description",
            channel_id="ch_dummy"
        )
        assert pub_res["id"].startswith("mock_")
        assert "shorts/mock_" in pub_res["url"]

    # 2. Verify that PUBLISH_MODE="test" does NOT alter downloader or transcriber behavior
    # For a job with is_test=False, it still MUST NOT use synthetic fixtures
    with patch("backend.services.downloader.settings.PUBLISH_MODE", "test"):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b'{"title": "Normal Video", "duration": 60.0, "id": "norm123"}', b'')
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            info = asyncio.run(get_video_info("https://www.youtube.com/watch?v=synth_vid01", is_test=False))
            # Must NOT substitute fixture despite PUBLISH_MODE="test"
            assert info["title"] == "Normal Video"
            mock_exec.assert_called_once()
            assert mock_exec.call_args[0][0] == "yt-dlp"
