from .base import BaseVoiceProvider, BaseVoiceCloneProvider
from .edge_tts import EdgeTTSVoiceProvider
from .elevenlabs import ElevenLabsVoiceCloneProvider

def get_voice_provider(provider_name: str):
    if provider_name.lower() == "elevenlabs":
        return ElevenLabsVoiceCloneProvider()
    elif provider_name.lower() == "edge_tts":
        return EdgeTTSVoiceProvider()
    else:
        # Default to Edge TTS
        return EdgeTTSVoiceProvider()
