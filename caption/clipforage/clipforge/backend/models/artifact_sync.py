from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from typing import Optional
from backend.core.config import settings
from backend.models.models import ArtifactRecord, ArtifactStatus, ArtifactType
from backend.core.storage import storage_service
from backend.models.models import Video, Clip
from datetime import datetime, timezone, timedelta

# Create a sync engine for synchronous Celery tasks
sync_engine = create_engine(settings.SYNC_DATABASE_URL)

def _validate_owner_sync(session: Session, owner_type: str, owner_id: str):
    if owner_type == "video":
        if not session.query(Video).filter(Video.id == owner_id).first():
            raise ValueError(f"Invalid owner: Video {owner_id} does not exist.")
    elif owner_type == "clip":
        if not session.query(Clip).filter(Clip.id == owner_id).first():
            raise ValueError(f"Invalid owner: Clip {owner_id} does not exist.")
    elif owner_type == "job":
        pass
    else:
        raise ValueError(f"Invalid owner_type: {owner_type}")

def register_artifact_sync(
    owner_type: str,
    owner_id: str,
    artifact_type: ArtifactType,
    storage_key: str,
    retention_policy: str,
    local_filepath: Optional[str] = None,
    processing_version: Optional[str] = None
) -> dict:
    """Synchronous version of ArtifactManager.register_artifact"""
    with Session(sync_engine) as session:
        _validate_owner_sync(session, owner_type, owner_id)
        
        record = session.query(ArtifactRecord).filter(ArtifactRecord.storage_key == storage_key).first()
        
        if record:
            if local_filepath:
                storage_service.put(storage_key, local_filepath)
                meta = storage_service.metadata(storage_key)
                record.size_bytes = meta.get("size_bytes")
                record.checksum = storage_service.checksum(local_filepath)
                
            record.status = ArtifactStatus.CREATED.value
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
                
            session.add(record)
            
        session.commit()
        session.refresh(record)
        return {
            "id": record.id,
            "storage_key": record.storage_key,
            "status": record.status
        }

def update_artifact_status_sync(
    storage_key: str,
    status: ArtifactStatus,
    set_expiration: bool = False
) -> Optional[dict]:
    with Session(sync_engine) as session:
        record = session.query(ArtifactRecord).filter(ArtifactRecord.storage_key == storage_key).first()
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
                
        session.commit()
        session.refresh(record)
        return {
            "id": record.id,
            "storage_key": record.storage_key,
            "status": record.status,
            "expires_at": record.expires_at
        }

def check_artifact_exists_sync(storage_key: str) -> bool:
    """Returns True if the artifact is in the database AND has status CREATED or READY"""
    with Session(sync_engine) as session:
        record = session.query(ArtifactRecord).filter(ArtifactRecord.storage_key == storage_key).first()
        if record and record.status in (ArtifactStatus.CREATED.value, ArtifactStatus.READY.value):
            return True
    return False

def retrieve_to_local_sync(storage_key: str, dest_path: str) -> bool:
    with Session(sync_engine) as session:
        record = session.query(ArtifactRecord).filter(ArtifactRecord.storage_key == storage_key).first()
        if not record or record.status in (ArtifactStatus.DELETED.value, ArtifactStatus.EXPIRED.value):
            return False
            
    if storage_service.exists(storage_key):
        storage_service.get(storage_key, dest_path)
        return True
    return False

import tempfile
import os
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

@contextmanager
def managed_download_sync(artifact_id: Optional[str] = None, storage_key: Optional[str] = None):
    """
    Context manager that resolves an artifact by ID or storage_key,
    downloads it to a secure temporary path, yields the path, and
    cleans up the temporary path upon exit.
    """
    if not artifact_id and not storage_key:
        raise ValueError("Must provide either artifact_id or storage_key")
        
    with Session(sync_engine) as session:
        query = session.query(ArtifactRecord)
        if artifact_id:
            record = query.filter_by(id=artifact_id).first()
        else:
            record = query.filter_by(storage_key=storage_key).first()
            
        if not record:
            raise ValueError(f"Artifact not found")
        if record.status not in (ArtifactStatus.READY.value, ArtifactStatus.CREATED.value):
            raise ValueError(f"Artifact is not in a ready state. Status: {record.status}")
            
        resolved_key = record.storage_key
        
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

@contextmanager
def managed_upload_sync(
    owner_type: str,
    owner_id: str,
    artifact_type: ArtifactType,
    storage_key: str,
    retention_policy: str,
    processing_version: Optional[str] = None
):
    """
    Context manager that yields a secure temporary path for writing.
    Upon successful exit, it validates the file, uploads to storage,
    verifies the upload, and atomically registers/promotes the ArtifactRecord.
    If an exception occurs within the context, the file is cleaned up and no record is made.
    """
    # Pre-validate owner to prevent orphaned uploads if the parent was deleted
    with Session(sync_engine) as session:
        _validate_owner_sync(session, owner_type, owner_id)
        
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
        record_info = register_artifact_sync(
            owner_type=owner_type,
            owner_id=owner_id,
            artifact_type=artifact_type,
            storage_key=storage_key,
            retention_policy=retention_policy,
            local_filepath=temp_path,
            processing_version=processing_version
        )
        update_artifact_status_sync(storage_key, ArtifactStatus.READY, set_expiration=True)
        
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Failed to clean up temporary upload path {temp_path}: {e}")
