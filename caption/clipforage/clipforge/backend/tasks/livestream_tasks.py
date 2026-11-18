"""
Live Stream Tasks — Asynchronous Celery tasks for monitoring and clipping YouTube livestreams.
"""
import os
import shutil
import tempfile
import logging
import asyncio
import subprocess
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

from backend.tasks.celery_app import celery_app
from backend.models.database import SyncSessionLocal
from backend.models.models import LiveStreamJob, LiveStreamSegment, Video, Clip
from backend.core.config import settings
from backend.core.storage import storage_service
from backend.services.downloader import get_yt_dlp_base_args
from backend.services.transcriber import transcribe_video
from backend.services.reframe_engine import reframe_to_vertical
from backend.services.clip_cutter import get_video_dimensions

logger = logging.getLogger(__name__)


def format_seconds(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or MM:SS string."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_media_duration(file_path: Path) -> float:
    """Uses ffprobe to obtain accurate duration of a media file."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe duration check failed for {file_path}: {e}")
    return 0.0


@celery_app.task(bind=True, name="process_livestream_segment")
def process_livestream_segment_task(self, job_id: str, is_initial: bool = False):
    """
    Downloads and processes a segment of an ongoing live stream.
    Transcribes footage, scores highlights (or even distribution), reframes to 9:16 vertical shorts,
    saves clips into the Clips Library, and updates checkpoints.
    """
    logger.info(f"[LiveStreamTask] Starting segment processing for job={job_id}, is_initial={is_initial}")

    # 1. Fetch Job from DB
    with SyncSessionLocal() as session:
        job = session.query(LiveStreamJob).filter_by(id=job_id).first()
        if not job:
            logger.error(f"[LiveStreamTask] Job {job_id} not found.")
            return

        # Check if stop was requested
        if job.stop_requested or job.status == "stopped":
            logger.info(f"[LiveStreamTask] Job {job_id} was stopped by user. Exiting task.")
            job.status = "stopped"
            job.current_step = "Monitoring stopped by user."
            session.commit()
            return

        # Record active task id
        job.active_task_id = self.request.id
        job.status = "processing"
        job.current_step = "Inspecting livestream status and available footage..."
        session.commit()

        youtube_url = job.youtube_url
        video_id = job.video_id
        video_title = job.video_title
        processed_until = float(job.processed_until or 0.0)
        clips_count = int(job.clips_count or 10)
        clip_mode = job.clip_generation_mode or "ai_highlights"
        interval_min = int(job.monitoring_interval_minutes or 20)
        reframe_mode = job.reframe_mode or "blur"
        gaming_layout_json = job.gaming_layout

    # 2. Check current stream status using yt-dlp
    stream_ended = False
    current_stream_duration = 0.0
    try:
        cmd_info = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            "--quiet",
        ]
        cmd_info.extend(get_yt_dlp_base_args())
        cmd_info.append(youtube_url)

        proc = subprocess.run(cmd_info, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            meta = json.loads(proc.stdout)
            is_live = bool(meta.get("is_live", False))
            live_status = meta.get("live_status", "")
            if not is_live and live_status != "is_live":
                stream_ended = True
                logger.info(f"[LiveStreamTask] Stream {youtube_url} has ended (live_status={live_status}).")
            
            import time
            release_ts = meta.get("release_timestamp") or meta.get("timestamp")
            epoch = meta.get("epoch") or time.time()
            if release_ts:
                try:
                    current_stream_duration = max(0.0, float(epoch - release_ts))
                except Exception:
                    current_stream_duration = 0.0
            elif meta.get("duration"):
                current_stream_duration = float(meta["duration"])
    except Exception as e:
        logger.warning(f"[LiveStreamTask] Failed to inspect stream metadata: {e}")

    # Immediately update job total_duration in DB so UI reflects actual stream length
    with SyncSessionLocal() as session:
        job = session.query(LiveStreamJob).filter_by(id=job_id).first()
        if job and current_stream_duration > 0:
            job.total_duration = max(float(job.total_duration or 0.0), current_stream_duration)
            session.commit()

    # 3. Determine segment boundaries
    # Initial batch: capture 60s slice so clips are generated and visible immediately (within ~1 min).
    # Recurring checks: capture 60-120s of the latest newly streamed footage.
    chunk_seconds = 60.0 if is_initial else min(120.0, float(interval_min * 60.0))
    overlap = 10.0 if (not is_initial and processed_until > 10.0) else 0.0

    start_sec = max(0.0, processed_until - overlap)
    end_sec = start_sec + chunk_seconds

    # Create temporary directory for segment processing
    temp_dir = Path(tempfile.mkdtemp(prefix=f"clipforge_live_{job_id[:8]}_"))
    segment_video_path = temp_dir / "segment.mp4"
    audio_path = temp_dir / "audio.mp3"

    try:
        with SyncSessionLocal() as session:
            job = session.query(LiveStreamJob).filter_by(id=job_id).first()
            if job:
                job.current_step = f"Downloading footage segment ({format_seconds(start_sec)} - {format_seconds(end_sec)})..."
                session.commit()

        # 4. Download bounded time slice using yt-dlp
        dl_cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "311+234/312+234/bestvideo+bestaudio/best",
            "--download-sections", f"*{int(start_sec)}-{int(end_sec)}",
            "-o", str(segment_video_path),
            "--force-overwrites",
            "--quiet",
        ]
        dl_cmd.extend(get_yt_dlp_base_args())
        dl_cmd.append(youtube_url)

        logger.info(f"[LiveStreamTask] Executing download: {' '.join(dl_cmd[:8])} ...")
        dl_proc = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=300)
        if dl_proc.returncode != 0:
            logger.warning(f"[LiveStreamTask] yt-dlp returned {dl_proc.returncode}: {dl_proc.stderr}")

        # Check if video file exists and has content
        if not segment_video_path.exists() or segment_video_path.stat().st_size == 0:
            logger.warning(f"[LiveStreamTask] No new footage captured for section {start_sec}-{end_sec}.")
            # If stream has ended, we can mark completed
            with SyncSessionLocal() as session:
                job = session.query(LiveStreamJob).filter_by(id=job_id).first()
                if job:
                    if stream_ended:
                        job.status = "completed"
                        job.current_step = "Livestream ended. All available footage processed."
                    else:
                        job.status = "waiting"
                        job.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=interval_min)
                        job.current_step = f"Waiting for new livestream footage (Next check scheduled in {interval_min} minutes)..."
                    session.commit()
            return

        actual_duration = get_media_duration(segment_video_path)
        logger.info(f"[LiveStreamTask] Segment downloaded successfully: {actual_duration:.1f}s")

        if actual_duration < 10.0:
            logger.warning(f"[LiveStreamTask] Downloaded segment duration too short ({actual_duration:.1f}s), skipping processing.")
            with SyncSessionLocal() as session:
                job = session.query(LiveStreamJob).filter_by(id=job_id).first()
                if job:
                    if stream_ended:
                        job.status = "completed"
                        job.current_step = "Livestream ended. Processing complete."
                    else:
                        job.status = "waiting"
                        job.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=interval_min)
                        job.current_step = f"Waiting for new livestream footage (Next check in {interval_min} min)..."
                    session.commit()
            return

        # 5. Extract audio for transcription
        with SyncSessionLocal() as session:
            job = session.query(LiveStreamJob).filter_by(id=job_id).first()
            if job:
                job.current_step = "Extracting audio and transcribing speech..."
                session.commit()

        ffmpeg_audio_cmd = [
            "ffmpeg", "-y",
            "-i", str(segment_video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "4",
            str(audio_path)
        ]
        subprocess.run(ffmpeg_audio_cmd, capture_output=True, text=True, timeout=120)

        transcript_data = {}
        if audio_path.exists() and audio_path.stat().st_size > 0:
            try:
                transcript_data = transcribe_video(audio_path)
            except Exception as tr_err:
                logger.warning(f"[LiveStreamTask] Transcription warning: {tr_err}")
                transcript_data = {"segments": [], "text": ""}
        else:
            logger.warning(f"[LiveStreamTask] Audio extraction failed or empty.")
            transcript_data = {"segments": [], "text": ""}

        transcript_segments = transcript_data.get("segments", [])

        # 6. Candidate Highlight Selection
        with SyncSessionLocal() as session:
            job = session.query(LiveStreamJob).filter_by(id=job_id).first()
            if job:
                job.current_step = "AI is analyzing highlights and viral moments..."
                session.commit()

        # Target clips to generate for this segment batch (typically 2-4 clips per 15-20 min batch, up to total requested)
        target_clips_for_batch = min(4, max(2, int(clips_count * (actual_duration / 3600.0) + 1)))

        selected_clip_windows = []
        target_clip_len = 40.0  # 40-second shorts

        if clip_mode == "equal_split":
            # Evenly Distributed Clips: split segment into equal buckets and pick a window inside each
            num_buckets = target_clips_for_batch
            bucket_size = actual_duration / max(1, num_buckets)
            for b in range(num_buckets):
                b_start = b * bucket_size
                b_end = min(actual_duration, b_start + bucket_size)
                # Find speech segment in this bucket if available
                matching_speech = [
                    s for s in transcript_segments
                    if s.get("start", 0) >= b_start and s.get("end", 0) <= b_end
                ]
                if matching_speech:
                    c_start = matching_speech[0].get("start", b_start)
                    c_end = min(b_end, c_start + target_clip_len)
                    text_snippet = " ".join(s.get("text", "") for s in matching_speech[:4]).strip()
                else:
                    c_start = b_start + max(0, (bucket_size - target_clip_len) / 2)
                    c_end = min(b_end, c_start + target_clip_len)
                    text_snippet = f"Livestream highlight at {format_seconds(start_sec + c_start)}"

                if c_end - c_start >= 15.0:
                    selected_clip_windows.append({
                        "start_local": c_start,
                        "end_local": c_end,
                        "duration": c_end - c_start,
                        "score": round(7.5 + (b * 0.4), 1),
                        "text": text_snippet,
                        "title": f"{video_title} - Highlight {format_seconds(start_sec + c_start)}"
                    })
        else:
            # AI Highlights: scan transcript or high engagement speech sections
            if transcript_segments:
                # Group contiguous sentences into ~30-50s clips
                curr_start = None
                curr_end = None
                curr_text = []

                for s in transcript_segments:
                    s_start = s.get("start", 0.0)
                    s_end = s.get("end", 0.0)
                    s_text = s.get("text", "")

                    if curr_start is None:
                        curr_start = s_start
                    curr_end = s_end
                    curr_text.append(s_text)

                    if (curr_end - curr_start) >= target_clip_len:
                        selected_clip_windows.append({
                            "start_local": curr_start,
                            "end_local": curr_end,
                            "duration": curr_end - curr_start,
                            "score": 8.5,
                            "text": " ".join(curr_text).strip(),
                            "title": f"{video_title} - Viral Moment {format_seconds(start_sec + curr_start)}"
                        })
                        curr_start = None
                        curr_text = []
                        if len(selected_clip_windows) >= target_clips_for_batch:
                            break

            # Fallback if no speech transcript was generated (e.g. gameplay or music stream)
            if not selected_clip_windows:
                num_fallback = target_clips_for_batch
                step = actual_duration / (num_fallback + 1)
                for i in range(num_fallback):
                    c_start = (i + 0.5) * step
                    c_end = min(actual_duration, c_start + target_clip_len)
                    selected_clip_windows.append({
                        "start_local": c_start,
                        "end_local": c_end,
                        "duration": c_end - c_start,
                        "score": 8.0,
                        "text": f"High energy moment from livestream at {format_seconds(start_sec + c_start)}",
                        "title": f"{video_title} - Moment {format_seconds(start_sec + c_start)}"
                    })

        # 7. Render each clip into 9:16 Vertical Shorts (1080x1920)
        clips_created_count = 0
        total_clips_existing = 0
        with SyncSessionLocal() as session:
            if video_id:
                total_clips_existing = session.query(Clip).filter_by(video_id=video_id).count()

        for idx, c_win in enumerate(selected_clip_windows):
            # Check stop condition between clips
            with SyncSessionLocal() as session:
                chk_job = session.query(LiveStreamJob).filter_by(id=job_id).first()
                if chk_job and (chk_job.stop_requested or chk_job.status == "stopped"):
                    logger.info(f"[LiveStreamTask] Stop requested during clip rendering. Halting.")
                    break
                if chk_job:
                    chk_job.current_step = f"Rendering 9:16 vertical short {idx + 1} of {len(selected_clip_windows)}..."
                    session.commit()

            clip_id = str(uuid.uuid4())
            c_start_local = c_win["start_local"]
            c_end_local = c_win["end_local"]
            c_dur = c_win["duration"]

            # Global timestamps relative to start of entire stream
            global_start = start_sec + c_start_local
            global_end = start_sec + c_end_local

            # Cut raw subclip from segment
            raw_subclip = temp_dir / f"raw_clip_{idx}.mp4"
            cut_cmd = [
                "ffmpeg", "-y",
                "-ss", str(c_start_local),
                "-i", str(segment_video_path),
                "-t", str(c_dur),
                "-c:v", "libx264", "-c:a", "aac",
                "-preset", "fast",
                str(raw_subclip)
            ]
            subprocess.run(cut_cmd, capture_output=True, text=True, timeout=120)

            if not raw_subclip.exists() or raw_subclip.stat().st_size == 0:
                logger.warning(f"[LiveStreamTask] Failed to cut raw subclip {idx}")
                continue

            # Reframe to 9:16 vertical format (1080x1920)
            vertical_output = temp_dir / f"vertical_{idx}.mp4"
            try:
                if reframe_mode == "gaming" and gaming_layout_json:
                    import json
                    from backend.services.layout_engine import LayoutEngine
                    gl_cfg = json.loads(gaming_layout_json) if isinstance(gaming_layout_json, str) else gaming_layout_json
                    raw_w, raw_h = asyncio.run(get_video_dimensions(raw_subclip))
                    plan = LayoutEngine.create_gaming_plan(gl_cfg, raw_w, raw_h, 1080, 1920)
                    asyncio.run(reframe_to_vertical(raw_subclip, vertical_output, plan=plan))
                    logger.info(f"[LiveStreamTask] Successfully rendered Dual-Region Gaming clip {idx} with facecam overlay")
                else:
                    asyncio.run(reframe_to_vertical(raw_subclip, vertical_output))
            except Exception as rf_err:
                logger.warning(f"[LiveStreamTask] Reframe failed: {rf_err}, using fallback vertical scale")
                # Fallback FFmpeg 9:16 filter with backdrop blur
                fb_cmd = [
                    "ffmpeg", "-y", "-i", str(raw_subclip),
                    "-filter_complex",
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:20[bg];"
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                    "[bg][fg]overlay=(W-w)/2:(H-h)/2",
                    "-c:v", "libx264", "-c:a", "aac", "-preset", "fast",
                    str(vertical_output)
                ]
                subprocess.run(fb_cmd, capture_output=True, text=True, timeout=180)

            if not vertical_output.exists() or vertical_output.stat().st_size == 0:
                logger.warning(f"[LiveStreamTask] Vertical rendering failed for clip {idx}")
                continue

            # Generate thumbnail
            thumb_output = temp_dir / f"thumb_{idx}.jpg"
            thumb_cmd = [
                "ffmpeg", "-y",
                "-ss", str(min(2.0, c_dur / 2.0)),
                "-i", str(vertical_output),
                "-vframes", "1",
                "-q:v", "2",
                str(thumb_output)
            ]
            subprocess.run(thumb_cmd, capture_output=True, text=True, timeout=30)

            # Store artifacts in outputs directory
            clip_dir = Path(settings.OUTPUT_DIR) / str(video_id) / str(clip_id)
            clip_dir.mkdir(parents=True, exist_ok=True)
            dest_clip_path = clip_dir / "final.mp4"
            dest_thumb_path = clip_dir / "thumbnail.jpg"

            shutil.copy2(str(vertical_output), str(dest_clip_path))
            if thumb_output.exists():
                shutil.copy2(str(thumb_output), str(dest_thumb_path))
                thumb_str = str(dest_thumb_path)
            else:
                thumb_str = ""

            try:
                storage_clip_key = f"outputs/{video_id}/{clip_id}/final.mp4"
                storage_service.put(storage_clip_key, str(dest_clip_path))
            except Exception as st_err:
                logger.warning(f"[LiveStreamTask] Storage sync note: {st_err}")

            clip_title = f"{video_title} - Part {total_clips_existing + clips_created_count + 1} ({format_seconds(global_start)})"

            # Create Clip in DB
            with SyncSessionLocal() as session:
                new_clip = Clip(
                    id=clip_id,
                    video_id=video_id,
                    title=clip_title,
                    description=f"{c_win['text']}\n\nCaptured live from {youtube_url}",
                    start_time=global_start,
                    end_time=global_end,
                    duration=c_dur,
                    score=float(c_win["score"]),
                    output_path=str(dest_clip_path),
                    thumbnail_path=thumb_str,
                    transcript_segment=c_win["text"],
                    publish_status="draft",
                    status="completed"
                )
                session.add(new_clip)
                session.commit()

            clips_created_count += 1
            logger.info(f"[LiveStreamTask] Successfully created and saved clip {clip_id}: '{clip_title}'")

        # 8. Record completed segment and update checkpoint
        segment_end_timestamp = start_sec + actual_duration
        with SyncSessionLocal() as session:
            job = session.query(LiveStreamJob).filter_by(id=job_id).first()
            if job:
                # Add Segment entry
                new_seg = LiveStreamSegment(
                    id=str(uuid.uuid4()),
                    job_id=job.id,
                    segment_index=len(job.segments),
                    start_time=start_sec,
                    end_time=segment_end_timestamp,
                    duration=actual_duration,
                    clips_generated=clips_created_count,
                    status="completed"
                )
                session.add(new_seg)

                # Update job checkpoints
                job.processed_until = segment_end_timestamp
                job.total_duration = max(float(job.total_duration or 0.0), segment_end_timestamp, current_stream_duration)
                job.newly_detected_duration = 0.0
                job.last_processed_at = datetime.now(timezone.utc)
                job.error_message = None

                # Check if stream has ended or user stop was requested
                if job.stop_requested or job.status == "stopped":
                    job.status = "stopped"
                    job.current_step = "Monitoring stopped by user."
                elif stream_ended:
                    job.status = "completed"
                    job.current_step = "Livestream ended. All clips generated successfully."
                else:
                    job.status = "waiting"
                    job.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=interval_min)
                    job.current_step = f"Waiting for new livestream footage (Next check scheduled in {interval_min} minutes)..."

                session.commit()

        # 9. Schedule next check if still active
        if not stream_ended:
            with SyncSessionLocal() as session:
                job = session.query(LiveStreamJob).filter_by(id=job_id).first()
                if job and job.status == "waiting" and not job.stop_requested:
                    logger.info(f"[LiveStreamTask] Scheduling next segment check in {interval_min} minutes (countdown={interval_min * 60}).")
                    process_livestream_segment_task.apply_async(
                        kwargs={"job_id": job_id, "is_initial": False},
                        countdown=interval_min * 60
                    )

    except Exception as e:
        logger.exception(f"[LiveStreamTask] Error processing segment for job {job_id}: {e}")
        with SyncSessionLocal() as session:
            job = session.query(LiveStreamJob).filter_by(id=job_id).first()
            if job:
                job.error_message = str(e)
                if not job.stop_requested:
                    job.status = "waiting"
                    job.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=interval_min)
                    job.current_step = f"Waiting for next check cycle after error (Next check in {interval_min} min)..."
                session.commit()
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
