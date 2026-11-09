from pydantic import BaseModel, Field
from typing import List, Optional

class DubbingSegmentInput(BaseModel):
    sequence: int
    source_text: str
    start_time: float
    end_time: float

class DubbingRequest(BaseModel):
    job_id: Optional[str] = Field(default=None, description="Optional parent Job ID")
    clip_id: str
    target_language: str = Field(..., description="Target language code (e.g., 'es', 'hi')")
    voice_provider: str = Field(default="edge_tts", description="The name of the voice provider (e.g., 'edge_tts')")
    voice_id: str = Field(default="default", description="The specific voice ID/profile to use")
    is_voice_clone: bool = Field(default=False, description="Whether this voice is a clone")
    authorization_granted: bool = Field(default=False, description="Must be True if is_voice_clone is True")
    plan_version: str = Field(default="v1", description="Versioning for the dubbing engine")
    segments: Optional[List[DubbingSegmentInput]] = None # If missing, backend derives them from transcript

class DubbingSegmentResponse(BaseModel):
    sequence: int
    source_text: str
    translated_text: Optional[str] = None
    start_time: float
    end_time: float
    generated_audio_reference: Optional[str] = None
    generated_audio_duration: Optional[float] = None
    fit_speed: Optional[float] = None
    status: str
    error_message: Optional[str] = None

class DubbingResponse(BaseModel):
    plan_id: str
    clip_id: str
    target_language: str
    voice_provider: str
    voice_id: str
    is_voice_clone: bool
    status: str
    error_message: Optional[str] = None
    segments: List[DubbingSegmentResponse] = []
