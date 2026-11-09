import logging
import tempfile
import subprocess
from pathlib import Path
from celery import shared_task
from backend.tasks.celery_app import celery_app
from backend.models.db_sync import update_job_sync
from backend.models.artifact_sync import managed_download_sync, managed_upload_sync
from backend.models.models import ArtifactType, ArtifactStatus

logger = logging.getLogger(__name__)

from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS

@celery_app.task(
    bind=True,
    name="extract_audio_task",
    **DEFAULT_RETRY_KWARGS,
)
def extract_audio_task(self, result: dict):
    """
    Extracts 16kHz mono mp3 audio from the raw video artifact.
    Registers the extracted audio as an Artifact.
    Returns: result dict (unchanged)
    """
    video_id = result.get("video_id")
    job_id = result.get("job_id")
    
    logger.info(f"Extracting audio for video {video_id} (job: {job_id})")
    update_job_sync(job_id, "extracting_audio", 20, "Extracting audio from video...")
    
    storage_key_video = f"uploads/{video_id}/source.mp4"
    storage_key_audio = f"uploads/{video_id}/extracted_audio.mp3"
    
    try:
        with managed_download_sync(storage_key=storage_key_video) as temp_video_path:
            with managed_upload_sync(
                owner_type="video",
                owner_id=video_id,
                artifact_type=ArtifactType.EXTRACTED_AUDIO,
                storage_key=storage_key_audio,
                retention_policy="persistent",
                processing_version=job_id
            ) as temp_audio_path:
            
                # Extract audio using FFmpeg
                cmd = [
                    "ffmpeg", "-y", "-i", str(temp_video_path),
                    "-vn", "-acodec", "libmp3lame", "-ac", "1", "-ar", "16000",
                    "-q:a", "5", "-f", "mp3",
                    str(temp_audio_path)
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    logger.error(f"FFmpeg failed with {proc.returncode}: {proc.stderr}")
                    proc.check_returncode()
        
    except Exception as e:
        logger.error(f"Failed to extract audio for video {video_id}: {e}")
        raise self.retry(exc=e, countdown=30)
            
    return result
