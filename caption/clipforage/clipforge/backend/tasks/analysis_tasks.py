import logging
import os
from backend.tasks.celery_app import celery_app
from backend.models.db_sync import update_job_sync
from backend.core.config import settings

logger = logging.getLogger(__name__)

from backend.tasks.retry_policy import DEFAULT_RETRY_KWARGS

@celery_app.task(
    bind=True,
    name="candidate_generation",
    **DEFAULT_RETRY_KWARGS,
)
def candidate_generation_task(self, chord_results):
    """
    Combines transcription and scene detection to generate clip candidates.
    Saves candidates to an artifact and returns artifact path.
    """
    import json
    import hashlib
    import tempfile
    from pathlib import Path
    from backend.services.clip_scorer import build_candidate_windows
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Video, ArtifactType, ArtifactStatus
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync

    video_id = None
    job_id = None
    for res in chord_results:
        if isinstance(res, dict) and "video_id" in res:
            video_id = res["video_id"]
            job_id = res["job_id"]
            break
            
    logger.info(f"Generating candidates for video {video_id}")
    update_job_sync(job_id, "analyzing", 40, "Generating clip candidates...")
    
    try:
        with SyncSessionLocal() as session:
            video = session.query(Video).filter_by(id=video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            storage_key = video.local_path
            transcript_json = video.transcript

        if not transcript_json:
            raise ValueError(f"Video {video_id} has no transcript data.")
            
        transcription_result = json.loads(transcript_json)
        segments = transcription_result.get("segments", [])

        # Source-Level AI Category Analysis & Canonical SEO Tag Generation (Analyze ONCE per source video)
        try:
            from backend.services.source_metadata_engine import get_or_analyze_source_seo_metadata
            source_meta = get_or_analyze_source_seo_metadata(video_id)
            logger.info(f"[CandidateGeneration] Source metadata resolved for {video_id}: category='{source_meta.primary_category}', tags={source_meta.seo_tags}")
        except Exception as seo_err:
            logger.warning(f"[CandidateGeneration] Source metadata analysis warning: {seo_err}")
        
        candidates_storage_key = f"uploads/{video_id}/candidates.json"
        scenes_storage_key = f"uploads/{video_id}/scenes.json"
        scenes = []
        
        try:
            with managed_download_sync(storage_key=scenes_storage_key) as temp_scenes_path:
                with open(temp_scenes_path, "r") as f:
                    scenes = json.load(f)
        except Exception as e:
            logger.warning(f"Could not retrieve scenes for {video_id}, proceeding without them: {e}")
            
        with managed_download_sync(storage_key=storage_key) as temp_video_path:
            with managed_upload_sync(
                owner_type="video",
                owner_id=video_id,
                artifact_type=ArtifactType.CANDIDATES,
                storage_key=candidates_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as temp_candidates_path:
                
                # Generate candidates
                from backend.core.config import settings
                from backend.models.database import SyncSessionLocal
                from backend.models.models import Job
                import json
                
                min_dur = settings.MIN_CLIP_DURATION
                max_dur = settings.MAX_CLIP_DURATION
                seg_strategy = None
                target_duration = None
                num_clips = None
                config_dict = {}
                raw_max = None
                
                if job_id:
                    with SyncSessionLocal() as session:
                        job = session.query(Job).filter_by(id=job_id).first()
                        if job and job.config:
                            try:
                                config_dict = json.loads(job.config)
                                seg_strategy = config_dict.get("segmentation_strategy")
                                target_duration = config_dict.get("target_duration")
                                if target_duration is not None:
                                    target_duration = float(target_duration)
                                num_clips = config_dict.get("clips_count") or config_dict.get("num_clips")
                                if num_clips is not None:
                                    num_clips = int(num_clips)
                                raw_min = config_dict.get("min_clip_duration")
                                raw_max = config_dict.get("max_clip_duration")
                                if raw_min is not None:
                                    raw_min = int(raw_min)
                                    if raw_min > 0:
                                        min_dur = raw_min
                                    else:
                                        logger.warning(f"Invalid min_clip_duration={raw_min}, using default {min_dur}")
                                if raw_max is not None:
                                    raw_max = int(raw_max)
                                    if raw_max > 0 and raw_max >= min_dur:
                                        max_dur = raw_max
                                    else:
                                        logger.warning(f"Invalid max_clip_duration={raw_max}, using default {max_dur}")
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Failed to parse Job.config for min/max duration: {e}")
                            except Exception as e:
                                logger.warning(f"Failed to parse Job.config for min/max duration: {e}")

                is_equal_split = (
                    seg_strategy in ("equal_splits", "equal_split")
                    or config_dict.get("clip_mode") in ("equal_split", "equal_splits")
                )

                if is_equal_split:
                    seg_strategy = "equal_splits"
                    from backend.services.segmentation import generate_equal_splits
                    from backend.models.models import Video
                    video_dur = None
                    with SyncSessionLocal() as session:
                        v_rec = session.query(Video).filter_by(id=video_id).first()
                        if v_rec and v_rec.duration:
                            video_dur = float(v_rec.duration)
                    if not video_dur or video_dur <= 0:
                        from backend.services.downloader import get_video_info
                        try:
                            info = get_video_info(temp_video_path)
                            video_dur = float(info.get("duration", 60.0))
                        except Exception:
                            video_dur = 60.0

                    # Resolve effective target duration for equal splits:
                    # Priority: target_duration from config > max_clip_duration
                    eff_target_duration = target_duration
                    if eff_target_duration is None or eff_target_duration <= 0:
                        if raw_max is not None and raw_max > 0:
                            eff_target_duration = float(raw_max)
                        else:
                            raise ValueError(
                                f"Maximum clip duration (target_duration) is mandatory for Equal Splits on video {video_id}. "
                                "Silent fallback to default duration is strictly prohibited."
                            )
                    else:
                        eff_target_duration = float(eff_target_duration)

                    update_job_sync(job_id, "analyzing", 45, f"Planning equal split segments for {video_dur:.1f}s video...")

                    # Equal Split: calculate N automatically from eff_target_duration (Lmax)
                    candidates = generate_equal_splits(
                        video_duration=video_dur,
                        target_duration=eff_target_duration
                    )
                    logger.info(
                        f"Equal Split generated {len(candidates)} segments for video {video_id} "
                        f"(video_dur={video_dur}s, target_dur={eff_target_duration}s)"
                    )
                else:
                    # Duration bounds for AI Highlights mode (Shorts max 60.0s)
                    target_limit = target_duration or raw_max or max_dur or 60.0
                    target_limit = min(60.0, max(15.0, float(target_limit)))
                    eff_min = max(15, min(int(min_dur), int(target_limit)))
                    eff_max = min(60, max(int(target_limit), eff_min))

                    candidates = build_candidate_windows(
                        segments,
                        video_path=temp_video_path,
                        min_dur=eff_min,
                        max_dur=eff_max,
                        scenes=scenes
                    )
                
                # Save candidates to artifact
                with open(temp_candidates_path, "w") as f:
                    json.dump(candidates, f)
                    
                candidate_hash = hashlib.md5(json.dumps(candidates, sort_keys=True).encode()).hexdigest()
        
    except Exception as e:
        logger.error(f"Candidate generation failed: {e}")
        update_job_sync(job_id, "failed", 100, f"Candidate generation failed: {e}")
        raise self.retry(exc=e, countdown=30)
    
    return {"video_id": video_id, "job_id": job_id, "candidate_set_hash": candidate_hash, "segmentation_strategy": seg_strategy}


@celery_app.task(
    bind=True,
    name="scoring",
    **DEFAULT_RETRY_KWARGS,
)
def scoring_task(self, result: dict):
    """
    Scores the generated candidates using the Cloud LLM router.
    Bypasses AI scoring when segmentation_strategy == 'equal_splits'.
    """
    import json
    import os
    import asyncio
    import tempfile
    from pathlib import Path
    from backend.services.clip_scorer import ai_score_candidates
    from backend.models.models import ArtifactType, ArtifactStatus
    from backend.models.artifact_sync import managed_download_sync, managed_upload_sync

    video_id = result.get("video_id")
    job_id = result.get("job_id")
    candidates_storage_key = f"uploads/{video_id}/candidates.json"
    
    logger.info(f"Scoring candidates for video {video_id}")
    update_job_sync(job_id, "analyzing", 60, "Scoring candidates...")
    
    try:
        with managed_download_sync(storage_key=candidates_storage_key) as temp_candidates_path:
            with open(temp_candidates_path, "r") as f:
                candidates = json.load(f)
                
            # Read config for clips_count and segmentation_strategy
            from backend.models.database import SyncSessionLocal
            from backend.models.models import Job
            from backend.core.config import settings
            import json
            
            clips_count = settings.CLIPS_PER_VIDEO
            seg_strategy = result.get("segmentation_strategy")
            raw_scoring_mode = None
            if job_id:
                with SyncSessionLocal() as session:
                    job = session.query(Job).filter_by(id=job_id).first()
                    if job and job.config:
                        try:
                            config_dict = json.loads(job.config)
                            raw_scoring_mode = config_dict.get("scoring_mode")
                            if not seg_strategy:
                                seg_strategy = config_dict.get("segmentation_strategy")
                            if not seg_strategy and config_dict.get("clip_mode") in ("equal_split", "equal_splits"):
                                seg_strategy = "equal_splits"
                            raw_count = config_dict.get("clips_count")
                            if raw_count is not None:
                                raw_count = int(raw_count)
                                if raw_count > 0:
                                    clips_count = raw_count
                                else:
                                    logger.warning(f"Invalid clips_count={raw_count}, using default {clips_count}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to parse Job.config for clips_count: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to parse Job.config for clips_count: {e}")

            if seg_strategy in ("equal_splits", "equal_split"):
                logger.info(f"Bypassing AI scoring for equal_splits segmentation with {len(candidates)} candidates.")
                # Preserve all N candidates without user-selected or default clips_count truncation
                scored_clips_dicts = candidates
                score_version = "equal_splits_v1"
            elif (
                raw_scoring_mode in ("fallback", "heuristic", "test")
                or (job and job.config and "test" in str(job.config).lower())
                or os.environ.get("SCORING_MODE") == "test"
                or getattr(settings, "SCORING_MODE", "prod") == "test"
            ):
                logger.info(f"Scoring via fallback/heuristic (mode={raw_scoring_mode}).")
                from backend.services.clip_scorer import _heuristic_fallback
                scored_clips = _heuristic_fallback(candidates, top_n=clips_count)
                scored_clips_dicts = [
                    {
                        "start": clip.start,
                        "end": clip.end,
                        "duration": clip.duration,
                        "text": clip.text,
                        "score": clip.score,
                        "title": clip.title,
                        "reason": clip.reason,
                        "description": getattr(clip, "description", ""),
                        "hashtags": getattr(clip, "hashtags", ""),
                        "pinned_comment": getattr(clip, "pinned_comment", "")
                    }
                    for clip in scored_clips
                ]
                score_version = "test_v1"
            else:
                logger.info(f"AI scoring required with clips_count={clips_count} for job {job_id}")
                # Call the async ai_score_candidates (strictly requires AI provider)
                scored_clips = asyncio.run(ai_score_candidates(candidates, top_n=clips_count))
                
                # Convert scored_clips back to dicts for JSON serialization
                scored_clips_dicts = [
                    {
                        "start": clip.start,
                        "end": clip.end,
                        "duration": clip.duration,
                        "text": clip.text,
                        "score": clip.score,
                        "title": clip.title,
                        "reason": clip.reason,
                        "description": getattr(clip, "description", ""),
                        "hashtags": getattr(clip, "hashtags", ""),
                        "pinned_comment": getattr(clip, "pinned_comment", "")
                    }
                    for clip in scored_clips
                ]
                score_version = "v1"
            
            scored_storage_key = f"uploads/{video_id}/scored_clips.json"
            with managed_upload_sync(
                owner_type="video",
                owner_id=video_id,
                artifact_type=ArtifactType.SCORED_CLIPS,
                storage_key=scored_storage_key,
                retention_policy="persistent",
                processing_version="v1"
            ) as temp_scored_path:
                # Save scored clips to artifact
                with open(temp_scored_path, "w") as f:
                    json.dump(scored_clips_dicts, f)
            
        result["scoring_version"] = score_version
        
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        update_job_sync(job_id, "failed", 100, f"Scoring failed: {e}")
        raise self.retry(exc=e, countdown=30)
        
    return result


@celery_app.task(
    bind=True,
    name="clip_selection",
    **DEFAULT_RETRY_KWARGS,
)
def clip_selection_task(self, result: dict):
    """
    Selects top candidates and persists them to the Clip table.
    Ensures idempotency using run_identity and creates PublishTarget records.
    Returns: list of created clip_ids.
    """
    import json
    from pathlib import Path
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip
    from backend.models.db_sync import save_clip_record

    from backend.models.artifact_sync import managed_download_sync

    video_id = result.get("video_id")
    job_id = result.get("job_id")
    candidate_hash = result.get("candidate_set_hash", "default")
    score_version = result.get("scoring_version", "default")
    scored_storage_key = f"uploads/{video_id}/scored_clips.json"
    
    run_identity = f"{job_id}_{score_version}_{candidate_hash}"
    
    logger.info(f"Selecting clips for video {video_id} with run identity {run_identity}")
    update_job_sync(job_id, "selecting", 80, "Selecting best clips...")
    
    try:
        with managed_download_sync(storage_key=scored_storage_key) as temp_scored_path:
            with open(temp_scored_path, "r") as f:
                scored_clips = json.load(f)
                
            # Check idempotency: Have we already created clips for this run?
            with SyncSessionLocal() as session:
                existing_clips = session.query(Clip).filter_by(run_identity=run_identity).all()
                if existing_clips:
                    logger.info(f"Clips already exist for run_identity {run_identity}, returning existing IDs.")
                    return [c.id for c in existing_clips]
                
                # Fetch job config to resolve destinations
                from backend.models.models import Job, Channel, Video
                from backend.services.publisher import resolve_publish_destinations
                job = session.query(Job).filter_by(id=job_id).first()
                video = session.query(Video).filter_by(id=video_id).first()
                source_channel_id = video.channel_id if video else None

                config_data = {}
                if job and job.config:
                    try:
                        config_data = json.loads(job.config)
                    except json.JSONDecodeError:
                        pass
                        
                channel = session.query(Channel).filter_by(id=source_channel_id).first() if source_channel_id else None

                final_dest_ids = []
                try:
                    final_dest_ids = resolve_publish_destinations(config_data, source_channel_id, session)
                except Exception as e:
                    logger.warning(f"Could not resolve publish destinations via publisher: {e}")

                # If no multi-destination was resolved, check for explicit single destination assignment
                # from job config or source channel (unless explicit empty destination_ids was set)
                explicit_empty = "destination_ids" in config_data and config_data.get("destination_ids") == []
                assigned_dest_id = None
                if not explicit_empty:
                    if final_dest_ids:
                        assigned_dest_id = final_dest_ids[0]
                    else:
                        assigned_dest_id = config_data.get("publish_destination_id") or (channel.publish_destination_id if channel else None)
                        if assigned_dest_id:
                            final_dest_ids = [assigned_dest_id]
                    
            # Resolve canonical source-level SEO metadata and provenance for inheritance
            from backend.services.source_metadata_engine import get_or_analyze_source_seo_metadata
            from backend.services.description_attribution import build_attributed_description
            source_meta = get_or_analyze_source_seo_metadata(video_id)
            canonical_tags_json = json.dumps(source_meta.seo_tags) if (source_meta and source_meta.seo_tags) else None
            canonical_cat = source_meta.youtube_category_id if source_meta else "28"
            source_yt_url = video.youtube_url if video else None
            source_yt_title = video.title if video else None
            source_ch_name = channel.channel_name if channel else None
            canonical_hashtags = source_meta.description_hashtags if source_meta else []

            # Persist clips — run_identity and PublishTargets set atomically with creation
            clip_ids = []
            for i, clip_data in enumerate(scored_clips):
                import uuid
                clip_id = str(uuid.uuid4())
                raw_desc = clip_data.get("description", "")
                attributed_desc = build_attributed_description(
                    clip_description=raw_desc,
                    source_youtube_url=source_yt_url,
                    source_title=source_yt_title,
                    source_channel=source_ch_name,
                    hashtags=canonical_hashtags
                )
                save_clip_record(
                    clip_id=clip_id,
                    video_id=video_id,
                    title=clip_data.get("title", f"Clip {i+1}"),
                    start=clip_data.get("start", 0.0),
                    end=clip_data.get("end", 0.0),
                    duration=clip_data.get("duration", 0.0),
                    score=clip_data.get("score", 0.0),
                    output_path="",
                    thumbnail_path="",
                    transcript_segment=clip_data.get("text", ""),
                    run_identity=run_identity,
                    description=attributed_desc,
                    tags=canonical_tags_json,
                    pinned_comment=clip_data.get("pinned_comment", ""),
                    publish_destination_id=assigned_dest_id,
                    destination_ids=final_dest_ids,
                    category=canonical_cat
                )
                clip_ids.append(clip_id)

            # Issue C: Safe increment of Channel.clips_generated
            # Only increment by the actual number of new clips just created
            if clip_ids:
                with SyncSessionLocal() as session:
                    from backend.models.models import Video, Channel
                    # Re-count clips with this run_identity to get the authoritative count
                    actual_new = session.query(Clip).filter_by(run_identity=run_identity).count()
                    video = session.query(Video).filter_by(id=video_id).first()
                    if video and video.channel_id:
                        channel = session.query(Channel).filter_by(id=video.channel_id).first()
                        if channel:
                            channel.clips_generated += actual_new
                            session.commit()
                            logger.info(f"Incremented Channel {channel.id} clips_generated by {actual_new}")
            
    except Exception as e:
        logger.error(f"Clip selection failed: {e}")
        update_job_sync(job_id, "failed", 100, f"Clip selection failed: {e}")
        raise self.retry(exc=e, countdown=30)
        
    return clip_ids


@celery_app.task(
    bind=True,
    name="analyze_podcast_shots_task",
    **DEFAULT_RETRY_KWARGS,
)
def analyze_podcast_shots_task(self, url: str, regions_json: str, ref_timestamp: float = 0.0, composition: str = "advanced_podcast"):
    """
    Celery task for asynchronous long-video podcast shot boundary detection
    and speaker classification with multi-stage progress reporting.
    """
    import json
    import shutil
    import asyncio
    import hashlib
    from pathlib import Path
    from backend.services.advanced_podcast_engine import (
        build_shot_schedule,
        build_fixed_boundary_schedule,
        build_visibility_driven_schedule,
    )
    from backend.services.downloader import download_video, extract_youtube_id

    raw_regions = json.loads(regions_json)
    yt_id = extract_youtube_id(url)

    # Stage 1: Acquisition / Source Resolution
    self.update_state(state="PROGRESS", meta={"progress": 15, "stage": "downloading", "message": "Acquiring source video..."})

    cleanup_needed = False
    resolved_path: Path | None = None
    source_type: str = "unknown"

    # Step A: Check if input `url` is a direct local file
    candidate_direct = Path(url)
    if candidate_direct.is_file():
        resolved_path = candidate_direct.resolve()
        source_type = "local_direct"
    else:
        # Step B: Check managed upload directory paths (relative to UPLOAD_DIR or uploads/)
        upload_dir = Path(getattr(settings, "UPLOAD_DIR", "uploads")).resolve()
        if not candidate_direct.is_absolute() and ".." not in Path(url).parts:
            candidate_upload = upload_dir / url
            if candidate_upload.is_file() and candidate_upload.resolve().is_relative_to(upload_dir):
                resolved_path = candidate_upload.resolve()
                source_type = "local_upload"
            elif (Path("uploads").resolve() / url).is_file():
                p_rel = (Path("uploads").resolve() / url).resolve()
                if p_rel.is_relative_to(Path("uploads").resolve()):
                    resolved_path = p_rel
                    source_type = "local_upload"

    # Step C: If not a local file, check YouTube source
    if not resolved_path:
        if yt_id:
            # Check cached download in managed storage
            upload_dir = Path(getattr(settings, "UPLOAD_DIR", "uploads"))
            cached_candidates = [
                upload_dir / f"{yt_id}.mp4",
                Path(f"/app/uploads/{yt_id}.mp4"),
                Path(f"uploads/{yt_id}.mp4"),
            ]
            cached_path = next((p for p in cached_candidates if p.is_file()), None)
            if cached_path:
                resolved_path = cached_path.resolve()
                source_type = "cached_youtube"
            else:
                # Not cached -> trigger downloader with bounded execution
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    dl_result = loop.run_until_complete(download_video(url, video_id=f"analysis_{yt_id}"))
                    resolved_path = Path(dl_result).resolve()
                    source_type = "downloaded_youtube"
                    # Cache to managed uploads directory so subsequent analysis and clipping reuse it
                    upload_dir = Path(getattr(settings, "UPLOAD_DIR", "uploads")).resolve()
                    cached_target = upload_dir / f"{yt_id}.mp4"
                    if resolved_path.is_file() and not cached_target.exists():
                        try:
                            upload_dir.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(resolved_path, cached_target)
                            # Remove temporary download wrapper directory now that cached copy exists
                            if resolved_path.parent.name.startswith("clipforge_dl_"):
                                shutil.rmtree(resolved_path.parent, ignore_errors=True)
                            resolved_path = cached_target
                            cleanup_needed = False
                        except Exception:
                            cleanup_needed = True
                    else:
                        cleanup_needed = True
                finally:
                    loop.close()
        else:
            # Neither a local file nor a valid YouTube URL
            raise FileNotFoundError(
                f"Source video could not be resolved from '{url}': path does not exist on disk and target is not a valid YouTube URL."
            )

    # Step D: Strict Input Validation Before Decode
    if not resolved_path or not resolved_path.is_file():
        raise FileNotFoundError(f"Resolved source video does not exist: {resolved_path}")

    file_size = resolved_path.stat().st_size
    if file_size == 0:
        raise ValueError(f"Resolved source video is empty (0 bytes): {resolved_path}")

    # Step E: Cryptographic Provenance Manifest Generation
    hasher = hashlib.sha256()
    with open(resolved_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    file_sha256 = hasher.hexdigest()

    effective_yt_id = yt_id or resolved_path.stem
    provenance = {
        "source_type": source_type,
        "resolved_path": str(resolved_path),
        "sha256": file_sha256,
        "size_bytes": file_size,
        "video_id": effective_yt_id,
    }

    self.update_state(
        state="PROGRESS",
        meta={
            "progress": 25,
            "stage": "source_verified",
            "message": "Source video cryptographically verified",
            "provenance": provenance,
        }
    )

    local_path = resolved_path

    try:
        # Stage 2: Camera Cut Detection & Signature Matching
        self.update_state(state="PROGRESS", meta={"progress": 45, "stage": "detecting_cuts", "message": "Detecting camera cuts..."})
        self.update_state(state="PROGRESS", meta={"progress": 70, "stage": "classifying_speakers", "message": "Classifying active speakers..."})

        if composition == "fixed_two_person":
            outer_bound = next((r for r in raw_regions if r.get("id") == "outer_boundary" or str(r.get("label", "")).lower().startswith("outer")), None)
            participants = [r for r in raw_regions if r != outer_bound]
            if not outer_bound:
                outer_bound = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
            schedule = build_fixed_boundary_schedule(local_path, outer_boundary=outer_bound, participant_regions=participants, ref_timestamp=ref_timestamp)
        elif composition == "visibility_driven":
            reg_a = raw_regions[0]
            reg_b = raw_regions[1] if len(raw_regions) > 1 else raw_regions[0]
            schedule = build_visibility_driven_schedule(local_path, region_a=reg_a, region_b=reg_b, ref_timestamp=ref_timestamp)
        else:
            schedule = build_shot_schedule(local_path, raw_regions, ref_timestamp=ref_timestamp)

        review_count = sum(1 for s in schedule if s.get("review_needed"))

        result = {
            "status": "success",
            "video_id": effective_yt_id,
            "ref_timestamp": ref_timestamp,
            "total_shots": len(schedule),
            "review_needed_count": review_count,
            "shots": schedule,
            "provenance": provenance,
        }
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 100,
                "stage": "complete",
                "message": "Shot analysis complete",
                "provenance": provenance,
            }
        )
        return result
    finally:
        if cleanup_needed and local_path and local_path.exists():
            try:
                if local_path.parent.name.startswith("clipforge_dl_"):
                    shutil.rmtree(local_path.parent, ignore_errors=True)
                else:
                    local_path.unlink(missing_ok=True)
            except Exception:
                pass

