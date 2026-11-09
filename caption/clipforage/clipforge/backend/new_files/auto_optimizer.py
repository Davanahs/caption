"""
auto_optimizer.py
=================
Phase 6 — Smart Context-Aware Metadata Optimization.

Called by realtime_tracker whenever the engagement score < 8.
Each call is a *single* optimization attempt.

Key improvements:
  - Uses cached content_analysis (niche, keywords, hashtag candidates) — no re-analysis.
  - Uses cached seo_analysis (weak hashtags, missing keywords, recommendations).
  - Uses optimization_context (previous titles, hashtags, scores) to avoid repetition.
  - LLM prompt includes all previous attempts to force unique improved output.
  - Updates YouTube metadata and persists locally.
  - Returns the new metadata dict so the caller can store it in optimization_context.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from backend.core.config import settings

logger = logging.getLogger("clipforge.optimizer")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False


# ── Banner helpers ────────────────────────────────────────────────────────────
def _banner(title: str):
    width = 60
    logger.info("=" * width)
    logger.info("  %s", title.center(width - 4))
    logger.info("=" * width)


def _section(label: str):
    logger.info("── %s %s", label, "─" * max(0, 56 - len(label)))


# ── DB helpers ────────────────────────────────────────────────────────────────
def _get_transcript_sync(clip_id: str) -> str:
    """
    Fetch transcript for a clip:
      1. clips.transcript_segment  (clip-specific segment)
      2. videos.transcript          (full parent-video transcript — fallback)
    """
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Clip, Video
    
    with SyncSessionLocal() as session:
        clip = session.query(Clip).filter_by(id=clip_id).first()
        if clip:
            segment = clip.transcript_segment
            if segment and len(segment.strip()) > 20 and not segment.startswith("[Visual"):
                return segment.strip()
            
            if clip.video_id:
                video = session.query(Video).filter_by(id=clip.video_id).first()
                if video and video.transcript:
                    return video.transcript.strip()
    return ""


def _get_content_analysis(clip_id: str) -> dict:
    """Fetch cached content_analysis from DB. Returns empty dict if not found."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import ContentAnalysis
    try:
        with SyncSessionLocal() as session:
            ca = session.query(ContentAnalysis).filter_by(clip_id=clip_id).first()
            if ca and ca.analysis_json:
                return json.loads(ca.analysis_json)
    except Exception as e:
        logger.error(f"[Optimizer] get_content_analysis error: {e}")
    return {}


def _get_seo_analysis(clip_id: str) -> dict:
    """Fetch cached seo_analysis from DB. Returns empty dict if not found."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import SEOAnalysis
    try:
        with SyncSessionLocal() as session:
            seo = session.query(SEOAnalysis).filter_by(clip_id=clip_id).first()
            if seo and seo.seo_json:
                return json.loads(seo.seo_json)
    except Exception as e:
        logger.error(f"[Optimizer] get_seo_analysis error: {e}")
    return {}


def _get_current_metadata(clip_id: str) -> dict:
    """Fetch the current published metadata for this clip from DB."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoMetadata
    try:
        with SyncSessionLocal() as session:
            meta = session.query(VideoMetadata).filter_by(video_id=clip_id).first()
            if meta:
                return {
                    "title": meta.title or "",
                    "description": meta.description or "",
                    "hashtags": [h.strip() for h in (meta.hashtags or "").split(",") if h.strip()],
                    "pinned_comment": meta.pinned_comment or "",
                }
    except Exception as e:
        logger.error(f"[Optimizer] get_current_metadata error: {e}")
    return {}


