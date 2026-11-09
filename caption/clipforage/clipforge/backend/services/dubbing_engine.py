import os
import subprocess
import asyncio
import tempfile
import uuid
from typing import Optional, List, Dict, Any
from backend.models.dubbing import DubbingRequest, DubbingResponse, DubbingSegmentResponse, DubbingSegmentInput
from backend.services.translator import translate_text
from backend.services.providers import get_voice_provider
from backend.services.providers.base import BaseVoiceCloneProvider

MAX_ATEMPO = 1.3

DEFAULT_VOICES = {
    "es": "es-ES-AlvaroNeural",
    "hi": "hi-IN-MadhurNeural",
    "de": "de-DE-ConradNeural",
    "ja": "ja-JP-KeitaNeural",
    "pt": "pt-BR-AntonioNeural",
    "fr": "fr-FR-HenriNeural",
    "en": "en-US-GuyNeural",
}

def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[TimingFit] Failed to get duration for {file_path}: {e}")
        return 0.0

def apply_atempo(input_path: str, output_path: str, atempo: float) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", f"atempo={atempo}",
        output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"[TimingFit] Failed to apply atempo: {e}")
        return False

async def process_dubbing_segment(
    segment: DubbingSegmentInput, 
    request: DubbingRequest, 
    provider: Any, 
    output_dir: str
) -> DubbingSegmentResponse:
    
    # 1. Translate
    translated_text = await translate_text(segment.source_text, request.target_language)
    
    # Resolve default voice if needed
    effective_voice_id = request.voice_id
    if not effective_voice_id or effective_voice_id.lower() == "default":
        effective_voice_id = DEFAULT_VOICES.get(request.target_language.lower(), "en-US-GuyNeural")
    
    # 2. Generate Audio
    audio_path = os.path.join(output_dir, f"segment_{segment.sequence}_{uuid.uuid4().hex[:8]}.wav")
    
    if request.is_voice_clone:
        if not isinstance(provider, BaseVoiceCloneProvider):
            return DubbingSegmentResponse(
                sequence=segment.sequence,
                source_text=segment.source_text,
                translated_text=translated_text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                status="failed",
                error_message="Provider does not support voice cloning"
            )
        audio_file = await provider.generate_cloned_audio(
            text=translated_text,
            voice_id=effective_voice_id,
            output_path=audio_path,
            authorization_granted=request.authorization_granted
        )
    else:
        audio_file = await provider.generate_audio(
            text=translated_text,
            voice_id=effective_voice_id,
            output_path=audio_path
        )
        
    if not audio_file:
        return DubbingSegmentResponse(
            sequence=segment.sequence,
            source_text=segment.source_text,
            translated_text=translated_text,
            start_time=segment.start_time,
            end_time=segment.end_time,
            status="failed",
            error_message="Audio generation failed or unauthorized"
        )
        
    # 3. Timing-fit
    generated_duration = get_audio_duration(audio_file)
    target_duration = segment.end_time - segment.start_time
    
    fit_speed = 1.0
    final_audio_path = audio_file
    
    if generated_duration > target_duration and target_duration > 0:
        required_speed = generated_duration / target_duration
        if required_speed > MAX_ATEMPO:
            return DubbingSegmentResponse(
                sequence=segment.sequence,
                source_text=segment.source_text,
                translated_text=translated_text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                status="failed",
                error_message=f"Required speed {required_speed:.2f}x exceeds maximum {MAX_ATEMPO}x"
            )
        
        fit_speed = required_speed
        fitted_audio_path = os.path.join(output_dir, f"segment_{segment.sequence}_fitted_{uuid.uuid4().hex[:8]}.wav")
        if apply_atempo(audio_file, fitted_audio_path, fit_speed):
            final_audio_path = fitted_audio_path
            generated_duration = target_duration # Update duration after fit
        else:
            return DubbingSegmentResponse(
                sequence=segment.sequence,
                source_text=segment.source_text,
                translated_text=translated_text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                status="failed",
                error_message="Atempo filter application failed"
            )
            
    return DubbingSegmentResponse(
        sequence=segment.sequence,
        source_text=segment.source_text,
        translated_text=translated_text,
        start_time=segment.start_time,
        end_time=segment.end_time,
        generated_audio_reference=final_audio_path,
        generated_audio_duration=generated_duration,
        fit_speed=fit_speed,
        status="completed"
    )

async def execute_dubbing_plan(request: DubbingRequest, segments: List[DubbingSegmentInput]) -> DubbingResponse:
    provider = get_voice_provider(request.voice_provider)
    
    temp_dir = tempfile.mkdtemp(prefix="dubbing_engine_")
    
    tasks = []
    for seg in segments:
        tasks.append(process_dubbing_segment(seg, request, provider, temp_dir))
        
    segment_responses = await asyncio.gather(*tasks)
    
    failed_segments = [s for s in segment_responses if s.status == "failed"]
    
    status = "completed"
    error_message = None
    if len(failed_segments) > 0:
        status = "failed"
        error_message = f"{len(failed_segments)} segments failed. First error: {failed_segments[0].error_message}"
    
    return DubbingResponse(
        plan_id=str(uuid.uuid4()),
        clip_id=request.clip_id,
        target_language=request.target_language,
        voice_provider=request.voice_provider,
        voice_id=request.voice_id,
        is_voice_clone=request.is_voice_clone,
        status=status,
        error_message=error_message,
        segments=segment_responses
    )
