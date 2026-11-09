from datetime import datetime, timezone
from backend.models.database import SyncSessionLocal
from backend.models.models import Job, Video, Clip, Channel

import json

def create_job_sync(job_id: str, source_url: str, config: str | dict = None, channel_id: str = None, is_test: bool = False, source_title: str = None) -> None:
    """Insert a Job row synchronously via SQLAlchemy so the Celery task can update it."""
    with SyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        config_str = json.dumps(config) if isinstance(config, dict) else config
        job = Job(
            id=job_id,
            status='pending',
            progress=0,
            current_step='Queued',
            source_url=source_url,
            source_title=source_title or source_url,
            config=config_str,
            channel_id=channel_id,
            is_test=is_test,
            created_at=now,
            updated_at=now
        )
        session.add(job)
        session.commit()

def update_job_sync(job_id: str, status: str, progress: int, step: str, error: str = None):
    """Synchronous DB update for job status with basic transition validation."""
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            # Prevent moving backward if already in a terminal state
            if job.status == 'cancelled':
                print(f"[Warning] Ignored update on cancelled Job {job_id}: cannot transition from cancelled to {status}")
                return
            if job.status in ('completed', 'failed', 'completed_with_failures') and status not in ('completed', 'failed', 'completed_with_failures', 'retrying'):
                print(f"[Warning] Ignored invalid Job transition: {job.status} -> {status} for job {job_id}")
                return

            job.status = status
            job.progress = progress
            job.current_step = step
            if error:
                job.error_message = error
            job.updated_at = datetime.now(timezone.utc)
            session.commit()

def update_clip_status_sync(clip_id: str, status: str, error_msg: str = None) -> bool:
    """
    Synchronous DB update for clip status enforcing strict legal transitions.
    Returns True if transition successful, False if ignored.
    """
    from backend.models.models import ClipStatus
    
    valid_transitions = {
        ClipStatus.PENDING.value: {ClipStatus.REFRAMING.value, ClipStatus.FAILED.value},
        ClipStatus.REFRAMING.value: {ClipStatus.RENDERING.value, ClipStatus.FAILED.value},
        ClipStatus.RENDERING.value: {ClipStatus.VALIDATING_OUTPUT.value, ClipStatus.FAILED.value},
        ClipStatus.VALIDATING_OUTPUT.value: {ClipStatus.PUBLISHING.value, ClipStatus.FAILED.value},
        ClipStatus.PUBLISHING.value: {ClipStatus.COMPLETED.value, ClipStatus.FAILED.value},
        ClipStatus.COMPLETED.value: set(), # Terminal
        ClipStatus.FAILED.value: {ClipStatus.PENDING.value}, # Only manual retry allows failed -> pending
    }

    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        if not clip:
            return False
            
        current = clip.status
        allowed = valid_transitions.get(current, set())
        
        if status not in allowed and status != ClipStatus.FAILED.value:
            print(f"[Warning] Ignored invalid Clip transition: {current} -> {status} for clip {clip_id}")
            return False
            
        clip.status = status
        if error_msg:
            clip.description = f"Error: {error_msg}\n\n{clip.description or ''}"
            
        session.commit()
        return True

def update_clip_paths_sync(clip_id: str, output_path: str, thumbnail_path: str = None):
    """Update clip file paths after rendering."""
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        if clip:
            if output_path:
                clip.output_path = output_path
            if thumbnail_path:
                clip.thumbnail_path = thumbnail_path
            session.commit()

def update_clip_publish_sync(clip_id: str, publish_status: str, youtube_short_id: str = None, url: str = None):
    """Update clip publishing status."""
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        if clip:
            clip.publish_status = publish_status
            if youtube_short_id:
                clip.youtube_short_id = youtube_short_id
            if publish_status == "published":
                clip.published_at = datetime.now(timezone.utc)
            session.commit()

def update_job_title_sync(job_id: str, source_title: str):
    """Update just the source_title of a job (called once we know the real video title)."""
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.source_title = source_title
            job.updated_at = datetime.now(timezone.utc)
            session.commit()

def link_job_video_sync(job_id: str, video_id: str):
    """Link a Job row to the Video record it produced (fills in the video_id FK)."""
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.video_id = video_id
            job.updated_at = datetime.now(timezone.utc)
            session.commit()

def create_video_record(video_id: str, title: str, youtube_url: str, youtube_id: str, local_path: str, duration: float, channel_id: str = None):
    """Create a new Video record synchronously."""
    with SyncSessionLocal() as session:
        # Check if exists to emulate INSERT OR IGNORE
        existing = session.query(Video).filter_by(id=video_id).first()
        if not existing:
            video = Video(
                id=video_id,
                title=title,
                youtube_url=youtube_url,
                youtube_id=youtube_id,
                local_path=local_path,
                duration=duration,
                channel_id=channel_id,
                created_at=datetime.now(timezone.utc)
            )
            session.add(video)
            session.commit()

