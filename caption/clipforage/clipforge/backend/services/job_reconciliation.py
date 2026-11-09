"""
job_reconciliation.py
======================
OPS-JOBS-RECONCILE-006: Diagnostic Reconciliation Engine for Historical
and Legacy Job and Clip Statuses.

STRICT INVARIANT:
- This module is READ-ONLY.
- No mutation switches (no update, delete, cancel, retry, enqueue, or repair).
- All database queries enforce SET TRANSACTION READ ONLY.
- Default and only operation mode is dry-run audit.
"""

from __future__ import annotations

import os
import enum
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session


class ReconciliationClassification(str, enum.Enum):
    CONFIRMED_ACTIVE = "CONFIRMED_ACTIVE"
    CONFIRMED_TERMINAL = "CONFIRMED_TERMINAL"
    STALE_AMBIGUOUS = "STALE_AMBIGUOUS"
    ORPHANED = "ORPHANED"
    INCONSISTENT = "INCONSISTENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class TaskExecutionSummary:
    id: str
    operation: str
    status: str
    attempt: int
    worker_id: Optional[str]
    started_at: Optional[str]
    last_heartbeat: Optional[str]
    completed_at: Optional[str]
    failure_reason: Optional[str]


@dataclass
class PublishRecordSummary:
    idempotency_key: str
    job_id: str
    target: str
    external_id: Optional[str]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class ReconciledRow:
    internal_id: str
    object_type: str  # "job" or "clip"
    current_status: str
    secondary_status: Optional[str]  # e.g. publish_status for clips
    created_at: Optional[str]
    updated_at: Optional[str]
    is_test: bool
    related_task_id: Optional[str]
    related_video_id: Optional[str]
    related_channel_id: Optional[str]
    artifact_exists: Optional[bool]
    artifact_path: Optional[str]
    remote_publish_id: Optional[str]
    task_executions: List[TaskExecutionSummary] = field(default_factory=list)
    publish_records: List[PublishRecordSummary] = field(default_factory=list)
    classification: ReconciliationClassification = ReconciliationClassification.INSUFFICIENT_EVIDENCE
    confidence_rationale: str = ""
    recommended_next_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value
        return d


@dataclass
class DatabaseIdentity:
    database_name: str
    user_name: str
    server_address: Optional[str]
    server_port: Optional[int]
    postgres_version: str
    read_only_verified: bool


@dataclass
class ReconciliationReport:
    generated_at_utc: str
    git_revision: str
    database_identity: DatabaseIdentity
    dry_run: bool
    summary_counts: Dict[str, int]
    classification_breakdown: Dict[str, int]
    seven_publishing_clips_audit: List[ReconciledRow]
    candidate_jobs: List[ReconciledRow]
    candidate_clips: List[ReconciledRow]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "git_revision": self.git_revision,
            "database_identity": asdict(self.database_identity),
            "dry_run": self.dry_run,
            "summary_counts": self.summary_counts,
            "classification_breakdown": self.classification_breakdown,
            "seven_publishing_clips_audit": [r.to_dict() for r in self.seven_publishing_clips_audit],
            "candidate_jobs_count": len(self.candidate_jobs),
            "candidate_clips_count": len(self.candidate_clips),
            "candidate_jobs": [r.to_dict() for r in self.candidate_jobs],
            "candidate_clips": [r.to_dict() for r in self.candidate_clips],
        }


