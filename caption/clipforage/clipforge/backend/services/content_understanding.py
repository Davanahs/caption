import json
import logging
import re
from datetime import datetime, timezone
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import ContentAnalysis
from backend.services.llm_router import route_and_generate

logger = logging.getLogger("clipforge.content_understanding")

_PROMPT_TEMPLATE = """You are an expert content analyzer for short-form videos. Analyze the given transcript, title, scene intensity, and engagement heuristics to perform a deep content understanding.

Provide the response in EXACTLY the following JSON format (no markdown, no other keys, no code fences):
{{
  "niche": "<niche/category, e.g. Tech, Anime, Finance>",
  "topic": "<primary topic>",
  "secondary_topics": ["<topic1>", "<topic2>"],
  "emotions": ["<emotion1>", "<emotion2>"],
  "audience_type": "<target audience type>",
  "content_style": "<e.g., educational, storytelling, comedy, high-energy>",
  "pacing": "<e.g., fast, moderate, slow>",
  "hook_type": "<e.g., curiosity, visual, controversial, question>",
  "searchable_keywords": ["<keyword1>", "<keyword2>", "<keyword3>", "<keyword4>", "<keyword5>"],
  "long_tail_keywords": ["<phrase1>", "<phrase2>", "<phrase3>"],
  "hashtag_candidates": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "cta_style": "<e.g., reply prompt, visit website, like and follow>",
  "sentiment_score": <float between -1.0 and 1.0>
}}

INPUT DATA:
Transcript: {transcript}
Transcript Segment: {transcript_segment}
Clip Title: {clip_title}
Scene Intensity: {scene_intensity}
Engagement Heuristics: {engagement_heuristics}
"""


async def analyze_content(
    clip_id: str,
    transcript: str,
    transcript_segment: str = "",
    clip_title: str = "",
    scene_intensity: float = 0.0,
    engagement_heuristics: dict = None,
    force_refresh: bool = False,
) -> dict:
    """
    Analyzes content of a clip once and stores it in the database.
    Reuses existing database entry if present and not force_refreshed.
    """
    # 1. Check database
    try:
        with SyncSessionLocal() as session:
            if not force_refresh:
                analysis = session.query(ContentAnalysis).filter_by(clip_id=clip_id).first()
                if analysis:
                    logger.info(
                        f"[ContentUnderstanding] Reusing cached analysis for clip_id={clip_id}"
                    )
                    return json.loads(analysis.analysis_json)
    except Exception as e:
        logger.error(f"[ContentUnderstanding] DB check error: {e}")

    # 2. Call LLM
    logger.info(f"[ContentUnderstanding] Running analysis for clip_id={clip_id}...")
    prompt = _PROMPT_TEMPLATE.format(
        transcript=transcript,
        transcript_segment=transcript_segment,
        clip_title=clip_title,
        scene_intensity=scene_intensity,
        engagement_heuristics=json.dumps(engagement_heuristics or {}),
    )

    try:
        raw = await route_and_generate(prompt)
        # Clean response
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw).strip()
        data = json.loads(raw)
    except Exception as exc:
        logger.error(f"[ContentUnderstanding] LLM execution failed: {exc}")
        # fallback
        data = {
            "niche": "General",
            "topic": clip_title or "General Topic",
            "secondary_topics": [],
            "emotions": [],
            "audience_type": "General",
            "content_style": "General",
            "pacing": "moderate",
            "hook_type": "standard",
            "searchable_keywords": [],
            "long_tail_keywords": [],
            "hashtag_candidates": [],
            "cta_style": "standard",
            "sentiment_score": 0.0,
        }

    # 3. Store in database
    try:
        with SyncSessionLocal() as session:
            niche = data.get("niche", "General")
            topic = data.get("topic", "General")
            emotions = ",".join(data.get("emotions", []))
            audience_type = data.get("audience_type", "General")
            searchable_keywords = ",".join(data.get("searchable_keywords", []))
            long_tail_keywords = ",".join(data.get("long_tail_keywords", []))
            hashtag_candidates = ",".join(data.get("hashtag_candidates", []))
            hook_type = data.get("hook_type", "standard")
            pacing = data.get("pacing", "moderate")
            sentiment_score = float(data.get("sentiment_score", 0.0))
            analysis_json = json.dumps(data)
            created_at = datetime.now(timezone.utc)

            analysis = session.query(ContentAnalysis).filter_by(clip_id=clip_id).first()
            if analysis:
                analysis.niche = niche
                analysis.topic = topic
                analysis.emotions = emotions
                analysis.audience_type = audience_type
                analysis.searchable_keywords = searchable_keywords
                analysis.long_tail_keywords = long_tail_keywords
                analysis.hashtag_candidates = hashtag_candidates
                analysis.hook_type = hook_type
                analysis.pacing = pacing
                analysis.sentiment_score = sentiment_score
                analysis.analysis_json = analysis_json
                analysis.created_at = created_at
            else:
                new_analysis = ContentAnalysis(
                    clip_id=clip_id,
                    niche=niche,
                    topic=topic,
                    emotions=emotions,
                    audience_type=audience_type,
                    searchable_keywords=searchable_keywords,
                    long_tail_keywords=long_tail_keywords,
                    hashtag_candidates=hashtag_candidates,
                    hook_type=hook_type,
                    pacing=pacing,
                    sentiment_score=sentiment_score,
                    analysis_json=analysis_json,
                    created_at=created_at
                )
                session.add(new_analysis)
            
            session.commit()
            logger.info(f"[ContentUnderstanding] Cached analysis for clip_id={clip_id}")
    except Exception as db_err:
        logger.error(f"[ContentUnderstanding] DB save error: {db_err}")

    return data
