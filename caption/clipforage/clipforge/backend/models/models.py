import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, BigInteger, Float, DateTime, Text, Boolean, Enum, ForeignKey, func, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.database import Base
import enum


class ArtifactStatus(str, enum.Enum):
    CREATED = "created"
    PROCESSING = "processing"
    READY = "ready"
    EXPIRED = "expired"
    QUARANTINED = "quarantined"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


class ArtifactType(str, enum.Enum):
    RAW_VIDEO = "raw_video"
    EXTRACTED_AUDIO = "extracted_audio"
    CLEAN_AUDIO = "clean_audio"
    SCENES = "scenes"
    CANDIDATES = "candidates"
    SCORED_CLIPS = "scored_clips"
    RAW_CLIP = "raw_clip"
    VERTICAL_CLIP = "vertical_clip"
    FINAL_CLIP = "final_clip"
    THUMBNAIL = "thumbnail"
    SFX_VARIANT = "sfx_variant"
    BROLL_ASSET = "broll_asset"
    BROLL_VARIANT = "broll_variant"
    AUDIO_VOICEOVER = "audio_voiceover"
    AUDIO_SFX = "audio_sfx"
    VIDEO_RENDER = "video_render"
    DUBBING_VARIANT = "dubbing_variant"

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    VALIDATING = "validating"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    SELECTING = "selecting"
    CLIPPING_IN_PROGRESS = "clipping_in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ClipStatus(str, enum.Enum):
    PENDING = "pending"
    REFRAMING = "reframing"
    RENDERING = "rendering"
    VALIDATING_OUTPUT = "validating_output"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


class PublishStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    UPLOADING = "uploading"
    FINALIZING = "finalizing"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"


class UploadBatchStatus(str, enum.Enum):
    STAGING = "staging"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    COMPLETED = "completed"
    QUEUED = "queued"
    PROCESSING = "processing"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    DELETING = "deleting"


class VideoUploadStatus(str, enum.Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    UPLOADED = "uploaded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoProcessingStatus(str, enum.Enum):
    NONE = "none"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    RETRY_QUEUED = "retry_queued"



class VideoReservationState(str, enum.Enum):
    NONE = "none"
    INITIAL = "initial"
    HEADROOM_ONLY = "headroom_only"
    RELEASED = "released"


class VideoPartDisposition(str, enum.Enum):
    NONE = "none"
    PROMOTE_TO_FINAL = "promote_to_final"
    DELETE = "delete"


class VideoFinalDisposition(str, enum.Enum):
    NONE = "none"
    RETAIN_VALID = "retain_valid"
    DELETE = "delete"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Untitled")
    youtube_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    youtube_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_optimize: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")  # Phase 5
    transcription_status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending")
    transcription_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scene_detection_status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending")
    scene_detection_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Upload Studio Phase 1 (Ingestion) ──────────────────────────────────
    is_manual_upload: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    resolution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    upload_batch_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("upload_batches.id", ondelete="RESTRICT"), nullable=True)
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    uploaded_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    client_item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_state: Mapped[str] = mapped_column(String(30), default=VideoReservationState.NONE.value, server_default=VideoReservationState.NONE.value)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    active_writer_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    part_disposition: Mapped[str] = mapped_column(String(30), default=VideoPartDisposition.NONE.value, server_default=VideoPartDisposition.NONE.value)
    final_disposition: Mapped[str] = mapped_column(String(30), default=VideoFinalDisposition.NONE.value, server_default=VideoFinalDisposition.NONE.value)

    # ── Upload Studio Phase 2 (Processing) ──────────────────────────────────
    processing_status: Mapped[str] = mapped_column(String(30), default=VideoProcessingStatus.NONE.value, server_default=VideoProcessingStatus.NONE.value)
    processing_progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    processing_step: Mapped[str | None] = mapped_column(String(200), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_processed(self) -> bool:
        return self.processing_status == VideoProcessingStatus.COMPLETED.value

    @is_processed.setter
    def is_processed(self, val: bool) -> None:
        if val:
            self.processing_status = VideoProcessingStatus.COMPLETED.value


class StorageReservationCoordinator(Base):
    __tablename__ = "storage_reservation_coordinators"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    volume_id: Mapped[str] = mapped_column(String(128), nullable=False)
    volume_hmac: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=UploadBatchStatus.STAGING.value, server_default=UploadBatchStatus.STAGING.value)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    total_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())

    # Phase 2 Processing Tracking
    active_video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    worker_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    batch_error: Mapped[str | None] = mapped_column(Text, nullable=True)



