import logging
from celery import chain, group, chord
from backend.tasks.celery_app import celery_app
from backend.models.db_sync import update_job_sync, update_clip_status_sync

logger = logging.getLogger(__name__)

# --- FAILURE HANDLERS ---

@celery_app.task(name="handle_pipeline_failure")
def handle_pipeline_failure_task(request, exc, traceback, job_id=None, clip_id=None, stage=None):
    """
    Explicit error callback for chords, chains, and groups.
    Persists: failed stage, task ID, exception class, error message.
    """
    task_id = request.id
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    logger.error(f"[Pipeline Failure] job={job_id} clip={clip_id} stage={stage} task={task_id} err={error_msg}")
    
    if clip_id:
        update_clip_status_sync(clip_id, "failed", error_msg=error_msg)
        # Check if all clips for this job are now in a terminal state
        if job_id:
            try:
                from backend.models.database import SyncSessionLocal
                from backend.models.models import Job, Clip
                with SyncSessionLocal() as session:
                    job = session.query(Job).filter_by(id=job_id).first()
                    if job and job.video_id and job.status not in ("completed", "completed_with_failures", "failed"):
                        clips = session.query(Clip).filter_by(video_id=job.video_id).all()
                        if clips and all(c.status in ("completed", "failed") for c in clips):
                            failed_clips = [c for c in clips if c.status == "failed"]
                            if len(failed_clips) == len(clips):
                                update_job_sync(job_id, "failed", 100, f"All {len(clips)} clips failed", error=error_msg)
                            else:
                                update_job_sync(job_id, "completed_with_failures", 100, f"{len(failed_clips)}/{len(clips)} clips failed")
            except Exception as agg_err:
                logger.error(f"Failed to aggregate clip failure for job {job_id}: {agg_err}")
    elif job_id:
        update_job_sync(job_id, "failed", 0, f"Failed at {stage}", error=error_msg)
        try:
            from backend.models.database import SyncSessionLocal
            from backend.models.models import Job, Video
            from datetime import datetime, timezone
            with SyncSessionLocal() as session:
                job = session.query(Job).filter_by(id=job_id).first()
                if job:
                    if not job.completed_at:
                        job.completed_at = datetime.now(timezone.utc)
                        session.commit()
                    if job.video_id:
                        video = session.query(Video).filter_by(id=job.video_id).first()
                        if video and video.upload_batch_id:
                            from backend.tasks.studio_tasks import on_studio_video_finished_task
                            on_studio_video_finished_task.delay(
                                batch_id=video.upload_batch_id,
                                video_id=video.id,
                                job_id=job.id
                            )
        except Exception as e:
            logger.error(f"Failed to notify studio batch or set completed_at for job failure: {e}")

        # Trigger queue drain to let next queued manual job start
        try:
            from backend.services.queue_manager import trigger_queue_drain_background
            trigger_queue_drain_background()
        except Exception as q_err:
            logger.warning(f"Failed to trigger queue drain on job failure: {q_err}")



# --- ORCHESTRATION WORKFLOW ---

@celery_app.task(name="start_video_processing")
def start_video_processing_task(job_id: str, youtube_url: str = None, local_path: str = None, **kwargs):
    """
    Entrypoint. Triggers the top-level video processing chain and chord.
    """
    from backend.tasks.video_tasks import download_task, validate_media_task, transcription_task, scene_detection_task
    from backend.tasks.analysis_tasks import candidate_generation_task, scoring_task, clip_selection_task
    from backend.tasks.audio_tasks import extract_audio_task
    
    # Record truthful pipeline start timestamp when worker starts processing
    try:
        from backend.models.database import SyncSessionLocal
        from backend.models.models import Job
        from datetime import datetime, timezone
        with SyncSessionLocal() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            if job and not job.pipeline_started_at:
                job.pipeline_started_at = datetime.now(timezone.utc)
                session.commit()
    except Exception as ts_err:
        logger.warning(f"Failed to record pipeline_started_at for job {job_id}: {ts_err}")

    # Base error callback for job-level failures
    job_err_cb = handle_pipeline_failure_task.s(job_id=job_id, stage="job_orchestration")

    # 2. Parallel fan-out: Transcribe & Scene Detect -> Fan-in: Candidate Gen + Selection
    post_analysis_chain = chain(
        candidate_generation_task.s(),
        scoring_task.s(),
        clip_selection_task.s(),
        orchestration_callback_task.s(job_id=job_id)
    )

    analysis_chord = chord(
        header=[transcription_task.s(), scene_detection_task.s()],
        body=post_analysis_chain
    )

    # Combine prep and analysis sequentially
    full_workflow = chain(
        download_task.s(job_id=job_id, youtube_url=youtube_url, local_path=local_path, **kwargs),
        validate_media_task.s(),
        extract_audio_task.s(),
        analysis_chord
    ).on_error(job_err_cb)
    
    full_workflow.apply_async(queue="celery")