def update_video_transcript_sync(video_id: str, transcript: str, version: str):
    """Save transcript text to video record."""
    with SyncSessionLocal() as session:
        video = session.query(Video).filter_by(id=video_id).first()
        if video:
            video.transcript = transcript
            video.transcription_version = version
            video.transcription_status = "completed"
            session.commit()

def update_video_status_sync(video_id: str, field: str, status: str, version: str = None):
    """Update a status field (like scene_detection_status) on the Video record."""
    with SyncSessionLocal() as session:
        video = session.query(Video).filter_by(id=video_id).first()
        if video:
            setattr(video, field, status)
            if version and field.endswith("_status"):
                ver_field = field.replace("_status", "_version")
                if hasattr(video, ver_field):
                    setattr(video, ver_field, version)
            session.commit()

def save_clip_record(clip_id: str, video_id: str, title: str, start: float, end: float,
                      duration: float, score: float, output_path: str, thumbnail_path: str,
                      transcript_segment: str, run_identity: str = None,
                      description: str = None, tags: str = None,
                      pinned_comment: str = None,
                      publish_destination_id: str = None,
                      destination_ids: list[str] = None,
                      category: str = None):
    """Save a generated Clip record synchronously.
    
    All fields including run_identity and PublishTarget rows are set atomically
    in a single transaction to prevent orphaned records on partial failure.
    """
    import uuid
    from backend.models.models import PublishTarget

    with SyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        clip = Clip(
            id=clip_id,
            video_id=video_id,
            title=title,
            start_time=start,
            end_time=end,
            duration=duration,
            score=score,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
            transcript_segment=transcript_segment,
            metadata_status='pending',
            analytics_views=0,
            analytics_likes=0,
            analytics_comments=0,
            analytics_engagement_rate=0.0,
            analytics_view_score=0.0,
            analytics_check_count=0,
            category=category or '22',
            license='youtube',
            publish_destination_id=publish_destination_id,
            created_at=now
        )
        if run_identity:
            clip.run_identity = run_identity
        if description:
            clip.description = description
        if tags:
            clip.tags = tags
        if pinned_comment:
            clip.pinned_comment = pinned_comment
        session.add(clip)

        # Create PublishTarget rows
        target_dest_ids = []
        if destination_ids:
            for dest_id in destination_ids:
                # Exclude orphaned or non-existent channels
                ch = session.query(Channel).filter_by(id=dest_id).first()
                if ch:
                    target_dest_ids.append(dest_id)
        elif publish_destination_id:
            # Exclude orphaned legacy destination IDs (e.g. 'test-destination-uuid')
            ch = session.query(Channel).filter_by(id=publish_destination_id).first()
            if ch:
                target_dest_ids.append(publish_destination_id)

        for d_id in target_dest_ids:
            pt = PublishTarget(
                id=str(uuid.uuid4()),
                clip_id=clip_id,
                destination_id=d_id,
                status="pending",
                created_at=now,
                updated_at=now
            )
            session.add(pt)

        session.commit()

def increment_channel_clips_generated(channel_id: str, count: int):
    """Increment the clips_generated count of a monitored Channel synchronously."""
    with SyncSessionLocal() as session:
        channel = session.query(Channel).filter_by(id=channel_id).first()
        if channel:
            channel.clips_generated += count
            channel.last_checked_at = datetime.now(timezone.utc)
            session.commit()

def save_clip_metadata(
    clip_id: str,
    title: str,
    description: str,
    tags_json: str,
    pinned_comment: str,
) -> None:
    """Save LLM-generated metadata for a clip and mark it as ready for review."""
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        if clip:
            clip.title = title
            clip.description = description
            clip.tags = tags_json
            clip.pinned_comment = pinned_comment
            clip.metadata_status = 'ready'
            session.commit()

def get_clip_metadata(clip_id: str) -> dict | None:
    """Fetch a clip's full metadata for review or publishing."""
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        if not clip:
            return None
        return {
            "id": clip.id, "video_id": clip.video_id, "title": clip.title,
            "description": clip.description, "tags": clip.tags, "pinned_comment": clip.pinned_comment,
            "metadata_status": clip.metadata_status,
            "output_path": clip.output_path, "thumbnail_path": clip.thumbnail_path,
            "privacy": clip.privacy, "made_for_kids": clip.made_for_kids,
            "category": clip.category, "license": clip.license,
            "publish_status": clip.publish_status, "youtube_short_id": clip.youtube_short_id,
        }
