import os
import json
import re
import time
from pathlib import Path
import requests
from backend.core.config import settings

# ---------------------------------------------------------------------------
# OpenRouter configuration
# ---------------------------------------------------------------------------
_OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

def _get_headers():
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


_SMART_PROMPT_TEMPLATE = """You are an expert YouTube Shorts strategist and SEO copywriter.
Use the provided video details and Content Analysis to generate highly relevant, search-optimized, and click-worthy metadata.

HASHTAG RULES:
- Generate niche-specific, content-aware hashtags based on the Content Analysis hashtag candidates.
- Prioritize searchable hashtags, names of anime/topics/people if detected.
- DO NOT use generic #viral, #fyp, or #trending spam.
- Total hashtags: exactly 5.

TITLE RULES:
- Length: under 60 characters.
- Start with a strong curiosity/visual hook (This is Variant A).
- Include 1-2 relevant emojis.

VARIANT B TITLE RULES:
- Length: under 60 characters.
- Start with a bold, high-energy hook (This is Variant B).
- Must be distinctly different from Variant A.
- Include 1 relevant emoji.

DESCRIPTION RULES:
- Length: 150-250 words.
- Start with a hook.
- Include a clear CTA.
- Incorporate searchable keywords naturally.
- Append the 5 niche hashtags at the end.

PINNED COMMENT RULES:
- Maximum 80 characters.
- Must spark replies and match the target audience.

Provide the response in EXACTLY the following JSON format (no markdown, no other keys, no code fences):
{{
  "title": "<hook title>",
  "variant_b_title": "<bold high-energy hook>",
  "description": "<niche-specific description>",
  "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "hashtags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "pinned_comment": "<provocative comment>"
}}

CONTENT ANALYSIS:
Niche: {niche}
Topic: {topic}
Emotions: {emotions}
Audience Type: {audience_type}
Content Style: {content_style}
Hook Type: {hook_type}
Searchable Keywords: {searchable_keywords}
Long-tail Keywords: {long_tail_keywords}
Hashtag Candidates: {hashtag_candidates}
CTA Style: {cta_style}

TRANSCRIPT:
{transcript}
"""


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt_from_segments(segments: list) -> str:
    """Build an accurate SRT file from Whisper transcript segments.

    Each segment is expected to be a dict with keys:
        start (float), end (float), text (str)
    """
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = _seconds_to_srt_time(float(seg.get("start", 0)))
        end = _seconds_to_srt_time(float(seg.get("end", 0)))
        text = seg.get("text", "").strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def _call_openrouter(transcript: str) -> dict:
    """Send the transcript to the unified LLM router and return the parsed JSON."""
    from backend.services.llm_router import route_and_generate
    import asyncio

    prompt = _SMART_PROMPT_TEMPLATE + "\n\nTRANSCRIPT:\n" + transcript
    
    # run the async router in the executor thread
    raw = asyncio.run(route_and_generate(prompt))

    # Strip <think>...</think> blocks if a reasoning model is used
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()

    return json.loads(raw)


def generate_metadata(video_id: str, transcript: str, segments: list | None = None) -> dict:
    """Generate AI metadata for a video.

    Args:
        video_id:   The internal ClipForge video identifier.
        transcript: Full transcript text of the source video.
        segments:   Optional list of Whisper segment dicts
                    (each with 'start', 'end', 'text').

    Returns:
        dict with keys:
            title, description, tags (list), hashtags (list),
            pinned_comment.
    """
    import asyncio
    from backend.services.content_understanding import analyze_content
    from backend.services.seo_analyzer import analyze_seo

    # 1. Fetch or generate content analysis
    try:
        content_analysis = asyncio.run(analyze_content(
            clip_id=video_id,
            transcript=transcript,
            clip_title=video_id
        ))
    except Exception as e:
        print(f"[MetadataGenerator] Content analysis error: {e}")
        content_analysis = {}

    # 2. Build the LLM prompt
    niche = content_analysis.get("niche", "General")
    topic = content_analysis.get("topic", "General")
    emotions = content_analysis.get("emotions", [])
    if isinstance(emotions, list):
        emotions = ", ".join(emotions)
    audience_type = content_analysis.get("audience_type", "General")
    content_style = content_analysis.get("content_style", "General")
    hook_type = content_analysis.get("hook_type", "standard")
    searchable_keywords = content_analysis.get("searchable_keywords", [])
    if isinstance(searchable_keywords, list):
        searchable_keywords = ", ".join(searchable_keywords)
    long_tail_keywords = content_analysis.get("long_tail_keywords", [])
    if isinstance(long_tail_keywords, list):
        long_tail_keywords = ", ".join(long_tail_keywords)
    hashtag_candidates = content_analysis.get("hashtag_candidates", [])
    if isinstance(hashtag_candidates, list):
        hashtag_candidates = ", ".join(hashtag_candidates)
    cta_style = content_analysis.get("cta_style", "standard")

    prompt = _SMART_PROMPT_TEMPLATE.format(
        niche=niche,
        topic=topic,
        emotions=emotions,
        audience_type=audience_type,
        content_style=content_style,
        hook_type=hook_type,
        searchable_keywords=searchable_keywords,
        long_tail_keywords=long_tail_keywords,
        hashtag_candidates=hashtag_candidates,
        cta_style=cta_style,
        transcript=transcript
    )

    # 3. Call OpenRouter
    from backend.services.llm_router import route_and_generate
    try:
        raw = asyncio.run(route_and_generate(prompt))
        # Strip thinking blocks/fences
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw).strip()
        meta = json.loads(raw)
    except Exception as exc:
        print(f"[MetadataGenerator] LLM failed: {exc}")
        meta = {
            "title": f"Short video about {topic}",
            "variant_b_title": f"Amazing short video about {topic}",
            "description": f"Check out this short video about {topic}. {cta_style}",
            "tags": [niche.lower(), topic.lower() if isinstance(topic, str) else ""],
            "hashtags": [f"#{niche.lower()}", f"#{topic.lower() if isinstance(topic, str) else ''}"],
            "pinned_comment": "What did you think of this video? Comment below!"
        }

    result = {
        "title": meta.get("title", ""),
        "variant_b_title": meta.get("variant_b_title", meta.get("title", "") + " (Alternate)"),
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "hashtags": meta.get("hashtags", []),
        "pinned_comment": meta.get("pinned_comment", ""),
    }

    # 4. Run SEO Analyzer on the metadata
    try:
        analyze_seo(
            clip_id=video_id,
            title=result["title"],
            description=result["description"],
            hashtags=result["hashtags"]
        )
    except Exception as seo_err:
        print(f"[MetadataGenerator] SEO analyze error: {seo_err}")

    return result



# ---------------------------------------------------------------------------
# CLI test helper
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python metadata_generator.py <video_id> <transcript_file>")
        sys.exit(1)
    vid = sys.argv[1]
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        txt = f.read()
    out = generate_metadata(vid, txt)
    print(json.dumps(out, indent=2, ensure_ascii=False))
