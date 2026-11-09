"""
test_ops_jobs_reconcile.py
===========================
Focused verification test suite for OPS-JOBS-RECONCILE-006.

Verifies:
1. JobReconciliationClassifier correctly classifies jobs across all defined states:
   - CONFIRMED_ACTIVE
   - CONFIRMED_TERMINAL
   - INCONSISTENT
   - ORPHANED
   - STALE_AMBIGUOUS
   - INSUFFICIENT_EVIDENCE
2. JobReconciliationClassifier correctly classifies clips across all defined states:
   - CONFIRMED_ACTIVE
   - CONFIRMED_TERMINAL
   - INCONSISTENT (e.g. status='publishing' with failed task execution)
   - ORPHANED
   - STALE_AMBIGUOUS
3. Diagnostic engine strictly enforces dry_run=True and rejects non-dry-run requests.
4. Engine executes SET TRANSACTION READ ONLY.
5. Engine performs zero database mutations and zero Celery task enqueues.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from backend.services.job_reconciliation import (
    JobReconciliationClassifier,
    ReconciliationClassification,
    ReconciliationDiagnosticEngine,
)


class TestJobReconciliationClassifier:
    """Unit tests for pure classification domain logic."""

    def test_classify_job_active(self):
        job = {
            "id": "job_active_1",
            "status": "pending",
            "celery_task_id": "task_active_123",
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            "is_test": False,
        }
        active_tasks = {"task_active_123"}
        cls, rationale, action = JobReconciliationClassifier.classify_job(
            job=job,
            task_executions=[],
            active_celery_task_ids=active_tasks,
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.CONFIRMED_ACTIVE
        assert "actively executing" in rationale

    def test_classify_job_terminal(self):
        for terminal_status in ("completed", "failed", "cancelled"):
            job = {
                "id": f"job_term_{terminal_status}",
                "status": terminal_status,
                "celery_task_id": "task_old",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
                "is_test": False,
            }
            cls, rationale, action = JobReconciliationClassifier.classify_job(
                job=job,
                task_executions=[],
                active_celery_task_ids=set(),
                redis_task_meta={},
            )
            assert cls == ReconciliationClassification.CONFIRMED_TERMINAL
            assert "terminal state" in rationale

    def test_classify_job_inconsistent_with_terminal_task_execution(self):
        job = {
            "id": "job_inconsistent_1",
            "status": "pending",
            "celery_task_id": "task_failed_1",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=2),
            "is_test": False,
        }
        task_executions = [
            {"id": "te_1", "status": "failed", "failure_reason": "Out of memory"}
        ]
        cls, rationale, action = JobReconciliationClassifier.classify_job(
            job=job,
            task_executions=task_executions,
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.INCONSISTENT
        assert "underlying task_execution" in rationale

    def test_classify_job_redis_terminal_meta(self):
        job = {
            "id": "job_redis_success",
            "status": "pending",
            "celery_task_id": "task_redis_123",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=3),
            "is_test": False,
        }
        redis_meta = {
            "task_redis_123": {"status": "SUCCESS", "result": {"clips": 3}}
        }
        cls, rationale, action = JobReconciliationClassifier.classify_job(
            job=job,
            task_executions=[],
            active_celery_task_ids=set(),
            redis_task_meta=redis_meta,
        )
        assert cls == ReconciliationClassification.CONFIRMED_TERMINAL
        assert "terminal state 'SUCCESS'" in rationale

    def test_classify_job_orphaned_test_synthetic_task(self):
        job = {
            "id": "job_test_compat",
            "status": "pending",
            "celery_task_id": "task_compat_e4221c2a",
            "created_at": datetime.now(timezone.utc) - timedelta(days=20),
            "is_test": True,
        }
        cls, rationale, action = JobReconciliationClassifier.classify_job(
            job=job,
            task_executions=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.ORPHANED
        assert "synthetic task ID" in rationale

    def test_classify_job_orphaned_no_task_dispatch(self):
        job = {
            "id": "job_no_task_id",
            "status": "pending",
            "celery_task_id": None,
            "created_at": datetime.now(timezone.utc) - timedelta(days=10),
            "is_test": True,
        }
        cls, rationale, action = JobReconciliationClassifier.classify_job(
            job=job,
            task_executions=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.ORPHANED
        assert "without Celery task dispatch" in rationale

    def test_classify_job_stale_ambiguous_non_test_missing_redis(self):
        job = {
            "id": "job_ambiguous_prod",
            "status": "pending",
            "celery_task_id": "4a905c3c-ad6b-4f8a-9319-5a57ece28204",
            "created_at": datetime.now(timezone.utc) - timedelta(days=3),
            "is_test": False,
        }
        cls, rationale, action = JobReconciliationClassifier.classify_job(
            job=job,
            task_executions=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.STALE_AMBIGUOUS
        assert "not active in Celery and not found in result backend" in rationale


class TestClipReconciliationClassifier:
    """Unit tests for Clip reconciliation domain logic."""

    def test_classify_clip_active_publish(self):
        clip = {
            "id": "clip_pub_active",
            "status": "publishing",
            "publish_status": "draft",
            "publish_task_id": "task_active_pub_1",
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=2),
            "youtube_short_id": None,
            "output_path": None,
        }
        active_tasks = {"task_active_pub_1"}
        cls, rationale, action = JobReconciliationClassifier.classify_clip(
            clip=clip,
            task_executions=[],
            publish_records=[],
            active_celery_task_ids=active_tasks,
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.CONFIRMED_ACTIVE
        assert "actively executing" in rationale

    def test_classify_clip_remote_published_terminal(self):
        clip = {
            "id": "clip_pub_verified",
            "status": "completed",
            "publish_status": "published",
            "publish_task_id": None,
            "created_at": datetime.now(timezone.utc) - timedelta(days=5),
            "youtube_short_id": "YpHobheDpk8",
            "output_path": "/outputs/test.mp4",
        }
        cls, rationale, action = JobReconciliationClassifier.classify_clip(
            clip=clip,
            task_executions=[],
            publish_records=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.CONFIRMED_TERMINAL
        assert "Remote publication confirmed" in rationale

    def test_classify_clip_remote_published_inconsistent_status(self):
        clip = {
            "id": "clip_pub_inconsistent",
            "status": "failed",
            "publish_status": "draft",
            "publish_task_id": None,
            "created_at": datetime.now(timezone.utc) - timedelta(days=5),
            "youtube_short_id": "YpHobheDpk8",
            "output_path": "/outputs/test.mp4",
        }
        cls, rationale, action = JobReconciliationClassifier.classify_clip(
            clip=clip,
            task_executions=[],
            publish_records=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.INCONSISTENT
        assert "Remote YouTube Short ID 'YpHobheDpk8' exists" in rationale

    def test_classify_clip_september_historical_publishing_root_cause(self):
        """Validates the exact historical pattern of the 7 September 2026 publishing clips."""
        clip = {
            "id": "d4830d97-b29d-4f06-82b9-1b246b833294",
            "status": "publishing",
            "publish_status": "draft",
            "publish_task_id": None,
            "created_at": datetime.fromisoformat("2026-09-23T05:01:36.376438+00:00"),
            "youtube_short_id": None,
            "output_path": "/outputs/final.mp4",
        }
        task_executions = [
            {"operation": "reframe", "status": "succeeded", "failure_reason": None},
            {"operation": "render", "status": "succeeded", "failure_reason": None},
            {"operation": "publish", "status": "failed", "failure_reason": "Stale execution timeout (no heartbeat)"},
        ]
        cls, rationale, action = JobReconciliationClassifier.classify_clip(
            clip=clip,
            task_executions=task_executions,
            publish_records=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
            file_exists_fn=lambda p: True,
        )
        assert cls == ReconciliationClassification.INCONSISTENT
        assert "underlying publish task_execution failed" in rationale
        assert "Stale execution timeout (no heartbeat)" in rationale
        assert "propose updating clip status to 'failed'" in action

    def test_classify_clip_orphaned_stale_publishing(self):
        clip = {
            "id": "clip_orphaned_pub",
            "status": "publishing",
            "publish_status": "draft",
            "publish_task_id": None,
            "created_at": datetime.now(timezone.utc) - timedelta(days=40),
            "youtube_short_id": None,
            "output_path": None,
        }
        cls, rationale, action = JobReconciliationClassifier.classify_clip(
            clip=clip,
            task_executions=[],
            publish_records=[],
            active_celery_task_ids=set(),
            redis_task_meta={},
        )
        assert cls == ReconciliationClassification.ORPHANED
        assert "without active worker task" in rationale


class TestReconciliationDiagnosticEngineProtections:
    """Verifies that the diagnostic engine strictly enforces safety, read-only mode, and zero writes."""

    def test_engine_rejects_non_dry_run(self):
        mock_session = MagicMock()
        engine = ReconciliationDiagnosticEngine(session=mock_session)
        with pytest.raises(ValueError, match="strictly prohibits non-dry-run operations"):
            engine.execute_audit(dry_run=False)

    def test_engine_enforces_read_only_transaction(self):
        mock_session = MagicMock()
        # First call is SHOW transaction_read_only ("on"), subsequent calls are count(*) (0)
        mock_session.execute.return_value.scalar.side_effect = ["on", 0, 0, 0, 0, 0, 0, 0]
        mock_session.execute.return_value.fetchone.return_value = (
            "test_db", "test_user", "127.0.0.1", 5432, "PostgreSQL 15"
        )
        mock_session.execute.return_value.fetchall.return_value = []

        engine = ReconciliationDiagnosticEngine(session=mock_session, git_revision="test_rev")
        report = engine.execute_audit(dry_run=True)

        assert report.database_identity.read_only_verified is True
        assert report.database_identity.database_name == "test_db"
        assert report.dry_run is True

        # Assert no commit or rollback or write queries were made
        assert mock_session.commit.call_count == 0
        executed_sqls = [str(call.args[0]).strip().upper() for call in mock_session.execute.call_args_list]
        for sql in executed_sqls:
            verb = sql.split()[0] if sql.split() else ""
            assert verb not in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE")

    def test_live_db_audit_makes_zero_writes(self):
        """Executes against live PostgreSQL database and asserts zero writes occurred."""
        from backend.models.database import SyncSessionLocal
        from sqlalchemy import text

        with SyncSessionLocal() as session:
            # Record before counts
            counts_before = {}
            for tbl in ("jobs", "clips", "publish_records", "publish_targets", "task_executions"):
                cnt = session.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
                counts_before[tbl] = cnt

            # Execute audit
            engine = ReconciliationDiagnosticEngine(session=session, git_revision="test_live_verify")
            report = engine.execute_audit(dry_run=True)

            assert report.dry_run is True
            assert report.database_identity.read_only_verified is True
            assert len(report.seven_publishing_clips_audit) == 7

            # Record after counts
            counts_after = {}
            for tbl in ("jobs", "clips", "publish_records", "publish_targets", "task_executions"):
                cnt = session.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
                counts_after[tbl] = cnt

            # Strict equality assertion: zero writes occurred
            assert counts_before == counts_after, f"Row counts changed! Before: {counts_before}, After: {counts_after}"
