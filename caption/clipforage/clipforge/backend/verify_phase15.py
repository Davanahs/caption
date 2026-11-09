import asyncio
import os
import uuid
import sys

# Ensure correct working directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.models.database import SyncSessionLocal
from backend.models.models import Clip, Video, ClipVariant, ArtifactRecord
from backend.models.dubbing import DubbingRequest
from backend.tasks.dubbing_tasks import generate_dubbing_variant_task


def setup_test_data():
    with SyncSessionLocal() as session:
        from backend.models.models import Job
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            status="completed"
        )
        session.add(job)
        
        # Create a dummy video
        video_id = str(uuid.uuid4())
        video = Video(
            id=video_id,
            youtube_url="https://youtube.com/watch?v=dummy",
            title="Phase 15 Test Video",
            local_path="dummy.mp4"
        )
        session.add(video)
        
        # Create a dummy clip
        clip_id = str(uuid.uuid4())
        clip = Clip(
            id=clip_id,
            video_id=video_id,
            start_time=0.0,
            end_time=8.0,
            duration=8.0,
            transcript_segment="Hello world. This is a test of Phase 15 multi language dubbing.",
            score=95
        )
        session.add(clip)
        
        # Create a dummy artifact and video_render variant for the clip
        artifact_id = str(uuid.uuid4())
        # We need a real file to exist to not fail ffmpeg. Let's create an empty mp4
        dummy_mp4 = f"dummy_phase15_{uuid.uuid4()}.mp4"
        os.system(f'ffmpeg -y -f lavfi -i color=c=black:s=1280x720:r=30 -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t 5 {dummy_mp4} -v error')
            
        artifact = ArtifactRecord(
            id=artifact_id,
            owner_type="clip",
            owner_id=clip_id,
            artifact_type="video_render",
            storage_key=dummy_mp4,
            backend="local",
            status="ready",
            retention_policy="keep"
        )
        session.add(artifact)
        
        variant = ClipVariant(
            clip_id=clip_id,
            variant_type="video_render",
            artifact_id=artifact_id,
            status="completed"
        )
        session.add(variant)
        
        session.commit()
        return clip_id, job_id

def verify_idempotency(clip_id: str, job_id: str):
    print(f"=== Verifying Phase 15 Idempotency ===")
    request_dict = {
        "job_id": job_id,
        "clip_id": clip_id,
        "target_language": "es",
        "voice_provider": "edge_tts",
        "voice_id": "es-ES-AlvaroNeural",
        "is_voice_clone": False,
        "authorization_granted": False,
        "plan_version": "v1"
    }
    
    print("1. Running first time...")
    res1 = generate_dubbing_variant_task(request_dict)
    print(f"Result 1: {res1}")
    assert res1["status"] == "completed", "First run should complete"
    var_id1 = res1["variant_id"]
    
    print("2. Running second time (same inputs)...")
    res2 = generate_dubbing_variant_task(request_dict)
    print(f"Result 2: {res2}")
    assert res2["status"] == "skipped", "Second run should be skipped due to idempotency"
    assert res2["variant_id"] == var_id1, "Variant ID should match"
    
    print("3. Running third time (different language - Hindi)...")
    request_dict["target_language"] = "hi"
    request_dict["voice_id"] = "hi-IN-MadhurNeural"
    res3 = generate_dubbing_variant_task(request_dict)
    print(f"Result 3: {res3}")
    assert res3["status"] == "completed", "Third run should complete (different language)"
    var_id3 = res3["variant_id"]
    assert var_id3 != var_id1, "Variant IDs should differ"
    
    print("4. Running fourth time (Voice clone without authorization)...")
    request_dict["is_voice_clone"] = True
    request_dict["authorization_granted"] = False
    request_dict["voice_provider"] = "elevenlabs"
    request_dict["target_language"] = "es"
    try:
        generate_dubbing_variant_task(request_dict)
        print("FAIL: Expected ValueError/Exception due to unauthorized clone")
    except Exception as e:
        print(f"PASS: Caught expected error for unauthorized clone: {e}")
        
    print("5. Running fifth time (Voice clone with authorization)...")
    request_dict["authorization_granted"] = True
    res5 = generate_dubbing_variant_task(request_dict)
    print(f"Result 5: {res5}")
    assert res5["status"] == "completed", "Fifth run should complete (authorized clone)"
    
    print("Idempotency verification passed!")

if __name__ == "__main__":
    clip_id, job_id = setup_test_data()
    verify_idempotency(clip_id, job_id)