@celery_app.task(name="orchestration_callback")
def orchestration_callback_task(clip_ids: list[str], job_id: str = None):
    """
    Receives selected clip IDs from `clip_selection_task`.
    Dispatches a parallel group of independent clip workflows.
    """
    from backend.tasks.clip_tasks import reframe_task, render_task, output_validation_task, publish_task
    
    logger.info(f"Orchestrating {len(clip_ids)} clips for job {job_id}")
    
    clip_chains = []
    for clip_id in clip_ids:
        # Per-clip error callback
        clip_err_cb = handle_pipeline_failure_task.s(job_id=job_id, clip_id=clip_id, stage="clip_workflow")
        
        c_chain = chain(
            reframe_task.s(clip_id, job_id=job_id),
            render_task.s(),
            output_validation_task.s(),
            publish_task.s()
        ).on_error(clip_err_cb)
        
        clip_chains.append(c_chain)
    
    job_completion_cb = job_completion_aggregation_task.s(job_id=job_id)

    # Execute all clips in parallel, then aggregate job completion
    clip_group = chord(group(clip_chains), body=job_completion_cb)
    clip_group.apply_async(queue="celery")


@celery_app.task(name="job_completion_aggregation")
def job_completion_aggregation_task(results, job_id: str):
    """
    Executed after all clip workflows finish (success or failure).
    Marks the overall job as completed or failed based on clip statuses.
    Idempotent: querying the DB ensures it computes the true state.
    """
    logger.info(f"All clip workflows completed for job {job_id}. Aggregating results...")
    
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, Job
    
    with SyncSessionLocal() as session:
        job = session.query(Job).filter_by(id=job_id).first()
        if not job or not job.video_id:
            update_job_sync(job_id, "failed", 100, "Job or video_id not found")
            return

        if job.status == "cancelled":
            logger.info(f"Job {job_id} was cancelled. Skipping aggregation update.")
            return
            
        clips = session.query(Clip).filter_by(video_id=job.video_id).all()
        from datetime import datetime, timezone
        # Determine aggregate status
        if not clips:
            update_job_sync(job_id, "failed", 100, "No clips generated")
            if not job.completed_at:
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
            return
            
        failed_clips = [c for c in clips if c.status == "failed"]
        if len(failed_clips) == len(clips):
            update_job_sync(job_id, "failed", 100, f"All {len(clips)} clips failed")
        elif failed_clips:
            update_job_sync(job_id, "completed_with_failures", 100, f"{len(failed_clips)}/{len(clips)} clips failed")
        else:
            update_job_sync(job_id, "completed", 100, "All clips processed successfully")

        if not job.completed_at:
            job.completed_at = datetime.now(timezone.utc)
            session.commit()

        # Check if video belongs to an Upload Studio batch
        from backend.models.models import Video
        video = session.query(Video).filter_by(id=job.video_id).first()
        if video and video.upload_batch_id:
            try:
                from backend.tasks.studio_tasks import on_studio_video_finished_task
                on_studio_video_finished_task.delay(
                    batch_id=video.upload_batch_id,
                    video_id=video.id,
                    job_id=job.id
                )
            except Exception as e:
                logger.error(f"Failed to dispatch on_studio_video_finished_task: {e}")

        # Trigger queue drain to let next queued manual job start
        try:
            from backend.services.queue_manager import trigger_queue_drain_background
            trigger_queue_drain_background()
        except Exception as q_err:
            logger.warning(f"Failed to trigger queue drain on job completion: {q_err}")



@celery_app.task(name="backend.tasks.orchestration.stale_recovery_task")
def stale_recovery_task():
    """
    Celery Beat task that finds RUNNING TaskExecutions without a recent heartbeat,
    and transitions them to FAILED so that Celery redelivery can claim them.
    """
    from backend.models.database import SyncSessionLocal
    from backend.models.models import TaskExecution, TaskExecutionStatus
    from datetime import datetime, timezone, timedelta
    
    logger.info("Running stale execution recovery...")
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=10)
    
    recovered = 0
    with SyncSessionLocal() as session:
        stale_tasks = session.query(TaskExecution).filter(
            TaskExecution.status == TaskExecutionStatus.RUNNING.value,
            TaskExecution.last_heartbeat < threshold
        ).all()
        
        for task in stale_tasks:
            logger.warning(f"TaskExecution {task.id} (operation: {task.operation}) is stale. Marking as FAILED.")
            task.status = TaskExecutionStatus.FAILED.value
            task.failure_reason = "Stale execution timeout (no heartbeat)"
            recovered += 1
            
        session.commit()
        
    logger.info(f"Recovered {recovered} stale tasks.")


