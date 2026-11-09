"""
ClipForge — FastAPI Main Application
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.models.database import init_db, cleanup_orphaned_jobs, AsyncSessionLocal
from backend.core.config import settings
from backend.api.routes import videos, clips, jobs, channels, publish, analytics, dubbing, studio, youtube_channels, captions, settings as settings_route
from backend.core.diagnostics import run_diagnostics


# ── Scheduler ──────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()


async def scheduled_channel_check():
    """Run every N minutes to check monitored channels."""
    try:
        from backend.services.channel_monitor import run_channel_monitor
        async with AsyncSessionLocal() as db:
            await run_channel_monitor(db)
    except Exception as e:
        print(f"[ScheduledChannelCheck] Error: {e}")


async def scheduled_publish_check():
    """Run every minute to check for scheduled clips and publish them."""
    try:
        from backend.tasks.scheduler import run_auto_publisher
        await run_auto_publisher()
    except Exception as e:
        print(f"[ScheduledPublishCheck] Error: {e}")


async def scheduled_tracker_check():
    """Run every minute to run the real-time delayed optimization check."""
    try:
        from backend.services.realtime_tracker import run_realtime_tracker
        await asyncio.to_thread(run_realtime_tracker)
    except Exception as e:
        print(f"[ScheduledTrackerCheck] Error: {e}")


async def scheduled_queue_drain_check():
    """Run every 30 seconds to drain pending manual video jobs."""
    try:
        from backend.services.queue_manager import dispatch_next_queued_manual_jobs_async
        async with AsyncSessionLocal() as db:
            await dispatch_next_queued_manual_jobs_async(db)
    except Exception as e:
        print(f"[ScheduledQueueDrainCheck] Error: {e}")



# ── App Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup diagnostics (Issue 10)
    print("[ClipForge] Running pre-flight diagnostics check...")
    diag_results = run_diagnostics()
    if diag_results["issues"]:
        print("[ClipForge] WARNING: Diagnostic issues found during startup:")
        for issue in diag_results["issues"]:
            print(f"  - {issue}")
    else:
        print("[ClipForge] Startup diagnostics passed successfully.")

    # Dynamic Settings Initialization (Phase 5.1 / C-09)
    try:
        settings_route.init_dynamic_settings()
        print("[ClipForge] Dynamic system settings initialized.")
    except Exception as e:
        print(f"[ClipForge] Dynamic settings initialization warning: {e}")

    await init_db()
    print("[ClipForge] Database initialized.")
    
    await cleanup_orphaned_jobs()

    # Reconcile interrupted storage cleanup batches on startup
    try:
        from backend.api.routes.clips import reconcile_quarantine
        await reconcile_quarantine()
    except Exception as e:
        print(f"[ClipForge] Quarantine reconciliation warning: {e}")

    scheduler.add_job(
        scheduled_channel_check,
        "interval",
        minutes=settings.CHANNEL_CHECK_INTERVAL_MINUTES,
        id="channel_monitor",
        replace_existing=True,
    )

    scheduler.add_job(
        scheduled_publish_check,
        "interval",
        minutes=1,
        id="auto_publisher",
        replace_existing=True,
    )

    scheduler.add_job(
        scheduled_tracker_check,
        "interval",
        minutes=1,
        id="realtime_tracker",
        replace_existing=True,
    )

    scheduler.add_job(
        scheduled_queue_drain_check,
        "interval",
        seconds=30,
        id="manual_queue_drain",
        replace_existing=True,
    )
    
    scheduler.start()
    print(f"[ClipForge] Channel monitor scheduled every {settings.CHANNEL_CHECK_INTERVAL_MINUTES} min")
    print("[ClipForge] Auto-publisher scheduled every 1 min")
    print("[ClipForge] Real-time delayed tracker scheduled every 1 min")
    print("[ClipForge] Manual video queue drain scheduled every 30 sec")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    print("[ClipForge] Scheduler stopped")


# ── App Instance ────────────────────────────────────────────────────────────
app = FastAPI(
    title="ClipForge API",
    description="AI-Powered YouTube Automation Platform",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ────────────────────────────────────────────────────────────────────
# Ensure CORS_ORIGINS is a list
cors_origins = settings.CORS_ORIGINS
if isinstance(cors_origins, str):
    cors_origins = [origins.strip() for origins in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(videos.router)
app.include_router(clips.router)
app.include_router(jobs.router)
app.include_router(channels.router)
app.include_router(publish.router)
app.include_router(analytics.router)   # Phase 4 — performance tracking
app.include_router(dubbing.router)     # Phase 15 — multi-language dubbing
app.include_router(studio.router)      # Upload Studio Phase 1
app.include_router(captions.router)    # Caption Studio AI Styling Engine
app.include_router(youtube_channels.router)  # My YouTube Channels Management
app.include_router(settings_route.router)    # Phase 5.1 — Settings Persistence (REQ-GAP-001)

# ── Quarantine Protection Route (Registered BEFORE static mount) ────────────
@app.api_route(
    "/outputs/.storage_quarantine/{rest:path}",
    methods=["GET", "HEAD", "POST"],
    include_in_schema=False
)
async def block_quarantine_access(rest: str):
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Not Found")


# ── Static Files (output videos/thumbnails) ─────────────────────────────────
app.mount("/outputs", StaticFiles(directory=str(settings.OUTPUT_DIR)), name="outputs")
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")


# ── Health Check ────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    import asyncio
    import redis.asyncio as aioredis
    from sqlalchemy import text
    from backend.models.database import AsyncSessionLocal

    components = {"api": "ok", "db": "unknown", "redis": "unknown", "worker": "unknown"}
    status = "ok"

    # 1. DB Check
    try:
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(session.execute(text('SELECT 1')), timeout=1.0)
        components["db"] = "ok"
    except asyncio.TimeoutError:
        components["db"] = "timeout"
        status = "degraded"
    except Exception as e:
        components["db"] = f"error: {str(e)}"
        status = "degraded"

    # 2. Redis Check
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        await r.ping()
        await r.aclose()
        components["redis"] = "ok"
    except asyncio.TimeoutError:
        components["redis"] = "timeout"
        status = "degraded"
    except Exception as e:
        components["redis"] = f"error: {str(e)}"
        status = "degraded"

    # 3. Worker Check — fast Redis heartbeat scan (avoids blocking TCP connect)
    try:
        r2 = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        # Celery workers write heartbeat keys like: _kombu.binding.celery, celery-task-meta-*, etc.
        # The most reliable fast probe: scan for any celery:* or _kombu.* key
        heartbeat_keys = await asyncio.wait_for(
            r2.keys("celery*"),
            timeout=1.5
        )
        await r2.aclose()
        if heartbeat_keys:
            components["worker"] = "online"
        else:
            # Fallback: check if worker registered via celery inspect (non-blocking keys)
            task_keys = await asyncio.wait_for(
                aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0).keys("_kombu*"),
                timeout=1.5
            )
            components["worker"] = "online" if task_keys else "offline"
            if not task_keys:
                status = "degraded"
    except asyncio.TimeoutError:
        components["worker"] = "timeout"
        status = "degraded"
    except Exception as e:
        components["worker"] = f"error: {str(e)}"
        status = "degraded"

    return {
        "status": status,
        "components": components,
        "version": settings.VERSION,
        "app": settings.APP_NAME,
    }


@app.get("/api/stats")
async def stats():
    """Dashboard stats."""
    from backend.models.models import Video, Clip, Channel
    from sqlalchemy import select, func
    
    async with AsyncSessionLocal() as session:
        videos_count = (await session.execute(select(func.count(Video.id)))).scalar()
        clips_count = (await session.execute(select(func.count(Clip.id)))).scalar()
        published_count = (await session.execute(
            select(func.count(Clip.id)).where(Clip.publish_status == 'published')
        )).scalar()
        channels_count = (await session.execute(
            select(func.count(Channel.id)).where(Channel.is_active == True)
        )).scalar()
        
    return {
        "total_videos": videos_count,
        "total_clips": clips_count,
        "published_clips": published_count,
        "active_channels": channels_count,
    }