def _upsert_metadata_sync(video_id: str, meta_dict: dict):
    """Insert/replace metadata row in the metadata table."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import VideoMetadata
    from datetime import datetime, timezone
    import uuid

    tags_str = ",".join(meta_dict.get("tags", []))
    hashtags_str = ",".join(meta_dict.get("hashtags", []))
    
    with SyncSessionLocal() as session:
        meta = session.query(VideoMetadata).filter_by(video_id=video_id).first()
        if not meta:
            meta = VideoMetadata(id=str(uuid.uuid4()), video_id=video_id)
            session.add(meta)
            
        meta.title = meta_dict.get("title", "")
        meta.description = meta_dict.get("description", "")
        meta.tags = tags_str
        meta.hashtags = hashtags_str
        meta.pinned_comment = meta_dict.get("pinned_comment", "")
        meta.created_at = datetime.now(timezone.utc)
        
        session.commit()


def _save_seo_analysis(clip_id: str, meta: dict, current_score: float, poll_num: int) -> None:
    """
    Save SEO analysis snapshot to seo_analysis table after each optimization.
    """
    from backend.models.database import SyncSessionLocal
    from backend.models.models import SEOAnalysis
    from datetime import datetime, timezone

    tags = meta.get("tags", [])
    hashtags = meta.get("hashtags", [])
    title = meta.get("title", "")

    title_score = min(len(title) / 60.0, 1.0) * 40
    tag_score = min(len(tags) / 15.0, 1.0) * 30
    hashtag_score = min(len(hashtags) / 5.0, 1.0) * 30
    seo_score = round(title_score + tag_score + hashtag_score, 1)

    has_emoji = any(ord(c) > 127 for c in title)
    starts_strong = title and title[0].isupper()
    ctr_score = round((50 if has_emoji else 0) + (50 if starts_strong else 0), 1)
    disc_score = round((seo_score + ctr_score) / 2.0, 1)

    rec_hashtags = json.dumps(hashtags[:5])
    missing_kw = json.dumps([])
    weak_tags = json.dumps([])

    seo_json = json.dumps({
        "title": title,
        "tags": tags,
        "hashtags": hashtags,
        "seo_score": seo_score,
        "ctr_score": ctr_score,
        "discoverability_score": disc_score,
        "view_score_at_optimization": current_score,
        "missing_keywords": [],
        "weak_hashtags": [],
        "recommended_hashtags": hashtags[:5],
        "poll_num": poll_num,
    })

    with SyncSessionLocal() as session:
        seo = session.query(SEOAnalysis).filter_by(clip_id=clip_id).first()
        if not seo:
            seo = SEOAnalysis(clip_id=clip_id)
            session.add(seo)
            
        seo.seo_score = seo_score
        seo.ctr_score = ctr_score
        seo.discoverability_score = disc_score
        seo.missing_keywords = missing_kw
        seo.recommended_hashtags = rec_hashtags
        seo.weak_hashtags = weak_tags
        seo.seo_json = seo_json
        seo.created_at = datetime.now(timezone.utc)
        session.commit()

    logger.info("[Optimizer] SEO snapshot saved for clip_id=%s (seo_score=%.1f, ctr=%.1f)",
                clip_id, seo_score, ctr_score)


def _log_optimization_sync(video_id: str, attempt: int, meta: dict, score: float | None):
    """Append an optimization attempt record to the 'optimizations' table."""
    from backend.models.database import SyncSessionLocal
    from backend.models.models import OptimizationLog
    from datetime import datetime, timezone
    
    with SyncSessionLocal() as session:
        log = OptimizationLog(
            video_id=video_id,
            attempt_number=attempt,
            new_title=meta.get("title", ""),
            new_description=meta.get("description", ""),
            new_tags=",".join(meta.get("tags", [])),
            new_hashtags=",".join(meta.get("hashtags", [])),
            view_score=score,
            created_at=datetime.now(timezone.utc)
        )
        session.add(log)
        session.commit()


# ── YouTube helpers ───────────────────────────────────────────────────────────
def _push_metadata_to_youtube(youtube_video_id: str, meta: dict):
    """Update YouTube video metadata (title, description, tags)."""
    from backend.services.publisher import update_video_metadata
    update_video_metadata(
        youtube_video_id=youtube_video_id,
        title=meta.get("title", ""),
        description=meta.get("description", ""),
        tags=meta.get("tags", []),
    )


def _post_pinned_comment(youtube_video_id: str, comment_text: str):
    """Post a comment on the YouTube video (best-effort)."""
    from backend.services.publisher import get_youtube_client
    yt = get_youtube_client()
    yt.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": youtube_video_id,
                "topLevelComment": {
                    "snippet": {"textOriginal": comment_text}
                },
            }
        },
    ).execute()


# ── Smart LLM Prompt Builder ──────────────────────────────────────────────────
def _build_optimization_prompt(
    transcript: str,
    content_analysis: dict,
    seo_analysis: dict,
    current_meta: dict,
    opt_ctx: dict,
    poll_num: int,
    score: float,
) -> str:
    """Build a rich context-aware prompt for the LLM optimizer."""
    niche = content_analysis.get("niche", "General")
    topic = content_analysis.get("topic", "General")
    audience = content_analysis.get("audience_type", "General")
    keywords = content_analysis.get("searchable_keywords", [])
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)
    long_tail = content_analysis.get("long_tail_keywords", [])
    if isinstance(long_tail, list):
        long_tail = ", ".join(long_tail)
    hashtag_candidates = content_analysis.get("hashtag_candidates", [])
    if isinstance(hashtag_candidates, list):
        hashtag_candidates = ", ".join(hashtag_candidates)
    emotions = content_analysis.get("emotions", [])
    if isinstance(emotions, list):
        emotions = ", ".join(emotions)

    missing_kw = seo_analysis.get("missing_keywords", [])
    if isinstance(missing_kw, list):
        missing_kw = ", ".join(missing_kw)
    weak_tags = seo_analysis.get("weak_hashtags", [])
    if isinstance(weak_tags, list):
        weak_tags = ", ".join(weak_tags)
    recommended_tags = seo_analysis.get("recommended_hashtags", [])
    if isinstance(recommended_tags, list):
        recommended_tags = ", ".join(recommended_tags)
    seo_score = seo_analysis.get("seo_score", 0)
    ctr_score = seo_analysis.get("ctr_score", 0)

    current_title = current_meta.get("title", "")
    current_desc = current_meta.get("description", "")
    current_hashtags = current_meta.get("hashtags", [])
    if isinstance(current_hashtags, list):
        current_hashtags = ", ".join(current_hashtags)

    prev_titles = opt_ctx.get("previous_titles", [])
    prev_hashtags = opt_ctx.get("previous_hashtags", [])
    prev_scores = opt_ctx.get("previous_scores", [])

    prev_attempts_block = ""
    if prev_titles:
        prev_attempts_block = "PREVIOUS FAILED ATTEMPTS (DO NOT REPEAT THESE):\n"
        for i, (pt, ph, ps) in enumerate(zip(prev_titles, prev_hashtags, prev_scores), 1):
            prev_attempts_block += f"  Attempt {i}: Title='{pt}' | Hashtags={ph} | Score={ps}\n"

    return f"""You are an expert YouTube Shorts SEO optimizer.