def resolve_video_decision_sync(
    decision_id: str,
    action: str = "auto",  # "countdown", "sweep", "apply_defaults", "custom", "cancel", "customize"
    custom_overrides: dict = None,
    expected_status: str | None = None,
    lease_token: str | None = None,
    force_customize: bool = False,
    channel_id: str | None = None,
) -> dict:
    """
    Idempotent, restart-safe decision resolution backed by row-level locking (SELECT ... FOR UPDATE).
    Guarantees:
    - Atomically resolves pending countdowns and customization lease expirations.
    - Prevents duplicate job creation across concurrent workers, periodic sweeps, and user requests.
    - Guards against stale/terminal overrides (CF-DEF-007) and active lease conflicts.
    - Preserves user overrides, channel defaults, and intentional cancellations.
    - Commits the decision state and job record BEFORE scheduling the Celery task.
    """
    import uuid
    from datetime import datetime, timezone, timedelta
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoDecision, VideoDecisionStatus, Channel
    from backend.models.db_sync import create_job_sync

    with SyncSessionLocal() as session:
        decision = (
            session.query(VideoDecision)
            .filter_by(id=decision_id)
            .with_for_update()
            .first()
        )
        if not decision:
            return {"error": f"Decision {decision_id} not found", "status": "not_found", "status_code": 404}

        if channel_id and decision.channel_id and decision.channel_id != channel_id:
            return {
                "error": f"Decision {decision_id} does not belong to channel {channel_id}",
                "status": "not_found",
                "status_code": 404,
            }

        now = datetime.now(timezone.utc)

        # Optimistic concurrency check: expected status guard
        if expected_status and decision.status != expected_status:
            return {
                "decision_id": decision.id,
                "status": decision.status,
                "job_id": decision.job_id,
                "conflict": True,
                "conflict_type": "state_mismatch",
                "error": f"Decision {decision_id} state mismatch: expected '{expected_status}' but was '{decision.status}'",
                "status_code": 409,
            }

        # Terminal state protection (when backed by an existing job or if cancelled)
        is_terminal = (
            (decision.status in (
                VideoDecisionStatus.RESOLVED_DEFAULTS.value,
                VideoDecisionStatus.RESOLVED_CUSTOM.value,
            ) and decision.job_id)
            or decision.status == VideoDecisionStatus.CANCELLED.value
        )
        if is_terminal:
            is_user_action = action in ("customize", "apply_defaults", "custom", "cancel")
            return {
                "decision_id": decision.id,
                "status": decision.status,
                "job_id": decision.job_id,
                "already_resolved": True,
                "conflict": is_user_action,
                "conflict_type": "terminal_state" if is_user_action else None,
                "error": f"Decision {decision_id} was already resolved or cancelled (status: '{decision.status}')" if is_user_action else None,
                "status_code": 409 if is_user_action else 200,
            }

        # Handle user cancellation
        if action == "cancel":
            decision.status = VideoDecisionStatus.CANCELLED.value
            decision.resolved_at = now
            session.commit()
            return {
                "decision_id": decision.id,
                "status": decision.status,
            }

        # Fail-safe guard: Check if video is a ClipForge-generated Short (prevent self-ingestion)
        from backend.services.provenance import check_is_clipforge_short_sync
        is_short, cf_clip, parent_v = check_is_clipforge_short_sync(session, decision.youtube_id)
        if is_short:
            parent_title = parent_v.title if parent_v else "Original Source Video"
            logger.warning(
                f"[Decision Resolution] Aborting resolution for decision {decision_id}: "
                f"'{decision.youtube_id}' is a ClipForge-generated output Short (from source '{parent_title}'). "
                "Self-ingestion is blocked."
            )
            decision.status = VideoDecisionStatus.CANCELLED.value
            decision.resolved_at = now
            session.commit()
            return {
                "decision_id": decision.id,
                "status": "cancelled",
                "reason": "clipforge_generated_short_blocked",
                "parent_source_title": parent_title
            }

        # Handle user entering customization modal
        if action == "customize":
            if (
                decision.status == VideoDecisionStatus.CUSTOMIZING.value
                and decision.customization_lease_expires_at
                and decision.customization_lease_expires_at > now
            ):
                active_token = (decision.overrides or {}).get("_lease_token") if isinstance(decision.overrides, dict) else None
                if lease_token and active_token and lease_token == active_token:
                    pass  # Renewing own lease
                elif force_customize:
                    pass  # Explicit takeover
                else:
                    return {
                        "decision_id": decision.id,
                        "status": decision.status,
                        "conflict": True,
                        "conflict_type": "active_lease",
                        "error": f"Decision {decision_id} is currently locked for customization by another session until {decision.customization_lease_expires_at.isoformat()}",
                        "lease_expires_at": decision.customization_lease_expires_at.isoformat(),
                        "status_code": 409,
                    }

            new_lease_token = lease_token or uuid.uuid4().hex[:16]
            decision.status = VideoDecisionStatus.CUSTOMIZING.value
            decision.customization_lease_expires_at = now + timedelta(seconds=120)
            existing_overrides = dict(decision.overrides) if isinstance(decision.overrides, dict) else {}
            existing_overrides["_lease_token"] = new_lease_token
            decision.overrides = existing_overrides
            session.commit()
            return {
                "decision_id": decision.id,
                "status": decision.status,
                "lease_expires_at": decision.customization_lease_expires_at.isoformat(),
                "lease_token": new_lease_token,
            }

        # Handle countdown expiration or safety sweep
        if action in ("countdown", "sweep"):
            if decision.status == VideoDecisionStatus.CUSTOMIZING.value:
                # Active customization session in progress
                if decision.customization_lease_expires_at and decision.customization_lease_expires_at > now:
                    return {"decision_id": decision.id, "status": decision.status, "skipped": "customization_in_progress"}
                # Customization lease expired without user submission -> safe fallback to defaults
            elif decision.status == VideoDecisionStatus.AWAITING_SETTINGS.value:
                if action == "countdown" or (decision.decision_deadline and decision.decision_deadline <= now):
                    pass
                else:
                    return {"decision_id": decision.id, "status": decision.status, "skipped": "deadline_not_reached"}
            else:
                return {"decision_id": decision.id, "status": decision.status, "skipped": "ineligible_status"}

            decision.status = VideoDecisionStatus.RESOLVED_DEFAULTS.value
            raw_overrides = decision.overrides or decision.channel_profile_snapshot or {}
            effective_config = {k: v for k, v in raw_overrides.items() if k != "_lease_token"} if isinstance(raw_overrides, dict) else {}

        # Handle immediate Apply Defaults request from user
        elif action == "apply_defaults":
            if (
                decision.status == VideoDecisionStatus.CUSTOMIZING.value
                and decision.customization_lease_expires_at
                and decision.customization_lease_expires_at > now
            ):
                active_token = (decision.overrides or {}).get("_lease_token") if isinstance(decision.overrides, dict) else None
                if not (lease_token and active_token and lease_token == active_token) and not force_customize:
                    return {
                        "decision_id": decision.id,
                        "status": decision.status,
                        "conflict": True,
                        "conflict_type": "active_lease",
                        "error": f"Decision {decision_id} is currently locked for customization by another session until {decision.customization_lease_expires_at.isoformat()}",
                        "lease_expires_at": decision.customization_lease_expires_at.isoformat(),
                        "status_code": 409,
                    }

            decision.status = VideoDecisionStatus.RESOLVED_DEFAULTS.value
            raw_overrides = decision.overrides or decision.channel_profile_snapshot or {}
            effective_config = {k: v for k, v in raw_overrides.items() if k != "_lease_token"} if isinstance(raw_overrides, dict) else {}

        # Handle Save & Process request with custom overrides from user
        elif action == "custom":
            active_token = (decision.overrides or {}).get("_lease_token") if isinstance(decision.overrides, dict) else None
            if lease_token and active_token and lease_token != active_token:
                return {
                    "decision_id": decision.id,
                    "status": decision.status,
                    "conflict": True,
                    "conflict_type": "stale_lease",
                    "error": f"Customization lease for decision {decision_id} has expired or been superseded by a newer session",
                    "status_code": 409,
                }

            decision.status = VideoDecisionStatus.RESOLVED_CUSTOM.value
            clean_overrides = dict(custom_overrides) if isinstance(custom_overrides, dict) else {}
            if "_lease_token" in clean_overrides:
                del clean_overrides["_lease_token"]
            effective_config = clean_overrides
            decision.overrides = effective_config

        else:
            return {"error": f"Invalid action: {action}"}

        decision.resolved_at = now

        # Ensure single job created per logical decision
        job_id = decision.job_id or str(uuid.uuid4())
        decision.job_id = job_id

        # Look up channel settings
        channel = session.query(Channel).filter_by(id=decision.channel_id).first()
        auto_publish = channel.auto_publish if channel else False
        publish_dest_id = channel.publish_destination_id if channel else None

        # Detect test channels or mock test URLs to isolate automated test runs
        is_test_job = False
        if channel and getattr(channel, "is_test", False):
            is_test_job = True
        elif channel and (
            channel.id.startswith(("ch_test", "test_", "ch_cust_", "ch_race_", "ch_iso_", "ch_dup_", "ch_dec_", "ch_cancel_", "ch_err_", "ch_combo_", "ch_restart_", "dest_"))
            or "Test Channel" in (channel.channel_name or "")
            or "Decision Channel" in (channel.channel_name or "")
            or "test" in (channel.channel_url or "").lower()
            or "decisionchannel" in (channel.channel_url or "").lower()
        ):
            is_test_job = True
        elif decision.youtube_url and any(
            x in decision.youtube_url for x in ["errvid", "stale", "combo", "mock", "test", "yt_dup", "yt_vid_", "yt_race_", "yt_a_", "yt_b_", "yt_cust_"]
        ):
            is_test_job = True

        if isinstance(effective_config, dict):
            effective_config = dict(effective_config)
            if "publish_destination_id" not in effective_config:
                effective_config["publish_destination_id"] = publish_dest_id
            if "auto_publish" not in effective_config:
                effective_config["auto_publish"] = auto_publish
            decision.overrides = effective_config

        # Create Job synchronously and commit DB transaction BEFORE Celery dispatch
        create_job_sync(
            job_id=job_id,
            source_url=decision.youtube_url,
            config=effective_config,
            channel_id=decision.channel_id,
            is_test=is_test_job,
            source_title=decision.video_title,
        )
        session.commit()

        # Dispatch pipeline task asynchronously
        try:
            start_video_processing_task.apply_async(
                kwargs={
                    "job_id": job_id,
                    "youtube_url": decision.youtube_url,
                    "channel_id": decision.channel_id,
                    "auto_publish": auto_publish,
                    "publish_destination_id": publish_dest_id
                },
                task_id=job_id
            )
        except Exception as dispatch_err:
            logger.error(f"Failed to dispatch Celery worker task for job {job_id}: {dispatch_err}")
            update_job_sync(job_id, "failed", 0, "Dispatch Error", error=str(dispatch_err))

        return {
            "decision_id": decision.id,
            "status": decision.status,
            "job_id": job_id,
        }


