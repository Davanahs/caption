import asyncio
from pathlib import Path
import sys
import os

# Add parent directory to path so we can import backend packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.clip_cutter import extract_thumbnail
from backend.services.reframe_engine import reframe_to_vertical

async def main():
    input_path = Path("/app/uploads/dummy_landscape.mp4")
    
    # 1. Test Blur Mode
    blur_output = Path("/app/outputs/test_vertical_blur.mp4")
    blur_thumb = Path("/app/outputs/test_vertical_blur_thumb.jpg")
    print("\n--- Testing Blur Mode Reframer ---")
    res_blur = await reframe_to_vertical(input_path, blur_output, mode="blur")
    print(f"Blur Video saved to: {res_blur}")
    print("Extracting thumbnail for blur mode...")
    thumb_blur = await extract_thumbnail(blur_output, blur_thumb, time=1.0)
    print(f"Blur Thumbnail saved to: {thumb_blur}")

    # 2. Test Crop Mode
    crop_output = Path("/app/outputs/test_vertical_crop.mp4")
    crop_thumb = Path("/app/outputs/test_vertical_crop_thumb.jpg")
    print("\n--- Testing Crop Mode Reframer ---")
    res_crop = await reframe_to_vertical(input_path, crop_output, mode="crop")
    print(f"Crop Video saved to: {res_crop}")
    print("Extracting thumbnail for crop mode...")
    thumb_crop = await extract_thumbnail(crop_output, crop_thumb, time=1.0)
    print(f"Crop Thumbnail saved to: {thumb_crop}")

    print("\nReframer and Thumbnail test complete!")

if __name__ == "__main__":
    asyncio.run(main())
