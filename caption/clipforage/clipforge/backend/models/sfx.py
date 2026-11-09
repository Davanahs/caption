from pydantic import BaseModel, Field

class SFXPlacement(BaseModel):
    asset_id: str
    category: str  # For debugging/display
    start_time: float
    end_time: float
    gain: float = Field(default=0.0)  # dB (e.g. -10 for background, 0 for normal)
    fade_in: float = Field(default=0.0)
    fade_out: float = Field(default=0.0)
    ducking_enabled: bool = False
    ducking_target_gain: float = Field(default=-15.0)  # Duck primary audio to -15dB
    confidence: float = Field(default=1.0)
    reason: str = Field(default="")

class SFXPlan(BaseModel):
    clip_id: str
    placements: list[SFXPlacement]
    pack_id: str | None = None
    planner_version: str = "v1"
