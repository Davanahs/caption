"""
Source-Level AI Metadata Engine — ClipForge
Analyzes source videos ONCE upon ingestion/transcription to generate:
1. Primary Category & Secondary Topics
2. 4–6 Canonical SEO Search Tags (for YouTube snippet.tags)
3. Canonical Description Hashtags (for YouTube snippet.description)
4. Persistent Storage & Reuse across all child clips.
"""
import re
import os
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.core.config import settings
from backend.services.llm_router import route_and_generate, is_ai_provider_configured
from backend.services.description_attribution import (
    build_attributed_description,
    extract_canonical_youtube_url,
    format_hashtag,
)

logger = logging.getLogger(__name__)

# Canonical mapping from semantic categories/keywords to YouTube Data API category IDs
YOUTUBE_CATEGORY_MAP: Dict[str, str] = {
    # 28: Science & Technology
    "artificial intelligence": "28",
    "ai": "28",
    "machine learning": "28",
    "software development": "28",
    "coding": "28",
    "programming": "28",
    "technology": "28",
    "tech": "28",
    "computer science": "28",
    "hardware": "28",
    "cybersecurity": "28",
    "data science": "28",
    "robotics": "28",
    
    # 27: Education
    "education": "27",
    "tutorial": "27",
    "tutorials": "27",
    "personal development": "27",
    "self improvement": "27",
    "learning": "27",
    "science": "27",
    "math": "27",
    
    # 20: Gaming
    "gaming": "20",
    "video games": "20",
    "gameplay": "20",
    "walkthrough": "20",
    "esports": "20",
    
    # 25: News & Politics / Business
    "business": "25",
    "entrepreneurship": "25",
    "startups": "25",
    "finance": "25",
    "economics": "25",
    "news": "25",
    "politics": "25",
    
    # 24: Entertainment
    "entertainment": "24",
    "podcast": "24",
    "podcasts": "24",
    "interview": "24",
    "interviews": "24",
    "talk show": "24",
    
    # 23: Comedy
    "comedy": "23",
    "humor": "23",
    
    # 26: Howto & Style
    "howto": "26",
    "how to": "26",
    "style": "26",
    "diy": "26",
    
    # 22: People & Blogs
    "people & blogs": "22",
    "people and blogs": "22",
    "vlog": "22",
    "lifestyle": "22",
    
    # 17: Sports
    "sports": "17",
    "fitness": "17",
    
    # 10: Music
    "music": "10",
    "musician": "10",
}


@dataclass
class SourceSeoMetadata:
    source_video_id: str
    primary_category: str
    youtube_category_id: str
    secondary_topics: List[str]
    seo_tags: List[str]  # 4–6 search-oriented tags (for snippet.tags)
    description_hashtags: List[str]  # 3–5 camel-case hashtags (for snippet.description)
    summary: str
    source_title: str = "Untitled"
    source_youtube_id: Optional[str] = None
    source_youtube_url: Optional[str] = None
    is_ai_generated: bool = True
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceSeoMetadata":
        return cls(
            source_video_id=data.get("source_video_id", ""),
            primary_category=data.get("primary_category", "Technology"),
            youtube_category_id=str(data.get("youtube_category_id", "28")),
            secondary_topics=data.get("secondary_topics", []),
            seo_tags=data.get("seo_tags", []),
            description_hashtags=data.get("description_hashtags", []),
            summary=data.get("summary", ""),
            source_title=data.get("source_title", "Untitled"),
            source_youtube_id=data.get("source_youtube_id"),
            source_youtube_url=data.get("source_youtube_url"),
            is_ai_generated=data.get("is_ai_generated", True),
            analyzed_at=data.get("analyzed_at", datetime.now(timezone.utc).isoformat()),
        )


def resolve_youtube_category_id(category_name: str) -> str:
    """Map human-readable category name or keyword to valid YouTube category ID."""
    if not category_name:
        return "28"
    
    clean = category_name.strip().lower()
    if clean in YOUTUBE_CATEGORY_MAP:
        return YOUTUBE_CATEGORY_MAP[clean]
    
    for kw, cat_id in YOUTUBE_CATEGORY_MAP.items():
        if kw in clean or clean in kw:
            return cat_id
            
    return "28"  # Default to Science & Technology / tech automation


