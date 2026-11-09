"""
Description Attribution Service — ClipForge
Constructs standardized, search-optimized descriptions for published YouTube Shorts
with automatic original source attribution, clickable source video links, and SEO hashtags.
"""
import re
import logging
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

YOUTUBE_URL_REGEX = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
    re.IGNORECASE
)

MAX_DESCRIPTION_LENGTH = 5000


def extract_canonical_youtube_url(source: Union[str, None]) -> Optional[str]:
    """
    Extracts a canonical clickable YouTube URL (https://www.youtube.com/watch?v=VIDEO_ID)
    from a full URL, short URL, or raw 11-character video ID.
    Returns None for local files, empty inputs, or non-YouTube identifiers.
    """
    if not source or not isinstance(source, str):
        return None
    
    clean_src = source.strip()
    if not clean_src:
        return None

    # Check if raw 11-char ID (alphanumeric, dashes, underscores)
    if len(clean_src) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', clean_src):
        return f"https://www.youtube.com/watch?v={clean_src}"

    match = YOUTUBE_URL_REGEX.search(clean_src)
    if match:
        yt_id = match.group(1)
        return f"https://www.youtube.com/watch?v={yt_id}"

    return None


def format_hashtag(tag: str) -> str:
    """Format a tag or topic into a clean camel-case hashtag with '#' prefix."""
    if not tag:
        return ""
    clean = str(tag).strip()
    if clean.startswith("#"):
        clean = clean[1:]
    # Remove punctuation except alphanumeric
    words = re.findall(r'[a-zA-Z0-9]+', clean)
    if not words:
        return ""
    # Capitalize each word for readability (#ArtificialIntelligence)
    camel = "".join(w.capitalize() for w in words)
    return f"#{camel}"


def build_attributed_description(
    clip_description: Optional[str] = None,
    source_youtube_url: Optional[str] = None,
    source_title: Optional[str] = None,
    source_channel: Optional[str] = None,
    hashtags: Optional[Union[List[str], str]] = None,
    include_attribution: bool = True,
    include_hashtags: bool = True,
    max_length: int = MAX_DESCRIPTION_LENGTH,
) -> str:
    """
    Builds a unified, professional, platform-compliant YouTube description:
    1. Preserves existing clip-specific narrative description.
    2. Adds clearly labeled original-source attribution with a clickable YouTube URL (if source is YouTube).
    3. Appends clean canonical SEO hashtags.
    4. Guards against duplicate attribution blocks or duplicate hashtags.
    5. Ensures zero fake YouTube URLs for local file uploads.
    6. Strictly respects YouTube's 5000 character limit.
    """
    base_desc = (clip_description or "").strip()

    # Clean existing base description of trailing whitespace
    # Check if attribution block already exists in base_desc to prevent duplicate blocks
    canonical_yt_url = extract_canonical_youtube_url(source_youtube_url)
    
    already_attributed = False
    if canonical_yt_url and canonical_yt_url in base_desc:
        already_attributed = True
    elif "Original video:" in base_desc or "Watch the complete video here:" in base_desc:
        already_attributed = True

    attribution_section = ""
    if include_attribution and canonical_yt_url and not already_attributed:
        lines = ["Original video:"]
        if source_title and source_title.strip() and source_title.strip() != "Untitled":
            clean_title = source_title.strip()
            # If title is long, keep it concise
            if len(clean_title) > 90:
                clean_title = clean_title[:87] + "..."
            lines.append(f'"{clean_title}"')
        if source_channel and source_channel.strip():
            lines.append(f"Source Channel: {source_channel.strip()}")
        lines.append("Watch the complete video here:")
        lines.append(canonical_yt_url)
        attribution_section = "\n".join(lines)

    # Process hashtags
    tag_list = []
    if include_hashtags and hashtags:
        raw_list = []
        if isinstance(hashtags, str):
            raw_list = [h.strip() for h in hashtags.replace(",", " ").split() if h.strip()]
        elif isinstance(hashtags, (list, tuple, set)):
            raw_list = [str(h).strip() for h in hashtags if str(h).strip()]
        
        for item in raw_list:
            formatted = format_hashtag(item)
            if formatted and formatted not in tag_list:
                tag_list.append(formatted)

    # Filter out hashtags that already appear in base_desc or attribution
    combined_existing = f"{base_desc} {attribution_section}".lower()
    new_hashtags = [
        ht for ht in tag_list
        if ht.lower() not in combined_existing
    ]

    hashtag_section = " ".join(new_hashtags) if new_hashtags else ""

    # Assemble sections with double newlines
    sections = []
    if base_desc:
        sections.append(base_desc)
    if attribution_section:
        sections.append(attribution_section)
    if hashtag_section:
        sections.append(hashtag_section)

    final_description = "\n\n".join(sections).strip()

    # Respect platform character limits
    if len(final_description) > max_length:
        # Calculate needed reduction from base_desc
        non_base_len = len(final_description) - len(base_desc)
        allowed_base_len = max(50, max_length - non_base_len - 10)
        truncated_base = base_desc[:allowed_base_len].rstrip() + "..."
        sections[0] = truncated_base
        final_description = "\n\n".join(s for s in sections if s).strip()
        final_description = final_description[:max_length]

    return final_description
