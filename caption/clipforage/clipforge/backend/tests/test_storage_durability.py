import os
import sys
import uuid
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path('.').resolve()))

from backend.core.config import settings
from backend.core.storage import storage_service, LocalStorageProvider
from backend.models.database import AsyncSessionLocal, SyncSessionLocal
from backend.models.models import Video, Job, Clip, ArtifactRecord, ArtifactType, ArtifactStatus
from backend.cleanup_storage import cleanup
from backend.models.artifact_sync import register_artifact_sync, update_artifact_status_sync

def setup_test_files(video_id: str, clip_id: str):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    upload_path = settings.UPLOAD_DIR / video_id / "source.mp4"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_text("dummy source")
    
    output_path = settings.OUTPUT_DIR / video_id / "clips" / clip_id / "final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("dummy output")
    
    return str(upload_path), str(output_path)

def test_resolution():
    print("\n--- Testing Storage Resolution ---")
    provider = storage_service
    
    # Uploads namespace
    up_key = "uploads/video123/source.mp4"
    up_path = provider.get_local_path(up_key)
    expected_up = settings.UPLOAD_DIR / "video123" / "source.mp4"
    assert up_path == expected_up, f"Upload resolution failed: {up_path} != {expected_up}"
    
    # Outputs namespace
    out_key = "outputs/video123/clips/clip123/final.mp4"
    out_path = provider.get_local_path(out_key)
    expected_out = settings.OUTPUT_DIR / "video123" / "clips" / "clip123" / "final.mp4"
    assert out_path == expected_out, f"Output resolution failed: {out_path} != {expected_out}"
    
    # Legacy key (default to upload dir)
    leg_key = "video123/source.mp4"
    leg_path = provider.get_local_path(leg_key)
    expected_leg = settings.UPLOAD_DIR / "video123" / "source.mp4"
    assert leg_path == expected_leg, f"Legacy resolution failed: {leg_path} != {expected_leg}"
    
    # Traversal attack
    trav_key = "outputs/../../windows/system32"
    assert provider.get_local_path(trav_key) is None, "Traversal was not rejected!"
    
    trav_key2 = "uploads/../outputs/test.mp4"
    # Should resolve strictly under UPLOAD_DIR despite trying to escape to outputs
    trav_path = provider.get_local_path(trav_key2)
    assert trav_path is None, f"Namespace escape was not rejected! Resolved to {trav_path}"
    
    print("Resolution tests passed.")

def test_list_prefix():
    print("\n--- Testing list_prefix ---")
    provider = storage_service
    
    # Create test files using the provider
    provider.put("uploads/test_list/a.txt", __file__)
    provider.put("outputs/test_list/b.txt", __file__)
    
    # List uploads
    up_list = provider.list_prefix("uploads/test_list")
    assert "uploads/test_list/a.txt" in up_list, "Uploads list failed"
    assert "outputs/test_list/b.txt" not in up_list, "Cross-namespace contamination"
    
    # List outputs
    out_list = provider.list_prefix("outputs/test_list")
    assert "outputs/test_list/b.txt" in out_list, "Outputs list failed"
    assert "uploads/test_list/a.txt" not in out_list, "Cross-namespace contamination"
    
    # List all (orphan detection usage)
    all_list = provider.list_prefix("")
    assert any(k.endswith("uploads/test_list/a.txt") for k in all_list), "Empty prefix missed uploads"
    assert any(k.endswith("outputs/test_list/b.txt") for k in all_list), "Empty prefix missed outputs"
    
    # Cleanup
    provider.delete("uploads/test_list/a.txt")
    provider.delete("outputs/test_list/b.txt")
    
    print("list_prefix tests passed.")

def test_cleanup_preserves_outputs():
    print("\n--- Testing Cleanup Preservation ---")
    
    vid = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    clip_id = str(uuid.uuid4())
    
    _, output_path = setup_test_files(vid, clip_id)
    out_key = f"outputs/{vid}/clips/{clip_id}/final.mp4"
    
    # Run cleanup (we mock the DB to say the job is 'done')
    # Since we can't easily patch the DB locally without dependencies, we'll just test that calling
    # the exact logic used in `cleanup` doesn't delete it.
    import backend.cleanup_storage as cs
    
    # Inject a mock DB session
    class MockQuery:
        def filter(self, *args, **kwargs): return self
        def all(self): return []
    class MockSession:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def query(self, *args): return MockQuery()
    
    import backend.models.database as db_models
    original_session = db_models.SyncSessionLocal
    db_models.SyncSessionLocal = MockSession
    try:
        cs.cleanup()
    finally:
        db_models.SyncSessionLocal = original_session
    
    # Assert
    assert Path(output_path).exists(), "Canonical output was DELETED by cleanup!"
    
    # API endpoints (simulate)
    local_path = storage_service.get_local_path(out_key)
    assert local_path and local_path.exists(), "Storage service could not resolve surviving output!"
    
    storage_service.delete(out_key)
    print("Cleanup preservation tests passed.")

if __name__ == "__main__":
    test_resolution()
    test_list_prefix()
    test_cleanup_preserves_outputs()
    print("\nALL STORAGE DURABILITY TESTS PASSED.")
