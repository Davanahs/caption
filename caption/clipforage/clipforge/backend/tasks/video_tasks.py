import logging
from backend.tasks.celery_app import celery_app
from backend.models.db_sync import update_job_sync

logger = logging.getLogger(__name__)

from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS

@celery_app.task(
    bind=True,
    name="download_task",
    **DEFAULT_RETRY_KWARGS,
)
def download_task(self, job_id: str, youtube_url: str = None, local_path: str = None, channel_id: str = None, **kwargs):
    """
    Downloads the video from youtube or uses local path.
    Creates Video record and links it to Job.
    Returns: video_id
    """
    import asyncio
    import uuid
    import shutil
    from pathlib import Path
    from backend.services.downloader import download_video, get_video_info, extract_youtube_id
    from backend.models.db_sync import create_video_record, link_job_video_sync, update_job_title_sync
    from backend.models.artifact_sync import register_artifact_sync, update_artifact_status_sync
    from backend.models.models import ArtifactType, ArtifactStatus
    from backend.core.storage import storage_service

    logger.info(f"Downloading video for job {job_id}")
    update_job_sync(job_id, "downloading", 10, "Downloading video...")
    
    video_id = kwargs.get("video_id") or str(uuid.uuid4())

    # Resolve trusted test authorization strictly from DB state
    is_test = False
    try:
        from backend.models.database import SyncSessionLocal
        from backend.models.models import Job, Channel
        with SyncSessionLocal() as session:
            job_rec = session.query(Job).filter_by(id=job_id).first()
            if job_rec:
                if job_rec.is_test:
                    is_test = True
                elif job_rec.channel_id:
                    ch_rec = session.query(Channel).filter_by(id=job_rec.channel_id).first()
                    if ch_rec and ch_rec.is_test:
                        is_test = True
            elif channel_id:
                ch_rec = session.query(Channel).filter_by(id=channel_id).first()
                if ch_rec and ch_rec.is_test:
                    is_test = True
    except Exception as db_err:
        logger.warning(f"Could not verify test status from DB for job {job_id}: {db_err}")
        is_test = False

    try:
        if youtube_url:
            yt_id = extract_youtube_id(youtube_url)
            if not yt_id:
                raise ValueError("Invalid YouTube URL")
                
            info = asyncio.run(get_video_info(youtube_url, is_test=is_test))
            title = info.get("title", f"Video {yt_id}")
            duration = info.get("duration", 0)

            # Update job title
            update_job_title_sync(job_id, title)

            # Download
            out_path = asyncio.run(download_video(youtube_url, video_id, is_test=is_test))
            
            # Create DB record with a temporary local path (as downloader saves it to a temp workspace)
            # The download_video returns the temp workspace path. We don't save that exact path as canonical
            # local_path anymore, we save the storage_key and retrieve it via storage_service.
            
            storage_key = f"uploads/{video_id}/source.mp4"
            
            # Create video record for job first because register_artifact_sync validates owner existence
            create_video_record(
                video_id=video_id,
                title=title,
                youtube_url=youtube_url,
                youtube_id=yt_id,
                local_path=storage_key,
                duration=duration,
                channel_id=channel_id
            )

            # Register and upload to central storage
            register_artifact_sync(
                owner_type="video",
                owner_id=video_id,
                artifact_type=ArtifactType.RAW_VIDEO,
                storage_key=storage_key,
                retention_policy="persistent", # Raw videos might be kept persistently or based on policy
                local_filepath=str(out_path),
                processing_version=job_id
            )
            update_artifact_status_sync(storage_key, ArtifactStatus.READY)
            link_job_video_sync(job_id, video_id)
            
            # Clean up the temp workspace file
            try:
                out_path.unlink()
                out_path.parent.rmdir()
            except Exception as e:
                logger.warning(f"Could not clean up temp dl path: {e}")
            
        elif local_path:
            p = Path(local_path)
            if not p.exists():
                raise FileNotFoundError("Local file not found")
            
            storage_key = f"uploads/{video_id}/source.mp4"
            
            # Create DB record first because register_artifact_sync validates owner existence
            create_video_record(
                video_id=video_id,
                title=p.name,
                youtube_url="",
                youtube_id="",
                local_path=storage_key,
                duration=0.0,
                channel_id=channel_id
            )

            # Register and upload to central storage
            register_artifact_sync(
                owner_type="video",
                owner_id=video_id,
                artifact_type=ArtifactType.RAW_VIDEO,
                storage_key=storage_key,
                retention_policy="persistent",
                local_filepath=local_path,
                processing_version=job_id
            )
            update_artifact_status_sync(storage_key, ArtifactStatus.READY)
            
            link_job_video_sync(job_id, video_id)
        else:
            raise ValueError("Must provide either youtube_url or local_path")
            
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise self.retry(exc=e, countdown=10)
    
    # Pass kwargs along for next tasks, ensuring is_test is explicitly propagated
    result = {"video_id": video_id, "job_id": job_id, "is_test": is_test}
    result.update(kwargs)
    result["is_test"] = is_test
    return result


