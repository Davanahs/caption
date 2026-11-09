import logging
import uuid
from datetime import datetime, timezone
from backend.models.database import SyncSessionLocal
from backend.models.models import PipelineMetrics
from backend.core.config import settings

logger = logging.getLogger("clipforge.pipeline_analytics")

# Typical thresholds in ms (log warning if exceeded)
THRESHOLDS_MS = {
    "video download": 180000,  # 3 min
    "transcription": 120000,  # 2 min
    "scene detection": 120000,  # 2 min
    "clip scoring": 60000,  # 1 min
    "metadata generation": 30000,  # 30 s
    "seo analysis": 5000,  # 5 s
    "ffmpeg processing": 180000,  # 3 min
    "upload": 300000,  # 5 min
    "optimization": 30000,  # 30 s
    "tracker execution": 30000,  # 30 s
}


def start_phase(clip_id: str, phase_name: str) -> datetime:
    """Marks the start of a pipeline phase."""
    now = datetime.now(timezone.utc)
    logger.info(
        f"[PipelineAnalytics] Phase '{phase_name}' started for clip_id={clip_id} at {now.isoformat()}"
    )
    return now


def complete_phase(
    clip_id: str,
    phase_name: str,
    started_at: datetime,
    success: bool = True,
    error_message: str = None,
) -> int:
    """Marks the completion of a pipeline phase, calculates duration, and records metrics."""
    completed_at = datetime.now(timezone.utc)
    duration_delta = completed_at - started_at
    duration_ms = int(duration_delta.total_seconds() * 1000)

    logger.info(
        f"[PipelineAnalytics] Phase '{phase_name}' completed for clip_id={clip_id} in {duration_ms} ms. "
        f"Success: {success}"
        + (f" | Error: {error_message}" if error_message else "")
    )

    # Log warning if threshold exceeded
    threshold = THRESHOLDS_MS.get(phase_name)
    if threshold and duration_ms > threshold:
        logger.warning(
            f"[PipelineAnalytics] ⚠ SLOW PHASE detected: '{phase_name}' took {duration_ms} ms (threshold: {threshold} ms)"
        )

    # Store in database
    try:
        with SyncSessionLocal() as session:
            metric = PipelineMetrics(
                id=str(uuid.uuid4()),
                clip_id=clip_id,
                phase_name=phase_name,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message
            )
            session.add(metric)
            session.commit()
    except Exception as db_err:
        logger.error(f"[PipelineAnalytics] DB write error: {db_err}")

    return duration_ms
