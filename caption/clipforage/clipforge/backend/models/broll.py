from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class OpportunityType(str, Enum):
    EXPLANATORY = "explanatory"
    CONTEXTUAL = "contextual"
    ILLUSTRATIVE = "illustrative"
    EMPHASIS = "emphasis"
    DIAGRAM = "diagram"
    TRANSITION = "transition"
    OBJECT = "object"
    PERSON = "person"
    ENVIRONMENT = "environment"
    CONCEPT = "concept"


class VisualOpportunity(BaseModel):
    id: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    concept: str
    opportunity_type: OpportunityType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    preferred_visual_type: str = Field(default="video") # "video" or "image"

    @model_validator(mode='after')
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self


class VisualAssetRef(BaseModel):
    asset_id: str
    asset_type: str
    artifact_id: str
    metadata: dict = Field(default_factory=dict)


class DisplayMode(str, Enum):
    FULL_CUTAWAY = "full_cutaway"
    PIP_TOP = "pip_top"
    PIP_BOTTOM = "pip_bottom"
    BACKGROUND = "background"


class BrollPlacement(BaseModel):
    asset_id: str
    opportunity_id: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    display_mode: DisplayMode
    # Region geometry mapping
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None
    scale_mode: str = "crop" # Using string instead of circular ref to layout.py ScaleMode, can map later
    fade_duration: float = Field(default=0.2, ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode='after')
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        
        if self.fade_duration > 0 and self.fade_duration * 2 > (self.end_time - self.start_time):
             raise ValueError("fade_duration must fit inside the active interval")
        return self


class BrollPlan(BaseModel):
    clip_id: str
    source_clip_version: str = "v1"
    planner_version: str = "1.0.0"
    analysis_version: Optional[str] = None
    placements: List[BrollPlacement] = Field(default_factory=list)
    plan_hash: Optional[str] = None
    generated_timestamp: Optional[float] = None
