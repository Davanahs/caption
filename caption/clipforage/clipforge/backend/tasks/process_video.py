"""
process_video.py

OBSOLETE: Monolithic process_video_task has been decomposed into Phase 5 tasks.
See:
- backend.tasks.orchestration
- backend.tasks.video_tasks
- backend.tasks.analysis_tasks
- backend.tasks.clip_tasks
"""

# Kept for backward compatibility if any old imports rely on it during transition
from backend.tasks.celery_app import celery_app
from backend.tasks.orchestration import start_video_processing_task
# Ensure analysis_tasks and other pipeline tasks are eagerly registered when worker boots via process_video
import backend.tasks.analysis_tasks  # noqa: F401
import backend.tasks.video_tasks  # noqa: F401
import backend.tasks.clip_tasks  # noqa: F401

from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS


@celery_app.task(name="track_and_optimize_clips", **DEFAULT_RETRY_KWARGS)
def track_and_optimize_clips_task():
    """Celery beat task: check analytics for all recently published clips and optimize if needed."""
    import asyncio
    from backend.services.performance_tracker import get_clips_needing_tracking, should_check_now
    from backend.services.auto_optimizer import check_and_optimize
    clips = get_clips_needing_tracking()
    print(f"[Beat] Checking analytics for {len(clips)} clip(s)...")
    for clip in clips:
        if should_check_now(clip):
            try:
                asyncio.run(check_and_optimize(clip))
            except Exception as e:
                print(f"[Beat] Optimization failed for clip {clip['id']}: {e}")
