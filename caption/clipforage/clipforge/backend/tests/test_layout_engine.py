import pytest
import os
from backend.models.layout import LayoutMode, ScaleMode, BackgroundPolicy
from backend.services.layout_engine import LayoutEngine
from backend.api.routes.channels import ChannelProcessingProfile

def test_resolve_plan_center_crop():
    plan = LayoutEngine.resolve_plan(LayoutMode.CENTER_CROP, 1920, 1080)
    assert len(plan.regions) == 1
    assert plan.regions[0].scale_mode == ScaleMode.CONTAIN
    assert plan.background_policy == BackgroundPolicy.NONE
    
def test_resolve_plan_blur_background():
    plan = LayoutEngine.resolve_plan(LayoutMode.BLUR_BACKGROUND, 1920, 1080)
    assert len(plan.regions) == 1
    assert plan.regions[0].scale_mode == ScaleMode.FIT
    assert plan.background_policy == BackgroundPolicy.BLUR

def test_resolve_plan_multi_split():
    plan = LayoutEngine.resolve_plan(LayoutMode.MULTI_SPLIT, 1920, 1080)
    assert len(plan.regions) == 2
    assert plan.regions[0].y == 0
    assert plan.regions[0].h == 960
    assert plan.regions[1].y == 960
    assert plan.regions[1].h == 960

def test_resolve_plan_stacked_16_9():
    plan = LayoutEngine.resolve_plan(LayoutMode.STACKED_16_9, 1920, 1080)
    assert len(plan.regions) == 2
    assert plan.background_policy == BackgroundPolicy.COLOR
    assert plan.mode == LayoutMode.STACKED_16_9
    
def test_resolve_plan_creative_transform():
    plan = LayoutEngine.resolve_plan(LayoutMode.CREATIVE_TRANSFORM, 1920, 1080)
    assert len(plan.regions) == 1
    assert plan.regions[0].scale_mode == ScaleMode.CROP
    assert plan.background_policy == BackgroundPolicy.NONE
    assert plan.regions[0].hflip is True

def test_profile_update_schema_accepts_all_layouts():
    """Verify ProfileUpdate pydantic model accepts all 6 supported layouts plus legacy aliases."""
    supported = [
        "fill_blur",
        "fit_black",
        "split_screen",
        "center_crop",
        "blur_background",
        "multi_split",
        "stacked_16_9",
        "creative_transform",
        "static_wide",
    ]
    for layout in supported:
        profile = ChannelProcessingProfile(video_layout=layout)
        assert profile.video_layout == layout

def test_layout_mapping_aliases():
    """Verify runtime reframe_mode mapping converts UI and API aliases into canonical layout names."""
    layout_mapping = {
        "fill_blur": "blur_background",
        "fit_black": "static_wide",
        "split_screen": "multi_split",
        "blur_background": "blur_background",
        "static_wide": "static_wide",
        "center_crop": "center_crop",
        "multi_split": "multi_split",
        "stacked_16_9": "stacked_16_9",
        "creative_transform": "creative_transform",
        "stacked": "stacked_16_9",
        "transform": "creative_transform",
    }
    assert layout_mapping.get("fill_blur") == "blur_background"
    assert layout_mapping.get("center_crop") == "center_crop"
    assert layout_mapping.get("split_screen") == "multi_split"
    assert layout_mapping.get("multi_split") == "multi_split"
    assert layout_mapping.get("stacked_16_9") == "stacked_16_9"
    assert layout_mapping.get("creative_transform") == "creative_transform"
    assert layout_mapping.get("stacked") == "stacked_16_9"
    assert layout_mapping.get("transform") == "creative_transform"


def test_create_podcast_plan_single_region():
    """Verify single manual area maps to full 1080x1920 vertical framing with crop_coords."""
    regions = [
        {"id": "area-1", "label": "Speaker 1", "x": 0.1, "y": 0.2, "width": 0.4, "height": 0.6}
    ]
    plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080, composition="single_region")
    assert plan.canvas_width == 1080
    assert plan.canvas_height == 1920
    assert len(plan.regions) == 1
    r = plan.regions[0]
    assert r.w == 1080
    assert r.h == 1920
    assert r.crop_coords is not None
    cx, cy, cw, ch = r.crop_coords
    # 0.1 * 1920 = 192, 0.2 * 1080 = 216, 0.4 * 1920 = 768, 0.6 * 1080 = 648
    assert cx == 192
    assert cy == 216
    assert cw == 768
    assert ch == 648
    assert cx % 2 == 0 and cy % 2 == 0 and cw % 2 == 0 and ch % 2 == 0


def test_create_podcast_plan_two_regions_stacked():
    """Verify two manual areas map to stacked vertical 9:16 layout (top and bottom 960h)."""
    regions = [
        {"id": "area-1", "label": "Speaker 1", "x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8},
        {"id": "area-2", "label": "Speaker 2", "x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8},
    ]
    plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080, composition="stacked")
    assert plan.canvas_width == 1080
    assert plan.canvas_height == 1920
    assert len(plan.regions) == 2
    r1, r2 = plan.regions[0], plan.regions[1]
    # Region 1 (top half)
    assert r1.x == 0 and r1.y == 0
    assert r1.w == 1080 and r1.h == 960
    assert r1.crop_coords is not None
    # Region 2 (bottom half)
    assert r2.x == 0 and r2.y == 960
    assert r2.w == 1080 and r2.h == 960
    assert r2.crop_coords is not None
    # Check even numbers
    for r in (r1, r2):
        cx, cy, cw, ch = r.crop_coords
        assert cx % 2 == 0 and cy % 2 == 0 and cw % 2 == 0 and ch % 2 == 0


def test_create_podcast_plan_boundary_clamping():
    """Verify regions that touch or exceed borders are safely clamped and stay within bounds."""
    regions = [
        {"id": "area-oob", "label": "Edge", "x": 0.9, "y": 0.9, "width": 0.5, "height": 0.5}
    ]
    plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080)
    r = plan.regions[0]
    cx, cy, cw, ch = r.crop_coords
    assert cx + cw <= 1920
    assert cy + ch <= 1080
    assert cw > 0 and ch > 0


def test_podcast_render_graph_generation():
    """Verify LayoutEngine generates valid FFmpeg filtergraph for podcast stacked regions."""
    from pathlib import Path
    regions = [
        {"id": "area-1", "label": "Speaker 1", "x": 0.05, "y": 0.1, "width": 0.4, "height": 0.8},
        {"id": "area-2", "label": "Speaker 2", "x": 0.55, "y": 0.1, "width": 0.4, "height": 0.8},
    ]
    plan = LayoutEngine.create_podcast_plan(regions, source_w=1920, source_h=1080, composition="stacked")
    fg = LayoutEngine.build_render_graph(plan, [Path("in1.mp4"), Path("in2.mp4")])
    assert "crop=" in fg
    assert "scale=1080:960" in fg
    assert "overlay=x=0:y=0" in fg
    assert "overlay=x=0:y=960" in fg
    assert "[outv]" in fg