def normalize_seo_tags(raw_tags: List[str], fallback_topics: List[str] = None) -> List[str]:
    """
    Normalizes, cleans, deduplicates, and validates SEO tags:
    - Strips leading '#' or whitespace.
    - Limits to alphanumeric and natural phrase boundaries.
    - Preserves title-casing or natural capitalization.
    - Deduplicates case-insensitively.
    - Enforces 4–6 tags constraint.
    - Ensures total character length is within YouTube constraints (< 450 chars).
    """
    normalized = []
    seen = set()

    # Process primary raw_tags first
    for tag in (raw_tags or []):
        if not tag:
            continue
        clean = str(tag).strip()
        if clean.startswith("#"):
            clean = clean[1:].strip()
        # Remove unwanted punctuation and brackets including < and >
        clean = re.sub(r'[,;\"\'\[\]{}()<>\n]+', '', clean).strip()
        if not clean or len(clean) < 2 or len(clean) > 50:
            continue
        
        lower_key = clean.lower()
        if lower_key not in seen:
            seen.add(lower_key)
            normalized.append(clean)
            if len(normalized) >= 6:
                return normalized

    # Only if fewer than 4 tags, pull from fallback_topics
    if len(normalized) < 4 and fallback_topics:
        fb_list = [fallback_topics] if isinstance(fallback_topics, str) else list(fallback_topics)
        for fb in fb_list:
            if not fb:
                continue
            clean = str(fb).strip()
            if clean.startswith("#"):
                clean = clean[1:].strip()
            clean = re.sub(r'[,;\"\'\[\]{}()<>\n]+', '', clean).strip()
            if not clean or len(clean) < 2 or len(clean) > 50:
                continue
            lower_key = clean.lower()
            if lower_key not in seen:
                seen.add(lower_key)
                normalized.append(clean)
                if len(normalized) >= 6:
                    return normalized

    # If fewer than 4 tags, pad with sensible generic domain terms if available
    defaults = ["Artificial Intelligence", "Technology", "Software", "Digital Innovation", "Online Tools", "Tech Updates"]
    for d in defaults:
        if len(normalized) >= 4:
            break
        if d.lower() not in seen:
            seen.add(d.lower())
            normalized.append(d)

    return normalized[:6]


def normalize_description_hashtags(raw_hashtags: List[str], fallback_tags: Any = None) -> List[str]:
    """Ensures 3–5 clean camel-cased description hashtags with '#' prefix."""
    hashtags = []
    seen = set()

    for item in (raw_hashtags or []):
        formatted = format_hashtag(item)
        if not formatted:
            continue
        key = formatted.lower()
        if key not in seen:
            seen.add(key)
            hashtags.append(formatted)
            if len(hashtags) >= 5:
                return hashtags

    # If fewer than 3 hashtags, pull from fallback_tags
    if len(hashtags) < 3 and fallback_tags:
        if isinstance(fallback_tags, str):
            fallback_list = [fallback_tags]
        elif isinstance(fallback_tags, (list, tuple, set)):
            fallback_list = list(fallback_tags)
        else:
            fallback_list = []
        for item in fallback_list:
            formatted = format_hashtag(item)
            if not formatted:
                continue
            key = formatted.lower()
            if key not in seen:
                seen.add(key)
                hashtags.append(formatted)
                if len(hashtags) >= 5:
                    return hashtags

    # If still fewer than 3 hashtags, synthesize from fallback defaults
    default_hts = ["#Tech", "#Innovation", "#Shorts", "#Trending"]
    for dh in default_hts:
        if len(hashtags) >= 3:
            break
        if dh.lower() not in seen:
            seen.add(dh.lower())
            hashtags.append(dh)

    return hashtags[:5]


