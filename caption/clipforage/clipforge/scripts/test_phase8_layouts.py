import asyncio
import os
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.reframe_engine import reframe_to_vertical
from backend.services.output_validator import validate_video_output
from backend.models.layout import LayoutPlan, ScaleMode
from backend.services.layout_engine import LayoutEngine

async def run_verification():
    # 1. Create a dummy landscape video
    scratch_dir = Path("C:/Users/Chinmaygouda/.gemini/antigravity-ide/brain/bd8ba98f-b065-4627-aa9f-197f9b7c7248/scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    
    input_vid = scratch_dir / "dummy_landscape_p8.mp4"
    if not input_vid.exists():
        logger.info("Generating dummy input video...")
        cmd = f"ffmpeg -f lavfi -i testsrc=duration=5:size=1920x1080:rate=30 -f lavfi -i sine=frequency=1000:duration=5 -c:v libx264 -c:a aac -preset fast -y {input_vid}"
        os.system(cmd)
        
    output_split = scratch_dir / "output_split_p8.mp4"
    output_blur = scratch_dir / "output_blur_p8.mp4"
    
    # Test Split Mode
    logger.info("Testing SPLIT mode via legacy string mode...")
    await reframe_to_vertical(input_vid, output_split, mode="split")
    validate_video_output(output_split, expected_width=1080, expected_height=1920, require_audio=True)
    logger.info("SPLIT mode passed!")
    
    # Test Blur Mode
    logger.info("Testing BLUR mode via legacy string mode...")
    await reframe_to_vertical(input_vid, output_blur, mode="blur")
    validate_video_output(output_blur, expected_width=1080, expected_height=1920, require_audio=True)
    logger.info("BLUR mode passed!")
    
    # Test Dynamic Face Mode (Simulated)
    output_face = scratch_dir / "output_face_p8.mp4"
    logger.info("Testing FACE (dynamic crop) mode via legacy string mode...")
    await reframe_to_vertical(input_vid, output_face, mode="crop")
    validate_video_output(output_face, expected_width=1080, expected_height=1920, require_audio=True)
    logger.info("FACE mode passed!")
    
    # Test Explicit LayoutPlan injection
    output_plan = scratch_dir / "output_plan_p8.mp4"
    logger.info("Testing explicitly injected LayoutPlan...")
    plan = LayoutEngine.create_vertical_plan(1920, 1080, 1080, 1920)
    plan.regions[0].scale_mode = ScaleMode.CROP
    await reframe_to_vertical(input_vid, output_plan, plan=plan)
    validate_video_output(output_plan, expected_width=1080, expected_height=1920, require_audio=True)
    logger.info("Explicit LayoutPlan mode passed!")

    logger.info("All Phase 8 layout verifications passed successfully.")

if __name__ == "__main__":
    asyncio.run(run_verification())