A published video has a low engagement score of {score:.2f}/10 (needs >= 8.0).
This is optimization attempt #{poll_num}.

Your task: Generate IMPROVED metadata that is unique from previous attempts, targets the exact audience, and maximizes discoverability.

CURRENT PERFORMANCE ISSUES:
- Current SEO Score: {seo_score:.1f}/100
- Current CTR Score: {ctr_score:.1f}/100
- Missing Keywords: {missing_kw}
- Weak Hashtags to replace: {weak_tags}
- Recommended Hashtags: {recommended_tags}

CONTENT CONTEXT (DO NOT RE-ANALYZE — use this directly):
- Niche: {niche}
- Topic: {topic}
- Target Audience: {audience}
- Emotions: {emotions}
- Searchable Keywords: {keywords}
- Long-tail Keywords: {long_tail}
- Hashtag Candidates: {hashtag_candidates}

CURRENT METADATA (to be improved):
- Title: {current_title}
- Description (first 200 chars): {current_desc[:200]}
- Hashtags: {current_hashtags}

{prev_attempts_block}

OPTIMIZATION RULES:
1. Do NOT repeat any previous title or hashtag set.
2. Prioritize the missing keywords and recommended hashtags.
3. Replace all weak hashtags.
4. Title must be under 60 chars, start with a strong curiosity/emotion hook.
5. Hashtags must be content-specific (topic, character, person, series names if applicable).
6. Never use #viral, #fyp, #trending, #explore as primary hashtags.
7. Description must naturally include missing keywords.
8. Pinned comment must be unique from previous attempts and < 80 chars.

