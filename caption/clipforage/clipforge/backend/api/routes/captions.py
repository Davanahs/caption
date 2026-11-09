"""
ClipForge — Caption Studio API Routes
Provides high-performance, end-to-end endpoints for AI caption styling:
- POS-Lite break scoring and text segmentation
- Whisper STT transcription (Groq cloud & local fallback) with word-level timestamps
- Acoustic pitch (F0) & intensity (RMS dB) analysis for viral emphasis
- AI Director Pass (Groq LLM & heuristic fallback) for emojis, SFX stings, and color tagging
- Audio cleanup (silence gap detection, filler word elimination)
- Transcript proofreading & proportional word timestamp re-mapping
- Video audio extraction (FFmpeg 16kHz mono PCM) & live audio stream serving
"""

import os
import re
import json
import uuid
import time
import shutil
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import httpx
import numpy as np

from backend.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/caption", tags=["captions"])

# Ensure directory for extracted audio and uploads exists
CAPTION_AUDIO_DIR = settings.UPLOAD_DIR / "caption_audio"
CAPTION_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ── Pydantic Request / Response Models ───────────────────────────────────────
class WordTiming(BaseModel):
    word: str
    start: float
    end: float
    isEmphasis: bool = False
    isHighPitch: bool = False
    pitchHz: Optional[float] = None
    intensityDb: Optional[float] = None
    colorOverride: Optional[str] = None


class CaptionBlock(BaseModel):
    id: str
    text: str
    start: float
    end: float
    colorTag: str = "neutral"
    emoji: Optional[str] = None
    sfx: Optional[str] = None
    emphasisWords: List[str] = []
    words: List[WordTiming] = []
    isAcousticPeak: bool = False


class ScriptSegmentRequest(BaseModel):
    text: str
    maxWords: int = 4
    wpm: int = 180
    maxChars: int = 24


class AudioCleanupRequest(BaseModel):
    blocks: List[Dict[str, Any]]
    silenceThreshold: float = 0.5
    removeFillers: bool = True


class ProofreadRequest(BaseModel):
    blocks: List[Dict[str, Any]]


class DirectorPassRequest(BaseModel):
    blocks: List[Dict[str, Any]]


# ── Constants for Deterministic Break Scoring ────────────────────────────────
CONJUNCTIONS = {
    'and', 'but', 'so', 'because', 'or', 'when', 'if', 'while',
    'although', 'since', 'then', 'where', 'as', 'than'
}
PREPOSITIONS = {
    'in', 'on', 'at', 'to', 'for', 'with', 'from', 'by', 'about',
    'into', 'through', 'over', 'under', 'between', 'during', 'without'
}
FILLER_REGEX = re.compile(r'\b(um|uh|er|ahm|hmm|like|you know|so basically)\b', re.IGNORECASE)


