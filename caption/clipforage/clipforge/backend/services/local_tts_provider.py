import asyncio
import logging
import subprocess
import time
from pathlib import Path

from backend.models.hook import VoiceoverSegment, VoiceoverArtifact
from backend.services.voiceover_engine import BaseVoiceProvider

logger = logging.getLogger(__name__)

class LocalTTSVoiceProvider(BaseVoiceProvider):
    """
    Windows-native TTS provider using System.Speech.Synthesis via PowerShell.
    Used for local execution and real-media verification gates.
    """
    async def generate_voiceover(
        self,
        clip_id: str,
        segment: VoiceoverSegment,
        output_dir: Path
    ) -> VoiceoverArtifact:
        
        logger.info(f"Generating local TTS voiceover for clip {clip_id}: '{segment.source_text}'")
        
        timestamp = int(time.time() * 1000)
        output_file = output_dir / f"tts_{clip_id}_{timestamp}.wav"
        
        # Clean and escape text for powershell
        # Remove quotes that could break the string wrapping
        safe_text = segment.source_text.replace("'", "").replace('"', "")
        
        # Safe powershell script structure. 
        ps_command = f"""
Add-Type -AssemblyName System.Speech;
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
$synth.SetOutputToWaveFile('{str(output_file)}');
$synth.Speak('{safe_text}');
$synth.Dispose();
"""
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_command
        ]
        
        try:
            # Run in a separate thread to not block the asyncio loop
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                err_msg = stderr.decode().strip()
                logger.error(f"Local TTS PowerShell failed: {err_msg}")
                raise RuntimeError(f"TTS generation failed: {err_msg}")
                
            if not output_file.exists() or output_file.stat().st_size == 0:
                raise RuntimeError("TTS generation resulted in an empty or missing file.")
                
            # Use ffprobe to get duration (this assumes ffmpeg/ffprobe is installed, which it is for SFXMixer)
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", str(output_file)
            ]
            probe_proc = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            probe_out, _ = await probe_proc.communicate()
            try:
                duration = float(probe_out.decode().strip())
            except ValueError:
                duration = max(segment.end_time - segment.start_time, 1.0)
                
        except Exception as e:
            logger.error(f"Failed to generate Local TTS voiceover: {e}")
            if output_file.exists():
                output_file.unlink()
            raise
            
        artifact = VoiceoverArtifact(
            artifact_id=f"local_tts_{clip_id}_{timestamp}",
            storage_key=str(output_file),
            provider="local_system_speech",
            duration=duration,
            sample_rate=44100,  # System.Speech defaults typically to 22050 or 44100
            format="wav",
            metadata={"source_text": safe_text}
        )
        return artifact
