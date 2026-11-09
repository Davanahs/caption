import abc
import asyncio
import logging
from typing import Optional
from pathlib import Path

from backend.models.hook import VoiceoverSegment, VoiceoverArtifact

logger = logging.getLogger(__name__)

class BaseVoiceProvider(abc.ABC):
    @abc.abstractmethod
    async def generate_voiceover(
        self,
        clip_id: str,
        segment: VoiceoverSegment,
        output_dir: Path
    ) -> VoiceoverArtifact:
        pass


class MockVoiceProvider(BaseVoiceProvider):
    async def generate_voiceover(
        self,
        clip_id: str,
        segment: VoiceoverSegment,
        output_dir: Path
    ) -> VoiceoverArtifact:
        
        logger.info(f"Generating mock voiceover for clip {clip_id}: '{segment.source_text}'")
        
        # Simulate network latency
        await asyncio.sleep(0.5)
        
        # Create a dummy audio file for testing
        # We can use ffmpeg to generate a silent audio file or a simple beep
        output_file = output_dir / f"mock_vo_{segment.start_time}_{segment.end_time}.wav"
        
        import subprocess
        
        # Generate 1 second of silence, or better, tone, but silence is safe
        # Duration is segment.end_time - segment.start_time
        duration = max(segment.end_time - segment.start_time, 0.5)
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-c:a", "pcm_s16le",
            str(output_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate mock voiceover: {e}")
            raise
            
        artifact = VoiceoverArtifact(
            artifact_id=f"mock_vo_{clip_id}_{segment.start_time}",
            storage_key=str(output_file),
            provider="mock_voice",
            duration=duration,
            sample_rate=44100,
            format="wav",
            metadata={"source_text": segment.source_text}
        )
        return artifact

class VoiceoverEngine:
    def __init__(self):
        self._providers = {
            "mock": MockVoiceProvider(),
        }
        
        # Try to register local TTS if available
        try:
            from backend.services.local_tts_provider import LocalTTSVoiceProvider
            self._providers["local_tts"] = LocalTTSVoiceProvider()
        except ImportError:
            logger.warning("LocalTTSVoiceProvider could not be imported.")

    async def execute_plan(
        self,
        clip_id: str,
        segments: list[VoiceoverSegment],
        output_dir: Path,
        provider_name: str = "mock"
    ) -> list[VoiceoverArtifact]:
        
        provider = self._providers.get(provider_name)
        if not provider:
            logger.warning(f"Provider '{provider_name}' not found, falling back to mock")
            provider = self._providers.get("mock")
            
        artifacts = []
        for seg in segments:
            art = await provider.generate_voiceover(clip_id, seg, output_dir)
            artifacts.append(art)
        
        return artifacts

voiceover_engine = VoiceoverEngine()