class JobReconciliationClassifier:
    """Pure domain logic classifier with zero database dependencies."""

    @staticmethod
    def classify_job(
        job: Dict[str, Any],
        task_executions: List[Dict[str, Any]],
        active_celery_task_ids: set[str],
        redis_task_meta: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> tuple[ReconciliationClassification, str, str]:
        if now is None:
            now = datetime.now(timezone.utc)

        status = str(job.get("status") or "").lower()
        task_id = job.get("celery_task_id")
        created_at = job.get("created_at")
        is_test = bool(job.get("is_test", False))

        # Calculate age in seconds
        age_seconds = 0.0
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - created_at).total_seconds()

        # 1. Active Task
        if task_id and task_id in active_celery_task_ids:
            return (
                ReconciliationClassification.CONFIRMED_ACTIVE,
                f"Task ID {task_id} is registered as actively executing on a live Celery worker.",
                "No action needed; job is actively processing in worker pool.",
            )

        # 2. Terminal status
        if status in ("completed", "failed", "cancelled"):
            return (
                ReconciliationClassification.CONFIRMED_TERMINAL,
                f"Job is already in terminal state '{status}'.",
                "No action needed; historical record is terminal.",
            )

        # 3. Pending status analysis
        if status == "pending":
            # Did underlying task executions finish?
            terminal_te = [
                te for te in task_executions
                if str(te.get("status") or "").lower() in ("succeeded", "failed", "cancelled")
            ]
            if terminal_te and not any(str(te.get("status") or "").lower() == "running" for te in task_executions):
                last_te = terminal_te[-1]
                return (
                    ReconciliationClassification.INCONSISTENT,
                    f"Job status is 'pending' but underlying task_execution {last_te.get('id')} reached terminal status '{last_te.get('status')}'.",
                    f"Upon explicit row-level authorization, propose synchronizing job status to '{last_te.get('status')}'.",
                )

            # Has Celery task ID
            if task_id:
                meta = redis_task_meta.get(task_id)
                meta_status = meta.get("status") if isinstance(meta, dict) else None

                if meta_status in ("SUCCESS", "FAILURE", "REVOKED"):
                    mapped_status = "completed" if meta_status == "SUCCESS" else "failed"
                    return (
                        ReconciliationClassification.CONFIRMED_TERMINAL,
                        f"Job status is 'pending', but Celery result backend records terminal state '{meta_status}' for task {task_id}.",
                        f"Upon explicit row-level authorization, propose updating job status to '{mapped_status}'.",
                    )

                if age_seconds > 3600:
                    if is_test or (task_id and "task_compat" in task_id or "task_" in task_id):
                        return (
                            ReconciliationClassification.ORPHANED,
                            f"Test job created {age_seconds / 86400:.1f} days ago with synthetic task ID '{task_id}', absent from Celery broker/backend.",
                            "Upon explicit row-level authorization, propose marking stale test job as 'cancelled'.",
                        )
                    return (
                        ReconciliationClassification.STALE_AMBIGUOUS,
                        f"Job is 'pending' with task ID '{task_id}' (age {age_seconds / 86400:.1f} days), not active in Celery and not found in result backend.",
                        "Upon explicit row-level authorization, propose verifying queue logs and transitioning to 'failed' (timeout).",
                    )

            # No Celery task ID
            if age_seconds > 3600:
                if is_test:
                    return (
                        ReconciliationClassification.ORPHANED,
                        f"Test job created {age_seconds / 86400:.1f} days ago without Celery task dispatch (celery_task_id is NULL); never enqueued.",
                        "Upon explicit row-level authorization, propose marking orphaned test job as 'cancelled'.",
                    )
                return (
                    ReconciliationClassification.ORPHANED,
                    f"Job created {age_seconds / 86400:.1f} days ago without Celery task dispatch; orphaned before enqueue.",
                    "Upon explicit row-level authorization, propose marking orphaned job as 'failed' (dispatch_missing).",
                )

            return (
                ReconciliationClassification.STALE_AMBIGUOUS,
                f"Job created recently ({age_seconds:.0f}s ago) without active worker confirmation.",
                "Wait for worker pickup or verify broker connectivity.",
            )

        return (
            ReconciliationClassification.INSUFFICIENT_EVIDENCE,
            f"Job status '{status}' has insufficient state correlation to classify definitively.",
            "Inspect raw transaction logs.",
        )

    @staticmethod
    def classify_clip(
        clip: Dict[str, Any],
        task_executions: List[Dict[str, Any]],
        publish_records: List[Dict[str, Any]],
        active_celery_task_ids: set[str],
        redis_task_meta: Dict[str, Any],
        file_exists_fn: Optional[Callable[[str], bool]] = None,
        now: Optional[datetime] = None,
    ) -> tuple[ReconciliationClassification, str, str]:
        if now is None:
            now = datetime.now(timezone.utc)
        if file_exists_fn is None:
            file_exists_fn = os.path.exists

        status = str(clip.get("status") or "").lower()
        pub_status = str(clip.get("publish_status") or "").lower()
        publish_task_id = clip.get("publish_task_id")
        created_at = clip.get("created_at")
        yt_short_id = clip.get("youtube_short_id")
        output_path = clip.get("output_path")

        age_seconds = 0.0
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - created_at).total_seconds()

        # Check artifact
        artifact_present = False
        if output_path:
            try:
                artifact_present = file_exists_fn(output_path)
            except Exception:
                artifact_present = False

        # 1. Active publish task
        if publish_task_id and publish_task_id in active_celery_task_ids:
            return (
                ReconciliationClassification.CONFIRMED_ACTIVE,
                f"Publish task {publish_task_id} is actively executing in Celery worker pool.",
                "No action needed; publishing in flight.",
            )

        # 2. Remote publication verified
        if yt_short_id and not yt_short_id.startswith("mock_"):
            if status != "completed" or pub_status != "published":
                return (
                    ReconciliationClassification.INCONSISTENT,
                    f"Remote YouTube Short ID '{yt_short_id}' exists, but status='{status}', publish_status='{pub_status}'.",
                    "Upon explicit row-level authorization, propose synchronizing status to 'completed' and publish_status to 'published'.",
                )
            return (
                ReconciliationClassification.CONFIRMED_TERMINAL,
                f"Remote publication confirmed with YouTube Short ID '{yt_short_id}'.",
                "No action needed; publication verified.",
            )

        # 3. Specific inspection for status == "publishing"
        if status == "publishing" or pub_status == "publishing":
            # Check publish task executions
            publish_tes = [
                te for te in task_executions
                if str(te.get("operation") or "").lower() == "publish"
            ]
            failed_publish_te = [
                te for te in publish_tes
                if str(te.get("status") or "").lower() in ("failed", "cancelled")
            ]

            if failed_publish_te:
                last_failed = failed_publish_te[-1]
                reason = last_failed.get("failure_reason") or "unspecified task failure"
                return (
                    ReconciliationClassification.INCONSISTENT,
                    f"Clip status is '{status}' (publish_status='{pub_status}'), but underlying publish task_execution failed with reason: '{reason}'.",
                    f"Upon explicit row-level authorization, propose updating clip status to 'failed' with error='{reason}'.",
                )

            # Check publish records
            completed_pr = [
                pr for pr in publish_records
                if str(pr.get("status") or "").lower() == "completed"
            ]
            if completed_pr:
                return (
                    ReconciliationClassification.INCONSISTENT,
                    "Clip status is 'publishing', but PublishRecord reports 'completed'.",
                    "Upon explicit row-level authorization, propose updating clip status to 'completed' / 'published'.",
                )

            # If age > 24 hours with no active task or queue
            if age_seconds > 86400:
                return (
                    ReconciliationClassification.ORPHANED,
                    f"Clip in '{status}' status for {age_seconds / 86400:.1f} days without active worker task, queue record, or remote publish response.",
                    "Upon explicit row-level authorization, propose transitioning status from 'publishing' to 'failed' (stale_timeout).",
                )

            return (
                ReconciliationClassification.STALE_AMBIGUOUS,
                "Clip in 'publishing' state without active worker heartbeat.",
                "Inspect worker logs or wait for heartbeat.",
            )

        # 4. Standard terminal
        if status in ("completed", "failed", "cancelled"):
            return (
                ReconciliationClassification.CONFIRMED_TERMINAL,
                f"Clip is in terminal state '{status}'.",
                "No action needed.",
            )

        # 5. Pending clips
        if status == "pending":
            if age_seconds > 86400 and not task_executions:
                return (
                    ReconciliationClassification.ORPHANED,
                    f"Clip in 'pending' status for {age_seconds / 86400:.1f} days with no task executions.",
                    "Upon explicit row-level authorization, propose marking orphaned clip as 'failed' or 'cancelled'.",
                )
            return (
                ReconciliationClassification.STALE_AMBIGUOUS,
                f"Clip in 'pending' status (age {age_seconds:.0f}s).",
                "Monitor for processing.",
            )

        return (
            ReconciliationClassification.INSUFFICIENT_EVIDENCE,
            f"Clip status '{status}' has insufficient data to classify.",
            "Inspect raw logs.",
        )


