"""
Publishing Cadence Governance Service
-------------------------------------
Enforces the mandatory 2-minute (120-second) publishing interval between successive
uploads to the SAME configured YouTube destination channel.

Key Architectural Invariants:
1. Destination-Scoped: Rate limits are partitioned strictly by destination channel ID.
   Publishing to Channel A never delays or throttles publishing to Channel B.
2. Non-Blocking Worker Concurrency: When an upload for a destination arrives before the
   2-minute cadence has elapsed, Celery tasks raise self.retry(countdown=wait_sec).
   The worker process is IMMEDIATELY freed to process other tasks without sleeping.
3. Durable Distributed Coordination: Uses Redis atomic reservation with PostgreSQL row/target
   fallback to prevent race conditions across concurrent workers.
4. Privacy & Idempotency Preserved: Cadence delays preserve original privacy defaults,
   stable idempotency keys, and manual-review states.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy import func, or_
from backend.core.config import settings
from backend.models.database import SyncSessionLocal

logger = logging.getLogger("clipforge.publishing_cadence")

MIN_PUBLISH_INTERVAL_SEC: float = 120.0  # 2 minutes minimum gap

_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1.5)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.debug(f"[Publish Cadence] Redis not available for cadence, falling back to DB: {e}")
        return None


def resolve_canonical_destination(dest_ref: str, session=None) -> Tuple[str, str]:
    """
    Resolves any destination reference (channel internal ID or youtube_channel_id)
    to a canonical tuple (internal_channel_id, youtube_channel_id).
    """
    from backend.models.models import Channel
    
    close_session = False
    if session is None:
        session = SyncSessionLocal()
        close_session = True
        
    try:
        ch = session.query(Channel).filter(
            or_(Channel.id == dest_ref, Channel.youtube_channel_id == dest_ref)
        ).first()
        if ch:
            return (ch.id, ch.youtube_channel_id)
        return (dest_ref, dest_ref)
    finally:
        if close_session:
            session.close()


def check_and_reserve_destination_cadence(
    destination_ref: str,
    min_interval_sec: float = MIN_PUBLISH_INTERVAL_SEC,
    now_ts: Optional[float] = None
) -> float:
    """
    Checks if the destination channel is currently eligible to publish immediately,
    or calculates the required delay (wait_sec) in seconds.
    
    If eligible (wait_sec <= 0), it atomically reserves the slot and advances the
    destination's next allowed publication timestamp.
    
    Returns:
        wait_sec: Number of seconds to wait before publishing can start.
                  0.0 indicates immediate publication is allowed.
    """
    if not destination_ref:
        return 0.0

    internal_id, yt_id = resolve_canonical_destination(destination_ref)
    canonical_key_id = yt_id or internal_id
    current_ts = time.time() if now_ts is None else now_ts

    redis_cli = get_redis_client()
    if redis_cli:
        key = f"publish:cadence:dest:{canonical_key_id}:next_allowed_ts"
        lock_key = f"publish:cadence:dest:{canonical_key_id}:lock"
        
        # Acquire short distributed lock (max 5s) for atomic reservation
        lock_acquired = False
        try:
            lock_acquired = bool(redis_cli.set(lock_key, "1", nx=True, ex=5))
            if not lock_acquired:
                # If contested, wait 50ms and check value
                time.sleep(0.05)
                val = redis_cli.get(key)
                if val:
                    next_allowed = float(val)
                    if next_allowed > current_ts:
                        return next_allowed - current_ts

            val = redis_cli.get(key)
            if val:
                next_allowed = float(val)
                if next_allowed > current_ts:
                    wait_sec = next_allowed - current_ts
                    # Reserve consecutive slot for queued task
                    new_next = next_allowed + min_interval_sec
                    redis_cli.setex(key, int(min_interval_sec * 3), str(new_next))
                    return wait_sec

            # Slot is available immediately
            new_next = current_ts + min_interval_sec
            redis_cli.setex(key, int(min_interval_sec * 3), str(new_next))
            return 0.0
        except Exception as r_err:
            logger.warning(f"[Publish Cadence] Redis error in cadence reservation: {r_err}")
        finally:
            if lock_acquired:
                try:
                    redis_cli.delete(lock_key)
                except Exception:
                    pass

    # Database-backed fallback using PostgreSQL transaction & last published timestamp
    from backend.models.models import PublishTarget, Clip
    with SyncSessionLocal() as session:
        # Check PublishTarget completion timestamps for this destination
        last_target_dt = session.query(func.max(PublishTarget.published_at)).filter(
            PublishTarget.destination_id == internal_id,
            PublishTarget.status == "completed"
        ).scalar()
        
        # Check Clip publish timestamps for this destination
        last_clip_dt = session.query(func.max(Clip.published_at)).filter(
            Clip.publish_destination_id == internal_id,
            Clip.youtube_short_id != None
        ).scalar()
        
        candidates = [dt for dt in (last_target_dt, last_clip_dt) if dt is not None]
        if candidates:
            most_recent = max(candidates)
            if most_recent.tzinfo is None:
                most_recent = most_recent.replace(tzinfo=timezone.utc)
            now_dt = datetime.fromtimestamp(current_ts, tz=timezone.utc)
            elapsed = (now_dt - most_recent).total_seconds()
            if elapsed < min_interval_sec:
                return min_interval_sec - elapsed

    return 0.0


def record_destination_published(
    destination_ref: str,
    published_at: Optional[datetime] = None
) -> None:
    """
    Records that an upload has just completed for this destination,
    updating the distributed cadence ledger.
    """
    if not destination_ref:
        return
    internal_id, yt_id = resolve_canonical_destination(destination_ref)
    canonical_key_id = yt_id or internal_id
    
    now_dt = published_at or datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    
    redis_cli = get_redis_client()
    if redis_cli:
        key = f"publish:cadence:dest:{canonical_key_id}:next_allowed_ts"
        new_next = now_ts + MIN_PUBLISH_INTERVAL_SEC
        try:
            redis_cli.setex(key, int(MIN_PUBLISH_INTERVAL_SEC * 3), str(new_next))
        except Exception as e:
            logger.warning(f"[Publish Cadence] Failed to update Redis cadence after publish: {e}")


def reset_destination_cadence(destination_ref: str) -> None:
    """
    Clears cadence records for a destination. Useful for test isolation.
    """
    if not destination_ref:
        return
    internal_id, yt_id = resolve_canonical_destination(destination_ref)
    canonical_key_id = yt_id or internal_id
    redis_cli = get_redis_client()
    if redis_cli:
        try:
            redis_cli.delete(f"publish:cadence:dest:{canonical_key_id}:next_allowed_ts")
            redis_cli.delete(f"publish:cadence:dest:{canonical_key_id}:lock")
        except Exception:
            pass
