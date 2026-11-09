import asyncio
from sqlalchemy import select
from backend.models.database import AsyncSessionLocal
from backend.models.models import Job, Clip, ArtifactRecord
import time

async def main():
    job_id = "ddfa7a81-f295-4f29-b1a1-22e39a0da112"
    print(f"Monitoring Job ID: {job_id}")
    
    while True:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if not job:
                    print("Job not found!")
                    return
                
                if job.status in ["completed", "completed_with_failures", "failed"]:
                    print(f"\nTerminal State Reached: {job.status}")
                    print(f"Progress: {job.progress}")
                    print(f"Video ID: {getattr(job, 'video_id', 'N/A')}")
                    
                    print("\n--- RESULTS ---")
                    
                    # Get clips
                    clips_result = await session.execute(select(Clip).where(Clip.job_id == job.id))
                    clips = clips_result.scalars().all()
                    print(f"\nGenerated Clips ({len(clips)}):")
                    for clip in clips:
                        print(f"  Clip ID: {clip.id}")
                        print(f"  Status: {clip.status}")
                        print(f"  Output Path: {clip.output_path}")
                        print(f"  Thumbnail Path: {clip.thumbnail_path}")

                    # Get artifacts
                    print("\nArtifacts:")
                    artifacts_result = await session.execute(select(ArtifactRecord).where(ArtifactRecord.processing_version == job.id))
                    artifacts = artifacts_result.scalars().all()
                    for art in artifacts:
                        print(f"  Artifact ID: {art.id} | Type: {art.artifact_type} | Key: {art.storage_key} | Status: {art.status}")
                    break
                
                print(f"Status: {job.status} (Progress: {job.progress}%)")
            time.sleep(5)
            
if __name__ == "__main__":
    asyncio.run(main())
