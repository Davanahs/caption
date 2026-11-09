import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.future import select
from backend.tasks.celery_app import celery_app
from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS
from backend.models.database import AsyncSessionLocal
from backend.models.models import ArtifactRecord, ArtifactStatus
from backend.core.storage import storage_service
from backend.core.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)

async def _cleanup_expired_artifacts():
    """Finds expired artifacts and quarantines them. If already quarantined and expired, deletes them."""
    from datetime import timedelta
    
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        
        # 1. Find artifacts that are expired and not yet quarantined
        result_to_quarantine = await db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.expires_at < now,
                ArtifactRecord.status.in_([
                    ArtifactStatus.CREATED.value,
                    ArtifactStatus.PROCESSING.value,
                    ArtifactStatus.READY.value, 
                    ArtifactStatus.FAILED.value, 
                    ArtifactStatus.EXPIRED.value
                ])
            )
        )
        to_quarantine = result_to_quarantine.scalars().all()
        
        for record in to_quarantine:
            logger.info(f"Quarantining expired artifact {record.storage_key}")
            record.status = ArtifactStatus.QUARANTINED.value
            # Extend expires_at by 7 days for the quarantine period
            record.expires_at = now + timedelta(days=7)
            
        await db.commit()
        
        # 2. Find artifacts that are in quarantine and their quarantine period has expired
        result_to_delete = await db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.expires_at < now,
                ArtifactRecord.status == ArtifactStatus.QUARANTINED.value
            )
        )
        to_delete = result_to_delete.scalars().all()
        
        for record in to_delete:
            logger.info(f"Cleaning up quarantined artifact {record.storage_key}")
            
            record.status = ArtifactStatus.DELETING.value
            await db.commit()
            
            try:
                storage_service.delete(record.storage_key)
                record.status = ArtifactStatus.DELETED.value
            except Exception as e:
                logger.error(f"Failed to delete artifact {record.storage_key}: {e}")
                record.status = ArtifactStatus.FAILED.value
                
            await db.commit()

async def _detect_orphans():
    """Scans the storage backend for files that are not tracked in ArtifactRecord and quarantines them."""
    from datetime import timedelta
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ArtifactRecord.storage_key))
        tracked_keys = {row[0] for row in result.all()}
        
        # list_prefix("") works for both local and s3 backends to recursively get all keys
        try:
            all_files = storage_service.list_prefix("")
        except Exception as e:
            logger.error(f"Failed to list prefix for orphan detection: {e}")
            return
            
        orphans = [f for f in all_files if f not in tracked_keys]
        
        for orphan in orphans:
            # Skip hidden files or directories
            if "/." in orphan or orphan.startswith(".") or orphan.endswith("/"):
                continue
                
            logger.warning(f"Orphan detected: {orphan} - Adding to quarantine.")
            
            now = datetime.now(timezone.utc)
            record = ArtifactRecord(
                owner_type="system",
                owner_id="orphan",
                artifact_type="unknown",
                storage_key=orphan,
                status=ArtifactStatus.QUARANTINED.value,
                retention_policy="temporary",
                local_filepath=None,
                expires_at=now + timedelta(days=7)
            )
            db.add(record)
            
        if orphans:
            await db.commit()

@celery_app.task(**DEFAULT_RETRY_KWARGS)
def cleanup_expired_artifacts_task():
    """Celery task to trigger artifact cleanup."""
    asyncio.run(_cleanup_expired_artifacts())

@celery_app.task(**DEFAULT_RETRY_KWARGS)
def detect_orphans_task():
    """Celery task to detect orphans."""
    asyncio.run(_detect_orphans())