def get_source_metadata_storage_path(video_id: str) -> Path:
    """Returns local path for durable source SEO metadata artifact."""
    base_dir = Path("uploads") / str(video_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "source_seo_metadata.json"


def load_persisted_source_metadata(video_id: str) -> Optional[SourceSeoMetadata]:
    """
    Attempts to load existing source metadata from:
    1. Disk artifact: uploads/{video_id}/source_seo_metadata.json
    2. VideoMetadata database record
    """
    # 1. Check disk artifact
    artifact_path = get_source_metadata_storage_path(video_id)
    if artifact_path.exists():
        try:
            with open(artifact_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SourceSeoMetadata.from_dict(data)
        except Exception as e:
            logger.warning(f"[SourceMetadata] Could not read disk artifact for {video_id}: {e}")

    # 2. Check VideoMetadata table
    try:
        from backend.models.database import SyncSessionLocal
        from backend.models.models import VideoMetadata
        with SyncSessionLocal() as session:
            meta = session.query(VideoMetadata).filter_by(video_id=video_id).first()
            if meta and meta.tags:
                tags = [t.strip() for t in meta.tags.split(",") if t.strip()]
                hts = [h.strip() for h in meta.hashtags.split(",") if h.strip()] if meta.hashtags else []
                if len(tags) >= 2:
                    return SourceSeoMetadata(
                        source_video_id=video_id,
                        primary_category="Technology",
                        youtube_category_id="28",
                        secondary_topics=[],
                        seo_tags=tags,
                        description_hashtags=hts,
                        summary=meta.description or "",
                        source_title=meta.title or "Untitled",
                        is_ai_generated=False
                    )
    except Exception as db_err:
        logger.debug(f"[SourceMetadata] Database lookup fallback error for {video_id}: {db_err}")

    return None


def persist_source_metadata(metadata: SourceSeoMetadata, session=None) -> None:
    """
    Persists source metadata to both:
    1. Disk artifact: uploads/{video_id}/source_seo_metadata.json
    2. Database VideoMetadata table record for video_id
    """
    # 1. Save disk artifact
    artifact_path = get_source_metadata_storage_path(metadata.source_video_id)
    try:
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)
        logger.info(f"[SourceMetadata] Persisted source metadata artifact to {artifact_path}")
    except Exception as e:
        logger.warning(f"[SourceMetadata] Could not write disk artifact for {metadata.source_video_id}: {e}")

    # 2. Upsert VideoMetadata database record
    def _do_db_persist(db_session):
        from backend.models.models import VideoMetadata
        tags_str = ",".join(metadata.seo_tags)
        hashtags_str = ",".join(metadata.description_hashtags)
        existing = db_session.query(VideoMetadata).filter_by(video_id=metadata.source_video_id).first()
        if existing:
            existing.title = metadata.source_title[:200]
            existing.description = metadata.summary
            existing.tags = tags_str
            existing.hashtags = hashtags_str
        else:
            rec = VideoMetadata(
                video_id=metadata.source_video_id,
                title=metadata.source_title[:200],
                description=metadata.summary,
                tags=tags_str,
                hashtags=hashtags_str,
            )
            db_session.add(rec)
        db_session.commit()

    if session:
        try:
            _do_db_persist(session)
        except Exception as e:
            logger.warning(f"[SourceMetadata] Failed to persist VideoMetadata in active session: {e}")
    else:
        try:
            from backend.models.database import SyncSessionLocal
            with SyncSessionLocal() as s:
                _do_db_persist(s)
        except Exception as e:
            logger.warning(f"[SourceMetadata] Failed to persist VideoMetadata in new session: {e}")


def _generate_deterministic_fallback_metadata(
    video_id: str,
    title: str,
    transcript_text: str,
    youtube_url: Optional[str] = None,
    youtube_id: Optional[str] = None
) -> SourceSeoMetadata:
    """
    Generates high-relevance deterministic fallback metadata when Cloud AI is unavailable
    or running in offline test fixtures. Understands content from title + transcript keywords.
    """
    combined_text = f"{title} {transcript_text[:2000]}".lower()

    # Rule-based primary category classification
    primary_cat = "Technology"
    cat_id = "28"
    if any(k in combined_text for k in ("game", "gaming", "playthrough", "gameplay", "walkthrough", "boss battle", "boss fight")):
        primary_cat = "Gaming"
        cat_id = "20"
    elif any(k in combined_text for k in ("code", "coding", "software", "developer", "programming", "python", "javascript", "backend", "fast api", "fastapi")):
        primary_cat = "Software Development"
        cat_id = "28"
    elif any(k in combined_text for k in ("ai", "artificial intelligence", "llm", "neural", "deepseek", "chatgpt", "gemini")):
        primary_cat = "Artificial Intelligence"
        cat_id = "28"
    elif any(k in combined_text for k in ("business", "startup", "founder", "money", "investing", "revenue", "valuation", "economics", "finance")):
        primary_cat = "Business and Entrepreneurship"
        cat_id = "25"
    elif any(k in combined_text for k in ("calculus", "math", "physics", "lecture", "tutorial", "education", "study", "history", "learning")):
        primary_cat = "Education"
        cat_id = "27"
    elif any(k in combined_text for k in ("podcast", "interview", "conversation", "discussion", "talk show", "episode")):
        primary_cat = "Entertainment"
        cat_id = "24"

    # Extract keywords
    words = re.findall(r'[a-zA-Z]{4,}', combined_text)
    stop_words = {"this", "that", "with", "from", "have", "were", "what", "when", "your", "they", "will", "would", "about", "there", "their"}
    freq = {}
    for w in words:
        if w not in stop_words:
            freq[w] = freq.get(w, 0) + 1
    top_words = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)[:6]
    
    tags = [primary_cat]
    for w in top_words:
        cap_word = w.capitalize()
        if cap_word not in tags:
            tags.append(cap_word)
        if len(tags) >= 5:
            break
            
    norm_tags = normalize_seo_tags(tags)
    norm_hts = normalize_description_hashtags([format_hashtag(t) for t in norm_tags])

    return SourceSeoMetadata(
        source_video_id=video_id,
        primary_category=primary_cat,
        youtube_category_id=cat_id,
        secondary_topics=["Content Analysis", "Video Highlights"],
        seo_tags=norm_tags,
        description_hashtags=norm_hts,
        summary=f"Automated content analysis and highlight segmentation for '{title}'.",
        source_title=title,
        source_youtube_id=youtube_id,
        source_youtube_url=youtube_url,
        is_ai_generated=False
    )