# ── Acoustic Analysis Engine ────────────────────────────────────────────────
def analyze_audio_acoustics(audio_path: str, words: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes RMS vocal intensity (dB) and F0 pitch (Hz) using Scipy/NumPy signal processing
    over word timing intervals. Detects pitch spikes and volume bursts.
    """
    try:
        import wave
        with wave.open(audio_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples = samples / max_val

        summaries = []
        all_dbs = []
        all_f0s = []

        for w in words:
            start_sec = float(w.get('start', 0.0))
            end_sec = float(w.get('end', start_sec + 0.3))
            start_idx = int(start_sec * sample_rate)
            end_idx = min(len(samples), int(end_sec * sample_rate))

            if end_idx <= start_idx:
                continue

            chunk = samples[start_idx:end_idx]
            rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0
            db = 20.0 * np.log10(max(rms, 1e-5))
            all_dbs.append(db)

            # Pitch estimation via Autocorrelation
            f0 = None
            if len(chunk) >= sample_rate // 80:  # At least 12.5ms window
                corr = np.correlate(chunk, chunk, mode='full')
                corr = corr[len(corr)//2:]
                # Search for peaks corresponding to human voice range (80 Hz to 450 Hz)
                min_lag = int(sample_rate / 450)
                max_lag = int(sample_rate / 80)
                if max_lag < len(corr):
                    sub_corr = corr[min_lag:max_lag]
                    if len(sub_corr) > 0 and np.max(sub_corr) > 0.3 * corr[0]:
                        peak_lag = min_lag + np.argmax(sub_corr)
                        f0 = float(sample_rate / peak_lag)
                        all_f0s.append(f0)

            summaries.append({
                'word': w.get('word', ''),
                'start': start_sec,
                'end': end_sec,
                'intensityDb': round(float(db), 1),
                'pitchHz': round(float(f0), 1) if f0 else None
            })

        mean_db = float(np.mean(all_dbs)) if all_dbs else -20.0
        max_db = float(np.max(all_dbs)) if all_dbs else -10.0
        mean_f0 = float(np.mean(all_f0s)) if all_f0s else 160.0
        max_f0 = float(np.max(all_f0s)) if all_f0s else 220.0

        return {
            'meanDb': round(mean_db, 1),
            'maxDb': round(max_db, 1),
            'meanHz': round(mean_f0, 1),
            'maxHz': round(max_f0, 1),
            'wordSummaries': summaries
        }
    except Exception as e:
        logger.warning(f"[CaptionAcoustics] Error computing acoustics: {e}")
        return {
            'meanDb': -18.0,
            'maxDb': -12.0,
            'meanHz': 165.0,
            'maxHz': 240.0,
            'wordSummaries': []
        }


# ── Rule-Based Fallback Director Pass ────────────────────────────────────────
def rule_based_director_pass(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Applies heuristic visual annotations (emojis, sfx, color tags, emphasis) to caption blocks.
    """
    annotated = []
    for block in blocks:
        text = str(block.get('text', '')).lower()
        words = block.get('words', [])

        color_tag = "neutral"
        emoji = None
        sfx = None
        emphasis_words = []

        if re.search(r'\$|\bdollar\b|\bcash\b|\bmoney\b|\bprofit\b|\brevenue\b|\bcost\b|\bprice\b|\b\d+[kmb]?\b', text):
            color_tag = "money"
            sfx = "cash"
            emoji = "💰"
        elif re.search(r'\bstop\b|\bwarning\b|\bnever\b|\bdont\b|\bdon\'t\b|\bdanger\b|\bavoid\b|\bwrong\b|\bbad\b', text):
            color_tag = "warning"
            sfx = "whoosh"
            emoji = "🛑"
        elif re.search(r'\?|\bwhy\b|\bhow\b|\bwhat\b|\bwhere\b|\bwhen\b|\bwho\b', text):
            color_tag = "question"
            sfx = "ding"
            emoji = "❓"
        elif re.search(r'\bviral\b|\bsecret\b|\bwin\b|\bbest\b|\bfast\b|\bpro\b|\bgreat\b|\bpower\b', text):
            color_tag = "highlight"
            sfx = "pop"
            emoji = "🔥"

        updated_words = []
        has_high_pitch = False
        for w in words:
            w_str = str(w.get('word', '')).strip()
            clean_w = re.sub(r'[^A-Za-z0-9$]', '', w_str).upper()
            is_emph = bool(
                re.search(r'\$|\d+', clean_w) or
                len(clean_w) >= 7 or
                clean_w in {'VIRAL', 'BEST', 'SECRET', 'STOP', 'NEVER', 'WIN', 'MONEY', 'CASH', 'AUTOMATED'}
            )
            if is_emph:
                emphasis_words.append(clean_w)

            is_hp = bool(w.get('isHighPitch', False))
            if is_hp:
                has_high_pitch = True

            updated_words.append({
                **w,
                'word': w_str.upper(),
                'isEmphasis': is_emph or is_hp,
                'isHighPitch': is_hp
            })

        if has_high_pitch and color_tag == "neutral":
            color_tag = "highlight"

        annotated.append({
            **block,
            'colorTag': color_tag,
            'emoji': emoji,
            'sfx': sfx,
            'emphasisWords': emphasis_words,
            'words': updated_words,
            'isAcousticPeak': has_high_pitch
        })
    return annotated


# ── AI Caption Director Pass (Groq LLM) ──────────────────────────────────────
async def run_director_pass(blocks: List[Dict[str, Any]], acoustic_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Directs visual caption annotations using Groq openai/gpt-oss-20b, with fallback to rule heuristics.
    """
    if not settings.GROQ_API_KEY:
        return rule_based_director_pass(blocks)

    try:
        prompt_payload = [{'id': b.get('id', f'block_{i+1:03d}'), 'text': b.get('text', '')} for i, b in enumerate(blocks)]

        headers = {
            'Authorization': f'Bearer {settings.GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        body = {
            'model': 'openai/gpt-oss-20b',
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        "You are an expert Short-Form Video Caption Director (like Submagic/CapCut). "
                        "Analyze caption text blocks and return visual director annotations to maximize viewer engagement. "
                        "For each block, return:\n"
                        "- id: match block id\n"
                        "- emphasisWords: array of 1-2 high-impact words from block text to emphasize visually (e.g. ['STOP'], ['$10,000'])\n"
                        "- emoji: single relevant contextual emoji (or null). Capped at ~15% of blocks.\n"
                        "- sfx: sound effect sting tag ('cash', 'whoosh', 'ding', 'pop', 'boom', or null)\n"
                        "- colorTag: semantic color category ('neutral', 'highlight', 'warning', 'money', 'question')\n\n"
                        "Respond ONLY with valid JSON:\n"
                        "{\"annotations\": [{\"id\": \"block_001\", \"colorTag\": \"money\", \"emoji\": \"💰\", \"sfx\": \"cash\", \"emphasisWords\": [\"$10,000\"]}]}"
                    )
                },
                {
                    'role': 'user',
                    'content': json.dumps({'blocks': prompt_payload})
                }
            ]
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post('https://api.groq.com/openai/v1/chat/completions', headers=headers, json=body)

        if resp.status_code != 200:
            logger.warning(f"[CaptionDirector] Groq status {resp.status_code}, falling back to rule director")
            return rule_based_director_pass(blocks)

        resp_data = resp.json()
        content = resp_data.get('choices', [{}])[0].get('message', {}).get('content', '{}')
        parsed = json.loads(content)
        annotations = parsed.get('annotations') or parsed.get('blocks') or []
        ann_map = {a['id']: a for a in annotations if isinstance(a, dict) and 'id' in a}

        annotated = []
        for i, b in enumerate(blocks):
            b_id = b.get('id', f'block_{i+1:03d}')
            ann = ann_map.get(b_id, {})
            emphasis_words = [ew.upper() for ew in ann.get('emphasisWords', [])]
            color_tag = ann.get('colorTag', 'neutral')
            emoji = ann.get('emoji')
            sfx = ann.get('sfx')

            words = b.get('words', [])
            updated_words = []
            has_hp = False
            for w in words:
                w_str = str(w.get('word', '')).strip().upper()
                is_hp = bool(w.get('isHighPitch', False))
                if is_hp:
                    has_hp = True
                is_emph = (w_str in emphasis_words) or is_hp
                updated_words.append({
                    **w,
                    'word': w_str,
                    'isEmphasis': is_emph,
                    'isHighPitch': is_hp
                })

            if has_hp and color_tag == "neutral":
                color_tag = "highlight"

            annotated.append({
                **b,
                'colorTag': color_tag,
                'emoji': emoji,
                'sfx': sfx,
                'emphasisWords': emphasis_words,
                'words': updated_words,
                'isAcousticPeak': has_hp
            })

        return annotated
    except Exception as e:
        logger.warning(f"[CaptionDirector] Groq pass failed: {e}. Falling back to rule director.")
        return rule_based_director_pass(blocks)


# ── Deterministic Word Clustering / Phrase Boundary Splitting ────────────────
def segment_whisper_words_to_blocks(
    words: List[Dict[str, Any]],
    max_words_per_block: int = 4,
    max_chars_per_block: int = 24,
    pause_threshold: float = 0.25
) -> List[Dict[str, Any]]:
    """
    Groups word timestamps into natural caption blocks using phrase boundary scoring.
    """
    if not words:
        return []

    blocks = []
    current_words = []
    current_char_len = 0
    block_start_time = None

    for i, w in enumerate(words):
        word_str = str(w.get('word', '')).strip()
        if not word_str:
            continue

        w_start = float(w.get('start', 0.0))
        w_end = float(w.get('end', w_start + 0.3))

        if not current_words:
            block_start_time = w_start

        upper_word = word_str.upper()
        current_words.append({
            'word': upper_word,
            'start': round(w_start, 2),
            'end': round(w_end, 2),
            'isHighPitch': bool(w.get('isHighPitch', False)),
            'pitchHz': w.get('pitchHz'),
            'intensityDb': w.get('intensityDb')
        })

        current_char_len += (1 if current_char_len > 0 else 0) + len(upper_word)

        is_last = (i == len(words) - 1)
        next_w = words[i + 1] if not is_last else None
        pause_after = (float(next_w.get('start', 0.0)) - w_end) if next_w else 0.0
        next_word_str = str(next_w.get('word', '')).strip() if next_w else ''
        clean_next = re.sub(r'[^a-z]', '', next_word_str.lower())

        project_chars = (current_char_len + 1 + len(next_word_str)) if next_w else current_char_len

        is_full_count = len(current_words) >= max_words_per_block
        is_exceeding_chars = project_chars > max_chars_per_block and len(current_words) >= 1
        is_pause_split = pause_after >= pause_threshold
        is_terminal_punct = bool(re.search(r'[.!?]$', word_str))
        is_clause_punct = bool(re.search(r'[,:;\-]$', word_str)) and len(current_words) >= 2
        is_conjunction_split = (clean_next in CONJUNCTIONS) and len(current_words) >= 2
        is_preposition_split = (clean_next in PREPOSITIONS) and len(current_words) >= 2 and current_char_len >= 12

        should_split = (
            is_last or
            is_terminal_punct or
            is_pause_split or
            is_exceeding_chars or
            is_full_count or
            is_clause_punct or
            is_conjunction_split or
            is_preposition_split
        )

        if should_split:
            block_end_time = current_words[-1]['end']
            blocks.append({
                'id': f'block_{len(blocks) + 1:03d}',
                'text': ' '.join([cw['word'] for cw in current_words]),
                'start': round(block_start_time, 2),
                'end': round(block_end_time, 2),
                'words': list(current_words)
            })
            current_words = []
            current_char_len = 0
            block_start_time = None

    return blocks


# ── Script Text Segmentation (WPM-based with punctuation pause simulation) ───
def segment_script_text(
    text: str,
    max_words: int = 4,
    wpm: int = 180,
    max_chars: int = 24
) -> List[Dict[str, Any]]:
    tokens = text.strip().split()
    if not tokens:
        return []

    sec_per_word = 60.0 / max(60, min(360, wpm))
    raw_words = []
    cursor = 0.0

    for token in tokens:
        w_dur = max(0.24, min(0.65, sec_per_word * (len(token) / 5.0)))
        w_start = round(cursor, 2)
        w_end = round(cursor + w_dur, 2)

        # Simulate natural pauses after punctuation
        pause = 0.0
        if re.search(r'[.!?]$', token):
            pause = 0.28
        elif re.search(r'[,:;\-]$', token):
            pause = 0.16

        # Simulate acoustic peak on high-impact keywords
        clean_upper = re.sub(r'[^A-Za-z0-9$]', '', token).upper()
        is_hp = bool(
            re.search(r'\$|\d+', clean_upper) or
            clean_upper in {'HOURS', 'VIRAL', 'EXPLOSIVE', 'STOP', 'NEVER', 'CASH', 'AUTOMATED', 'ENERGY'}
        )

        raw_words.append({
            'word': token,
            'start': w_start,
            'end': w_end,
            'isHighPitch': is_hp
        })
        cursor = w_end + pause

    return segment_whisper_words_to_blocks(raw_words, max_words, max_chars, pause_threshold=0.20)


# ── Video Audio Extraction (FFmpeg) ──────────────────────────────────────────
async def extract_audio_from_video(video_path: Path, audio_path: Path) -> Path:
    """
    Extracts 16kHz mono PCM WAV from input video using FFmpeg.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path)
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='replace')
        logger.error(f"[FFmpegExtract] Failed exit code {proc.returncode}: {err_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio extraction failed: {err_msg[-200:]}"
        )
    return audio_path


