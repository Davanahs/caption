import os
import sys
import uuid
import json
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.models.database import SessionLocal
from backend.models.models import SFXPack, SFXAsset, ArtifactRecord
from backend.services.storage.manager import ArtifactManager

async def ingest_sfx_directory(directory: str, pack_name: str, category: str):
    """
    Scans a directory for audio files, creates an SFXPack, and ingests them as SFXAssets.
    """
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        print(f"Directory {directory} does not exist.")
        return

    db = SessionLocal()
    try:
        # Create pack
        pack_id = str(uuid.uuid4())
        pack = SFXPack(
            id=pack_id,
            name=pack_name,
            description=f"Imported from {directory}"
        )
        db.add(pack)
        await db.commit()

        manager = ArtifactManager()
        
        count = 0
        for file in dir_path.iterdir():
            if file.suffix.lower() in [".mp3", ".wav", ".aac", ".m4a"]:
                print(f"Ingesting {file.name}...")
                # 1. Upload to storage
                # Generate a unique storage key for SFX
                with open(file, "rb") as f:
                    file_data = f.read()
                
                # We mock duration for this script, ideally use ffprobe
                # For Phase 11 testing, we assume fixed duration or extract with tinytag
                duration = 2.0  
                
                record = await manager.store_artifact(
                    owner_type="sfx_pack",
                    owner_id=pack_id,
                    artifact_type="sfx_audio",
                    file_path=str(file),
                    db=db
                )
                
                asset = SFXAsset(
                    pack_id=pack_id,
                    artifact_id=record.id,
                    name=file.stem,
                    category=category,
                    duration=duration
                )
                db.add(asset)
                count += 1
                
        await db.commit()
        print(f"Successfully ingested {count} SFX assets into pack '{pack_name}'.")

    finally:
        await db.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python ingest_sfx.py <directory> <pack_name> <category>")
        sys.exit(1)
        
    asyncio.run(ingest_sfx_directory(sys.argv[1], sys.argv[2], sys.argv[3]))
