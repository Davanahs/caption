"""
Metadata Generator — generates YouTube Shorts metadata from clip transcript using LLM.

Generates:
- Title (< 60 chars)
- Description (200–300 words + 5 hashtags)
- Tags/Hashtags (15–20)
- Pinned comment (< 100 chars, CTA)
"""
import json
import re
from pathlib import Path
from typing import Optional




# ── LLM Metadata Generation ───────────────────────────────────────────────────

def _build_metadata_prompt(transcript: str, clip_title: str, clip_duration: float) -> str:
    """Build the LLM prompt for metadata generation."""
    return f"""You are a YouTube Shorts growth expert. Generate viral metadata for this short clip.

CLIP TITLE: {clip_title}
CLIP DURATION: {clip_duration:.0f} seconds
TRANSCRIPT:
{transcript[:2000]}

Generate metadata in this EXACT JSON format (no markdown, no code blocks, just raw JSON):
{{
  "title": "...",
  "variant_b_title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", "..."],
  "pinned_comment": "..."
}}

RULES:
- title: (Variant A) Under 60 characters. Punchy, curiosity-driven, no clickbait. Include 1 relevant emoji.
- variant_b_title: (Variant B) Under 60 characters. Bold, high-energy hook. Must be distinct from Variant A. Include 1 relevant emoji.
- description: 200-300 words. Hook in first line. Tell the story. End with 5 hashtags on their own line. (e.g. #Shorts #viral #trending)
- tags: Exactly 15 tags. Mix of broad (shorts, viral) and specific (topic keywords). No # prefix.
- pinned_comment: Under 100 characters. Strong CTA (e.g. "Follow for more! 🔥 Comment your thoughts below 👇")

Respond with ONLY the raw JSON object. No explanations."""


def _parse_metadata_response(raw: str) -> dict:
    """Parse and validate LLM response into metadata dict."""
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    raw = raw.strip()

    data = json.loads(raw)

    title = str(data.get("title", "")).strip()[:60]
    variant_b_title = str(data.get("variant_b_title", "")).strip()[:60]
    if not variant_b_title:
        variant_b_title = title  # Fallback if model misses it
    description = str(data.get("description", "")).strip()
    tags = data.get("tags", [])
    if isinstance(tags, list):
        tags = [str(t).strip().lstrip("#") for t in tags[:20]]
    else:
        tags = []
    pinned_comment = str(data.get("pinned_comment", "")).strip()[:100]

    return {
        "title": title,
        "variant_b_title": variant_b_title,
        "description": description,
        "tags": tags,
        "pinned_comment": pinned_comment,
    }


async def generate_metadata(
    transcript: str,
    clip_title: str,
    clip_duration: float,
    segments: Optional[list[dict]] = None,
    max_retries: int = 3,
) -> dict:
    """
    Generate full YouTube Shorts metadata from transcript using LLM.

    Returns:
        {
          "title": str,
          "description": str,
          "tags": list[str],
          "pinned_comment": str,
        }
    """
    from backend.services.llm_router import route_and_generate

    prompt = _build_metadata_prompt(transcript, clip_title, clip_duration)

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[MetadataGen] Attempt {attempt}/{max_retries} - generating metadata...")
            raw = await route_and_generate(prompt)
            metadata = _parse_metadata_response(raw)
            safe_title = metadata['title'].encode('ascii', 'ignore').decode('ascii')
            print(f"[MetadataGen] Generated: '{safe_title}'")
            return metadata
        except Exception as e:
            last_err = e
            print(f"[MetadataGen] Attempt {attempt} failed: {e}")

    # Fallback: return basic metadata if LLM fails
    print(f"[MetadataGen] All attempts failed ({last_err}). Using fallback metadata.")
    return {
        "title": clip_title[:60],
        "variant_b_title": (clip_title + " (Alternate)")[:60],
        "description": f"{transcript[:200]}\n\n#Shorts #viral #trending #fyp #foryou",
        "tags": ["shorts", "viral", "trending", "fyp", "foryou",
                 "youtube", "youtubeshorts", "reels", "tiktok", "content"],
        "pinned_comment": "🔔 Follow for more! Drop a comment below 👇",
    }