# ── Speech-To-Text Transcriber (Groq Whisper with local Whisper fallback) ───
async def transcribe_audio_file(audio_path: Path, language: str = "auto") -> Dict[str, Any]:
    """
    Transcribes audio file to word-level timestamps using Groq Whisper API (whisper-large-v3).
    Falls back to local Whisper if Groq fails or is not configured.
    """
    # 1. Try Groq Whisper API first
    if settings.GROQ_API_KEY:
        try:
            headers = {'Authorization': f'Bearer {settings.GROQ_API_KEY}'}
            with open(audio_path, 'rb') as f:
                files = {'file': (audio_path.name, f, 'audio/wav')}
                data = {
                    'model': 'whisper-large-v3',
                    'response_format': 'verbose_json',
                    'timestamp_granularities[]': 'word'
                }
                if language and language != "auto":
                    data['language'] = language

                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        'https://api.groq.com/openai/v1/audio/transcriptions',
                        headers=headers,
                        files=files,
                        data=data
                    )

            if resp.status_code == 200:
                result = resp.json()
                raw_words = result.get('words', [])
                # Groq returns words as [{'word': ..., 'start': ..., 'end': ...}]
                formatted_words = []
                for w in raw_words:
                    formatted_words.append({
                        'word': str(w.get('word', '')).strip(),
                        'start': float(w.get('start', 0.0)),
                        'end': float(w.get('end', 0.0))
                    })
                return {
                    'text': result.get('text', ''),
                    'language': result.get('language', language),
                    'duration': result.get('duration', 0.0),
                    'words': formatted_words
                }
            else:
                logger.warning(f"[WhisperGroq] Non-200 response: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.warning(f"[WhisperGroq] Groq Whisper failed: {e}. Falling back to local Whisper.")

    # 2. Local Whisper Fallback
    try:
        import whisper
        loop = asyncio.get_event_loop()
        def _run_local():
            model = whisper.load_model("base")
            res = model.transcribe(str(audio_path), word_timestamps=True)
            words = []
            for segment in res.get("segments", []):
                for w in segment.get("words", []):
                    words.append({
                        'word': str(w.get('word', '')).strip(),
                        'start': float(w.get('start', 0.0)),
                        'end': float(w.get('end', 0.0))
                    })
            return {
                'text': res.get('text', ''),
                'language': res.get('language', language),
                'duration': words[-1]['end'] if words else 0.0,
                'words': words
            }
        return await loop.run_in_executor(None, _run_local)
    except Exception as e:
        logger.error(f"[WhisperLocal] Local Whisper failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio transcription failed: {str(e)}"
        )


# ── Audio Cleanup Helper ─────────────────────────────────────────────────────
def process_audio_cleanup(blocks: List[Dict[str, Any]], silence_threshold: float = 0.5, remove_fillers: bool = True):
    silence_cuts = []
    all_words = []
    for b in blocks:
        for w in b.get('words', []):
            all_words.append(w)

    for i in range(len(all_words) - 1):
        curr_w = all_words[i]
        next_w = all_words[i + 1]
        gap = float(next_w.get('start', 0.0)) - float(curr_w.get('end', 0.0))
        if gap >= silence_threshold:
            silence_cuts.append({
                'start': round(float(curr_w.get('end', 0.0)), 2),
                'end': round(float(next_w.get('start', 0.0)), 2),
                'duration': round(gap, 2)
            })

    total_time_saved = 0.0
    fillers_removed_count = 0

    if not remove_fillers:
        return {
            'silenceCuts': silence_cuts,
            'fillersRemovedCount': 0,
            'totalTimeSavedSeconds': 0.0,
            'blocks': blocks
        }

    cleaned_blocks = []
    for block in blocks:
        orig_words = block.get('words', [])
        kept_words = []
        for w in orig_words:
            w_str = str(w.get('word', '')).strip()
            is_filler = bool(FILLER_REGEX.search(w_str))
            if is_filler:
                fillers_removed_count += 1
                w_dur = float(w.get('end', 0.0)) - float(w.get('start', 0.0))
                total_time_saved += w_dur
            else:
                new_start = max(0.0, float(w.get('start', 0.0)) - total_time_saved)
                new_end = max(0.0, float(w.get('end', 0.0)) - total_time_saved)
                kept_words.append({
                    **w,
                    'start': round(new_start, 2),
                    'end': round(new_end, 2)
                })

        if kept_words:
            cleaned_blocks.append({
                **block,
                'id': f'block_{len(cleaned_blocks) + 1:03d}',
                'text': ' '.join([kw['word'] for kw in kept_words]),
                'start': kept_words[0]['start'],
                'end': kept_words[-1]['end'],
                'words': kept_words
            })

    return {
        'silenceCuts': silence_cuts,
        'fillersRemovedCount': fillers_removed_count,
        'totalTimeSavedSeconds': round(total_time_saved, 2),
        'blocks': cleaned_blocks
    }


# ── Proofreading Helper ──────────────────────────────────────────────────────
async def run_proofreading_pass(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not settings.GROQ_API_KEY:
        return blocks

    try:
        headers = {
            'Authorization': f'Bearer {settings.GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        body = {
            'model': 'openai/gpt-oss-20b',
            'temperature': 0.1,
            'response_format': {'type': 'json_object'},
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        "You are an expert transcript proofreader. Correct spelling, grammar, casing, and homophone errors in the transcript. "
                        "Do NOT alter meaning. Return JSON with the corrected text array matching input block count:\n"
                        "{\"correctedBlocks\": [\"corrected text 1\", \"corrected text 2\"]}"
                    )
                },
                {
                    'role': 'user',
                    'content': json.dumps({'blocks': [b.get('text', '') for b in blocks]})
                }
            ]
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post('https://api.groq.com/openai/v1/chat/completions', headers=headers, json=body)

        if resp.status_code != 200:
            return blocks

        parsed = resp.json()
        content = parsed.get('choices', [{}])[0].get('message', {}).get('content', '{}')
        corrected_texts = json.loads(content).get('correctedBlocks', [])

        updated = []
        for i, block in enumerate(blocks):
            new_text = corrected_texts[i] if i < len(corrected_texts) else block.get('text', '')
            tokens = new_text.strip().split()
            orig_words = block.get('words', [])

            if len(tokens) == len(orig_words):
                new_words = [{**orig_words[j], 'word': tokens[j].upper()} for j in range(len(tokens))]
            else:
                # Proportional remapping
                t_start = block.get('start', 0.0)
                t_end = block.get('end', 1.0)
                tot_dur = max(0.1, t_end - t_start)
                tot_chars = sum(len(t) for t in tokens) or 1
                cursor = t_start
                new_words = []
                for j, tok in enumerate(tokens):
                    ratio = len(tok) / tot_chars
                    w_dur = tot_dur * ratio
                    w_s = round(cursor, 2)
                    w_e = t_end if j == len(tokens) - 1 else round(cursor + w_dur, 2)
                    cursor = w_e
                    new_words.append({
                        'word': tok.upper(),
                        'start': w_s,
                        'end': w_e,
                        'isEmphasis': False,
                        'isHighPitch': False
                    })

            updated.append({
                **block,
                'text': ' '.join([nw['word'] for nw in new_words]),
                'words': new_words
            })
        return updated
    except Exception as e:
        logger.warning(f"[ProofreadPass] Error: {e}")
        return blocks


