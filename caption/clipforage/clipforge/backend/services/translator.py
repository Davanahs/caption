"""
Phase 15: AI Multi-Language Translator Service 🌍
Translates transcripts and titles into target languages using LLM / Router.
Supported Target Languages:
  - es (Spanish)
  - hi (Hindi)
  - de (German)
  - ja (Japanese)
  - pt (Portuguese)
  - fr (French)
"""
from __future__ import annotations

import re
import json
import asyncio
from typing import Dict, Any, Optional

LANGUAGE_MAP = {
    "es": "Spanish",
    "hi": "Hindi",
    "de": "German",
    "ja": "Japanese",
    "pt": "Portuguese",
    "fr": "French"
}

_TRANSLATE_PROMPT = """\
You are an expert natural audio dubbing translator. Translate the following video transcript text into {target_language}.

Original Text:
{text}

Rules:
1. Preserve natural spoken tone, pacing, and emotional impact.
2. Keep length and word count comparable to original for smooth voice synchronization.
3. Return ONLY the translated text without commentary, quotes, or markdown.
"""


async def translate_text(text: str, target_lang: str) -> str:
    """
    Translates text into target_lang ('es', 'hi', 'de', 'ja', 'pt', 'fr').
    Uses LLM router with fallback if offline.
    """
    if not text or not text.strip():
        return ""
    
    lang_name = LANGUAGE_MAP.get(target_lang.lower(), target_lang)
    prompt = _TRANSLATE_PROMPT.format(target_language=lang_name, text=text.strip())

    try:
        from backend.services.llm_router import route_and_generate
        translated = await route_and_generate(prompt, max_tokens=1000)
        translated = re.sub(r"```[a-z]*\n?", "", translated).strip().rstrip("```").strip()
        if translated:
            return translated
    except Exception as e:
        print(f"[Translator] LLM translation failed ({e}). Returning original text.")

    return text