async def analyze_source_content_ai(
    video_id: str,
    title: str,
    transcript_text: str,
    description: str = "",
    duration: float = 0.0,
    youtube_url: Optional[str] = None,
    youtube_id: Optional[str] = None
) -> SourceSeoMetadata:
    """
    Executes source-level AI analysis via Cloud LLM router.
    Evaluates original title, description, and complete transcript to identify:
    - Genuine subject matter (filtering out clickbait or misleading titles)
    - Primary category and secondary topics
    - 4–6 search-oriented SEO tags (for YouTube snippet.tags)
    - 3–5 camel-case hashtags (for description)
    - Source content summary
    """
    # Sample up to first 6000 characters of transcript to ensure thorough content understanding
    transcript_sample = transcript_text[:8000].strip() if transcript_text else ""

    prompt = f"""You are an elite YouTube SEO strategist and video metadata expert.
Analyze this entire source video's content to classify its core topic and generate canonical discovery metadata.

SOURCE VIDEO TITLE:
{title}

SOURCE DESCRIPTION:
{description[:1000] if description else "None provided"}

TRANSCRIPT CONTENT:
{transcript_sample if transcript_sample else "No dialogue transcript available"}

INSTRUCTIONS:
1. UNDERSTAND THE REAL SUBJECT: Analyze the actual transcript dialogue and topics discussed. Do NOT rely solely on the title, which may be clickbait, incomplete, or humorous.
2. PRIMARY CATEGORY: Select a clear primary topic (e.g., "Artificial Intelligence", "Software Development", "Gaming", "Business and Entrepreneurship", "Technology", "Education and Personal Development", "Entertainment", "Comedy", "Music", "Sports").
3. SECONDARY TOPICS: List 2–3 specific sub-topics or entities mentioned.
4. CANONICAL SEO TAGS: Generate EXACTLY 4 to 6 highly relevant, search-oriented phrases that viewers would search to find this video on YouTube.
   - Tags must be clean phrases without '#' symbol.
   - High relevance, descriptive, search discovery terms.
   - Do NOT use generic useless words like "video", "shorts", "viral", "fyp".
   - Each tag must be under 40 characters.
5. DESCRIPTION HASHTAGS: Generate EXACTLY 3 to 5 camel-case hashtags starting with '#' (e.g. #ArtificialIntelligence, #SoftwareDevelopment, #Coding).
6. SUMMARY: Write a concise 1–2 sentence factual summary of what the video covers.

RESPOND ONLY WITH A VALID JSON OBJECT (no markdown, no code block backticks):
{{
  "primary_category": "<Category Name>",
  "secondary_topics": ["<topic1>", "<topic2>"],
  "seo_tags": ["<Tag 1>", "<Tag 2>", "<Tag 3>", "<Tag 4>", "<Tag 5>"],
  "description_hashtags": ["#TagOne", "#TagTwo", "#TagThree"],
  "summary": "<Concise 1-2 sentence overview>"
}}"""

    try:
        raw_output = await route_and_generate(prompt)
        if hasattr(raw_output, "content"):
            raw_output = getattr(raw_output, "content")
        if isinstance(raw_output, (dict, list)):
            raw_output = json.dumps(raw_output)
        raw_output = str(raw_output or "").strip()
        if not raw_output:
            raise ValueError("Empty response from AI model")

        # Strip think blocks (DeepSeek-R1 / reasoning models) and markdown fences
        clean_text = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL).strip()
        clean_text = re.sub(r'^```[a-zA-Z]*\s*', '', clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r'\s*```\s*$', '', clean_text, flags=re.MULTILINE).strip()

        # Extract first JSON object
        decoder = json.JSONDecoder()
        json_obj = None
        pos = 0
        while pos < len(clean_text):
            brace_pos = clean_text.find('{', pos)
            if brace_pos == -1:
                break
            try:
                obj, end_pos = decoder.raw_decode(clean_text, brace_pos)
                if isinstance(obj, dict):
                    json_obj = obj
                    break
            except json.JSONDecodeError:
                pass
            pos = brace_pos + 1

        if not json_obj:
            raise ValueError("No valid JSON object found in LLM response")

        primary_cat = str(json_obj.get("primary_category", "Technology")).strip()
        cat_id = resolve_youtube_category_id(primary_cat)
        sec_topics = [str(t).strip() for t in json_obj.get("secondary_topics", []) if str(t).strip()]
        raw_tags = [str(t).strip() for t in json_obj.get("seo_tags", []) if str(t).strip()]
        raw_hts = [str(h).strip() for h in json_obj.get("description_hashtags", []) if str(h).strip()]
        summary = str(json_obj.get("summary", f"Highlights from {title}")).strip()

        norm_tags = normalize_seo_tags(raw_tags, fallback_topics=sec_topics)
        norm_hts = normalize_description_hashtags(raw_hts, fallback_tags=norm_tags)

        return SourceSeoMetadata(
            source_video_id=video_id,
            primary_category=primary_cat,
            youtube_category_id=cat_id,
            secondary_topics=sec_topics,
            seo_tags=norm_tags,
            description_hashtags=norm_hts,
            summary=summary,
            source_title=title,
            source_youtube_id=youtube_id,
            source_youtube_url=youtube_url,
            is_ai_generated=True
        )

    except Exception as e:
        logger.warning(f"[SourceMetadata] Cloud AI analysis failed for {video_id}: {e}. Engaging deterministic content analysis...")
        return _generate_deterministic_fallback_metadata(
            video_id=video_id,
            title=title,
            transcript_text=transcript_text,
            youtube_url=youtube_url,
            youtube_id=youtube_id
        )


