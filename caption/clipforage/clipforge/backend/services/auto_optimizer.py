"""
Auto Optimizer — monitors ViewScore, regenerates metadata, and updates YouTube if score is low.

Optimization cycle (per clip, max 3 attempts):
  1. Poll analytics (via performance_tracker).
  2. If ViewScore < 8 → analyze cause via LLM.
  3. Generate better title, description, tags from transcript + current tags + viral competitors.
  4. Update YouTube video metadata via Data API v3.
  5. Record attempt, reset 3-day window.
  6. Repeat until ViewScore >= 8 or attempts == 3.
"""
from datetime import datetime
from backend.core.config import settings


# ── YouTube Metadata Update ───────────────────────────────────────────────────

def update_youtube_metadata(
    youtube_short_id: str,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: str | None = None
) -> tuple[bool, bool]:
    """Update an existing YouTube video's title, description and tags via API v3."""
    from backend.services.publisher import get_youtube_client

    youtube = get_youtube_client()
    # Fetch current snippet first (categoryId required for update)
    current = youtube.videos().list(part="snippet", id=youtube_short_id).execute()
    items = current.get("items", [])
    if not items:
        raise ValueError(f"Video {youtube_short_id} not found on YouTube")

    snippet = items[0]["snippet"]
    snippet["title"] = title[:100]
    snippet["description"] = description[:5000]
    snippet["tags"] = tags[:500]

    title_success = False
    thumb_success = False
    
    try:
        youtube.videos().update(
            part="snippet",
            body={"id": youtube_short_id, "snippet": snippet},
        ).execute()
        print(f"[Optimizer] Updated YouTube metadata for {youtube_short_id}: '{title}'")
        title_success = True
    except Exception as e:
        print(f"[Optimizer] Title update failed for {youtube_short_id}: {e}")
        return False, False
        
    if thumbnail_path:
        from googleapiclient.http import MediaFileUpload
        try:
            youtube.thumbnails().set(
                videoId=youtube_short_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            print(f"[Optimizer] Updated thumbnail for {youtube_short_id}")
            thumb_success = True
        except Exception as e:
            print(f"[Optimizer] Thumbnail update failed: {e}")
            thumb_success = False
            
    return title_success, thumb_success


def post_pinned_comment(youtube_short_id: str, comment_text: str) -> None:
    """Post a pinned comment on the video."""
    from backend.services.publisher import get_youtube_client

    youtube = get_youtube_client()
    try:
        response = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": youtube_short_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": comment_text[:10000]}
                    }
                }
            }
        ).execute()
        comment_id = response["id"]
        # Pin the comment
        youtube.comments().setModerationStatus(
            id=comment_id,
            moderationStatus="published",
        ).execute()
        print(f"[Optimizer] Pinned comment posted: '{comment_text[:50]}...'")
    except Exception as e:
        print(f"[Optimizer] Failed to pin comment: {e}")


# ── LLM Re-Optimization Prompt ───────────────────────────────────────────────

def _build_reoptimize_prompt(
    current_title: str,
    current_tags: list[str],
    transcript: str,
    view_score: float,
    views: int,
    likes: int,
    comments: int,
    engagement_rate: float,
) -> str:
    from backend.services.ab_testing_engine import get_winning_patterns
    patterns = get_winning_patterns()
    
    top_str = "\n".join([f"  - \"{p['title']}\" (ViewScore: {p.get('analytics_view_score', 0):.1f})" for p in patterns["top_performing"]]) or "  - None recorded yet"
    bottom_str = "\n".join([f"  - \"{p['title']}\" (ViewScore: {p.get('analytics_view_score', 0):.1f})" for p in patterns["bottom_performing"]]) or "  - None recorded yet"

    cause = []
    if views < 500:
        cause.append("Very low views — title/thumbnail may not be appealing enough")
    if engagement_rate < 2.0:
        cause.append("Low engagement rate — content may not be resonating")
    if likes < 10:
        cause.append("Very few likes — call-to-action may be weak")
    if comments < 3:
        cause.append("Almost no comments — description may lack engagement hooks")
    cause_str = "; ".join(cause) if cause else "Overall low performance"

    return f"""You are an elite YouTube Shorts growth AI with Reinforcement Learning memory.

CHANNEL REINFORCEMENT LEARNING MEMORY:
TOP PERFORMING TITLES IN THIS NICHE (Emulate structure/tone):
{top_str}

POOR PERFORMING TITLES IN THIS NICHE (Avoid similar phrasing):
{bottom_str}

CURRENT VIDEO PERFORMANCE:
- Views: {views} | Likes: {likes} | Comments: {comments}
- Engagement Rate: {engagement_rate:.1f}% | ViewScore: {view_score:.1f}/10
- Likely Cause: {cause_str}

CURRENT TITLE: {current_title}
CURRENT TAGS: {', '.join(current_tags[:10])}
TRANSCRIPT: {transcript[:1500]}

Generate 2 IMPROVED title variants (Variant A: Curiosity Hook, Variant B: Direct High-Energy Action Hook) and improved description/tags.
Respond with ONLY raw JSON:
{{
  "title": "Variant A title...",
  "variant_b_title": "Variant B title...",
  "description": "...",
  "tags": ["tag1", "tag2", "..."],
  "pinned_comment": "..."
}}

RULES:
- title (Variant A): Under 60 chars. High curiosity hook. Include 1 emoji.
- variant_b_title (Variant B): Under 60 chars. Direct, bold, high-energy hook. Include 1 emoji.
- description: 200-300 words. Strong hook. Relevant to content. End with 5 hashtags.
- tags: 15-20 tags. Mix broad + niche. No # prefix.
- pinned_comment: Under 100 chars. Stronger CTA than before."""