class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Untitled Clip")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    output_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    transcript_segment: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_status: Mapped[str] = mapped_column(String(50), default=PublishStatus.DRAFT, server_default="draft")
    publish_destination_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    youtube_short_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    privacy: Mapped[str] = mapped_column(String(50), default="private", server_default="private")
    made_for_kids: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    age_restricted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON array string
    category: Mapped[str | None] = mapped_column(String(100), default="22", server_default="22")
    license: Mapped[str | None] = mapped_column(String(100), default="youtube", server_default="youtube")
    status: Mapped[str] = mapped_column(String(50), default=ClipStatus.PENDING, server_default="pending")
    run_identity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Feature 1: PreUpload Metadata ──────────────────────────────────────
    pinned_comment: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending")
    # "pending" = not yet generated, "ready" = generated, awaiting review,
    # "approved" = user clicked Publish

    # ── Phase 3 Publishing Tracking ────────────────────────────────────────
    publish_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publish_attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    publish_progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    publish_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publish_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    upload_session_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Feature 2: PostUpload Optimization ─────────────────────────────────
    analytics_views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    analytics_likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    analytics_comments: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    analytics_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    analytics_view_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    analytics_last_checked: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analytics_check_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    optimization_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_optimized_at: Mapped[str | None] = mapped_column(String(50), nullable=True)



class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)   # YouTube URL or filename
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True) # Display name shown in UI
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.PENDING)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class VideoDecisionStatus(str, enum.Enum):
    AWAITING_SETTINGS = "awaiting_settings"
    CUSTOMIZING = "customizing"
    RESOLVED_DEFAULTS = "resolved_defaults"
    RESOLVED_CUSTOM = "resolved_custom"
    CANCELLED = "cancelled"


class VideoDecision(Base):
    __tablename__ = "video_decisions"
    __table_args__ = (
        UniqueConstraint('channel_id', 'youtube_id', name='uix_video_decisions_channel_yt'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    channel_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    youtube_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    youtube_url: Mapped[str] = mapped_column(String(500), nullable=False)
    video_title: Mapped[str] = mapped_column(String(500), nullable=False, default="Untitled", server_default="Untitled")
    video_thumbnail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channel_profile_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=VideoDecisionStatus.AWAITING_SETTINGS.value, server_default="awaiting_settings")
    decision_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    customization_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    youtube_channel_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel_name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_clip: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_pilot: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_video_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    clips_generated: Mapped[int] = mapped_column(Integer, default=0)
    publish_destination_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    processing_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Phase 8: Branding Profile
    watermark_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    brand_color_primary: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand_logo_position: Mapped[str | None] = mapped_column(String(50), nullable=True, default="top_right", server_default="top_right")

    # Multi-Account Publishing Destinations
    is_destination: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_default_destination: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    default_destination_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Automated Test Data Isolation
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)

    # Multi-Channel Publishing Settings & Cached Analytics
    publishing_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cached_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChannelDestination(Base):
    __tablename__ = "channel_destinations"
    __table_args__ = (
        UniqueConstraint('source_channel_id', 'destination_channel_id',
                         name='uix_source_dest'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True,
                                     default=lambda: str(uuid.uuid4()))
    source_channel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    destination_channel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))


class PublishTarget(Base):
    __tablename__ = "publish_targets"
    __table_args__ = (
        UniqueConstraint('clip_id', 'destination_id',
                         name='uix_clip_destination'),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True,
                                     default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    destination_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    youtube_video_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    privacy: Mapped[str] = mapped_column(String(50), default="public")
    made_for_kids: Mapped[bool] = mapped_column(Boolean, default=False)
    age_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))