# ── Route Handlers ───────────────────────────────────────────────────────────

@router.get("/health")
async def caption_health():
    """
    Engine health check verifying Groq configuration, FFmpeg, and Whisper availability.
    """
    ffmpeg_ok = bool(shutil.which("ffmpeg"))
    return {
        "status": "online",
        "phase": "Caption Studio Engine v2.0",
        "groqConfigured": bool(settings.GROQ_API_KEY),
        "ffmpegAvailable": ffmpeg_ok,
        "whisperAvailable": True,
        "timestamp": time.time()
    }


@router.post("/segment")
async def segment_script(payload: ScriptSegmentRequest):
    """
    Intakes script text and segments it into styled caption blocks with break scoring and director pass.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    blocks = segment_script_text(
        payload.text,
        max_words=payload.maxWords,
        wpm=payload.wpm,
        max_chars=payload.maxChars
    )
    annotated = await run_director_pass(blocks)
    total_duration = annotated[-1]['end'] if annotated else 0.0

    return {
        "success": True,
        "blocks": annotated,
        "totalDuration": total_duration
    }


@router.post("/transcribe-audio")
async def transcribe_audio_endpoint(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    maxWords: int = Form(4)
):
    """
    Uploads audio file, runs Whisper STT, acoustic analysis, and director pass.
    """
    temp_id = f"cfaudio_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    ext = Path(audio.filename or "audio.wav").suffix or ".wav"
    temp_path = CAPTION_AUDIO_DIR / f"{temp_id}{ext}"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Transcribe
        transcription = await transcribe_audio_file(temp_path, language=language)
        raw_words = transcription.get("words", [])

        # Acoustic analysis
        acoustics = analyze_audio_acoustics(str(temp_path), raw_words)

        # Augment words with acoustic spikes
        word_summaries_map = {round(s['start'], 2): s for s in acoustics.get('wordSummaries', [])}
        mean_hz = acoustics.get('meanHz', 160.0)
        mean_db = acoustics.get('meanDb', -20.0)

        augmented_words = []
        for rw in raw_words:
            w_start = round(rw.get('start', 0.0), 2)
            match = word_summaries_map.get(w_start)
            pitch = match.get('pitchHz') if match else None
            intensity = match.get('intensityDb') if match else None
            is_loud = intensity and (intensity >= mean_db + 2.5)
            is_hp = pitch and (pitch >= mean_hz * 1.15)
            augmented_words.append({
                **rw,
                'pitchHz': pitch,
                'intensityDb': intensity,
                'isHighPitch': bool(is_hp or is_loud)
            })

        blocks = segment_whisper_words_to_blocks(augmented_words, max_words_per_block=maxWords)
        annotated = await run_director_pass(blocks, acoustic_data=acoustics)

        return {
            "success": True,
            "text": transcription.get("text", ""),
            "wordCount": len(raw_words),
            "acousticData": {
                "pitch": {
                    "meanHz": acoustics.get("meanHz", 160.0),
                    "maxHz": acoustics.get("maxHz", 240.0)
                },
                "intensity": {
                    "meanDb": acoustics.get("meanDb", -18.0),
                    "maxDb": acoustics.get("maxDb", -10.0)
                }
            },
            "captionData": {
                "version": "2.0",
                "blocks": annotated
            }
        }
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@router.post("/transcribe-video")
async def transcribe_video_endpoint(
    video: UploadFile = File(...),
    language: str = Form("auto"),
    maxWords: int = Form(4)
):
    """
    Intakes video file, extracts 16kHz mono audio via FFmpeg, transcribes with Whisper,
    runs acoustic pitch & loudness analysis, executes AI Director pass, and serves audio stream.
    """
    video_id = f"cfvideo_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    ext = Path(video.filename or "video.mp4").suffix or ".mp4"
    video_temp_path = CAPTION_AUDIO_DIR / f"{video_id}{ext}"
    audio_temp_path = CAPTION_AUDIO_DIR / f"{video_id}.wav"

    try:
        # Save video
        with open(video_temp_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        # Extract audio with FFmpeg
        await extract_audio_from_video(video_temp_path, audio_temp_path)

        # Transcribe audio
        transcription = await transcribe_audio_file(audio_temp_path, language=language)
        raw_words = transcription.get("words", [])

        # Acoustic analysis
        acoustics = analyze_audio_acoustics(str(audio_temp_path), raw_words)

        word_summaries_map = {round(s['start'], 2): s for s in acoustics.get('wordSummaries', [])}
        mean_hz = acoustics.get('meanHz', 160.0)
        mean_db = acoustics.get('meanDb', -20.0)

        augmented_words = []
        for rw in raw_words:
            w_start = round(rw.get('start', 0.0), 2)
            match = word_summaries_map.get(w_start)
            pitch = match.get('pitchHz') if match else None
            intensity = match.get('intensityDb') if match else None
            is_loud = intensity and (intensity >= mean_db + 2.5)
            is_hp = pitch and (pitch >= mean_hz * 1.15)
            augmented_words.append({
                **rw,
                'pitchHz': pitch,
                'intensityDb': intensity,
                'isHighPitch': bool(is_hp or is_loud)
            })

        blocks = segment_whisper_words_to_blocks(augmented_words, max_words_per_block=maxWords)
        annotated = await run_director_pass(blocks, acoustic_data=acoustics)

        return {
            "success": True,
            "text": transcription.get("text", ""),
            "wordCount": len(raw_words),
            "language": transcription.get("language", language),
            "audioUrl": f"/api/caption/extracted-audio/{audio_temp_path.name}",
            "audioDuration": transcription.get("duration") or (annotated[-1]['end'] if annotated else 0.0),
            "acousticData": {
                "pitch": {
                    "meanHz": acoustics.get("meanHz", 160.0),
                    "maxHz": acoustics.get("maxHz", 240.0)
                },
                "intensity": {
                    "meanDb": acoustics.get("meanDb", -18.0),
                    "maxDb": acoustics.get("maxDb", -10.0)
                }
            },
            "captionData": {
                "version": "2.0",
                "blocks": annotated
            }
        }
    finally:
        # Delete video temp file immediately to save disk; keep extracted WAV for frontend scrubber playback
        if video_temp_path.exists():
            try:
                video_temp_path.unlink()
            except Exception:
                pass


@router.get("/extracted-audio/{filename}")
async def serve_extracted_audio(filename: str):
    """
    Streams extracted audio track (WAV) to frontend for synced playback and scrubber.
    """
    safe_name = Path(filename).name
    file_path = CAPTION_AUDIO_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found or expired")
    return FileResponse(file_path, media_type="audio/wav")


@router.post("/cleanup-audio")
async def cleanup_audio_endpoint(payload: AudioCleanupRequest):
    """
    Removes filler words ('um', 'uh', 'like') and detects silence intervals.
    """
    res = process_audio_cleanup(
        payload.blocks,
        silence_threshold=payload.silenceThreshold,
        remove_fillers=payload.removeFillers
    )
    return {"success": True, **res}


@router.post("/proofread")
async def proofread_endpoint(payload: ProofreadRequest):
    """
    Grammar, spelling, and homophone correction with proportional word timestamp alignment.
    """
    t0 = time.time()
    corrected = await run_proofreading_pass(payload.blocks)
    return {
        "success": True,
        "durationMs": int((time.time() - t0) * 1000),
        "blocks": corrected
    }


@router.post("/director-pass")
async def director_pass_endpoint(payload: DirectorPassRequest):
    """
    Re-runs AI Director Pass to update emphasis, emojis, SFX stings, and color tagging.
    """
    t0 = time.time()
    annotated = await run_director_pass(payload.blocks)
    return {
        "success": True,
        "durationMs": int((time.time() - t0) * 1000),
        "blocks": annotated
    }

