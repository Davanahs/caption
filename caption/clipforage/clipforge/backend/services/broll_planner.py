import json
import hashlib
import uuid
import asyncio
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.models import VisualAsset, ClipVisualPlan, ArtifactType
from backend.models.broll import (
    VisualOpportunity, 
    VisualAssetRef, 
    BrollPlacement, 
    BrollPlan,
    DisplayMode
)
from backend.services.artifact_manager import artifact_manager
from backend.services.contextual_visual_analyzer import ContextualVisualAnalyzer
from backend.services.pexels_service import pexels_service
from backend.core.storage import storage_service

class BrollPlanner:
    """
    Plans contextual B-roll placement based on transcript and visual assets.
    """
    
    @staticmethod
    async def _is_trusted_test_clip(db: AsyncSession, clip_id: str) -> bool:
        """Verifies if clip belongs to a trusted test Job or Channel in database."""
        from backend.models.models import Clip, Job, Channel
        import logging
        logger = logging.getLogger(__name__)
        if not clip_id:
            return False
        try:
            clip_res = await db.execute(select(Clip).where(Clip.id == clip_id))
            clip = clip_res.scalar_one_or_none()
            if not clip:
                return False

            job = None
            if clip.video_id:
                job_res = await db.execute(select(Job).where(Job.video_id == clip.video_id).order_by(Job.created_at.desc()))
                job = job_res.scalars().first()

            if not job and clip.run_identity:
                parts = clip.run_identity.split("_")
                job_id = "_".join(parts[:-2]) if len(parts) > 2 else clip.run_identity
                job_res = await db.execute(select(Job).where(Job.id == job_id))
                job = job_res.scalar_one_or_none()

            channel = None
            if clip.video_id:
                from backend.models.models import Video
                vid_res = await db.execute(select(Video).where(Video.id == clip.video_id))
                video = vid_res.scalar_one_or_none()
                if video and video.channel_id:
                    chan_res = await db.execute(select(Channel).where(Channel.id == video.channel_id))
                    channel = chan_res.scalar_one_or_none()

            if not channel and job and job.channel_id:
                chan_res = await db.execute(select(Channel).where(Channel.id == job.channel_id))
                channel = chan_res.scalar_one_or_none()

            if job is not None and bool(job.is_test):
                return True
            if channel is not None and bool(channel.is_test):
                return True
            return False
        except Exception as e:
            logger.warning(f"Could not verify test context for clip {clip_id}: {e}")
            return False

    @staticmethod
    def hash_plan(plan: BrollPlan) -> str:
        s = plan.model_dump_json()
        return hashlib.sha256(s.encode()).hexdigest()

    @staticmethod
    async def match_assets(db: AsyncSession, opportunities: list[VisualOpportunity], clip_id: str) -> list[BrollPlacement]:
        """
        Matches opportunities to available VisualAssets or fetches from Pexels.
        Falls back to mock asset generation only in verified test context.
        """
        import logging
        logger = logging.getLogger(__name__)
        is_test_clip = await BrollPlanner._is_trusted_test_clip(db, clip_id)

        placements = []
        for opp in opportunities:
            clean_keyword = opp.concept.split(',')[0].strip()
            # First, check for an existing VisualAsset that matches the concept
            res = await db.execute(
                select(VisualAsset).where(
                    VisualAsset.is_enabled == True,
                    VisualAsset.keyword.ilike(f"%{clean_keyword}%")
                ).limit(1)
            )
            asset = res.scalar_one_or_none()
            
            # Second, attempt to fetch real stock footage from Pexels Video API
            if not asset:
                asset = await BrollPlanner._fetch_pexels_asset(db, opp.concept, clip_id)

            # Third, fallback to synthetic mock generation only if in test context
            if not asset and is_test_clip:
                asset = await BrollPlanner._mock_generate_asset(db, opp.concept, opp.preferred_visual_type, clip_id)
            elif not asset:
                logger.info(f"Production context: No stock footage found for '{clean_keyword}'; skipping placement.")
            
            if asset:
                placement = BrollPlacement(
                    asset_id=asset.id,
                    opportunity_id=opp.id,
                    start_time=opp.start_time,
                    end_time=opp.end_time,
                    display_mode=DisplayMode.FULL_CUTAWAY if opp.preferred_visual_type == "video" else DisplayMode.PIP_BOTTOM,
                    scale_mode="crop",
                    fade_duration=0.5, # Smooth half-second fade
                    confidence=opp.confidence
                )
                # If PIP, give it dimensions (e.g. 500x500 at bottom center)
                if placement.display_mode == DisplayMode.PIP_BOTTOM:
                    placement.w = 600
                    placement.h = 600
                    placement.x = 240 # (1080 - 600) / 2
                    placement.y = 1000 # Put it towards the bottom
                    
                placements.append(placement)
                
        return placements

    @staticmethod
    async def _fetch_pexels_asset(db: AsyncSession, concept: str, clip_id: str) -> Optional[VisualAsset]:
        """
        Searches and downloads real stock footage from Pexels Video API for the concept.
        Registers the footage with ArtifactManager and attaches creator attribution metadata.
        """
        if not pexels_service.is_configured():
            return None

        clean_keyword = concept.split(",")[0].strip()
        if not clean_keyword:
            return None

        import tempfile
        import os
        import shutil
        from pathlib import Path

        # Search Pexels (portrait orientation preferred for 9:16 Shorts)
        results = pexels_service.search_videos(clean_keyword, orientation="portrait", per_page=3)
        if not results:
            results = pexels_service.search_videos(clean_keyword, orientation="", per_page=3)

        if not results:
            return None

        best_video = results[0]
        download_url = best_video.get("download_url")
        if not download_url:
            return None

        fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

        try:
            success = pexels_service.download_video(download_url, Path(temp_path), timeout=30)
            if not success or not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                return None

            asset_id = str(uuid.uuid4())
            storage_key = f"pexels_assets/{asset_id}.mp4"
            attribution_meta = json.dumps({
                "source": "pexels",
                "creator_name": best_video.get("creator_name"),
                "creator_url": best_video.get("creator_url"),
                "pexels_video_url": best_video.get("pexels_video_url"),
                "pexels_video_id": best_video.get("video_id")
            })

            async with artifact_manager.managed_upload(
                db=db,
                owner_type="clip",
                owner_id=clip_id,
                artifact_type=ArtifactType.BROLL_ASSET,
                storage_key=storage_key,
                retention_policy="persistent",
                processing_version=attribution_meta
            ) as upload_path:
                shutil.copy2(temp_path, upload_path)

            record = await artifact_manager.get_artifact(db, storage_key)
            new_asset = VisualAsset(
                id=asset_id,
                artifact_id=record.id,
                asset_type="pexels_video",
                keyword=clean_keyword
            )
            db.add(new_asset)
            await db.commit()
            await db.refresh(new_asset)
            return new_asset

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error fetching Pexels asset for '{clean_keyword}': {e}")
            return None
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    @staticmethod
    async def _mock_generate_asset(db: AsyncSession, concept: str, visual_type: str, clip_id: str) -> VisualAsset:
        """
        Mocks the generation of an AI asset (image or video) and registers it with artifact_manager.
        Must clearly mark it as mock/generated_placeholder.
        """
        import tempfile
        import os
        from backend.core.config import settings
        
        # Create a dummy file (1x1 red pixel or simple ffmpeg generated video)
        fd, temp_path = tempfile.mkstemp(suffix=".mp4" if visual_type == "video" else ".png")
        os.close(fd)
        
        try:
            if visual_type == "video":
                # Create a 2s dummy video with text using ffmpeg
                cmd = [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"color=c=gray:s=1080x1920:d=2",
                    "-vf", f"drawtext=text='Mock AI Video\\nConcept\\: {concept}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
                    "-c:v", "libx264", "-movflags", "+faststart", temp_path
                ]
            else:
                # Create a dummy image
                cmd = [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", f"color=c=gray:s=1080x1080:d=1",
                    "-vf", f"drawtext=text='Mock AI Image\\nConcept\\: {concept}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2",
                    "-vframes", "1", temp_path
                ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            # Register it via managed_upload to ensure tracking and physical persistence
            asset_id = str(uuid.uuid4())
            storage_key = f"mock_assets/{asset_id}.{'mp4' if visual_type == 'video' else 'png'}"
            
            async with artifact_manager.managed_upload(
                db=db,
                owner_type="clip", # We attach the mock generation loosely to the clip requesting it for tracking
                owner_id=clip_id,
                artifact_type=ArtifactType.BROLL_ASSET,
                storage_key=storage_key,
                retention_policy="persistent", # Keep visual assets persistently
                processing_version="mock_1.0"
            ) as upload_path:
                import shutil
                shutil.copy2(temp_path, upload_path)
            
            # Create VisualAsset DB record
            record = await artifact_manager.get_artifact(db, storage_key)
            new_asset = VisualAsset(
                id=asset_id,
                artifact_id=record.id,
                asset_type="generated_visual",
                keyword=concept.split(",")[0].strip()
            )
            db.add(new_asset)
            await db.commit()
            await db.refresh(new_asset)
            return new_asset
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    async def create_plan(db: AsyncSession, clip_id: str, transcript: list[dict], clip_start_time: float, clip_end_time: float) -> BrollPlan:
        """
        Creates and stores a BrollPlan in the database.
        """
        opportunities = ContextualVisualAnalyzer.extract_opportunities(transcript, clip_start_time, clip_end_time)
        placements = await BrollPlanner.match_assets(db, opportunities, clip_id)
        
        plan = BrollPlan(
            clip_id=clip_id,
            placements=placements,
            generated_timestamp=datetime.now(timezone.utc).timestamp()
        )
        plan.plan_hash = BrollPlanner.hash_plan(plan)
        
        # Save to DB
        db_plan = ClipVisualPlan(
            clip_id=clip_id,
            plan_json=plan.model_dump_json(),
            plan_hash=plan.plan_hash
        )
        
        # Upsert
        existing = await db.execute(select(ClipVisualPlan).where(ClipVisualPlan.clip_id == clip_id))
        existing_plan = existing.scalar_one_or_none()
        if existing_plan:
            existing_plan.plan_json = db_plan.plan_json
            existing_plan.plan_hash = db_plan.plan_hash
        else:
            db.add(db_plan)
        
        await db.commit()
        return plan
