import asyncio
import os
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.database import AsyncSessionLocal
from backend.models.models import Clip, ClipRetention
from backend.services.virality_predictor import ViralityPredictor
from sqlalchemy.future import select
import json

async def run_test():
    async with AsyncSessionLocal() as db:
        # Find a clip with an output_path
        result = await db.execute(select(Clip).where(Clip.output_path.isnot(None)))
        clip = result.scalars().first()
        
        if not clip:
            print("No clip found. Creating a dummy clip...")
            clip = Clip(
                id="dummy_clip_123",
                video_id="dummy_vid",
                title="Dummy Clip",
                start_time=0.0,
                end_time=15.0,
                duration=15.0,
                score=9.5,
                output_path=os.path.abspath("dummy.mp4")
            )
            db.add(clip)
            await db.commit()
            print("Created dummy clip.")

        print(f"Testing ViralityPredictor on clip: {clip.id}")
        print(f"Output path: {clip.output_path}")

        predictor = ViralityPredictor()
        
        try:
            # 1. Run Analysis
            analysis = predictor.analyze_video(Path(clip.output_path), clip.id)
            overall_score = sum(p.retention_score for p in analysis.points) / max(len(analysis.points), 1)
            
            print("\n--- ANALYSIS RESULTS ---")
            print(f"Overall Score: {overall_score}")
            print(f"Number of Risks: {len(analysis.risks)}")
            for risk in analysis.risks:
                print(f" - [{risk.severity}] {risk.start_time:.1f}s to {risk.end_time:.1f}s: {risk.primary_reason}")
                
            print("\nSUCCESS: ViralityPredictor ran without crashing.")
            
            # Optionally check if DB integration works by saving it
            risks_dict = [r.dict() for r in analysis.risks]
            
            # Check if exists
            ret_result = await db.execute(select(ClipRetention).where(ClipRetention.clip_id == clip.id))
            existing = ret_result.scalars().first()
            if not existing:
                new_record = ClipRetention(
                    clip_id=clip.id,
                    overall_score=overall_score,
                    analysis_json=json.dumps(risks_dict)
                )
                db.add(new_record)
                await db.commit()
                print("SUCCESS: Retention record saved to database.")
            else:
                print("Retention record already existed for this clip.")

        except Exception as e:
            print(f"\nERROR running ViralityPredictor: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
