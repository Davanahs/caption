import json
import logging
from datetime import datetime, timezone
from backend.core.config import settings
from backend.models.database import SyncSessionLocal
from backend.models.models import ContentAnalysis, SEOAnalysis

logger = logging.getLogger("clipforge.seo_analyzer")


def analyze_seo(
    clip_id: str, title: str, description: str, hashtags: list[str]
) -> dict:
    """
    Evaluates metadata quality BEFORE publishing.
    Uses cached content_analysis data.
    Runs algorithmically to avoid expensive LLM calls.
    """
    # 1. Fetch content analysis
    content_data = {}
    try:
        with SyncSessionLocal() as session:
            analysis = session.query(ContentAnalysis).filter_by(clip_id=clip_id).first()
            if analysis and analysis.analysis_json:
                content_data = json.loads(analysis.analysis_json)
    except Exception as e:
        logger.error(f"[SEOAnalyzer] DB fetch error: {e}")

    # Fallbacks if no content_analysis exists
    keywords = content_data.get("searchable_keywords", [])
    hashtag_candidates = content_data.get("hashtag_candidates", [])
    niche = content_data.get("niche", "General")

    # Lowercase title & description for checking
    title_lower = title.lower()
    desc_lower = description.lower()
    meta_hashtags_lower = [h.lower().lstrip("#") for h in hashtags]

    # Check missing keywords
    missing_keywords = []
    found_keywords_count = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower or kw_lower in desc_lower:
            found_keywords_count += 1
        else:
            missing_keywords.append(kw)

    # Check keyword density
    total_words = len(title.split()) + len(description.split())
    keyword_density = round(found_keywords_count / max(total_words, 1), 4)

    # Identify weak/generic hashtags
    weak_candidates = {
        "viral",
        "fyp",
        "xyz",
        "trending",
        "shorts",
        "explore",
        "foryou",
    }
    weak_hashtags = []
    for h in meta_hashtags_lower:
        if h in weak_candidates:
            weak_hashtags.append(f"#{h}")

    # Recommended hashtags that are NOT currently used
    recommended_hashtags = []
    for h in hashtag_candidates:
        h_clean = h.lower().lstrip("#")
        if h_clean not in meta_hashtags_lower:
            recommended_hashtags.append(f"#{h_clean}")

    # Title strength check
    title_len = len(title)
    # Ideal YouTube title length: 30-70 characters
    length_score = 100 if 30 <= title_len <= 70 else (50 if title_len > 0 else 0)

    # Emotional hook words
    emotional_words = {
        "secret",
        "why",
        "reveal",
        "never",
        "insane",
        "shocking",
        "mind-blowing",
        "viral",
        "epic",
        "perfect",
        "easy",
    }
    has_emotion = any(w in title_lower for w in emotional_words)
    emotion_score = 100 if has_emotion else 60

    # Title strength calculation
    title_strength = round((length_score + emotion_score) / 2.0, 2)

    # Curiosity gap score
    has_question = "?" in title
    has_exclamation = "!" in title
    curiosity_keywords = {
        "secret",
        "why",
        "how",
        "what happened",
        "this is",
        "never tell",
    }
    has_curiosity_kw = any(w in title_lower for w in curiosity_keywords)
    curiosity_score = 90 if (has_question or has_exclamation or has_curiosity_kw) else 60

    # CTR Score: combo of curiosity, title strength, and emotion
    ctr_score = round((curiosity_score + title_strength) / 2.0, 2)

    # Discoverability Score: keyword usage and hashtag placement
    kw_factor = (found_keywords_count / max(len(keywords), 1)) * 100
    hashtag_factor = (
        len([h for h in hashtags if h.lower().lstrip("#") not in weak_candidates])
        / max(len(hashtags), 1)
    ) * 100
    discoverability_score = round((kw_factor + hashtag_factor) / 2.0, 2)

    # Final SEO Score
    seo_score = round((ctr_score + discoverability_score) / 2.0, 2)

    seo_json_data = {
        "seo_score": seo_score,
        "ctr_score": ctr_score,
        "discoverability_score": discoverability_score,
        "keyword_density": keyword_density,
        "missing_keywords": missing_keywords,
        "weak_hashtags": weak_hashtags,
        "recommended_hashtags": recommended_hashtags,
        "title_strength": title_strength,
        "curiosity_gap_score": curiosity_score,
        "niche_relevance": niche,
    }

    # Save to database
    try:
        with SyncSessionLocal() as session:
            existing = session.query(SEOAnalysis).filter_by(clip_id=clip_id).first()
            if existing:
                existing.seo_score = seo_score
                existing.ctr_score = ctr_score
                existing.discoverability_score = discoverability_score
                existing.missing_keywords = ",".join(missing_keywords)
                existing.recommended_hashtags = ",".join(recommended_hashtags)
                existing.weak_hashtags = ",".join(weak_hashtags)
                existing.seo_json = json.dumps(seo_json_data)
                existing.created_at = datetime.now(timezone.utc)
            else:
                new_analysis = SEOAnalysis(
                    clip_id=clip_id,
                    seo_score=seo_score,
                    ctr_score=ctr_score,
                    discoverability_score=discoverability_score,
                    missing_keywords=",".join(missing_keywords),
                    recommended_hashtags=",".join(recommended_hashtags),
                    weak_hashtags=",".join(weak_hashtags),
                    seo_json=json.dumps(seo_json_data),
                    created_at=datetime.now(timezone.utc)
                )
                session.add(new_analysis)
            session.commit()
            logger.info(
                f"[SEOAnalyzer] Saved SEO analysis for clip_id={clip_id} (Score: {seo_score})"
            )
    except Exception as db_err:
        logger.error(f"[SEOAnalyzer] DB save error: {db_err}")

    return seo_json_data
