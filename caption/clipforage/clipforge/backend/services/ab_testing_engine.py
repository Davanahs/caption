"""
AB Testing Engine — Autonomous title & metadata experimentation loop for YouTube Shorts.

Capabilities:
1. Create and track A/B title/thumbnail variant experiments in PostgreSQL (`ab_experiments`).
2. Calculate Viral Score Index (VSI) and Click-Through Rate (CTR) lift.
3. Automatically swap underperforming video titles (Variant A → Variant B) via YouTube Data API v3.
4. Export top-performing and bottom-performing metadata patterns for Reinforcement Learning.
"""
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import ABExperiment, Clip


def calculate_vsi(views: int, likes: int, comments: int, engagement_rate: float) -> float:
    """
    Calculate Viral Score Index (VSI):
    Logarithmic scale view factor + engagement & comment weightings.
    Range: ~0.0 to 10.0+
    """
    if views <= 0:
        return 0.0
    
    view_factor = math.log10(views + 1) * 1.8
    like_ratio = (likes / views) * 40.0
    comment_ratio = (comments / views) * 80.0
    
    vsi = view_factor + like_ratio + comment_ratio + (engagement_rate * 0.2)
    return round(min(10.0, max(0.0, vsi)), 2)


def create_ab_experiment(
    clip_id: str,
    youtube_short_id: str,
    variant_a_title: str,
    variant_b_title: str,
    variant_a_thumbnail: str | None = None,
    variant_b_thumbnail: str | None = None
) -> str:
    """Create a new A/B experiment record for a published clip."""
    exp_id = str(uuid.uuid4())
    try:
        with SyncSessionLocal() as session:
            experiment = ABExperiment(
                id=exp_id,
                clip_id=clip_id,
                youtube_short_id=youtube_short_id,
                variant_a_title=variant_a_title,
                variant_b_title=variant_b_title,
                variant_a_thumbnail=variant_a_thumbnail,
                variant_b_thumbnail=variant_b_thumbnail,
                active_variant='A',
                status='running',
                created_at=datetime.now(timezone.utc)
            )
            session.add(experiment)
            session.commit()
            print(f"[AB-Engine] Created experiment {exp_id} for clip {clip_id}: 'A' ({variant_a_title[:30]}...) vs 'B' ({variant_b_title[:30]}...)")
            return exp_id
    except Exception as e:
        print(f"[AB-Engine] Failed to create experiment: {e}")
        return ""