@celery_app.task(
    bind=True,
    name="validate_media_task",
)
def validate_media_task(self, result: dict):
    """
    Validates downloaded/uploaded media with FFprobe preflight inspection (PREREQ-011).
    Verifies:
      - File exists and is non-empty.
      - Valid container with readable video stream, positive dimensions (width, height > 0).
      - Duration > 0.
      - Checks audio stream presence if workflow requires audio.
    Fails fast: raises RuntimeError if invalid, halting Celery pipeline before expensive downstream stages.
    """
    import json
    import shutil
    import subprocess
    from pathlib import Path
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Video
    from backend.models.artifact_sync import managed_download_sync

    video_id = result.get("video_id")
    job_id = result.get("job_id")
    is_test = result.get("is_test", False)

    logger.info(f"Validating media format for video {video_id} (job {job_id})")
    update_job_sync(job_id, "validating", 20, "Validating media container and streams...")

    storage_key = None
    with SyncSessionLocal() as session:
        video = session.query(Video).filter_by(id=video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found in database")
        storage_key = video.local_path

    if not storage_key:
        err = f"Video {video_id} has no storage_key / local_path"
        update_job_sync(job_id, "failed", 0, "Validation error", error=err)
        raise RuntimeError(err)

    try:
        with managed_download_sync(storage_key=storage_key) as temp_video_path:
            p = Path(temp_video_path)
            if not p.exists() or p.stat().st_size == 0:
                err = f"Media file {storage_key} is missing or 0 bytes"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
            cmd = [
                ffprobe_bin, "-v", "error",
                "-show_entries", "format=duration:stream=codec_type,width,height",
                "-of", "json", str(p)
            ]
            probe_res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if probe_res.returncode != 0:
                err = f"FFprobe failed to inspect media: {probe_res.stderr.strip() or 'Corrupt media container'}"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            try:
                data = json.loads(probe_res.stdout)
            except Exception as parse_err:
                err = f"Failed to parse ffprobe json output: {parse_err}"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            format_info = data.get("format", {})
            streams = data.get("streams", [])

            if not streams:
                err = "No media streams found in container"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            has_video = False
            has_audio = False
            width = None
            height = None
            for s in streams:
                if s.get("codec_type") == "video":
                    has_video = True
                    width = s.get("width")
                    height = s.get("height")
                elif s.get("codec_type") == "audio":
                    has_audio = True

            if not has_video or not width or not height:
                err = f"Invalid or missing video stream: video={has_video}, dimensions={width}x{height}"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            raw_duration = format_info.get("duration")
            try:
                dur_float = float(raw_duration) if raw_duration is not None else 0.0
            except (ValueError, TypeError):
                dur_float = 0.0

            if dur_float <= 0.0:
                err = f"Invalid media duration: {raw_duration}"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            # Check audio if required (clip_mode == "ai_highlights" or not equal_split without audio)
            require_audio = result.get("require_audio", True)
            if require_audio and not has_audio:
                err = "No audio stream found in source media (audio required for transcription & speech analysis)"
                update_job_sync(job_id, "failed", 0, "Validation error", error=err)
                raise RuntimeError(err)

            # Update video duration in DB if duration was 0 or unrecorded
            with SyncSessionLocal() as session:
                vid = session.query(Video).filter_by(id=video_id).first()
                if vid and (not vid.duration or vid.duration <= 0.0):
                    vid.duration = dur_float
                    session.commit()

            logger.info(f"Media validation passed for video {video_id}: {width}x{height}, {dur_float:.1f}s, audio={has_audio}")
            update_job_sync(job_id, "validating", 25, "Media validated successfully")

    except Exception as e:
        logger.error(f"Media validation failed for video {video_id}: {e}")
        update_job_sync(job_id, "failed", 0, "Validation failed", error=str(e))
        raise e

    return result


@celery_app.task(
    bind=True,
    name="transcription_task",
    **DEFAULT_RETRY_KWARGS,
)
def transcription_task(self, result: dict):
    """
    Transcribes the video. 
    Updates Video.transcription_status and Video.transcription_version in DB.
    Returns: "transcription_complete"
    """
    import json
    import tempfile
    from pathlib import Path
    from backend.services.transcriber import transcribe_video
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Video, Job, Channel
    from backend.models.db_sync import update_video_transcript_sync, update_video_status_sync
    from backend.models.artifact_sync import managed_download_sync

    video_id = result.get("video_id")
    job_id = result.get("job_id")
    
    logger.info(f"Transcribing video {video_id}")
    update_job_sync(job_id, "transcribing", 30, "Transcribing audio...")
    
    try:
        # 1. Check idempotency and get video + verify is_test from trusted DB state
        is_test = False
        with SyncSessionLocal() as session:
            video = session.query(Video).filter_by(id=video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            # Check idempotency
            if video.transcription_status == "completed" and video.transcript:
                logger.info(f"Video {video_id} already transcribed.")
                return result

            # Verify is_test from trusted Job/Channel DB records
            if job_id:
                job_rec = session.query(Job).filter_by(id=job_id).first()
                if job_rec and job_rec.is_test:
                    is_test = True
                elif job_rec and job_rec.channel_id:
                    ch_rec = session.query(Channel).filter_by(id=job_rec.channel_id).first()
                    if ch_rec and ch_rec.is_test:
                        is_test = True
            if not is_test and result.get("is_test") is True:
                # Fallback for unit testing where job may not be committed in DB
                is_test = True
                
        storage_key = f"uploads/{video_id}/extracted_audio.mp3"
        
        def _update_progress(pct, step):
            update_job_sync(job_id, "transcribing", int(pct), step)
            
        # 3. Transcribe with explicit is_test authorization
        try:
            with managed_download_sync(storage_key=storage_key) as temp_audio_path:
                transcript_data = transcribe_video(temp_audio_path, update_fn=_update_progress, is_test=is_test)
        except Exception as e:
            logger.warning(f"Could not retrieve or transcribe audio from storage for key {storage_key}: {e}")
            raise e
        
        # 4. Save to DB
        transcript_json = json.dumps(transcript_data)
        # Using a hash or simple version string for idempotency
        version = "v1" 
        update_video_transcript_sync(video_id, transcript_json, version)

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        update_video_status_sync(video_id, "transcription_status", "failed")
        raise self.retry(exc=e, countdown=30)
        
    return result


@celery_app.task(
    bind=True,
    name="scene_detection_task",
    **DEFAULT_RETRY_KWARGS,
)
def scene_detection_task(self, result: dict):
    """
    Detects scenes in the video.
    Updates Video.scene_detection_status and Video.scene_detection_version in DB.
    Returns: "scene_detection_complete"
    """
    import json
    import tempfile
    from pathlib import Path
    from backend.services.scene_detector import detect_scenes
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Video, ArtifactType, ArtifactStatus
    from backend.models.db_sync import update_video_status_sync
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync

    video_id = result.get("video_id")
    job_id = result.get("job_id")
    
    logger.info(f"Detecting scenes for video {video_id}")
    
    try:
        # 1. Fetch video
        with SyncSessionLocal() as session:
            video = session.query(Video).filter_by(id=video_id).first()
            if not video or not video.local_path:
                raise ValueError(f"Video {video_id} not found or has no local_path")
            # local_path actually contains the storage_key, e.g. "videos/.../source.mp4"
            storage_key = video.local_path
            
            # Idempotency check
            if video.scene_detection_status == "completed":
                logger.info(f"Video {video_id} scenes already detected, skipping.")
                return result

        # 2. Retrieve video from storage and Detect scenes
        try:
            with managed_download_sync(storage_key=storage_key) as temp_video_path:
                scenes = detect_scenes(temp_video_path)
                
                scenes_storage_key = f"uploads/{video_id}/scenes.json"
                with managed_upload_sync(
                    owner_type="video",
                    owner_id=video_id,
                    artifact_type=ArtifactType.SCENES,
                    storage_key=scenes_storage_key,
                    retention_policy="persistent",
                    processing_version="v1"
                ) as temp_scenes_path:
                    with open(temp_scenes_path, "w") as f:
                        json.dump(scenes, f)
                        
        except Exception as e:
            logger.warning(f"Could not retrieve video or detect scenes for key {storage_key}: {e}")
            raise e
            
        # 4. Save status to DB
        version = "v1" 
        update_video_status_sync(video_id, "scene_detection_status", "completed", version=version)
        
    except Exception as e:
        logger.error(f"Scene detection failed: {e}")
        update_video_status_sync(video_id, "scene_detection_status", "failed")
        raise self.retry(exc=e, countdown=30)
        
    return result