Return ONLY valid JSON (no markdown fences):
{{
  "title": "<improved hook title>",
  "description": "<SEO-optimized description with keywords>",
  "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "hashtags": ["<content-specific hashtag1>", "<hashtag2>", "<hashtag3>", "<hashtag4>", "<hashtag5>"],
  "pinned_comment": "<unique reply-sparking comment under 80 chars>"
}}

TRANSCRIPT (for reference):
{transcript[:800]}
"""


# ── Public Entry Point ────────────────────────────────────────────────────────
async def run_single_optimization(
    video_id: str,
    youtube_video_id: str,
    current_score: float,
    poll_num: int,
    opt_ctx: dict = None,
) -> dict:
    """
    Run one smart optimization cycle:
      1. Load cached content_analysis + seo_analysis (NO re-analysis).
      2. Load current metadata + optimization_context history.
      3. Build context-aware LLM prompt with previous attempt data.
      4. Generate new UNIQUE improved metadata.
      5. Push to YouTube.
      6. Persist locally and log attempt.
      7. Return the new metadata dict for the caller to store in optimization_context.

    Args:
        video_id:          Internal ClipForge id (Clip or Video).
        youtube_video_id:  Real YouTube video ID.
        current_score:     Latest engagement score.
        poll_num:          Which optimization attempt this is (1 or 2).
        opt_ctx:           Existing optimization context (passed by tracker to avoid DB round-trip).

    Returns:
        dict: new metadata { title, description, tags, hashtags, pinned_comment }
    """
    _banner(f"SMART OPTIMIZER  |  poll={poll_num}  score={current_score:.2f}")
    logger.info("[Optimizer] clip_id      : %s", video_id)
    logger.info("[Optimizer] youtube_id   : %s", youtube_video_id)
    logger.info("[Optimizer] current score: %.2f (threshold=8.0)", current_score)

    # ── Step 1: Load transcript (mandatory) ───────────────────────────────
    _section("STEP 1 — Loading transcript (cached)")
    transcript = await asyncio.get_event_loop().run_in_executor(
        None, _get_transcript_sync, video_id
    )
    if not transcript:
        logger.warning("[Optimizer] No transcript found — skipping optimization.")
        return {}

    # ── Step 2: Load cached analysis (NO LLM calls here) ─────────────────
    _section("STEP 2 — Loading cached analysis context (no re-analysis)")
    content_analysis = await asyncio.get_event_loop().run_in_executor(
        None, _get_content_analysis, video_id
    )
    seo_analysis = await asyncio.get_event_loop().run_in_executor(
        None, _get_seo_analysis, video_id
    )
    current_meta = await asyncio.get_event_loop().run_in_executor(
        None, _get_current_metadata, video_id
    )

    if content_analysis:
        logger.info("[Optimizer] ✅  content_analysis found (niche=%s, topic=%s)",
                    content_analysis.get("niche"), content_analysis.get("topic"))
    else:
        logger.warning("[Optimizer] ⚠  No content_analysis cached — optimization context will be limited.")

    if seo_analysis:
        logger.info("[Optimizer] ✅  seo_analysis found (seo_score=%.1f)", seo_analysis.get("seo_score", 0))
    else:
        logger.warning("[Optimizer] ⚠  No seo_analysis cached.")

    # Use passed opt_ctx or empty defaults
    if opt_ctx is None:
        opt_ctx = {
            "previous_titles": [],
            "previous_descriptions": [],
            "previous_hashtags": [],
            "optimization_attempt": 0,
            "previous_scores": [],
        }

    # ── Step 3: Build smart LLM prompt ───────────────────────────────────
    _section("STEP 3 — Building smart optimization prompt")
    prompt = _build_optimization_prompt(
        transcript=transcript,
        content_analysis=content_analysis,
        seo_analysis=seo_analysis,
        current_meta=current_meta,
        opt_ctx=opt_ctx,
        poll_num=poll_num,
        score=current_score,
    )
    logger.info("[Optimizer] Prompt built (%d chars). Calling LLM...", len(prompt))

    # ── Step 4: Generate new metadata via LLM ────────────────────────────
    _section("STEP 4 — Generating improved metadata via LLM")
    try:
        from backend.services.llm_router import route_and_generate
        raw = await route_and_generate(prompt)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw).strip()
        meta = json.loads(raw)
    except Exception as exc:
        logger.error("[Optimizer] ❌  LLM failed: %s", exc)
        _log_optimization_sync(video_id, poll_num, {}, current_score)
        return {}

    logger.info("[Optimizer] ✅  New metadata generated:")
    logger.info("  Title    : %s", meta.get("title", "—"))
    logger.info("  Hashtags : %s", " ".join(meta.get("hashtags", [])))
    logger.info("  Comment  : %s", meta.get("pinned_comment", "—"))

    # ── Step 5: Push to YouTube ───────────────────────────────────────────
    _section("STEP 5 — Updating YouTube metadata")
    try:
        await asyncio.get_event_loop().run_in_executor(
            None, _push_metadata_to_youtube, youtube_video_id, meta
        )
        logger.info("[Optimizer] ✅  YouTube title / description / tags updated.")
    except Exception as exc:
        logger.error("[Optimizer] ❌  YouTube metadata update failed: %s", exc)
        _log_optimization_sync(video_id, poll_num, meta, current_score)
        return meta

    # ── Step 6: Persist metadata locally ─────────────────────────────────
    _section("STEP 6 — Saving metadata to local DB")
    try:
        await asyncio.get_event_loop().run_in_executor(
            None, _upsert_metadata_sync, video_id, meta
        )
        logger.info("[Optimizer] ✅  Metadata saved to local DB.")
    except Exception as exc:
        logger.error("[Optimizer] ❌  Local DB write failed: %s", exc)

    # ── Step 6b: Save SEO analysis snapshot (Phase 1 wiring) ────────────────────
    try:
        await asyncio.get_event_loop().run_in_executor(
            None, _save_seo_analysis, video_id, meta, current_score, poll_num
        )
    except Exception as exc:
        logger.warning("[Optimizer] ⚠  SEO snapshot write failed (non-fatal): %s", exc)

    # ── Step 7: Post pinned comment (best-effort) ─────────────────────────
    _section("STEP 7 — Posting pinned comment")
    pinned = meta.get("pinned_comment", "")
    if pinned:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, _post_pinned_comment, youtube_video_id, pinned
            )
            logger.info("[Optimizer] ✅  Pinned comment posted: '%s'", pinned)
        except Exception as exc:
            logger.warning("[Optimizer] ⚠  Pinned comment failed (non-fatal): %s", exc)
    else:
        logger.info("[Optimizer] No pinned comment generated — skipping.")

    # ── Step 8: Log attempt ───────────────────────────────────────────────
    _section("STEP 8 — Logging optimization attempt")
    try:
        await asyncio.get_event_loop().run_in_executor(
            None, _log_optimization_sync, video_id, poll_num, meta, current_score
        )
        logger.info("[Optimizer] ✅  Optimization attempt logged.")
    except Exception as exc:
        logger.error("[Optimizer] ❌  Log write failed: %s", exc)

    _banner(f"OPTIMIZATION COMPLETE  |  poll={poll_num}")
    return meta


# ── Legacy compatibility shim ─────────────────────────────────────────────────
def start_optimizer(video_id: str, youtube_video_id: str) -> asyncio.Task:
    """Legacy entry-point: schedule one optimization attempt as a background task."""
    async def _one_shot():
        await run_single_optimization(video_id, youtube_video_id, current_score=0.0, poll_num=1)

    task = asyncio.ensure_future(_one_shot())
    logger.info(
        "[Optimizer] (legacy) Task scheduled for video_id=%s youtube_id=%s",
        video_id, youtube_video_id,
    )
    return task