def get_or_analyze_source_seo_metadata(
    video_id: str,
    session=None,
    force_refresh: bool = False
) -> SourceSeoMetadata:
    """
    Canonical Entrypoint: Reuses existing source-level metadata if present.
    If missing or force_refresh is True, inspects source Video record and executes
    AI category classification and SEO tag generation ONCE.
    """
    if not force_refresh:
        existing = load_persisted_source_metadata(video_id)
        if existing and existing.seo_tags and len(existing.seo_tags) >= 4:
            logger.info(f"[SourceMetadata] Reusing canonical source metadata for video {video_id} (0 duplicate AI calls)")
            return existing

    # Needs generation: retrieve Video details from database
    import asyncio
    from backend.models.database import SyncSessionLocal
    from backend.models.models import Video

    def _query_video(s):
        return s.query(Video).filter_by(id=video_id).first()

    video = None
    if session:
        video = _query_video(session)
    else:
        with SyncSessionLocal() as s:
            video = _query_video(s)

    if not video:
        logger.warning(f"[SourceMetadata] Video record {video_id} not found, generating stub metadata")
        return _generate_deterministic_fallback_metadata(video_id, "Untitled Video", "")

    # Extract transcript text
    transcript_text = ""
    if video.transcript:
        try:
            parsed = json.loads(video.transcript)
            if isinstance(parsed, dict) and "segments" in parsed:
                transcript_text = " ".join(seg.get("text", "") for seg in parsed["segments"])
            elif isinstance(parsed, list):
                transcript_text = " ".join(seg.get("text", "") for seg in parsed if isinstance(seg, dict))
            elif isinstance(parsed, str):
                transcript_text = parsed
        except Exception:
            transcript_text = str(video.transcript)

    # Execute analysis
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                metadata = pool.submit(
                    asyncio.run,
                    analyze_source_content_ai(
                        video_id=video_id,
                        title=video.title or "Untitled",
                        transcript_text=transcript_text,
                        description="",
                        duration=video.duration or 0.0,
                        youtube_url=video.youtube_url,
                        youtube_id=video.youtube_id
                    )
                ).result()
        else:
            metadata = loop.run_until_complete(
                analyze_source_content_ai(
                    video_id=video_id,
                    title=video.title or "Untitled",
                    transcript_text=transcript_text,
                    description="",
                    duration=video.duration or 0.0,
                    youtube_url=video.youtube_url,
                    youtube_id=video.youtube_id
                )
            )
    except Exception as e:
        logger.warning(f"[SourceMetadata] Async loop execution failure: {e}, falling back to deterministic metadata")
        metadata = _generate_deterministic_fallback_metadata(
            video_id=video_id,
            title=video.title or "Untitled",
            transcript_text=transcript_text,
            youtube_url=video.youtube_url,
            youtube_id=video.youtube_id
        )

    # Persist for all subsequent clips and operations
    persist_source_metadata(metadata, session=session)
    return metadata