def evaluate_and_swap_experiments() -> List[Dict[str, Any]]:
    """
    Celery Beat periodic task runner:
    Checks running A/B experiments. If 24h passed and VSI for Variant A is < 5.0,
    swaps title to Variant B on YouTube Data API.
    """
    from backend.services.auto_optimizer import update_youtube_metadata
    from backend.services.performance_tracker import fetch_video_analytics

    swapped_summary = []
    
    try:
        with SyncSessionLocal() as session:
            # Atomic lock on all running experiments
            experiments = session.query(ABExperiment).filter_by(status='running').with_for_update(skip_locked=True).all()

            for exp in experiments:
                created_at = exp.created_at
                # If naive, assume UTC
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                hours_elapsed = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0

                # Only evaluate strictly after >= 3.0 hours of live performance
                if hours_elapsed < 3.0:
                    continue

                yt_id = exp.youtube_short_id
                try:
                    analytics = fetch_video_analytics(yt_id)
                    views = analytics.get("views", 0)
                    likes = analytics.get("likes", 0)
                    comments = analytics.get("comments", 0)
                    eng_rate = analytics.get("engagement_rate", 0.0)
                    
                    vsi = calculate_vsi(views, likes, comments, eng_rate)

                    # We are in state A.
                    if exp.active_variant == "A":
                        exp.vsi_score_a = vsi
                        exp.views_a = views

                        # Trigger swap if Variant A strictly performed poorly (< 5.0 VSI)
                        if vsi < 5.0:
                            print(f"[AB-Engine] [WARNING] Variant A underperforming (VSI={vsi} < 5.0). Swapping to Variant B...")
                            
                            from backend.models.artifact_sync import retrieve_to_local_sync
                            import os
                            
                            thumb_path = None
                            if exp.variant_b_thumbnail:
                                try:
                                    thumb_path = retrieve_to_local_sync(exp.variant_b_thumbnail)
                                except Exception as e:
                                    print(f"[AB-Engine] Could not download Variant B thumbnail: {e}")
                                    
                            title_success, thumb_success = update_youtube_metadata(
                                youtube_short_id=yt_id,
                                title=exp.variant_b_title,
                                description=f"Auto-optimized variant B test.\n\n{exp.variant_b_title}",
                                tags=["shorts", "viral", "trending"],
                                thumbnail_path=thumb_path
                            )
                            
                            if thumb_path and os.path.exists(thumb_path):
                                os.remove(thumb_path)
                                
                            if title_success and thumb_success:
                                exp.active_variant = 'B'
                                exp.status = 'swapped_to_b'
                                exp.swapped_at = datetime.now(timezone.utc).isoformat()
                                exp.winner_variant = 'B'
                                swapped_summary.append({
                                    "exp_id": exp.id,
                                    "clip_id": exp.clip_id,
                                    "old_title": exp.variant_a_title,
                                    "new_title": exp.variant_b_title,
                                    "vsi_score_a": vsi
                                })
                            elif title_success or thumb_success:
                                if title_success:
                                    exp.active_variant = 'B'
                                exp.status = 'partial_swap_failed'
                                exp.swapped_at = datetime.now(timezone.utc).isoformat()
                                exp.winner_variant = 'B'
                                swapped_summary.append({
                                    "exp_id": exp.id,
                                    "clip_id": exp.clip_id,
                                    "old_title": exp.variant_a_title,
                                    "new_title": exp.variant_b_title,
                                    "vsi_score_a": vsi
                                })
                            else:
                                print(f"[AB-Engine] Title and thumbnail update failed entirely. Not transitioning state.")
                        else:
                            print(f"[AB-Engine] Variant A performing well (VSI={vsi} >= 5.0). Retaining Variant A...")
                            exp.status = 'retained_a'
                            exp.winner_variant = 'A'
                            
                except Exception as err:
                    print(f"[AB-Engine] Error evaluating experiment {exp.id}: {err}")

            session.commit()
    except Exception as e:
        print(f"[AB-Engine] Error in evaluate_and_swap_experiments: {e}")

    return swapped_summary


def get_ab_experiments_summary() -> List[Dict[str, Any]]:
    """Return all experiments for the analytics dashboard UI."""
    try:
        with SyncSessionLocal() as session:
            experiments = session.query(ABExperiment).order_by(ABExperiment.created_at.desc()).limit(30).all()
            return [
                {
                    "id": e.id,
                    "clip_id": e.clip_id,
                    "youtube_short_id": e.youtube_short_id,
                    "variant_a_title": e.variant_a_title,
                    "variant_b_title": e.variant_b_title,
                    "active_variant": e.active_variant,
                    "status": e.status,
                    "vsi_score_a": e.vsi_score_a,
                    "vsi_score_b": e.vsi_score_b,
                    "views_a": e.views_a,
                    "views_b": e.views_b,
                    "swapped_at": e.swapped_at,
                    "winner_variant": e.winner_variant,
                    "created_at": e.created_at.isoformat() if isinstance(e.created_at, datetime) else e.created_at
                }
                for e in experiments
            ]
    except Exception as e:
        print(f"[AB-Engine] Error getting experiments summary: {e}")
        return []


def get_winning_patterns() -> Dict[str, Any]:
    """
    Extract high-VSI patterns to feed into the Reinforcement Learning Optimizer.
    """
    try:
        with SyncSessionLocal() as session:
            top_clips = session.query(Clip).filter(Clip.analytics_views > 0).order_by(Clip.analytics_view_score.desc()).limit(5).all()
            bottom_clips = session.query(Clip).filter(Clip.analytics_views > 0).order_by(Clip.analytics_view_score.asc()).limit(5).all()

            def clip_to_dict(c):
                return {
                    "title": c.title,
                    "analytics_view_score": c.analytics_view_score,
                    "analytics_views": c.analytics_views
                }

            return {
                "top_performing": [clip_to_dict(c) for c in top_clips],
                "bottom_performing": [clip_to_dict(c) for c in bottom_clips]
            }
    except Exception as e:
        print(f"[AB-Engine] Error getting winning patterns: {e}")
        return {
            "top_performing": [],
            "bottom_performing": []
        }
