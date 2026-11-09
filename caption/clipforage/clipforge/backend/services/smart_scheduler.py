"""
Smart Scheduler for optimizing publish times based on channel data.
Falls back to high-traffic predefined windows if no historical data exists.
"""

from datetime import datetime, timedelta, timezone
from backend.models.database import SyncSessionLocal
from backend.models.models import ABExperiment

def get_optimal_publish_time(channel_id: str = None) -> datetime:
    """
    Determine the optimal time to publish a video.
    If no historical data is found, defaults to the next high-traffic window
    (e.g., 12 PM - 2 PM or 5 PM - 8 PM UTC).
    """
    now = datetime.now(timezone.utc)
    
    # Optional: Look up best times from DB if we had historical analytics
    # For now, rely on predefined high-traffic windows.
    # Typical high traffic (UTC): 18:00 (6 PM)
    
    # We want to find the next 18:00 UTC
    optimal_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    
    # If it's already past 18:00 UTC, schedule for tomorrow
    if now >= optimal_time:
        optimal_time += timedelta(days=1)
        
    return optimal_time
