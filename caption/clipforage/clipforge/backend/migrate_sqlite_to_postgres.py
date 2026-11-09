import os
import sys
import sqlite3
from datetime import datetime, timezone
import json

# Ensure repo root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.models.database import SyncSessionLocal
from backend.models.models import (
    Video, Clip, Job, Channel, VideoMetadata, VideoAnalytics, 
    OptimizationLog, VideoTrackingQueue, ContentAnalysis, 
    SEOAnalysis, OptimizationContext, PipelineMetrics, ABExperiment
)

def _parse_datetime(val: str) -> datetime | None:
    if not val:
        return None
    try:
        # SQLite typically stores isoformat without timezone or with +00:00
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

def migrate_data():
    sqlite_db_path = os.path.join(_repo_root, "clipforge.db")
    if not os.path.exists(sqlite_db_path):
        print(f"No SQLite database found at {sqlite_db_path}. Skipping migration.")
        return

    print("Connecting to SQLite database...")
    conn = sqlite3.connect(sqlite_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        with SyncSessionLocal() as session:
            print("Migrating Channels...")
            cursor.execute("SELECT * FROM channels")
            for row in cursor.fetchall():
                ch = Channel(**dict(row))
                if isinstance(ch.created_at, str): ch.created_at = _parse_datetime(ch.created_at)
                if isinstance(ch.last_checked_at, str): ch.last_checked_at = _parse_datetime(ch.last_checked_at)
                session.merge(ch)
            session.commit()

            print("Migrating Videos...")
            cursor.execute("SELECT * FROM videos")
            for row in cursor.fetchall():
                v = Video(**dict(row))
                if isinstance(v.created_at, str): v.created_at = _parse_datetime(v.created_at)
                session.merge(v)
            session.commit()

            print("Migrating Clips...")
            cursor.execute("SELECT * FROM clips")
            for row in cursor.fetchall():
                c = Clip(**dict(row))
                if isinstance(c.created_at, str): c.created_at = _parse_datetime(c.created_at)
                if isinstance(c.scheduled_at, str): c.scheduled_at = _parse_datetime(c.scheduled_at)
                if isinstance(c.published_at, str): c.published_at = _parse_datetime(c.published_at)
                session.merge(c)
            session.commit()

            print("Migrating Jobs...")
            cursor.execute("SELECT * FROM jobs")
            for row in cursor.fetchall():
                j = Job(**dict(row))
                if isinstance(j.created_at, str): j.created_at = _parse_datetime(j.created_at)
                if isinstance(j.updated_at, str): j.updated_at = _parse_datetime(j.updated_at)
                session.merge(j)
            session.commit()

            # For the other tables, we can just do similarly, wrapping in try/except in case they don't exist
            # in older sqlite schema versions
            def migrate_table(table_name, model_class, date_fields):
                try:
                    cursor.execute(f"SELECT * FROM {table_name}")
                    for row in cursor.fetchall():
                        obj = model_class(**dict(row))
                        for df in date_fields:
                            val = getattr(obj, df, None)
                            if isinstance(val, str):
                                setattr(obj, df, _parse_datetime(val))
                        session.merge(obj)
                    session.commit()
                    print(f"Migrated {table_name}.")
                except sqlite3.OperationalError:
                    print(f"Table {table_name} does not exist in SQLite DB. Skipping.")

            migrate_table("metadata", VideoMetadata, ["created_at"])
            migrate_table("video_analytics", VideoAnalytics, ["fetched_at"])
            migrate_table("optimizations", OptimizationLog, ["created_at"])
            migrate_table("video_tracking_queue", VideoTrackingQueue, ["uploaded_at", "next_check_at"])
            migrate_table("content_analysis", ContentAnalysis, ["created_at"])
            migrate_table("seo_analysis", SEOAnalysis, ["created_at"])
            migrate_table("optimization_context", OptimizationContext, ["created_at"])
            migrate_table("pipeline_metrics", PipelineMetrics, ["started_at", "completed_at"])
            migrate_table("ab_experiments", ABExperiment, ["created_at"])

            print("Migration complete!")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_data()
