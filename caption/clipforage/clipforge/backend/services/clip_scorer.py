"""
Clip Scorer — AI-powered viral moment detection using Cloud LLMs.
Analyzes transcript segments to score and select viral-worthy clips.
"""
import json
import re
import httpx
from pathlib import Path
from dataclasses import dataclass
from backend.core.config import settings
from backend.services.llm_router import route_and_generate


@dataclass
class ClipCandidate:
    start: float
    end: float
    duration: float
    text: str
    score: float
    title: str
    reason: str
    description: str = ""
    hashtags: str = ""
    pinned_comment: str = ""


def score_segment_heuristic(segment_text: str, duration: float) -> float:
    """Fast heuristic scoring before AI scoring."""
    score = 0.0
    text = segment_text.lower()

    # Engagement signals
    engagement_keywords = [
        "secret", "never", "always", "biggest", "worst", "best",
        "truth", "mistake", "actually", "literally", "insane",
        "crazy", "shocked", "amazing", "incredible", "unbelievable",
        "hate", "love", "fail", "win", "broke", "changed",
        "revealed", "exposed", "honest", "real", "raw"
    ]
    for kw in engagement_keywords:
        if kw in text:
            score += 2.0

    # Punctuation signals
    score += segment_text.count("!") * 1.5
    score += segment_text.count("?") * 1.2

    # Sentence completeness (not cut mid-thought)
    if segment_text.strip().endswith((".", "!", "?")):
        score += 3.0

    # Duration sweet spot (15-40s is ideal based on user requirements)
    if 20 <= duration <= 35:
        score += 5.0
    elif 15 <= duration <= 40:
        score += 2.0

    # Word density (engaging content)
    words = len(segment_text.split())
    if words > 40:
        score += 2.0

    return round(score, 2)


def build_candidate_windows(
    segments: list[dict],
    video_path: Path = None,
    min_dur: int = 15,
    max_dur: int = 60,
    max_filtered: int = 20,
    scenes: list = None
) -> list[dict]:
    """Slide a window over transcript segments and visual scene changes to build hybrid candidates."""
    if scenes is None:
        from backend.services.scene_detector import detect_scenes
        scenes = detect_scenes(video_path) if (video_path and video_path.exists()) else []

    candidates = []
    n = len(segments)

    # 1. Dialogue-based candidates (with visual scoring boost)
    for i in range(n):
        window_text = ""
        window_start = segments[i]["start"]
        window_end = segments[i]["end"]

        for j in range(i, n):
            window_text += " " + segments[j]["text"]
            window_end = segments[j]["end"]
            duration = window_end - window_start

            if min_dur <= duration <= max_dur:
                # Calculate base dialogue heuristic
                heuristic_score = score_segment_heuristic(window_text.strip(), duration)
                
                # Incorporate visual activity (scene cuts)
                num_cuts = sum(1 for s_start, s_end in scenes if window_start <= s_start <= window_end)
                heuristic_score += num_cuts * 1.5
                
                candidates.append({
                    "start": window_start,
                    "end": window_end,
                    "duration": duration,
                    "text": window_text.strip(),
                    "heuristic_score": heuristic_score,
                })

            if duration >= max_dur:
                break

    # 2. Visual-only candidates (for silent/music parts or videos without speech)
    # Check for gaps between dialogue segments or if there's no speech at all
    gaps = []
    if n == 0:
        if scenes:
            video_end = scenes[-1][1]
            gaps.append((0.0, video_end))
    else:
        if segments[0]["start"] >= min_dur:
            gaps.append((0.0, segments[0]["start"]))
        for i in range(n - 1):
            gap_start = segments[i]["end"]
            gap_end = segments[i + 1]["start"]
            if gap_end - gap_start >= min_dur:
                gaps.append((gap_start, gap_end))
        if scenes:
            video_end = scenes[-1][1]
            if video_end - segments[-1]["end"] >= min_dur:
                gaps.append((segments[-1]["end"], video_end))

    # For each gap, build candidate windows from scenes
    for gap_start, gap_end in gaps:
        gap_scenes = [s for s in scenes if gap_start <= s[0] <= gap_end]
        m = len(gap_scenes)
        for i in range(m):
            w_start = gap_scenes[i][0]
            w_end = gap_scenes[i][1]
            for j in range(i, m):
                w_end = gap_scenes[j][1]
                duration = w_end - w_start
                if min_dur <= duration <= max_dur:
                    num_cuts = j - i + 1
                    h_score = 5.0 + (num_cuts * 2.0)
                    candidates.append({
                        "start": w_start,
                        "end": w_end,
                        "duration": duration,
                        "text": f"[Visual Highlight: High activity sequence with {num_cuts} cuts]",
                        "heuristic_score": h_score,
                    })
                if duration > max_dur:
                    break

    # Sort by heuristic score and filter out highly overlapping candidates (max 30% overlap)
    candidates.sort(key=lambda x: x["heuristic_score"], reverse=True)
    filtered = []
    for c in candidates:
        is_overlapping = False
        for existing in filtered:
            overlap_start = max(c["start"], existing["start"])
            overlap_end = min(c["end"], existing["end"])
            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                min_duration = min(c["duration"], existing["duration"])
                if (overlap_duration / min_duration) > 0.3:
                    is_overlapping = True
                    break
        if not is_overlapping:
            filtered.append(c)
            if len(filtered) >= max_filtered:
                break
    return filtered


