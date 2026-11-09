import logging
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from backend.models.database import SyncSessionLocal
from backend.models.models import TaskExecution, TaskExecutionStatus
from celery.exceptions import Ignore

logger = logging.getLogger(__name__)

def claim_task_execution(
    session,
    task_id: str,
    job_id: str,
    clip_id: str,
    operation: str,
    idempotency_key: str,
    worker_id: str
) -> TaskExecution:
    """
    Attempts to claim a task execution safely using INSERT ... ON CONFLICT DO NOTHING.
    Returns the current TaskExecution state. If it was already completed by another worker,
    the returned TaskExecution will have status == TaskExecutionStatus.SUCCEEDED.
    """
    now = datetime.now(timezone.utc)
    
    # Ensure job_id exists in jobs table to satisfy foreign key constraint
    valid_job_id = None
    if job_id:
        from backend.models.models import Job
        job_exists = session.query(Job.id).filter_by(id=job_id).first()
        if job_exists:
            valid_job_id = job_id
        elif clip_id:
            from backend.models.models import Clip
            clip = session.query(Clip.video_id).filter_by(id=clip_id).first()
            if clip:
                job_by_video = session.query(Job.id).filter_by(video_id=clip.video_id).order_by(Job.created_at.desc()).first()
                if job_by_video:
                    valid_job_id = job_by_video[0]
    elif clip_id:
        from backend.models.models import Clip, Job
        clip = session.query(Clip.video_id).filter_by(id=clip_id).first()
        if clip:
            job_by_video = session.query(Job.id).filter_by(video_id=clip.video_id).order_by(Job.created_at.desc()).first()
            if job_by_video:
                valid_job_id = job_by_video[0]

    stmt = insert(TaskExecution).values(
        id=task_id,
        task_id=task_id,
        job_id=valid_job_id,
        clip_id=clip_id,
        operation=operation,
        status=TaskExecutionStatus.RUNNING.value,
        attempt=1,
        retry_count=0,
        worker_id=worker_id,
        started_at=now,
        last_heartbeat=now,
        idempotency_key=idempotency_key
    )
    
    # On conflict, do not update (we just want to see what's there)
    stmt = stmt.on_conflict_do_nothing(index_elements=['idempotency_key'])
    
    session.execute(stmt)
    session.commit()
    
    # Now retrieve the authoritative record
    record = session.query(TaskExecution).filter_by(idempotency_key=idempotency_key).first()
    return record


def check_and_claim_execution(
    task_id: str,
    job_id: str,
    clip_id: str,
    operation: str,
    idempotency_key: str,
    worker_id: str
):
    """
    High-level helper to wrap the reconciliation logic.
    Raises celery.exceptions.Ignore if another worker is handling it or it's done.
    """
    with SyncSessionLocal() as session:
        record = claim_task_execution(
            session=session,
            task_id=task_id,
            job_id=job_id,
            clip_id=clip_id,
            operation=operation,
            idempotency_key=idempotency_key,
            worker_id=worker_id
        )
        
        if record.id == task_id:
            # We are the winner
            return record
            
        # We are NOT the winner. Another execution holds this idempotency key.
        if record.status == TaskExecutionStatus.SUCCEEDED.value:
            logger.info(f"[{operation}] idempotency key {idempotency_key} already completed by {record.id}.")
            raise Ignore()
            
        if record.status == TaskExecutionStatus.RUNNING.value:
            # Is it stale? Let's check heartbeat
            now = datetime.now(timezone.utc)
            # If last_heartbeat is naive, make it aware (or just compare properly, assume it's aware)
            delta = now - record.last_heartbeat.replace(tzinfo=timezone.utc) if record.last_heartbeat.tzinfo is None else now - record.last_heartbeat
            if delta.total_seconds() > 300: # 5 minutes
                logger.warning(f"[{operation}] Task {record.id} seems stale. Taking over.")
                # We could take over here, but the stale_recovery_task handles this better.
                # Just ignore for now and let the recovery task handle transitioning it to FAILED/RETRYING.
                pass
                
            logger.info(f"[{operation}] idempotency key {idempotency_key} is currently running by {record.id}.")
            raise Ignore()
            
        if record.status == TaskExecutionStatus.FAILED.value:
            # We can allow a retry if policy permits. We should bump attempt.
            logger.info(f"[{operation}] Previous execution {record.id} failed. Assuming this is a Celery retry.")
            # For simplicity, we just let the task continue.
            return record
            
        raise Ignore()

def heartbeat_task_execution(task_id: str):
    """
    Updates the last_heartbeat timestamp for a running task.
    """
    try:
        with SyncSessionLocal() as session:
            tx = session.query(TaskExecution).filter_by(id=task_id).first()
            if tx and tx.status == TaskExecutionStatus.RUNNING.value:
                tx.last_heartbeat = datetime.now(timezone.utc)
                session.commit()
    except Exception as e:
        logger.error(f"Failed to heartbeat task execution {task_id}: {e}")

import threading
from contextlib import contextmanager

@contextmanager
def execution_heartbeater(task_id: str, interval: int = 60):
    """
    Context manager that spawns a background thread to periodically heartbeat a TaskExecution.
    """
    stop_event = threading.Event()
    def _beat():
        while not stop_event.wait(interval):
            heartbeat_task_execution(task_id)
            
    t = threading.Thread(target=_beat, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()
        t.join(timeout=2.0)
