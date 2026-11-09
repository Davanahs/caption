from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class HookOpportunityType(str, Enum):
    OPENING_HOOK = "opening_hook"
    WEAK_OPENING = "weak_opening"
    CURIOSITY_GAP = "curiosity_gap"
    VALUE_STATEMENT = "value_statement"
    EMPHASIS = "emphasis"
    CONTEXT_REVEAL = "context_reveal"
    RETENTION_RISK = "retention_risk"
    TRANSITION_HOOK = "transition_hook"


class HookOpportunity(BaseModel):
    id: str
    clip_id: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    opportunity_type: HookOpportunityType
    source_text: Optional[str] = None
    hook_objective: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    priority: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self


class HookStyle(str, Enum):
    CURIOSITY = "curiosity"
    DIRECT_VALUE = "direct_value"
    QUESTION = "question"
    CONTRAST = "contrast"
    REVEAL = "reveal"
    URGENCY = "urgency"
    STATEMENT = "statement"


class DeliveryMode(str, Enum):
    VOICEOVER_ONLY = "voiceover_only"
    VISUAL_ONLY = "visual_only"
    COMBINED = "combined"


class HookConcept(BaseModel):
    opportunity_id: str
    hook_style: HookStyle
    hook_text: str = Field(max_length=500, description="Content metadata only. MUST NOT be rendered as a subtitle/caption.")
    target_duration: float = Field(ge=0.5, le=15.0)
    delivery_mode: DeliveryMode
    confidence: float = Field(ge=0.0, le=1.0)
    planner_version: str = "1.0.0"


class DuckingPolicy(str, Enum):
    NONE = "none"
    SUBTLE = "subtle"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class VoiceoverArtifact(BaseModel):
    artifact_id: str
    storage_key: str = ""
    provider: str
    duration: float = Field(ge=0.0)
    sample_rate: int = Field(default=48000)
    channels: int = Field(default=2)
    format: str = Field(default="wav")
    metadata: dict = Field(default_factory=dict)


class VoiceoverSegment(BaseModel):
    source_text: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    artifact: Optional[VoiceoverArtifact] = None
    voice_id: str
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    gain: float = Field(default=1.0, ge=0.0, le=5.0)
    fade_in: float = Field(default=0.1, ge=0.0)
    fade_out: float = Field(default=0.1, ge=0.0)
    ducking_policy: DuckingPolicy = Field(default=DuckingPolicy.MODERATE)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode='after')
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        if self.fade_in + self.fade_out > (self.end_time - self.start_time):
            raise ValueError("Fades cannot exceed segment duration")
        return self


class VoiceoverPlan(BaseModel):
    clip_id: str
    source_clip_version: str = "v1"
    planner_version: str = "1.0.0"
    analysis_version: Optional[str] = None
    provider: str = "mock"
    segments: List[VoiceoverSegment] = Field(default_factory=list)
    plan_hash: Optional[str] = None
    generated_timestamp: Optional[float] = None


from backend.models.layout import ZoomIntervention

class HookPlan(BaseModel):
    clip_id: str
    planner_version: str = "1.0.0"
    source_analysis_version: Optional[str] = None
    plan_hash: Optional[str] = None
    opportunities: List[HookOpportunity] = Field(default_factory=list)
    concepts: List[HookConcept] = Field(default_factory=list)
    voiceover_plan: Optional[VoiceoverPlan] = None
    visual_interventions: List[ZoomIntervention] = Field(default_factory=list)
