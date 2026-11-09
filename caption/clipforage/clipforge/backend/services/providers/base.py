from abc import ABC, abstractmethod
from typing import Optional

class BaseVoiceProvider(ABC):
    """Base class for standard Text-To-Speech providers."""
    
    @abstractmethod
    async def generate_audio(self, text: str, voice_id: str, output_path: str) -> Optional[str]:
        """
        Generates audio for the given text and saves it to output_path.
        Returns the output_path if successful, else None.
        """
        pass

class BaseVoiceCloneProvider(BaseVoiceProvider):
    """Base class for Voice Cloning providers.
    These require explicit authorization state before generating."""
    
    @abstractmethod
    async def generate_cloned_audio(self, text: str, voice_id: str, output_path: str, authorization_granted: bool) -> Optional[str]:
        """
        Generates cloned audio. 
        Must raise an error or return None if authorization_granted is False.
        """
        pass
