"""
Phase 13: AI Kinetic Curiosity Hook Generator ⚡
Generates a 3-second animated intro teaser prepended to every Short.

Workflow:
  1. hook_generator(transcript) → 3 curiosity hook variants (LLM)
  2. render_kinetic_hook_video(hook_text) → 3-second MP4 via FFmpeg lavfi
  3. generate_hook_voiceover(hook_text) → WAV via EdgeTTS (free, offline)
  4. merge_hook_with_audio(hook_video, hook_audio) → hook_with_audio.mp4
  5. prepend_hook_to_clip(hook_clip, main_clip) → final output with seamless concat
"""
from __future__ import annotations

import os
import re
import sys
import json
import asyncio
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


# ── Cross-platform font resolver ─────────────────────────────────────────────

def _resolve_font() -> str:
    """
    Return the best available bold/heavy font path for the current OS.
    Probes Windows → Linux → macOS paths. Returns empty string if none found
    (FFmpeg will use its built-in default font, which is still usable).
    """
    candidates = [
        # Windows
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\Arial_Bold.ttf",
        r"C:\Windows\Fonts\impact.ttf",
        # Linux (Ubuntu/Debian via fonts-liberation)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Linux (via fontconfig fallback)
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        # macOS
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""  # FFmpeg will use its built-in default


_FONT_PATH = _resolve_font()


def _fontfile_arg(extra: str = "") -> str:
    """Return fontfile=... drawtext arg, or empty string if no font found."""
    if _FONT_PATH:
        # Escape backslashes for FFmpeg filter strings
        escaped = _FONT_PATH.replace("\\", "/")
        return f"fontfile={escaped}:{extra}" if extra else f"fontfile={escaped}"
    return extra



# ── Hook Data Model ─────────────────────────────────────────────────────────

@dataclass
class HookVariants:
    curiosity_question: str   # "Why 99% of people fail at X..."
    secret_reveal: str        # "The 1 secret nobody tells you about Y..."
    bold_statement: str       # "This changes everything about Z..."
    selected: str = ""        # Best hook selected by score

    def best(self) -> str:
        """Return selected hook, fallback to curiosity_question."""
        return self.selected or self.curiosity_question


# ── 1. LLM Curiosity Hook Extractor ─────────────────────────────────────────

_HOOK_PROMPT = """\
You are a viral short-form video strategist. Analyze this transcript excerpt and write 3 ultra-short \
curiosity hooks (max 9 words each) that would make someone STOP scrolling. 

Transcript:
{transcript}

Return ONLY valid JSON — no markdown, no extra text:
{{
  "curiosity_question": "...",
  "secret_reveal": "...",
  "bold_statement": "...",
  "selected": "..."
}}

Rules:
- Each hook ≤ 9 words
- curiosity_question starts with "Why" or "How"
- secret_reveal starts with "The" or "This"  
- bold_statement is a punchy provocative claim
- selected = whichever hook would stop the most scrolls
"""


async def generate_hooks(transcript: str) -> HookVariants:
    """
    Use the LLM router to generate 3 curiosity hook variants.
    Falls back to heuristic extraction if LLM is unavailable.
    """
    from backend.services.llm_router import route_and_generate

    excerpt = transcript[:1500].strip()
    prompt = _HOOK_PROMPT.format(transcript=excerpt)

    try:
        raw = await route_and_generate(prompt, max_tokens=200)
        # Strip markdown fences if present
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip().rstrip("```").strip()
        data = json.loads(raw)
        hooks = HookVariants(
            curiosity_question=data.get("curiosity_question", "")[:80],
            secret_reveal=data.get("secret_reveal", "")[:80],
            bold_statement=data.get("bold_statement", "")[:80],
            selected=data.get("selected", "")[:80],
        )
        return hooks
    except Exception as e:
        print(f"[HookGen] LLM hook generation failed ({e}), using heuristic fallback")
        return _heuristic_hooks(transcript)


def _heuristic_hooks(transcript: str) -> HookVariants:
    """Rule-based hook fallback when LLM is offline."""
    words = transcript.strip().split()
    topic = " ".join(words[:4]) if len(words) >= 4 else "this"
    cq = f"Why most people never learn {topic[:30]}..."
    sr = f"The secret behind {topic[:30]} revealed..."
    bs = f"This changes everything about {topic[:25]}..."
    return HookVariants(curiosity_question=cq, secret_reveal=sr,
                        bold_statement=bs, selected=cq)


# ── 2. Kinetic Hook Video Renderer (FFmpeg lavfi) ────────────────────────────

def _wrap_text(text: str, max_chars: int = 22) -> str:
    """Wrap hook text into at most 2 lines for the kinetic overlay."""
    lines = textwrap.wrap(text, width=max_chars)
    return "\\n".join(lines[:2])


def render_kinetic_hook_video(hook_text: str, output_path: str,
                               width: int = 1080, height: int = 1920,
                               duration: float = 4.0) -> str:
    """
    Render a 4-second ENERGETIC kinetic intro MP4 using FFmpeg lavfi filters.

    Visual design:
      - Deep dark gradient background (obsidian → deep violet) with animated radial pulse
      - Large bold white hook text with ZOOM-IN pop animation (scale 0.5→1.08→1.0 spring)
      - Double neon glow bars (purple + cyan) sliding in from sides
      - Strong white flash on frame 0 for scroll-stop attention grab
      - 3 staggered horizontal energy lines that sweep across the frame
      - 30 fps, yuv420p, H.264 output
    """
    wrapped = _wrap_text(hook_text, max_chars=18)  # tighter wrap for bigger text
    fps = 30

    # Build drawtext segment — zoom-in spring pop via fontsize modulated by time
    # alpha fade-in over 0.15s, then pulse glow via shadowx oscillation
    _font = (f"fontfile={_FONT_PATH.replace(chr(92), '/')}:" if _FONT_PATH else "")

    # Two overlapping drawtext: shadow (glow) + main white text
    _drawtext_glow = (
        f"[bgwflash]drawtext="
        f"text='{wrapped}':"
        f"fontcolor=0x9333ea:"
        f"fontsize='if(lt(t,0.25), 60+160*t/0.25, if(lt(t,0.45), 100+16*(1-(t-0.25)/0.2)*sin(3.14*(t-0.25)/0.2), 100))':"
        f"{_font}"
        f"x=(w-tw)/2:"
        f"y=(h-th)/2-80:"
        f"shadowcolor=0x7c3aed:shadowx=0:shadowy=0:"
        f"alpha='min(1,t/0.15)*0.55'[txtglow];"
    )
    _drawtext_main = (
        f"[txtglow]drawtext="
        f"text='{wrapped}':"
        f"fontcolor=white:"
        f"fontsize='if(lt(t,0.25), 60+160*t/0.25, if(lt(t,0.45), 100+16*(1-(t-0.25)/0.2)*sin(3.14*(t-0.25)/0.2), 100))':"
        f"{_font}"
        f"x=(w-tw)/2:"
        f"y=(h-th)/2-80:"
        f"shadowcolor=black:shadowx=3:shadowy=5:"
        f"alpha='min(1,t/0.12)'[txt];"
    )

    # ── Build lavfi filter graph ─────────────────────────────────────────
    filter_complex = (
        # 1. Deep dark animated background
        f"color=c=#06060f:s={width}x{height}:r={fps}:d={duration}[bg];"

        # 2. Animated radial glow pulse (expands outward from center)
        f"color=c=#1e0a3c:s={width}x{height}:r={fps}:d={duration}[bg2];"
        f"[bg][bg2]blend=all_expr='A*(1-hypot((X-W/2)/(W/2),(Y-H/2)/(H/2))*min(1,t*0.8))+B*(hypot((X-W/2)/(W/2),(Y-H/2)/(H/2))*min(1,t*0.8))'[bgblend];"

        # 3. Bright white flash on frame 0 (hard attention grab)
        f"color=c=white:s={width}x{height}:r={fps}:d={duration}[flash];"
        f"[flash]geq=r='255*max(0,1-t*18)':g='255*max(0,1-t*18)':b='255*max(0,1-t*18)'[flashfade];"
        f"[bgblend][flashfade]blend=all_expr='A*(min(1,N/3))+B*(max(0,1-N/3))'[bgwflash];"

        # 4. Glow layer + main text with zoom pop animation
        + _drawtext_glow
        + _drawtext_main +

        # 5. Purple neon bar slides in from LEFT
        f"color=c=#7c3aed:s={width}x6:r={fps}:d={duration}[bar1];"
        f"[bar1]geq=r=124:g=58:b=237:a='255*min(1,max(0,(t-0.2)*8))'[bar1a];"
        f"[txt][bar1a]overlay=x='W/2-w*min(1,max(0,(t-0.2)*4))':y=(H/2)+110:shortest=0[v1];"

        # 6. Cyan neon bar slides in from RIGHT
        f"color=c=#06b6d4:s={width}x6:r={fps}:d={duration}[bar2];"
        f"[bar2]geq=r=6:g=182:b=212:a='255*min(1,max(0,(t-0.3)*8))'[bar2a];"
        f"[v1][bar2a]overlay=x='W/2':y=(H/2)+122:shortest=0[v2];"

        # 7. Subtle horizontal sweep line (energy feel)
        f"color=c=white:s={width}x2:r={fps}:d={duration}[sweep];"
        f"[sweep]geq=r=255:g=255:b=255:a='255*max(0,sin(t*8)*0.3+0.1)*max(0,1-t*0.5)'[sweepa];"
        f"[v2][sweepa]overlay=x=0:y='H*0.72':shortest=0[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(duration),
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[HookGen] Rendering energetic kinetic intro → {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Minimal reliable fallback — solid color + text
        print(f"[HookGen] Complex filter failed, using simple fallback: {result.stderr[-400:]}")
        _render_simple_hook(hook_text, output_path, width, height, duration, fps)

    return output_path


def _render_simple_hook(hook_text: str, output_path: str,
                         width: int, height: int,
                         duration: float, fps: int) -> None:
    """Ultra-minimal fallback: gradient bg + white text, no compositing."""
    wrapped = _wrap_text(hook_text)
    vf_args = f"drawtext=text='{wrapped}':fontcolor=white:fontsize=80:x=(w-tw)/2:y=(h-th)/2"
    if _FONT_PATH:
        vf_args += ":fontfile=" + _FONT_PATH.replace("\\", "/")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=#0d0d1a:s={width}x{height}:r={fps}",
        "-vf", vf_args,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# ── 3. EdgeTTS AI Voiceover (free, offline-capable) ─────────────────────────

async def generate_hook_voiceover(hook_text: str, output_wav: str,
                                   voice: str = "en-US-GuyNeural") -> Optional[str]:
    """
    Generate a crisp, energetic TTS voiceover for the hook intro using EdgeTTS.
    Returns path to WAV file, or None if EdgeTTS is unavailable.
    """
    try:
        import edge_tts  # type: ignore

        tts = edge_tts.Communicate(
            text=hook_text,
            voice=voice,
            rate="+20%",    # faster = more energetic
            volume="+10%",
            pitch="+5Hz",
        )
        await tts.save(output_wav)
        print(f"[HookGen] Voiceover saved → {output_wav}")
        return output_wav
    except ImportError:
        print("[HookGen] edge-tts not installed — skipping voiceover (pip install edge-tts)")
        return None
    except Exception as e:
        print(f"[HookGen] EdgeTTS failed ({e}) — skipping voiceover")
        return None


# ── 4. Merge Hook Video + Voiceover Audio ────────────────────────────────────

def merge_hook_with_audio(hook_video: str, hook_audio: Optional[str],
                           output_path: str, hook_duration: float = 3.0) -> str:
    """
    Combine the silent kinetic hook video with the TTS audio track.
    If no audio provided, the hook video is used as-is (no audio track).
    """
    if hook_audio and os.path.exists(hook_audio) and os.path.getsize(hook_audio) > 0:
        cmd = [
            "ffmpeg", "-y",
            "-i", hook_video,
            "-i", hook_audio,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", str(hook_duration),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path
        ]
    else:
        # No TTS — add silent audio track so concat demuxer works cleanly
        cmd = [
            "ffmpeg", "-y",
            "-i", hook_video,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", str(hook_duration),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[HookGen] Audio merge failed: {result.stderr[-200:]}, using video-only")
        return hook_video
    return output_path


# ── 5. Prepend Hook to Main Clip (seamless concat) ───────────────────────────

def prepend_hook_to_clip(hook_clip: str, main_clip: str, output_path: str) -> str:
    """
    Concatenate the hook intro with the main clip using FFmpeg filter_complex concat.
    Uses filter_complex (NOT concat demuxer) to guarantee continuous audio across both
    segments — the demuxer silently drops audio when sample rates differ.

    Audio handling:
      - Hook clip: TTS voiceover (or silent pad) at 44100 Hz stereo
      - Main clip: original video audio at whatever rate it was encoded
      - filter_complex aresample normalizes both to 44100 Hz before concat
      - Result: seamless video + full audio throughout
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", hook_clip,
            "-i", main_clip,
            "-filter_complex",
            # Normalize both audio streams to same rate/channels, then concat v+a
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];"
            "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];"
            "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
            "[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]",
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"[HookGen] filter_complex concat failed: {result.stderr[-400:]}")
            # Fallback: try simple concat demuxer
            return _fallback_concat(hook_clip, main_clip, output_path)
        print(f"[HookGen] Hook prepended with full audio → {output_path}")
        return output_path
    except Exception as e:
        print(f"[HookGen] prepend_hook_to_clip error: {e}")
        return main_clip


def _fallback_concat(hook_clip: str, main_clip: str, output_path: str) -> str:
    """Fallback: use concat demuxer if filter_complex fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(hook_clip)}'\n")
        f.write(f"file '{os.path.abspath(main_clip)}'\n")
        concat_list = f.name
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"[HookGen] Fallback concat also failed — returning main clip")
            return main_clip
        return output_path
    finally:
        try:
            os.unlink(concat_list)
        except OSError:
            pass


# ── 6. High-Level Pipeline Entrypoint ────────────────────────────────────────

def apply_hook_intro(
    main_clip_path: str,
    transcript: str,
    output_path: str,
    voice: str = "en-US-GuyNeural",
    duration: float = 4.0,
) -> str:
    """
    Full Phase 13 pipeline (synchronous wrapper):
      transcript → hooks → kinetic video → voiceover → merged → prepended

    Returns:
        Path to the final clip with hook prepended.
        Falls back to main_clip_path if any stage fails completely.
    """
    tmp_dir = tempfile.mkdtemp(prefix="hookgen_")
    hook_video_raw   = os.path.join(tmp_dir, "hook_raw.mp4")
    hook_audio_wav   = os.path.join(tmp_dir, "hook_audio.wav")
    hook_video_final = os.path.join(tmp_dir, "hook_final.mp4")

    try:
        # 1. Generate hook text
        hooks = asyncio.run(generate_hooks(transcript))
        best_hook = hooks.best()
        print(f"[HookGen] Selected hook: «{best_hook}»")

        # 2. Render kinetic video
        render_kinetic_hook_video(best_hook, hook_video_raw,
                                   duration=duration)
        if not os.path.exists(hook_video_raw) or os.path.getsize(hook_video_raw) == 0:
            print("[HookGen] Kinetic render produced empty file — skipping hook")
            return main_clip_path

        # 3. Generate voiceover (async inside sync context)
        hook_audio = asyncio.run(
            generate_hook_voiceover(best_hook, hook_audio_wav, voice=voice)
        )

        # 4. Merge hook video + voiceover
        merged = merge_hook_with_audio(hook_video_raw, hook_audio,
                                        hook_video_final, hook_duration=duration)

        # 5. Prepend to main clip
        final = prepend_hook_to_clip(merged, main_clip_path, output_path)
        return final

    except Exception as e:
        print(f"[HookGen] Hook pipeline failed ({e}) — returning original clip")
        return main_clip_path
    finally:
        # Cleanup temp files
        for f in [hook_video_raw, hook_audio_wav, hook_video_final]:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