async def ai_score_candidates(
    candidates: list[dict],
    top_n: int = 5,
    min_dur: int = 15,
    max_dur: int = 60
) -> list[ClipCandidate]:
    """Use dynamic LLM routing to intelligently score and select the best viral clips.
    Zero heuristic fallback: AI scoring is strictly required. Failure must raise an error.
    """
    if not candidates:
        return []

    # Build prompt
    # Send at least 10 candidates to the model, but include more when the user asked for more clips
    slice_len = min(len(candidates), max(10, top_n))
    segments_text = "\n".join([
        f"[Segment {i+1}] ({c['start']:.1f}s - {c['end']:.1f}s, {c['duration']:.1f}s)\n{c['text'][:300]}"
        for i, c in enumerate(candidates[:slice_len])
    ])

    prompt = f"""You are an elite short-form video strategist and SEO copywriter. Analyze these video transcript segments and pick the {top_n} most viral-worthy clips for YouTube Shorts/TikTok.

CRITICAL RULES FOR METADATA GENERATION:
1. STRICT DURATION LIMIT: Only select segments that are between {min_dur} and {max_dur} seconds long. Do not select clips outside of this range.
2. IGNORE SPONSORSHIPS: Strictly avoid sponsorships, brand intros, outros, or call-to-actions from the original video. Only select the core, high-value, highly engaging dialogue or action.
3. SEARCH-DRIVEN SEO TITLES: Titles must be under 60 characters, starting with a strong emotional or curiosity hook, incorporating a primary search keyword naturally, and ending with 1 relevant emoji.
4. CONTEXTUAL KEYWORD DESCRIPTIONS: Write a 3-4 sentence description that naturally integrates 2-3 searchable high-volume keywords from the transcript segment. Do not stuff keywords. Include a clear engagement call-to-action (CTA) inviting viewer feedback.
5. HASHTAG STRATEGY: Generate exactly 4-5 niche-specific, content-aware hashtags based on the actual names of topics, people, entities, or concepts discussed in the segment. DO NOT use generic #viral, #fyp, #trending, or #explore.
6. ENGAGING PINNED COMMENT: Generate a reply-sparking question under 80 characters targeted at the clip's audience to drive the comment section.

SEGMENTS:
{segments_text}

For each selected segment, respond with ONLY a JSON array (no markdown, no explanation, no markdown backticks):
[
  {{
    "segment_index": 1,
    "viral_score": 8.5,
    "title": "<hook title under 60 chars>",
    "reason": "Why this segment will perform well",
    "description": "<natural search-optimized description with keywords>",
    "hashtags": "#seoTag1 #seoTag2 #seoTag3 #seoTag4",
    "pinned_comment": "<provocative/question comment>"
  }}
]

Select exactly {top_n} segments. Score from 1-10. Focus on emotional hooks, surprising facts, actionable advice, conflict, and humor."""

    # Route and generate via dynamic broker
    try:
        raw_text = await route_and_generate(prompt)
    except Exception as e:
        print(f"[AI Scorer] Provider routing failed: {e}")
        raise RuntimeError(f"AI candidate scoring failed: {e}. Heuristic scoring fallback is strictly forbidden.")

    if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
        print(f"[AI Scorer] Received invalid/empty raw_text: {raw_text}")
        raise RuntimeError("AI scoring failed: Cloud AI provider returned empty or invalid response. Heuristic scoring fallback is strictly forbidden.")

    try:
        # Parse JSON from response (handling reasoning models like DeepSeek-R1 / Gemini)
        clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
        # Strip markdown fences if any (```json ... ``` or ``` ... ```)
        clean_text = re.sub(r'^```[a-zA-Z]*\s*', '', clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r'\s*```\s*$', '', clean_text, flags=re.MULTILINE).strip()

        # Robustly find the FIRST valid JSON array in the text using json.JSONDecoder
        rankings = None
        decoder = json.JSONDecoder()
        search_text = clean_text
        pos = 0
        while pos < len(search_text):
            bracket_pos = search_text.find('[', pos)
            if bracket_pos == -1:
                break
            try:
                obj, end_pos = decoder.raw_decode(search_text, bracket_pos)
                if isinstance(obj, list):
                    rankings = obj
                    break
            except json.JSONDecodeError:
                pass
            pos = bracket_pos + 1

        if not rankings:
            raise ValueError(f"No JSON array found in model output: {clean_text[:200]}")

        clips = []
        for rank in rankings:
            idx_val = rank.get("segment_index")
            if idx_val is None:
                continue
            # Accept both int and float (some models return 1.0)
            try:
                idx = int(idx_val) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(candidates):
                c = candidates[idx]

                # Prevent selection of highly overlapping clips (max 30% overlap ratio)
                is_overlapping = False
                for existing in clips:
                    overlap_start = max(c["start"], existing.start)
                    overlap_end = min(c["end"], existing.end)
                    if overlap_start < overlap_end:
                        overlap_duration = overlap_end - overlap_start
                        min_duration = min(c["duration"], existing.duration)
                        if (overlap_duration / min_duration) > 0.3:
                            is_overlapping = True
                            break

                if not is_overlapping:
                    clips.append(ClipCandidate(
                        start=c["start"],
                        end=c["end"],
                        duration=c["duration"],
                        text=c["text"],
                        score=float(rank.get("viral_score", 5.0)),
                        title=rank.get("title", "Untitled Clip"),
                        reason=rank.get("reason", ""),
                        description=rank.get("description", ""),
                        hashtags=rank.get("hashtags", "#Shorts #viral"),
                        pinned_comment=rank.get("pinned_comment", "")
                    ))
                    if len(clips) >= top_n:
                        break

        if not clips:
            raise ValueError("No valid clip candidates could be formed from AI rankings.")

        return clips

    except Exception as e:
        print(f"[AI Scorer] Failed to parse LLM response: {e}")
        print(f"[AI Scorer] Raw LLM output was:\n{raw_text[:2000] if raw_text else 'None'}")
        raise RuntimeError(f"AI Scoring failed: {e}. Heuristic scoring fallback is strictly forbidden.")


