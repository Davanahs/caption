import os
from typing import Optional
from backend.services.providers.base import BaseVoiceProvider

class EdgeTTSVoiceProvider(BaseVoiceProvider):
    """
    TTS Provider using Microsoft Edge TTS.
    """
    async def generate_audio(self, text: str, voice_id: str, output_path: str) -> Optional[str]:
        try:
            import edge_tts  # type: ignore
            tts = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate="+5%",
                volume="+5%",
            )
            await tts.save(output_path)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"[EdgeTTS] Generated audio via {voice_id} -> {output_path}")
                return output_path
        except ImportError:
            print("[EdgeTTS] edge-tts not installed. Voice generation skipped.")
            return None
        except Exception as e:
            print(f"[EdgeTTS] TTS synthesis failed ({e}). Returning failure.")
            return None
