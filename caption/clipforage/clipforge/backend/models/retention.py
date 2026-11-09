from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from datetime import datetime

class RetentionPoint(BaseModel):
    timestamp: int = Field(..., description="The second index of the video")
    retention_score: float = Field(..., description="Heuristic retention risk score (0-100)")
    audio_score: float = Field(..., description="Heuristic audio energy/cadence score")
    motion_score: float = Field(..., description="Heuristic visual motion score")
    scene_activity_score: float = Field(..., description="Heuristic scene change activity score")
    risk_level: Literal['low', 'medium', 'high', 'critical'] = Field(..., description="Risk severity categorization")

class DropoffRisk(BaseModel):
    start_time: float
    end_time: float
    severity: Literal['low', 'medium', 'high', 'critical']
    primary_reason: Literal['low_audio_energy', 'silence', 'low_visual_motion', 'low_scene_activity', 'combined_low_engagement']
    contributing_reasons: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_intervention_types: List[str] = Field(default_factory=list, description="e.g. ['zoom_push', 'sfx_opportunity']")

class RetentionAnalysis(BaseModel):
    clip_id: str
    duration: float
    analysis_version: str
    points: List[RetentionPoint]
    risks: List[DropoffRisk]
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def overall_score(self) -> float:
        if not self.points:
            return 0.0
        return round(sum(p.retention_score for p in self.points) / len(self.points), 2)
