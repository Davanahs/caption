from celery import Celery
from backend.core.config import settings

celery_app = Celery(
    "clipforge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # Re-queue tasks if a worker is killed mid-job (prevents silent task loss on restart)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    # Phase 5: Routing Configuration
    # We will define queues, but for now we rely on default unless specified.
    # ── Celery Beat Schedule ──
    beat_schedule={
        "track-and-optimize-clips": {
            "task": "track_and_optimize_clips",
            "schedule": 43200,  # 12 hours in seconds
        },
        "cleanup-expired-artifacts": {
            "task": "backend.tasks.storage_tasks.cleanup_expired_artifacts_task",
            "schedule": settings.STORAGE_CLEANUP_INTERVAL_SECONDS,
        },
        "stale-execution-recovery": {
            "task": "backend.tasks.orchestration.stale_recovery_task",
            "schedule": 300,  # runs every 5 minutes
        },
        "recover-stale-studio-batches": {
            "task": "backend.tasks.studio_tasks.recover_stale_studio_batches_task",
            "schedule": 300,  # runs every 5 minutes
        },
        "recover-stranded-publish-jobs": {
            "task": "recover_stranded_publish_jobs",
            "schedule": 120,  # runs every 2 minutes
        },
        "sweep-pending-decisions": {
            "task": "backend.tasks.orchestration.sweep_pending_decisions_task",
            "schedule": 15,  # runs every 15 seconds
        },
        "drain-manual-queue": {
            "task": "backend.services.queue_manager.drain_manual_queue",
            "schedule": 30,  # runs every 30 seconds
        },
    },
)

# Important: we define task modules so Celery worker and app discover and register them
TASK_MODULES = [
    "backend.services.queue_manager",
    "backend.tasks.orchestration",
    "backend.tasks.video_tasks",
    "backend.tasks.audio_tasks",
    "backend.tasks.analysis_tasks",
    "backend.tasks.clip_tasks",
    "backend.tasks.scheduler",
    "backend.tasks.storage_tasks",
    "backend.tasks.hook_tasks",
    "backend.tasks.dubbing_tasks",
    "backend.tasks.studio_tasks",
]

celery_app.conf.update(
    imports=TASK_MODULES,
    include=TASK_MODULES,
)

