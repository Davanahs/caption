import uuid
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.models import ArtifactRecord, ArtifactStatus, ArtifactType
from backend.core.storage import storage_service
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

class ArtifactManager:
    """Manages the lifecycle, ownership, and state of artifacts."""

    async def resolve_artifact_path(self, artifact_id: str) -> Optional[str]:
        # For Pass 1 verification, we stored the raw local path as the storage_key
        # in the managed_upload_sync call (we passed storage_key=f"artifacts/{art.artifact_id}.wav", local_filepath=art.storage_key)
        # We need to query the sync engine for the artifact and return its local path if possible.
        from backend.models.artifact_sync import sync_engine
        from sqlalchemy.orm import Session
        with Session(sync_engine) as session:
            record = session.query(ArtifactRecord).filter(
                (ArtifactRecord.id == artifact_id) | (ArtifactRecord.storage_key.like(f"%{artifact_id}%"))
            ).first()
            if not record:
                from backend.models.models import SFXAsset, VisualAsset
                sfx_a = session.query(SFXAsset).filter_by(id=artifact_id).first()
                if sfx_a and sfx_a.artifact_id:
                    record = session.query(ArtifactRecord).filter_by(id=sfx_a.artifact_id).first()
                else:
                    vis_a = session.query(VisualAsset).filter_by(id=artifact_id).first()
                    if vis_a and vis_a.artifact_id:
                        record = session.query(ArtifactRecord).filter_by(id=vis_a.artifact_id).first()
            if record:
                # If the backend is local, the storage_key might be the path, or we can use storage_service
                # We'll just return the storage_service path for it.
                from backend.core.storage import storage_service
                # storage_service.get local path? No, storage_service is a physical backend.
                # In verification, we can just return the storage key itself if it's an absolute path, 
                # or download it.
                # Let's download it to temp
                import tempfile, os
                ext = os.path.splitext(record.storage_key)[1] or ".tmp"
                fd, temp_path = tempfile.mkstemp(prefix="resolved_art_", suffix=ext)
                os.close(fd)
                if storage_service.exists(record.storage_key):
                    storage_service.get(record.storage_key, temp_path)
                    return temp_path
                elif os.path.exists(record.storage_key):
                    return record.storage_key
        return None

    @staticmethod
    async def register_artifact(
        db: AsyncSession,
        owner_type: str,
        owner_id: str,
        artifact_type: ArtifactType,
        storage_key: str,
        retention_policy: str,
        local_filepath: Optional[str] = None,
        processing_version: Optional[str] = None
    ) -> ArtifactRecord:
        """
        Validates ownership and registers an artifact. 
        If local_filepath is provided, puts the file into storage immediately.
        """
        await ArtifactManager._validate_owner(db, owner_type, owner_id)

        # Check if we already have an artifact for this key
        existing = await db.execute(
            select(ArtifactRecord).where(ArtifactRecord.storage_key == storage_key)
        )
        record = existing.scalar_one_or_none()

        if record:
            # Overwrite scenario (e.g. retry)
            if local_filepath:
                storage_service.put(storage_key, local_filepath)
                meta = storage_service.metadata(storage_key)
                record.size_bytes = meta.get("size_bytes")
                record.checksum = storage_service.checksum(local_filepath)
            
            record.status = ArtifactStatus.CREATED
            record.processing_version = processing_version
            record.backend = storage_service.backend_type
            record.retention_policy = retention_policy
        else:
            record = ArtifactRecord(
                owner_type=owner_type,
                owner_id=owner_id,
                artifact_type=artifact_type.value,
                storage_key=storage_key,
                backend=storage_service.backend_type,
                status=ArtifactStatus.CREATED.value,
                retention_policy=retention_policy,
                processing_version=processing_version
            )
            
            if local_filepath:
                storage_service.put(storage_key, local_filepath)
                meta = storage_service.metadata(storage_key)
                record.size_bytes = meta.get("size_bytes")
                record.checksum = storage_service.checksum(local_filepath)

            db.add(record)
        
        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def update_status(
        db: AsyncSession, 
        storage_key: str, 
        status: ArtifactStatus,
        set_expiration: bool = False
    ) -> Optional[ArtifactRecord]:
        """Update artifact status, optionally calculating expiration based on retention policy."""
        result = await db.execute(
            select(ArtifactRecord).where(ArtifactRecord.storage_key == storage_key)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        record.status = status.value
        
        if set_expiration:
            if record.retention_policy == "temporary":
                hours = settings.RETENTION_TEMP_HOURS
                record.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
            elif record.retention_policy == "persistent":
                days = settings.RETENTION_PERSISTENT_DAYS
                record.expires_at = datetime.now(timezone.utc) + timedelta(days=days)

        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_artifact(db: AsyncSession, storage_key: str) -> Optional[ArtifactRecord]:
        result = await db.execute(
            select(ArtifactRecord).where(ArtifactRecord.storage_key == storage_key)
        )
        return result.scalar_one_or_none()
        
    @staticmethod
    async def delete_artifact(db: AsyncSession, artifact_id: str) -> bool:
        """Safely deletes an artifact record and its physical file if no other active records share it."""
        from backend.models.models import ArtifactStatus
        
        record_res = await db.execute(select(ArtifactRecord).where(ArtifactRecord.id == artifact_id))
        record = record_res.scalar_one_or_none()
        if not record or record.status == ArtifactStatus.DELETED.value:
            return False

        # Check if physical file is shared by other active records
        shared_res = await db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.storage_key == record.storage_key,
                ArtifactRecord.id != artifact_id,
                ArtifactRecord.status != ArtifactStatus.DELETED.value
            )
        )
        shared_records = shared_res.scalars().all()
        
        if not shared_records:
            # Safe to delete physical file because no other active record references it
            try:
                storage_service.delete(record.storage_key)
            except Exception as e:
                logger.error(f"Failed to delete physical artifact {record.storage_key}: {e}")
                
        # Mark the record deleted
        record.status = ArtifactStatus.DELETED.value
        await db.commit()
        return True
        
    @staticmethod
    async def retrieve_to_local(db: AsyncSession, storage_key: str, dest_path: str) -> bool:
        """Retrieve an artifact from storage to a local path if it exists."""
        record = await ArtifactManager.get_artifact(db, storage_key)
        if not record or record.status in (ArtifactStatus.DELETED.value, ArtifactStatus.EXPIRED.value):
            return False
            
        if storage_service.exists(storage_key):
            storage_service.get(storage_key, dest_path)
            return True
        return False

    @staticmethod
    async def _validate_owner(db: AsyncSession, owner_type: str, owner_id: str):
        """Validates that the owner exists in the database to prevent orphaned references."""
        from backend.models.models import Video, Clip
        
        if owner_type == "video":
            res = await db.execute(select(Video).where(Video.id == owner_id))
            if not res.scalar_one_or_none():
                raise ValueError(f"Invalid owner: Video {owner_id} does not exist.")
        elif owner_type == "clip":
            res = await db.execute(select(Clip).where(Clip.id == owner_id))
            if not res.scalar_one_or_none():
                raise ValueError(f"Invalid owner: Clip {owner_id} does not exist.")
        elif owner_type == "job":
            # For simplicity, if we have a job table we'd check it here
            pass
        else:
            raise ValueError(f"Invalid owner_type: {owner_type}")

    @staticmethod
    @asynccontextmanager
    async def managed_download(db: AsyncSession, artifact_id: Optional[str] = None, storage_key: Optional[str] = None):
        """
        Async context manager that resolves an artifact by ID or storage_key,
        downloads it to a secure temporary path, yields the path, and
        cleans up the temporary path upon exit.
        """
        if not artifact_id and not storage_key:
            raise ValueError("Must provide either artifact_id or storage_key")
            
        if artifact_id:
            res = await db.execute(select(ArtifactRecord).where(ArtifactRecord.id == artifact_id))
        else:
            res = await db.execute(select(ArtifactRecord).where(ArtifactRecord.storage_key == storage_key))
            
        record = res.scalar_one_or_none()
        if not record:
            raise ValueError("Artifact not found")
        if record.status not in (ArtifactStatus.READY.value, ArtifactStatus.CREATED.value):
            raise ValueError(f"Artifact is not in a ready state. Status: {record.status}")
            
        resolved_key = record.storage_key
        
        import tempfile
        import os
        fd, temp_path = tempfile.mkstemp(prefix="clipforge_managed_dl_")
        os.close(fd)
        
        try:
            if not storage_service.exists(resolved_key):
                raise FileNotFoundError(f"Storage key {resolved_key} missing from physical backend")
            storage_service.get(resolved_key, temp_path)
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.error(f"Failed to clean up temporary download path {temp_path}: {e}")

    @staticmethod
    @asynccontextmanager
    async def managed_upload(
        db: AsyncSession,
        owner_type: str,
        owner_id: str,
        artifact_type: ArtifactType,
        storage_key: str,
        retention_policy: str,
        processing_version: Optional[str] = None
    ):
        """
        Async context manager that yields a secure temporary path for writing.
        Upon successful exit, it validates the file, uploads to storage,
        verifies the upload, and atomically registers/promotes the ArtifactRecord.
        If an exception occurs within the context, the file is cleaned up and no record is made.
        """
        import tempfile
        import os
        fd, temp_path = tempfile.mkstemp(prefix="clipforge_managed_ul_")
        os.close(fd)
        
        try:
            yield temp_path
            
            # Validation
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                raise ValueError("Generated artifact is missing or empty")
                
            # Upload
            storage_service.put(storage_key, temp_path)
            
            # Verify
            if not storage_service.exists(storage_key):
                raise RuntimeError(f"Upload verification failed for {storage_key}")
                
            # Atomic Promotion
            await ArtifactManager.register_artifact(
                db=db,
                owner_type=owner_type,
                owner_id=owner_id,
                artifact_type=artifact_type,
                storage_key=storage_key,
                retention_policy=retention_policy,
                local_filepath=temp_path,
                processing_version=processing_version
            )
            await ArtifactManager.update_status(db, storage_key, ArtifactStatus.READY, set_expiration=True)
            
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.error(f"Failed to clean up temporary upload path {temp_path}: {e}")

artifact_manager = ArtifactManager()