def _heuristic_fallback(candidates: list[dict], top_n: int) -> list[ClipCandidate]:
    """Fallback logic moved to a helper for test mode reuse."""
    sorted_candidates = sorted(candidates, key=lambda x: x.get("heuristic_score", 0), reverse=True)
    fallback_clips: list[ClipCandidate] = []
    for cand in sorted_candidates:
        clip = ClipCandidate(
            start=cand["start"],
            end=cand["end"],
            duration=cand["duration"],
            text=cand["text"],
            score=cand.get("heuristic_score", 0),
            title="Untitled Clip",
            reason="Fallback heuristic selection",
            description="",
            hashtags="#Shorts",
            pinned_comment=""
        )
        overlap_ok = True
        for existing in fallback_clips:
            overlap_start = max(clip.start, existing.start)
            overlap_end = min(clip.end, existing.end)
            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                min_duration = min(clip.duration, existing.duration)
                if (overlap_duration / min_duration) > 0.3:
                    overlap_ok = False
                    break
        if overlap_ok:
            fallback_clips.append(clip)
            if len(fallback_clips) >= top_n:
                break
    return fallback_clips


async def find_best_clips(
    segments: list[dict],
    video_path: Path = None,
    top_n: int = 5,
    scenes: list = None,
    max_clip_duration: int = None
) -> list[ClipCandidate]:
    """Full pipeline: window → heuristic → AI rank."""
    # Determine video length from transcript segments or scene detector (best effort)
    video_length = 0.0
    if segments:
        try:
            video_length = float(segments[-1].get("end", 0.0))
        except Exception:
            video_length = 0.0
    else:
        from backend.services.scene_detector import detect_scenes
        scenes = detect_scenes(video_path) if (video_path and video_path.exists()) else []
        if scenes:
            video_length = float(scenes[-1][1])

    # Compute how many non-overlapping clips of minimum duration fit in the video
    min_dur = settings.MIN_CLIP_DURATION
    if video_length and video_length > 0:
        max_possible = max(1, int(video_length // min_dur))
    else:
        max_possible = settings.CLIPS_PER_VIDEO

    # Respect explicit request but cap by what can realistically fit in video
    effective_top_n = top_n
    if effective_top_n > max_possible:
        effective_top_n = max_possible

    # Expand candidate pool when user asks for more than default
    if effective_top_n > settings.CLIPS_PER_VIDEO:
        max_filtered = max(effective_top_n, 20)
    else:
        max_filtered = 20

    candidates = build_candidate_windows(
        segments,
        video_path=video_path,
        min_dur=min_dur,
        max_dur=max_clip_duration if (max_clip_duration and max_clip_duration > 0) else settings.MAX_CLIP_DURATION,
        max_filtered=max_filtered,
        scenes=scenes
    )
    if not candidates:
        return []
    return await ai_score_candidates(candidates, top_n=effective_top_n)