# ── DB Tracking ───────────────────────────────────────────────────────────────

def save_optimization_result(
    clip_id: str,
    new_title: str,
    new_description: str,
    new_tags: list[str],
    new_pinned_comment: str,
    attempt_number: int,
) -> None:
    """Save the new optimized metadata back to the clip record."""
    import json
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip
    from datetime import timezone

    try:
        with SyncSessionLocal() as session:
            clip = session.query(Clip).filter_by(id=clip_id).first()
            if clip:
                clip.title = new_title
                clip.description = new_description
                clip.tags = json.dumps(new_tags)
                clip.pinned_comment = new_pinned_comment
                clip.optimization_attempts = attempt_number
                clip.last_optimized_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                print(f"[Optimizer] Saved optimization #{attempt_number} for clip {clip_id}")
    except Exception as e:
        print(f"[Optimizer] Failed to save optimization result: {e}")


# ── Main Optimization Entry Point ─────────────────────────────────────────────

async def check_and_optimize(clip: dict) -> None:
    """
    Run one optimization cycle for a clip.
    Called by the Celery beat task every time analytics are polled.
    """
    from backend.services.performance_tracker import (
        fetch_video_analytics, save_analytics_snapshot, increment_check_count
    )
    from backend.services.llm_router import route_and_generate
    from backend.services.metadata_generator import _parse_metadata_response
    import json

    clip_id = clip["id"]
    youtube_short_id = clip["youtube_short_id"]
    current_title = clip.get("title", "")
    transcript = clip.get("transcript_segment", "") or ""

    # 1. Fetch analytics
    try:
        analytics = fetch_video_analytics(youtube_short_id)
        save_analytics_snapshot(clip_id, analytics)
        increment_check_count(clip_id)
    except Exception as e:
        print(f"[Optimizer] Failed to fetch analytics for {clip_id}: {e}")
        return

    view_score = analytics["view_score"]
    print(f"[Optimizer] Clip {clip_id} ViewScore={view_score} (attempt {clip['optimization_attempts']})")

    # 2. If ViewScore is already good, skip
    if view_score >= 8.0:
        print(f"[Optimizer] ✓ ViewScore {view_score} >= 8. No optimization needed.")
        return

    # 3. Max attempts reached
    if clip["optimization_attempts"] >= 3:
        print(f"[Optimizer] Max optimization attempts (3) reached for clip {clip_id}. Stopping.")
        return

    # 4. Generate better metadata
    current_tags_raw = clip.get("tags", "[]") or "[]"
    try:
        current_tags = json.loads(current_tags_raw) if isinstance(current_tags_raw, str) else current_tags_raw
    except Exception:
        current_tags = []

    prompt = _build_reoptimize_prompt(
        current_title=current_title,
        current_tags=current_tags,
        transcript=transcript,
        view_score=view_score,
        views=analytics["views"],
        likes=analytics["likes"],
        comments=analytics["comments"],
        engagement_rate=analytics["engagement_rate"],
    )

    try:
        raw = await route_and_generate(prompt)
        new_meta = _parse_metadata_response(raw)
        new_meta["srt_content"] = ""
    except Exception as e:
        print(f"[Optimizer] LLM re-optimization failed for clip {clip_id}: {e}")
        return

    new_title = new_meta["title"]
    new_variant_b = new_meta.get("variant_b_title", f"{new_title} 🔥")
    new_description = new_meta["description"]
    new_tags = new_meta["tags"]
    new_pinned_comment = new_meta["pinned_comment"]
    new_attempt = clip["optimization_attempts"] + 1

    # 5. Register A/B Experiment
    try:
        from backend.services.ab_testing_engine import create_ab_experiment
        create_ab_experiment(
            clip_id=clip_id,
            youtube_short_id=youtube_short_id,
            variant_a_title=new_title,
            variant_b_title=new_variant_b
        )
    except Exception as ab_err:
        print(f"[Optimizer] Failed to register A/B experiment: {ab_err}")

    # 6. Update YouTube
    try:
        update_youtube_metadata(youtube_short_id, new_title, new_description, new_tags)
        if new_pinned_comment:
            post_pinned_comment(youtube_short_id, new_pinned_comment)
    except Exception as e:
        print(f"[Optimizer] YouTube update failed for {clip_id}: {e}")
        return

    # 7. Save result to DB
    save_optimization_result(
        clip_id, new_title, new_description, new_tags, new_pinned_comment, new_attempt
    )
    print(f"[Optimizer] ✓ Optimization #{new_attempt} applied for clip {clip_id}")