class ReconciliationDiagnosticEngine:
    """Orchestrates database queries and generates the read-only reconciliation report."""

    def __init__(self, session: Session, git_revision: str = "unknown"):
        self.session = session
        self.git_revision = git_revision

    def assert_read_only_and_get_identity(self) -> DatabaseIdentity:
        # Enforce read-only transaction mode
        self.session.execute(text("SET TRANSACTION READ ONLY"))

        # Verify transaction_read_only setting
        check_ro = self.session.execute(text("SHOW transaction_read_only")).scalar()
        is_ro = str(check_ro).strip().lower() in ("on", "true", "yes", "1")

        # Get DB identity
        row = self.session.execute(
            text("SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), version()")
        ).fetchone()

        if row is None:
            raise RuntimeError("Failed to query PostgreSQL database identity")

        return DatabaseIdentity(
            database_name=str(row[0]),
            user_name=str(row[1]),
            server_address=str(row[2]) if row[2] else None,
            server_port=int(row[3]) if row[3] else None,
            postgres_version=str(row[4]),
            read_only_verified=is_ro,
        )

    def execute_audit(
        self,
        active_celery_task_ids: Optional[set[str]] = None,
        redis_task_meta: Optional[Dict[str, Any]] = None,
        file_exists_fn: Optional[Callable[[str], bool]] = None,
        dry_run: bool = True,
    ) -> ReconciliationReport:
        if not dry_run:
            raise ValueError("OPS-JOBS-RECONCILE-006 strictly prohibits non-dry-run operations. dry_run must be True.")

        if active_celery_task_ids is None:
            active_celery_task_ids = set()
        if redis_task_meta is None:
            redis_task_meta = {}

        now_utc = datetime.now(timezone.utc)
        db_identity = self.assert_read_only_and_get_identity()

        # 1. Total counts across repository tables
        tables = ["jobs", "clips", "publish_records", "publish_targets", "task_executions", "videos", "channels"]
        summary_counts: Dict[str, int] = {}
        for t in tables:
            cnt = self.session.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            summary_counts[t] = int(cnt or 0)

        # 2. Query Candidate Jobs (all non-terminal jobs)
        job_rows = self.session.execute(text("""
            SELECT id, video_id, source_url, source_title, status, progress, current_step,
                   celery_task_id, channel_id, is_test, created_at, updated_at
            FROM jobs
            WHERE status NOT IN ('completed', 'failed', 'cancelled')
            ORDER BY created_at ASC
        """)).fetchall()

        # Pre-fetch task executions for candidate jobs
        job_ids = [str(r[0]) for r in job_rows]
        te_by_job: Dict[str, List[Dict[str, Any]]] = {}
        if job_ids:
            te_rows = self.session.execute(text("""
                SELECT id, job_id, operation, status, attempt, worker_id, started_at,
                       last_heartbeat, completed_at, failure_reason
                FROM task_executions
                WHERE job_id = ANY(:jids)
                ORDER BY started_at ASC
            """), {"jids": job_ids}).fetchall()
            for r in te_rows:
                te_dict = {
                    "id": str(r[0]),
                    "job_id": str(r[1]),
                    "operation": str(r[2]),
                    "status": str(r[3]),
                    "attempt": int(r[4] or 1),
                    "worker_id": str(r[5]) if r[5] else None,
                    "started_at": r[6].isoformat() if r[6] else None,
                    "last_heartbeat": r[7].isoformat() if r[7] else None,
                    "completed_at": r[8].isoformat() if r[8] else None,
                    "failure_reason": str(r[9]) if r[9] else None,
                }
                te_by_job.setdefault(str(r[1]), []).append(te_dict)

        candidate_jobs: List[ReconciledRow] = []
        for r in job_rows:
            jid = str(r[0])
            j_dict = {
                "id": jid,
                "video_id": str(r[1]) if r[1] else None,
                "source_url": str(r[2]) if r[2] else None,
                "source_title": str(r[3]) if r[3] else None,
                "status": str(r[4]),
                "progress": int(r[5] or 0),
                "current_step": str(r[6]) if r[6] else None,
                "celery_task_id": str(r[7]) if r[7] else None,
                "channel_id": str(r[8]) if r[8] else None,
                "is_test": bool(r[9]),
                "created_at": r[10],
                "updated_at": r[11],
            }
            tes = te_by_job.get(jid, [])
            classification, rationale, next_action = JobReconciliationClassifier.classify_job(
                j_dict, tes, active_celery_task_ids, redis_task_meta, now=now_utc
            )
            te_summaries = [
                TaskExecutionSummary(
                    id=t["id"],
                    operation=t["operation"],
                    status=t["status"],
                    attempt=t["attempt"],
                    worker_id=t["worker_id"],
                    started_at=t["started_at"],
                    last_heartbeat=t["last_heartbeat"],
                    completed_at=t["completed_at"],
                    failure_reason=t["failure_reason"],
                )
                for t in tes
            ]
            candidate_jobs.append(
                ReconciledRow(
                    internal_id=jid,
                    object_type="job",
                    current_status=j_dict["status"],
                    secondary_status=None,
                    created_at=r[10].isoformat() if r[10] else None,
                    updated_at=r[11].isoformat() if r[11] else None,
                    is_test=j_dict["is_test"],
                    related_task_id=j_dict["celery_task_id"],
                    related_video_id=j_dict["video_id"],
                    related_channel_id=j_dict["channel_id"],
                    artifact_exists=None,
                    artifact_path=None,
                    remote_publish_id=None,
                    task_executions=te_summaries,
                    publish_records=[],
                    classification=classification,
                    confidence_rationale=rationale,
                    recommended_next_action=next_action,
                )
            )

        # 3. Query Candidate Clips (status == 'publishing' OR publish_status == 'publishing' OR status == 'pending')
        clip_rows = self.session.execute(text("""
            SELECT id, video_id, title, status, publish_status, publish_stage,
                   publish_task_id, output_path, thumbnail_path, youtube_short_id,
                   publish_destination_id, privacy, created_at
            FROM clips
            WHERE status IN ('publishing', 'pending') OR publish_status = 'publishing'
            ORDER BY created_at ASC
        """)).fetchall()

        clip_ids = [str(r[0]) for r in clip_rows]
        te_by_clip: Dict[str, List[Dict[str, Any]]] = {}
        pr_by_clip: Dict[str, List[Dict[str, Any]]] = {}

        if clip_ids:
            te_clip_rows = self.session.execute(text("""
                SELECT id, clip_id, operation, status, attempt, worker_id, started_at,
                       last_heartbeat, completed_at, failure_reason
                FROM task_executions
                WHERE clip_id = ANY(:cids)
                ORDER BY started_at ASC
            """), {"cids": clip_ids}).fetchall()
            for r in te_clip_rows:
                te_dict = {
                    "id": str(r[0]),
                    "clip_id": str(r[1]),
                    "operation": str(r[2]),
                    "status": str(r[3]),
                    "attempt": int(r[4] or 1),
                    "worker_id": str(r[5]) if r[5] else None,
                    "started_at": r[6].isoformat() if r[6] else None,
                    "last_heartbeat": r[7].isoformat() if r[7] else None,
                    "completed_at": r[8].isoformat() if r[8] else None,
                    "failure_reason": str(r[9]) if r[9] else None,
                }
                te_by_clip.setdefault(str(r[1]), []).append(te_dict)

            pr_rows = self.session.execute(text("""
                SELECT idempotency_key, job_id, clip_id, target, external_id, status, created_at, updated_at
                FROM publish_records
                WHERE clip_id = ANY(:cids)
                ORDER BY created_at ASC
            """), {"cids": clip_ids}).fetchall()
            for r in pr_rows:
                pr_dict = {
                    "idempotency_key": str(r[0]),
                    "job_id": str(r[1]),
                    "clip_id": str(r[2]),
                    "target": str(r[3]),
                    "external_id": str(r[4]) if r[4] else None,
                    "status": str(r[5]),
                    "created_at": r[6].isoformat() if r[6] else None,
                    "updated_at": r[7].isoformat() if r[7] else None,
                }
                pr_by_clip.setdefault(str(r[2]), []).append(pr_dict)

        candidate_clips: List[ReconciledRow] = []
        seven_sept_publishing_clips: List[ReconciledRow] = []

        seven_target_ids = {
            "d4830d97-b29d-4f06-82b9-1b246b833294",
            "d95b56db-1139-402e-9e78-90a119f7f3ed",
            "a5a85107-d0f5-48ca-94d3-498bd0ae4bbc",
            "c0cdcbed-7b2c-42a0-b41d-7ae8f609d307",
            "86b3193b-4c93-4367-a7db-6b7e757ef43f",
            "33268872-05b8-47f2-9974-0fda8057b2b6",
            "9374817f-0f8b-42a8-84d2-f0737513de01",
        }

        for r in clip_rows:
            cid = str(r[0])
            c_dict = {
                "id": cid,
                "video_id": str(r[1]),
                "title": str(r[2]),
                "status": str(r[3]),
                "publish_status": str(r[4]),
                "publish_stage": str(r[5]) if r[5] else None,
                "publish_task_id": str(r[6]) if r[6] else None,
                "output_path": str(r[7]) if r[7] else None,
                "thumbnail_path": str(r[8]) if r[8] else None,
                "youtube_short_id": str(r[9]) if r[9] else None,
                "publish_destination_id": str(r[10]) if r[10] else None,
                "privacy": str(r[11]),
                "created_at": r[12],
            }
            tes = te_by_clip.get(cid, [])
            prs = pr_by_clip.get(cid, [])

            classification, rationale, next_action = JobReconciliationClassifier.classify_clip(
                c_dict, tes, prs, active_celery_task_ids, redis_task_meta,
                file_exists_fn=file_exists_fn, now=now_utc
            )

            te_summaries = [
                TaskExecutionSummary(
                    id=t["id"],
                    operation=t["operation"],
                    status=t["status"],
                    attempt=t["attempt"],
                    worker_id=t["worker_id"],
                    started_at=t["started_at"],
                    last_heartbeat=t["last_heartbeat"],
                    completed_at=t["completed_at"],
                    failure_reason=t["failure_reason"],
                )
                for t in tes
            ]
            pr_summaries = [
                PublishRecordSummary(
                    idempotency_key=p["idempotency_key"],
                    job_id=p["job_id"],
                    target=p["target"],
                    external_id=p["external_id"],
                    status=p["status"],
                    created_at=p["created_at"],
                    updated_at=p["updated_at"],
                )
                for p in prs
            ]

            artifact_path = c_dict["output_path"]
            art_exists = None
            if artifact_path:
                try:
                    art_exists = (file_exists_fn or os.path.exists)(artifact_path)
                except Exception:
                    art_exists = False

            row = ReconciledRow(
                internal_id=cid,
                object_type="clip",
                current_status=c_dict["status"],
                secondary_status=c_dict["publish_status"],
                created_at=r[12].isoformat() if r[12] else None,
                updated_at=None,
                is_test=False,
                related_task_id=c_dict["publish_task_id"],
                related_video_id=c_dict["video_id"],
                related_channel_id=c_dict["publish_destination_id"],
                artifact_exists=art_exists,
                artifact_path=artifact_path,
                remote_publish_id=c_dict["youtube_short_id"],
                task_executions=te_summaries,
                publish_records=pr_summaries,
                classification=classification,
                confidence_rationale=rationale,
                recommended_next_action=next_action,
            )
            candidate_clips.append(row)

            if cid in seven_target_ids:
                seven_sept_publishing_clips.append(row)

        # 4. Aggregations
        classification_breakdown: Dict[str, int] = {}
        for r in candidate_jobs + candidate_clips:
            k = r.classification.value
            classification_breakdown[k] = classification_breakdown.get(k, 0) + 1

        return ReconciliationReport(
            generated_at_utc=now_utc.isoformat(),
            git_revision=self.git_revision,
            database_identity=db_identity,
            dry_run=True,
            summary_counts=summary_counts,
            classification_breakdown=classification_breakdown,
            seven_publishing_clips_audit=seven_sept_publishing_clips,
            candidate_jobs=candidate_jobs,
            candidate_clips=candidate_clips,
        )