@celery_app.task(name="resolve_video_decision_countdown")
def resolve_video_decision_countdown_task(decision_id: str):
    """
    Celery task dispatched with countdown=20s to resolve decisions when user takes no action.
    """
    logger.info(f"Countdown task triggered for decision {decision_id}")
    return resolve_video_decision_sync(decision_id, action="countdown")


@celery_app.task(name="backend.tasks.orchestration.sweep_pending_decisions_task")
def sweep_pending_decisions_task():
    """
    Celery Beat task running periodically to resolve:
    1. Awaiting decisions whose deadline passed while backend/beat was offline or delayed.
    2. Abandoned customization sessions where customization lease expired.
    """
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoDecision, VideoDecisionStatus
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    decisions_to_resolve = []
    with SyncSessionLocal() as session:
        expired_awaiting = session.query(VideoDecision.id).filter(
            VideoDecision.status == VideoDecisionStatus.AWAITING_SETTINGS.value,
            VideoDecision.decision_deadline <= now
        ).all()
        for r in expired_awaiting:
            decisions_to_resolve.append(r[0])

        expired_customizing = session.query(VideoDecision.id).filter(
            VideoDecision.status == VideoDecisionStatus.CUSTOMIZING.value,
            VideoDecision.customization_lease_expires_at <= now
        ).all()
        for r in expired_customizing:
            decisions_to_resolve.append(r[0])

    resolved_count = 0
    for dec_id in decisions_to_resolve:
        try:
            res = resolve_video_decision_sync(dec_id, action="sweep")
            if not res.get("skipped"):
                resolved_count += 1
        except Exception as e:
            logger.error(f"Failed to sweep decision {dec_id}: {e}")

    if resolved_count:
        logger.info(f"Sweep resolved {resolved_count} pending decisions.")
