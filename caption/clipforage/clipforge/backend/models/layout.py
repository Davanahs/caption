from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator



class LayoutMode(str, Enum):
    CENTER_CROP = "center_crop"
    STATIC_WIDE = "static_wide"
    BLUR_BACKGROUND = "blur_background"
    MODERN_PADDING = "modern_padding"
    MULTI_SPLIT = "multi_split"
    STACKED_16_9 = "stacked_16_9"
    CREATIVE_TRANSFORM = "creative_transform"

class ScaleMode(str, Enum):
    CROP = "crop"
    CONTAIN = "contain"
    FILL = "fill"
    FIT = "fit" # Scales proportionally without padding


class AudioPolicy(str, Enum):
    PRIMARY_ONLY = "primary_only"
    MUTE_SECONDARY = "mute_secondary"
    MIX = "mix"


class BackgroundPolicy(str, Enum):
    BLUR = "blur"
    COLOR = "color"
    GRADIENT = "gradient"
    NONE = "none"


class ZoomIntervention(BaseModel):
    start_time: float = Field(ge=0.0, description="Start time in seconds")
    end_time: float = Field(ge=0.0, description="End time in seconds")
    zoom_factor: float = Field(ge=1.0, le=2.0, description="Zoom scale factor (1.0 to 2.0)")
    
    @model_validator(mode='after')
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self


class RegionModel(BaseModel):
    source_index: int = Field(default=0, ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    scale_mode: ScaleMode = Field(default=ScaleMode.CROP)
    z_order: int = Field(default=0)
    # Optional crop coordinates applied to the source before scaling to (w, h)
    # Tuple of (x, y, w, h)
    crop_coords: Optional[Tuple[int, int, int, int]] = None
    # Optional file path to an FFmpeg sendcmd script for dynamic cropping over time
    dynamic_crop_file: Optional[str] = None
    # Temporal zoom interventions for this region
    zoom_interventions: List[ZoomIntervention] = Field(default_factory=list)
    # Temporal rendering fields for B-roll or dynamic elements
    start_time: Optional[float] = Field(default=None, description="Start time in seconds")
    end_time: Optional[float] = Field(default=None, description="End time in seconds")
    fade_duration: float = Field(default=0.0, ge=0.0, description="Fade in/out duration in seconds")
    
    # Bounded visual transformations
    hflip: bool = Field(default=False, description="Horizontal flip")
    rotation_angle: float = Field(default=0.0, description="Rotation angle in degrees")
    scale_factor: float = Field(default=1.0, ge=0.1, le=5.0, description="Static scale/zoom factor")
    
    @model_validator(mode='after')
    def validate_crop_coords(self):
        crop_coords = self.crop_coords
        if crop_coords is not None:
            cx, cy, cw, ch = crop_coords
            if cx < 0 or cy < 0 or cw <= 0 or ch <= 0:
                raise ValueError("crop_coords must have non-negative x,y and positive w,h")
        
        # Temporal validation
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be strictly greater than start_time")
            
            if self.fade_duration > 0:
                # Fade in and fade out must fit inside the interval
                if self.fade_duration * 2 > (self.end_time - self.start_time):
                    raise ValueError("fade_duration must fit inside the active interval (times two for fade in and fade out)")
        elif self.start_time is not None or self.end_time is not None:
            raise ValueError("Both start_time and end_time must be provided together")
        
        return self


class LayoutPlan(BaseModel):
    mode: LayoutMode = Field(default=LayoutMode.CENTER_CROP)
    canvas_width: int = Field(gt=0)
    canvas_height: int = Field(gt=0)
    regions: List[RegionModel] = Field(min_items=1)
    background_policy: BackgroundPolicy = Field(default=BackgroundPolicy.NONE)
    audio_policy: AudioPolicy = Field(default=AudioPolicy.PRIMARY_ONLY)
    
    @model_validator(mode='after')
    def validate_regions(self):
        if not self.regions:
            raise ValueError("LayoutPlan must have at least one region.")
        for r in self.regions:
            if r.w <= 0 or r.h <= 0:
                raise ValueError(f"Region has invalid dimensions: {r.w}x{r.h}")
        
        cw = self.canvas_width
        ch = self.canvas_height
        regions = self.regions
        
        if not cw or not ch:
            return self
            
        z_orders = set()
        for i, region in enumerate(regions):
            if region.x + region.w > cw or region.y + region.h > ch:
                raise ValueError(f"Region {i} out of bounds: x={region.x}, y={region.y}, w={region.w}, h={region.h} canvas={cw}x{ch}")
            if region.z_order in z_orders:
                # Basic overlap/z-order check: if z-order is not unique, there shouldn't be overlap, 
                # but for simplicity we mandate unique z_orders or explicitly separated regions.
                for j, other in enumerate(regions[:i]):
                    if other.z_order == region.z_order:
                        # check overlap
                        if not (region.x + region.w <= other.x or region.x >= other.x + other.w or
                                region.y + region.h <= other.y or region.y >= other.y + other.h):
                            raise ValueError(f"Region {i} overlaps with Region {j} at same z_order {region.z_order}")
            z_orders.add(region.z_order)
            
        return self


    @model_validator(mode='after')
    def validate_effect_stack(self):
        # Enforce single-effect render policy
        if self.mode == LayoutMode.CENTER_CROP:
            # Cannot combine center crop tracking with background blur (causes excessive compute and visual noise)
            if self.background_policy == BackgroundPolicy.BLUR:
                raise ValueError("Effect stacking forbidden: Cannot use BLUR background with CENTER_CROP mode.")
            # Zoom interventions are forbidden in center crop for this validation run
            for r in self.regions:
                if len(r.zoom_interventions) > 0:
                    raise ValueError("Effect stacking forbidden: Cannot use zoom interventions in CENTER_CROP mode.")
        elif self.mode == LayoutMode.BLUR_BACKGROUND:
            if self.background_policy != BackgroundPolicy.BLUR:
                raise ValueError("BLUR_BACKGROUND mode requires BackgroundPolicy.BLUR")
        return self
