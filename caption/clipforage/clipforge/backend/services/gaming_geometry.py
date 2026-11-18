"""
backend/services/gaming_geometry.py

Authoritative Unified Geometry Engine for ClipForge Dual-Region Gaming Layout (Milestone M1).
Provides normalized coordinate math [0.0, 1.0], strict boundary validation, even-pixel
quantization matching YUV420p video codecs, facecam presets, scale-to-fill gameplay framing,
preview-to-FFmpeg parity calculations, and LayoutPlan integration.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.models.layout import (
    AudioPolicy,
    BackgroundPolicy,
    LayoutMode,
    LayoutPlan,
    RegionModel,
    ScaleMode,
)


class FacecamPreset(str, Enum):
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_RIGHT = "bottom-right"


class NormalizedRect(dict):
    """
    Normalized unit rectangle [0.0, 1.0] representing coordinates relative to frame.
    Inherits from dict for JSON/dict parity and exposes attribute properties.
    """

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        **kwargs: Any
    ):
        super().__init__(
            x=round(float(x), 6),
            y=round(float(y), 6),
            width=round(float(width), 6),
            height=round(float(height), 6),
            **kwargs
        )

    @property
    def x(self) -> float:
        return self["x"]

    @property
    def y(self) -> float:
        return self["y"]

    @property
    def width(self) -> float:
        return self["width"]

    @property
    def height(self) -> float:
        return self["height"]

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


class PixelRect(dict):
    """
    Pixel rectangle with integer boundaries aligned to even dimensions for video codecs.
    Inherits from dict for JSON/dict parity and exposes attribute properties.
    """

    def __init__(self, x: int, y: int, w: int, h: int, **kwargs: Any):
        super().__init__(
            x=int(x),
            y=int(y),
            w=int(w),
            h=int(h),
            **kwargs
        )

    @property
    def x(self) -> int:
        return self["x"]

    @property
    def y(self) -> int:
        return self["y"]

    @property
    def w(self) -> int:
        return self["w"]

    @property
    def h(self) -> int:
        return self["h"]

    @property
    def width(self) -> int:
        return self["w"]

    @property
    def height(self) -> int:
        return self["h"]

    def to_crop_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


# Semantic aliases per task specification
SourceCrop = PixelRect
CanvasOverlay = PixelRect


@dataclass
class GamingCanvasPlan:
    """
    Authoritative calculation result matching golden vectors and FFmpeg execution requirements.
    Supports attribute access and dict indexing.
    """
    gameplay_crop: PixelRect
    facecam_crop: PixelRect
    facecam_dest: PixelRect
    facecam_resolved_output_rect: NormalizedRect
    canvas_width: int
    canvas_height: int
    gameplay_scale_factor: float
    gameplay_scaled_w: int
    gameplay_scaled_h: int
    ffmpeg_crop_gameplay: str
    ffmpeg_crop_facecam: str
    ffmpeg_filtergraph: str
    is_valid: bool = True
    ffmpeg_gameplay_crop: str = ""
    ffmpeg_facecam_crop: str = ""
    ffmpeg_facecam_scale: str = ""
    ffmpeg_overlay: str = ""

    def __post_init__(self):
        if not self.ffmpeg_gameplay_crop:
            self.ffmpeg_gameplay_crop = self.ffmpeg_crop_gameplay
        if not self.ffmpeg_facecam_crop:
            self.ffmpeg_facecam_crop = self.ffmpeg_crop_facecam
        if not self.ffmpeg_facecam_scale:
            self.ffmpeg_facecam_scale = (
                f"scale={self.facecam_dest.w}:{self.facecam_dest.h}:"
                f"force_original_aspect_ratio=increase,crop={self.facecam_dest.w}:{self.facecam_dest.h}"
            )
        if not self.ffmpeg_overlay:
            self.ffmpeg_overlay = (
                f"overlay=x={self.facecam_dest.x}:y={self.facecam_dest.y}:"
                f"eof_action=pass:repeatlast=0"
            )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


# Semantic alias
GamingCropGeometry = GamingCanvasPlan

# Constants
DEFAULT_CANVAS_WIDTH = 1080
DEFAULT_CANVAS_HEIGHT = 1920
DEFAULT_FACECAM_WIDTH = 0.30
DEFAULT_FACECAM_HEIGHT = 0.22
DEFAULT_FACECAM_MARGIN_X = 0.05
DEFAULT_FACECAM_MARGIN_Y = 0.04
MIN_ROI_SIZE = 0.05


def validate_normalized_rect(
    rect: Union[NormalizedRect, Dict[str, Any], Any],
    field_name: str = "rect",
    min_size: float = MIN_ROI_SIZE,
    eps: float = 1e-4
) -> NormalizedRect:
    """
    Validates that a normalized rectangle lies strictly within [0.0, 1.0]
    with finite numbers, minimum dimensions >= min_size, and non-negative values.
    Raises ValueError with descriptive context matching golden vector expectations.
    """
    if not isinstance(rect, (dict, NormalizedRect)):
        raise ValueError(f"{field_name} must be a dict or NormalizedRect, got {type(rect).__name__}")

    raw_x = rect.get("x") if isinstance(rect, dict) else getattr(rect, "x", None)
    raw_y = rect.get("y") if isinstance(rect, dict) else getattr(rect, "y", None)
    raw_w = rect.get("width") if (isinstance(rect, dict) and rect.get("width") is not None) else (
        rect.get("w") if isinstance(rect, dict) else getattr(rect, "width", getattr(rect, "w", None))
    )
    raw_h = rect.get("height") if (isinstance(rect, dict) and rect.get("height") is not None) else (
        rect.get("h") if isinstance(rect, dict) else getattr(rect, "height", getattr(rect, "h", None))
    )

    for val, prop in [(raw_x, "x"), (raw_y, "y"), (raw_w, "width"), (raw_h, "height")]:
        if val is None:
            raise ValueError(f"non-finite coordinate in {field_name}.{prop}: None")
        if isinstance(val, str):
            if val in ("NaN", "nan", "Infinity", "inf", "-Infinity", "-inf"):
                raise ValueError(f"non-finite coordinate in {field_name}.{prop}: {val}")
            try:
                num = float(val)
                if not math.isfinite(num):
                    raise ValueError(f"non-finite coordinate in {field_name}.{prop}: {val}")
            except Exception:
                raise ValueError(f"non-finite coordinate in {field_name}.{prop}: {val}")
        elif not isinstance(val, (int, float)) or not math.isfinite(val):
            raise ValueError(f"non-finite coordinate in {field_name}.{prop}: {val}")

    x = float(raw_x)
    y = float(raw_y)
    width = float(raw_w)
    height = float(raw_h)

    if x < -eps or y < -eps:
        raise ValueError(f"negative coordinate in {field_name}: x={x}, y={y}")

    if width < (min_size - eps):
        raise ValueError(f"{field_name}.width must be >= {min_size}, got {width}")
    if height < (min_size - eps):
        raise ValueError(f"{field_name}.height must be >= {min_size}, got {height}")

    if x > (1.0 + eps) or y > (1.0 + eps):
        raise ValueError(f"coordinate out of bounds in {field_name}: x={x}, y={y} exceeds 1.0")

    if (x + width) > (1.0 + eps) or (y + height) > (1.0 + eps):
        raise ValueError(f"{field_name} out of bounds: sum exceeds 1.0 (x+w={x+width}, y+h={y+height})")

    clean_x = max(0.0, min(1.0 - min_size, x))
    clean_y = max(0.0, min(1.0 - min_size, y))
    clean_w = max(min_size, min(1.0 - clean_x, width))
    clean_h = max(min_size, min(1.0 - clean_y, height))

    return NormalizedRect(
        x=round(clean_x, 6),
        y=round(clean_y, 6),
        width=round(clean_w, 6),
        height=round(clean_h, 6)
    )


def to_even_pixel(val: float, dim: int) -> int:
    """
    Converts a normalized [0.0, 1.0] coordinate or offset to an even integer pixel value.
    Formula: floor((coord * dim) / 2) * 2
    """
    if not isinstance(val, (int, float)) or not math.isfinite(val):
        raise ValueError(f"Coordinate must be finite, got {val}")
    if not isinstance(dim, (int, float)) or not math.isfinite(dim):
        raise ValueError(f"Dimension must be finite, got {dim}")
    if val < -1e-4:
        raise ValueError(f"negative coordinate: {val} is less than 0")
    px = math.floor((max(0.0, float(val)) * dim) / 2.0) * 2
    return int(px)


def to_even_span(val: float, dim: int) -> int:
    """
    Converts a normalized dimension span to an even integer pixel value.
    Guarantees at least 2 pixels and even parity.
    Formula: max(2, floor((coord * dim) / 2) * 2)
    """
    if not isinstance(val, (int, float)) or not math.isfinite(val):
        raise ValueError(f"Dimension must be finite, got {val}")
    if not isinstance(dim, (int, float)) or not math.isfinite(dim):
        raise ValueError(f"Dimension must be finite, got {dim}")
    px = math.floor((max(0.0, float(val)) * dim) / 2.0) * 2
    return max(2, int(px))


def get_facecam_preset(
    preset: Union[str, FacecamPreset],
    canvas_w: int = DEFAULT_CANVAS_WIDTH,
    canvas_h: int = DEFAULT_CANVAS_HEIGHT,
    custom_w: float = DEFAULT_FACECAM_WIDTH,
    custom_h: float = DEFAULT_FACECAM_HEIGHT,
    margin_x: float = DEFAULT_FACECAM_MARGIN_X,
    margin_y: float = DEFAULT_FACECAM_MARGIN_Y
) -> NormalizedRect:
    """
    Computes normalized coordinates for standard facecam placement presets.
    """
    preset_str = preset.value if isinstance(preset, FacecamPreset) else str(preset).lower()

    if preset_str == "top-left":
        x = margin_x
        y = margin_y
    elif preset_str == "top-right":
        x = 1.0 - custom_w - margin_x
        y = margin_y
    elif preset_str == "bottom-left":
        x = margin_x
        y = 1.0 - custom_h - margin_y
    elif preset_str == "bottom-right":
        x = 1.0 - custom_w - margin_x
        y = 1.0 - custom_h - margin_y
    else:
        raise ValueError(
            f"Unknown facecam preset '{preset}'. Expected: 'top-left', 'top-right', 'bottom-left', 'bottom-right'"
        )

    return NormalizedRect(
        x=round(x, 4),
        y=round(y, 4),
        width=round(custom_w, 4),
        height=round(custom_h, 4)
    )


# Semantic alias
get_facecam_preset_rect = get_facecam_preset


def to_source_crop(
    rect: Union[NormalizedRect, Dict[str, Any]],
    source_w: int,
    source_h: int
) -> SourceCrop:
    """
    Converts a normalized ROI to even pixel source crop coordinates (cx, cy, cw, ch).
    Clamps bounds within even source dimensions.
    """
    if source_w <= 0 or source_h <= 0:
        raise ValueError(f"Source dimensions must be positive, got {source_w}x{source_h}")

    norm = validate_normalized_rect(rect, "source_crop")
    max_w = (source_w // 2) * 2
    max_h = (source_h // 2) * 2

    cx = to_even_pixel(norm.x, source_w)
    cy = to_even_pixel(norm.y, source_h)
    cw = to_even_span(norm.width, source_w)
    ch = to_even_span(norm.height, source_h)

    if max_w < 2:
        cx = 0
        cw = 0
    else:
        cw = min(cw, max_w)
        if cx + cw > max_w:
            cx = max(0, max_w - cw)

    if max_h < 2:
        cy = 0
        ch = 0
    else:
        ch = min(ch, max_h)
        if cy + ch > max_h:
            cy = max(0, max_h - ch)

    return PixelRect(x=cx, y=cy, w=cw, h=ch)


# Semantic alias
calculate_source_crop = to_source_crop


def to_canvas_overlay(
    rect: Union[NormalizedRect, Dict[str, Any]],
    canvas_w: int = DEFAULT_CANVAS_WIDTH,
    canvas_h: int = DEFAULT_CANVAS_HEIGHT
) -> CanvasOverlay:
    """
    Converts normalized facecam output coordinates to even pixel destination bounds on canvas.
    """
    if canvas_w <= 0 or canvas_h <= 0:
        raise ValueError(f"Canvas dimensions must be positive, got {canvas_w}x{canvas_h}")

    norm = validate_normalized_rect(rect, "canvas_overlay")
    max_w = (canvas_w // 2) * 2
    max_h = (canvas_h // 2) * 2

    dest_x = to_even_pixel(norm.x, canvas_w)
    dest_y = to_even_pixel(norm.y, canvas_h)
    dest_w = to_even_span(norm.width, canvas_w)
    dest_h = to_even_span(norm.height, canvas_h)

    if max_w < 2:
        dest_x = 0
        dest_w = 0
    else:
        dest_w = min(dest_w, max_w)
        if dest_x + dest_w > max_w:
            dest_x = max(0, max_w - dest_w)

    if max_h < 2:
        dest_y = 0
        dest_h = 0
    else:
        dest_h = min(dest_h, max_h)
        if dest_y + dest_h > max_h:
            dest_y = max(0, max_h - dest_h)

    return PixelRect(x=dest_x, y=dest_y, w=dest_w, h=dest_h)


# Semantic alias
calculate_canvas_dest = to_canvas_overlay


def to_gameplay_canvas_framing(
    crop_w: int,
    crop_h: int,
    canvas_w: int = DEFAULT_CANVAS_WIDTH,
    canvas_h: int = DEFAULT_CANVAS_HEIGHT
) -> Dict[str, Any]:
    """
    Computes scale-to-fill framing metrics for gameplay layer without stretching or distortion.
    """
    if crop_w <= 0 or crop_h <= 0:
        raise ValueError(f"Crop dimensions must be positive, got {crop_w}x{crop_h}")
    if canvas_w <= 0 or canvas_h <= 0:
        raise ValueError(f"Canvas dimensions must be positive, got {canvas_w}x{canvas_h}")

    scale_factor = max(canvas_w / float(crop_w), canvas_h / float(crop_h))
    scaled_w = int(round(crop_w * scale_factor))
    scaled_h = int(round(crop_h * scale_factor))
    offset_x = (scaled_w - canvas_w) // 2
    offset_y = (scaled_h - canvas_h) // 2

    return {
        "scale_factor": round(scale_factor, 6),
        "scaled_w": scaled_w,
        "scaled_h": scaled_h,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "ffmpeg_scale_filter": (
            f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,crop={canvas_w}:{canvas_h}"
        )
    }


# Semantic alias
calculate_gameplay_scale_fill = lambda crop, cw=1080, ch=1920: to_gameplay_canvas_framing(
    crop.w if hasattr(crop, "w") else crop["w"],
    crop.h if hasattr(crop, "h") else crop["h"],
    cw,
    ch
)


def calculate_render_offsets(
    container_width: float,
    container_height: float,
    video_width: float,
    video_height: float
) -> Dict[str, Any]:
    """
    Calculates letterbox/pillarbox padding for video fitted with object-fit: contain.
    """
    if container_width <= 0 or container_height <= 0 or video_width <= 0 or video_height <= 0:
        return {
            "render_left": 0,
            "render_top": 0,
            "render_width": int(max(0, container_width)),
            "render_height": int(max(0, container_height))
        }

    ar_video = video_width / video_height
    ar_container = container_width / container_height

    if ar_video > ar_container:
        render_w = int(container_width)
        render_h = int(round(container_width / ar_video))
        render_top = int(math.floor((container_height - render_h) / 2))
        render_left = 0
    else:
        render_h = int(container_height)
        render_w = int(round(container_height * ar_video))
        render_left = int(math.floor((container_width - render_w) / 2))
        render_top = 0

    return {
        "render_left": render_left,
        "render_top": render_top,
        "render_width": render_w,
        "render_height": render_h
    }


def display_to_normalized_letterbox(
    client_x: float,
    client_y: float,
    container: Dict[str, Any],
    src_w: int,
    src_h: int
) -> Dict[str, Any]:
    """
    Converts DOM mouse pointer coordinates to normalized coordinates, compensating
    for letterbox/pillarbox bars. Returns both render_rect and normalized_pointer.
    """
    c_left = float(container.get("left", 0))
    c_top = float(container.get("top", 0))
    c_w = float(container.get("width", 0))
    c_h = float(container.get("height", 0))

    offsets = calculate_render_offsets(c_w, c_h, src_w, src_h)
    render_left = offsets["render_left"]
    render_top = offsets["render_top"]
    render_w = offsets["render_width"]
    render_h = offsets["render_height"]

    if render_w <= 0 or render_h <= 0:
        return {
            "render_rect": {"x": 0, "y": 0, "width": int(c_w), "height": int(c_h)},
            "normalized_pointer": {"x": 0.0, "y": 0.0}
        }

    rel_x = client_x - (c_left + render_left)
    rel_y = client_y - (c_top + render_top)

    norm_x = max(0.0, min(1.0, rel_x / render_w))
    norm_y = max(0.0, min(1.0, rel_y / render_h))

    return {
        "render_rect": {
            "x": render_left,
            "y": render_top,
            "width": render_w,
            "height": render_h
        },
        "normalized_pointer": {
            "x": round(norm_x, 4),
            "y": round(norm_y, 4)
        }
    }


def validate_gaming_layout(input_data: Dict[str, Any]) -> bool:
    """
    Validates the complete gaming layout configuration dictionary.
    Raises ValueError on negative, non-finite, out-of-bounds coordinates, or sub-minimum sizes.
    """
    if not isinstance(input_data, dict):
        raise ValueError("Gaming layout input must be a dictionary")

    validate_normalized_rect(input_data.get("gameplay_roi"), "gameplay_roi")
    validate_normalized_rect(input_data.get("facecam_roi"), "facecam_roi")

    output_rect = input_data.get("facecam_output_rect")
    if output_rect is not None:
        validate_normalized_rect(output_rect, "facecam_output_rect")

    preset = input_data.get("facecam_placement")
    if preset and preset != "custom":
        get_facecam_preset(preset)

    return True


def calculate_gaming_coordinates(
    input_data: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> GamingCanvasPlan:
    """
    Authoritative computation function for Dual-Region Gaming Layout geometry.
    Accepts either an input dict or keyword arguments, validates all constraints,
    and returns a fully resolved GamingCanvasPlan matching golden vector expectations.
    """
    data = dict(input_data or {})
    data.update(kwargs)

    validate_gaming_layout(data)

    src_w = int(data["src_w"])
    src_h = int(data["src_h"])
    canvas_w = int(data.get("canvas_w", DEFAULT_CANVAS_WIDTH))
    canvas_h = int(data.get("canvas_h", DEFAULT_CANVAS_HEIGHT))

    gameplay_roi = validate_normalized_rect(data["gameplay_roi"], "gameplay_roi")
    facecam_roi = validate_normalized_rect(data["facecam_roi"], "facecam_roi")

    output_rect = data.get("facecam_output_rect")
    if output_rect is not None:
        resolved_facecam_output = validate_normalized_rect(output_rect, "facecam_output_rect")
    elif data.get("facecam_placement") and data.get("facecam_placement") != "custom":
        resolved_facecam_output = get_facecam_preset(data["facecam_placement"])
    else:
        resolved_facecam_output = get_facecam_preset("top-right")

    # 1. Gameplay Source Crop
    gameplay_crop = to_source_crop(gameplay_roi, src_w, src_h)

    # 2. Facecam Source Crop
    facecam_crop = to_source_crop(facecam_roi, src_w, src_h)

    # 3. Facecam Destination Overlay on Canvas
    facecam_dest = to_canvas_overlay(resolved_facecam_output, canvas_w, canvas_h)

    # 4. Gameplay Scale-to-Fill Metrics
    framing = to_gameplay_canvas_framing(gameplay_crop.w, gameplay_crop.h, canvas_w, canvas_h)

    # 5. FFmpeg Filters
    ffmpeg_crop_gameplay = f"crop={gameplay_crop.w}:{gameplay_crop.h}:{gameplay_crop.x}:{gameplay_crop.y}"
    ffmpeg_crop_facecam = f"crop={facecam_crop.w}:{facecam_crop.h}:{facecam_crop.x}:{facecam_crop.y}"
    ffmpeg_filtergraph = (
        f"[0:v]crop={gameplay_crop.w}:{gameplay_crop.h}:{gameplay_crop.x}:{gameplay_crop.y},"
        f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,crop={canvas_w}:{canvas_h}[v0];"
        f"[1:v]crop={facecam_crop.w}:{facecam_crop.h}:{facecam_crop.x}:{facecam_crop.y},"
        f"scale={facecam_dest.w}:{facecam_dest.h}:force_original_aspect_ratio=increase,crop={facecam_dest.w}:{facecam_dest.h}[v1];"
        f"[v0][v1]overlay=x={facecam_dest.x}:y={facecam_dest.y}:eof_action=pass:repeatlast=0,setsar=1[outv]"
    )

    return GamingCanvasPlan(
        gameplay_crop=gameplay_crop,
        facecam_crop=facecam_crop,
        facecam_dest=facecam_dest,
        facecam_resolved_output_rect=resolved_facecam_output,
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        gameplay_scale_factor=framing["scale_factor"],
        gameplay_scaled_w=framing["scaled_w"],
        gameplay_scaled_h=framing["scaled_h"],
        ffmpeg_crop_gameplay=ffmpeg_crop_gameplay,
        ffmpeg_crop_facecam=ffmpeg_crop_facecam,
        ffmpeg_filtergraph=ffmpeg_filtergraph,
        is_valid=True
    )


# Semantic alias
resolve_gaming_geometry = calculate_gaming_coordinates


def create_gaming_layout_plan(
    config: Union[Dict[str, Any], Any],
    src_w: int,
    src_h: int
) -> LayoutPlan:
    """
    Synthesizes a canonical, validated LayoutPlan for ClipForge Dual-Region Gaming Layout.
    Layer 1 (Gameplay): z_order=1, source_index=0, canvas-filling 1080x1920.
    Layer 2 (Facecam): z_order=2, source_index=1, overlay at facecam_dest.
    Maintains zero-caption invariant and native primary audio copying.
    """
    if isinstance(config, dict):
        cfg = dict(config)
        cfg["src_w"] = src_w
        cfg["src_h"] = src_h
    else:
        cfg = {
            "src_w": src_w,
            "src_h": src_h,
            "gameplay_roi": getattr(config, "gameplay_roi", None),
            "facecam_roi": getattr(config, "facecam_roi", None),
            "facecam_placement": getattr(config, "facecam_placement", "top-right"),
            "facecam_output_rect": getattr(config, "facecam_output_rect", None),
            "canvas_w": getattr(config, "canvas_width", DEFAULT_CANVAS_WIDTH),
            "canvas_h": getattr(config, "canvas_height", DEFAULT_CANVAS_HEIGHT),
        }

    plan_geom = calculate_gaming_coordinates(cfg)

    # If the user selected a wide custom gameplay area (e.g. full 16:9 screen where aspect > 0.65):
    # ScaleMode.CONTAIN fits the entire gameplay width into the 9:16 canvas centered vertically
    # preserving 100% of the game action without chopping off the screen!
    gp_aspect = plan_geom.gameplay_crop.w / max(1, plan_geom.gameplay_crop.h)
    gameplay_scale = ScaleMode.CONTAIN if gp_aspect > 0.65 else ScaleMode.CROP

    r_gameplay = RegionModel(
        source_index=0,
        x=0,
        y=0,
        w=plan_geom.canvas_width,
        h=plan_geom.canvas_height,
        scale_mode=gameplay_scale,
        z_order=1,
        crop_coords=plan_geom.gameplay_crop.to_crop_tuple()
    )

    r_facecam = RegionModel(
        source_index=1,
        x=plan_geom.facecam_dest.x,
        y=plan_geom.facecam_dest.y,
        w=plan_geom.facecam_dest.w,
        h=plan_geom.facecam_dest.h,
        scale_mode=ScaleMode.CROP,
        z_order=2,
        crop_coords=plan_geom.facecam_crop.to_crop_tuple()
    )

    mode = getattr(LayoutMode, "GAMING", LayoutMode.CENTER_CROP)

    return LayoutPlan(
        mode=mode,
        canvas_width=plan_geom.canvas_width,
        canvas_height=plan_geom.canvas_height,
        regions=[r_gameplay, r_facecam],
        background_policy=BackgroundPolicy.NONE,
        audio_policy=AudioPolicy.PRIMARY_ONLY
    )