class VideoMetadata(Base):
    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str | None] = mapped_column(String, nullable=True)  # comma‑separated
    hashtags: Mapped[str | None] = mapped_column(String, nullable=True)  # comma‑separated
    pinned_comment: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VideoAnalytics(Base):
    __tablename__ = "video_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    view_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class OptimizationLog(Base):
    __tablename__ = "optimizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[str] = mapped_column(String, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    new_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    new_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_tags: Mapped[str | None] = mapped_column(String, nullable=True)
    new_hashtags: Mapped[str | None] = mapped_column(String, nullable=True)
    view_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VideoTrackingQueue(Base):
    __tablename__ = "video_tracking_queue"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    youtube_video_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    optimization_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, completed, skipped
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublishRecord(Base):
    """
    Guarantees strict publish idempotency via a DB-level lock and unique idempotency key.
    idempotency_key = {job_id}_{clip_id}_{publish_target}_{content_version}
    """
    __tablename__ = "publish_records"
    
    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    target: Mapped[str] = mapped_column(String, nullable=False)  # e.g., 'youtube'
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="publishing") # 'publishing', 'completed', 'failed'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class ContentAnalysis(Base):
    __tablename__ = "content_analysis"

    clip_id: Mapped[str] = mapped_column(String, primary_key=True)
    niche: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    emotions: Mapped[str] = mapped_column(String(500), nullable=False)
    audience_type: Mapped[str] = mapped_column(String(500), nullable=False)
    searchable_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    long_tail_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    hashtag_candidates: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(String(200), nullable=False)
    pacing: Mapped[str] = mapped_column(String(100), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SEOAnalysis(Base):
    __tablename__ = "seo_analysis"

    clip_id: Mapped[str] = mapped_column(String, primary_key=True)
    seo_score: Mapped[float] = mapped_column(Float, nullable=False)
    ctr_score: Mapped[float] = mapped_column(Float, nullable=False)
    discoverability_score: Mapped[float] = mapped_column(Float, nullable=False)
    missing_keywords: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_hashtags: Mapped[str] = mapped_column(Text, nullable=False)
    weak_hashtags: Mapped[str] = mapped_column(Text, nullable=False)
    seo_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClipRetention(Base):
    __tablename__ = "clip_retention"

    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), primary_key=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OptimizationContext(Base):
    __tablename__ = "optimization_context"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, nullable=False)
    previous_titles: Mapped[str] = mapped_column(Text, default="")
    previous_descriptions: Mapped[str] = mapped_column(Text, default="")
    previous_hashtags: Mapped[str] = mapped_column(Text, default="")
    optimization_attempt: Mapped[int] = mapped_column(Integer, default=0)
    optimization_reason: Mapped[str] = mapped_column(String(500), default="")
    previous_scores: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PipelineMetrics(Base):
    __tablename__ = "pipeline_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, nullable=False)
    phase_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ArtifactRecord(Base):
    __tablename__ = "artifact_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'video', 'clip', 'job'
    owner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    backend: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    retention_policy: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(256), nullable=True)
    processing_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ABExperiment(Base):
    __tablename__ = "ab_experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, nullable=False)
    youtube_short_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    variant_a_title: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_b_title: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_a_thumbnail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    variant_b_thumbnail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    active_variant: Mapped[str] = mapped_column(String(50), default="A")
    status: Mapped[str] = mapped_column(String(50), default="running")
    vsi_score_a: Mapped[float] = mapped_column(Float, default=0.0)
    vsi_score_b: Mapped[float] = mapped_column(Float, default=0.0)
    views_a: Mapped[int] = mapped_column(Integer, default=0)
    views_b: Mapped[int] = mapped_column(Integer, default=0)
    swapped_at: Mapped[str | None] = mapped_column(String(100), nullable=True)
    winner_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Celery task ID
    job_id: Mapped[str | None] = mapped_column(String, ForeignKey("jobs.id"), nullable=True)
    clip_id: Mapped[str | None] = mapped_column(String, ForeignKey("clips.id", ondelete="SET NULL"), nullable=True)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=TaskExecutionStatus.PENDING)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)


class SFXPack(Base):
    __tablename__ = "sfx_packs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SFXAsset(Base):
    __tablename__ = "sfx_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pack_id: Mapped[str | None] = mapped_column(String, ForeignKey("sfx_packs.id"), nullable=True)
    artifact_id: Mapped[str] = mapped_column(String, ForeignKey("artifact_records.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClipVariant(Base):
    __tablename__ = "clip_variants"

    variant_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), nullable=False)
    variant_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_variant_id: Mapped[str | None] = mapped_column(String, ForeignKey("clip_variants.variant_id"), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String, ForeignKey("artifact_records.id"), nullable=True)
    configuration_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    variant_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def id(self) -> str:
        return self.variant_id


class ClipSFXPlan(Base):
    __tablename__ = "clip_sfx_plans"

    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), primary_key=True)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VisualAsset(Base):
    __tablename__ = "visual_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id: Mapped[str] = mapped_column(String, ForeignKey("artifact_records.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'video', 'image', 'generated_visual'
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClipVisualPlan(Base):
    __tablename__ = "clip_visual_plans"

    clip_id: Mapped[str] = mapped_column(String, ForeignKey("clips.id", ondelete="CASCADE"), primary_key=True)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



class ClipHookPlan(Base):
    __tablename__ = 'clip_hook_plans'

    clip_id: Mapped[str] = mapped_column(String, ForeignKey('clips.id', ondelete='CASCADE'), primary_key=True)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DubbingPlan(Base):
    __tablename__ = 'dubbing_plans'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id: Mapped[str] = mapped_column(String, ForeignKey('clips.id', ondelete='CASCADE'), nullable=False)
    target_language: Mapped[str] = mapped_column(String(50), nullable=False)
    voice_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_voice_clone: Mapped[bool] = mapped_column(Boolean, default=False)
    authorization_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_version: Mapped[str] = mapped_column(String(50), default="v1")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DubbingSegment(Base):
    __tablename__ = 'dubbing_segments'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String, ForeignKey('dubbing_plans.id', ondelete='CASCADE'), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    generated_audio_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    generated_audio_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    fit_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
