"""
start_tracking.py
=================
CLI helper — manually trigger the performance tracker for a published clip.

USAGE
-----
  # Auto-detect last published clip (no args needed):
      python start_tracking.py

  # Explicit clip + YouTube ID:
      python start_tracking.py <clip_id> <youtube_video_id>

FLOW (test config from .env)
-----------------------------
  1. Wait TRACKER_INITIAL_WAIT_SECONDS  (default 300 s = 5 min) after launch.
  2. POLL 1  — fetch YouTube stats, compute engagement score.
               If score < 8  →  auto-optimize title / description / hashtags.
  3. Wait TRACKER_RECHECK_WAIT_SECONDS  (default 120 s = 2 min).
  4. POLL 2  — fetch stats again, re-optimize if still < 8.
  5. Stop (TRACKER_POLLS=2 for testing).

All steps are printed to the terminal in real time.
"""

import asyncio
import sys
import logging
import os
from datetime import datetime, timezone

# ── Ensure the repo root (/app) is on sys.path so 'backend' can be imported ──
# Works whether the script is run from /app, /app/backend, or anywhere else.
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ── DB helper — fetch last published clip ─────────────────────────────────────
def _get_last_published_clip() -> tuple[str, str] | None:
    """
    Return (clip_id, youtube_short_id) for the most recently published clip,
    or None if no published clips exist.
    """
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip
    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter(
                Clip.publish_status == 'published',
                Clip.youtube_short_id.isnot(None)
            ).order_by(Clip.published_at.desc()).first()
            if clip:
                return (clip.id, clip.youtube_short_id)
    except Exception as e:
        print(f"ERROR: DB read failed: {e}")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # ── Resolve clip_id / youtube_id ─────────────────────────────────────────
    if len(sys.argv) == 3:
        clip_id          = sys.argv[1]
        youtube_video_id = sys.argv[2]
    elif len(sys.argv) == 1:
        result = _get_last_published_clip()
        if result is None:
            print("ERROR: No published clips found in the database.")
            print("       Upload and publish a video first, then re-run this script.")
            sys.exit(1)
        clip_id, youtube_video_id = result
        print(f"[Auto-detect] Last published clip found:")
        print(f"              clip_id  = {clip_id}")
        print(f"              yt_id    = {youtube_video_id}")
    else:
        print(__doc__)
        print("ERROR: Pass 0 args (auto-detect) or exactly 2 args: <clip_id> <youtube_video_id>")
        sys.exit(1)

    # ── Read tracker config (from env) ───────────────────────────────────────
    initial_wait = int(os.getenv("TRACKER_INITIAL_WAIT_SECONDS", "300"))
    recheck_wait = int(os.getenv("TRACKER_RECHECK_WAIT_SECONDS", "120"))
    max_polls    = int(os.getenv("TRACKER_MAX_POLLS", "2"))

    # ── Banner ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  ClipForge — Performance Tracker (Test Mode)".center(60))
    print("=" * 60)
    print(f"  clip_id        : {clip_id}")
    print(f"  youtube_id     : {youtube_video_id}")
    print(f"  YouTube URL    : https://youtube.com/shorts/{youtube_video_id}")
    print(f"  initial wait   : {initial_wait}s ({initial_wait//60} min) — 5 min after publish")
    print(f"  recheck wait   : {recheck_wait}s ({recheck_wait//60} min) — between polls")
    print(f"  max polls      : {max_polls}")
    print(f"  score threshold: 8.0  (lower -> optimize)")
    print("=" * 60)
    print()

    # ── Run ──────────────────────────────────────────────────────────────────
    from backend.new_files.performance_tracker import start_tracking
    from backend.services.realtime_tracker import run_realtime_tracker
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoTrackingQueue

    async def run():
        # Queue it
        task_id = start_tracking(clip_id, youtube_video_id)
        # Update next_check_at to now so it runs immediately
        try:
            with SyncSessionLocal() as session:
                task = session.query(VideoTrackingQueue).filter_by(id=task_id).first()
                if task:
                    task.next_check_at = datetime.now(timezone.utc)
                    session.commit()
        except Exception as e:
            print(f"ERROR updating next_check_at: {e}")

        # Run tracker to evaluate immediately
        print("[CLI] Running check now...")
        await run_realtime_tracker()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[CLI] Tracker interrupted by user. Exiting.", flush=True)


if __name__ == "__main__":
    main()
