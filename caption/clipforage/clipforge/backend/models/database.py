from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from backend.core.config import settings
from sqlalchemy import select

# ── Centralized Async Engine & Session (for FastAPI / background loops) ──────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Force False to prevent charmap crashes on Windows with emojis
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# ── Centralized Sync Engine & Session (for Celery workers) ───────────────────
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=False,  # Force False to prevent charmap crashes on Windows with emojis
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=sync_engine
)

class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Called on startup by FastAPI.
    Since we now use Alembic for migrations, we do not auto-create tables
    or execute dynamic ALTER TABLE statements here.
    """
    pass


async def cleanup_orphaned_jobs():
    """
    On startup: report any jobs that were mid-flight when the server last crashed.
    We do NOT auto-fail them — the worker will re-pick them up or the user can cancel manually.
    """
    from backend.models.models import Job, JobStatus
    
    async with AsyncSessionLocal() as session:
        try:
            terminal = [JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_FAILURES.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]
            result = await session.execute(
                select(Job).where(Job.status.not_in(terminal))
            )
            orphans = result.scalars().all()
            if orphans:
                print(f"[ClipForge] Startup: {len(orphans)} job(s) were mid-flight when server last stopped.")
                for j in orphans:
                    print(f"  → {j.id[:8]}... status={j.status} title={j.source_title or j.source_url or 'unknown'}")
            else:
                print("[ClipForge] Startup: no orphaned jobs found.")
        except Exception as e:
            print(f"[ClipForge] Failed to check orphaned jobs on startup: {e}")


