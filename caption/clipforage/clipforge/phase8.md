# Phase 8: Split-Screen & Multi-Subject Vertical Video Layout Engine

## 🎯 Goal
Create multi-layout reframing support for podcast dual-speaker top/bottom split screens, gaming overlay split screens, custom branding watermarks, and blurred backdrop video frames with configurable blur radii and border strokes.

---

## 🛠️ Implementation Tasks

### 1. Dual-Speaker & Podcast Split-Screen Detector
- **Target Files:** `backend/services/reframe_engine.py` (NEW), `backend/services/clip_cutter.py`
- Build multi-speaker reframing layout generator:
  - Detects multi-speaker conversation via MediaPipe FaceMesh & lip movement variance.
  - Generates a 9:16 vertical stack canvas split into two 1:1 square windows (Speaker A on Top half, Speaker B on Bottom half).
  - Uses FFmpeg `hstack`/`vstack` filter graphs with customizable separator stroke borders (`stroke_width=4px`, `stroke_color=#FFE500`).

### 2. Gameplay & Dynamic Backdrop Blur Composite Template
- **Target File:** `backend/services/reframe_engine.py`
- Add dynamic backdrop blur template option (`mode="blur"`):
  - Scales 16:9 original widescreen video to fit vertical frame with background gaussian blur (`boxblur=luma_radius=30:luma_power=2`).
  - Overlay foreground cropped video with subtle drop-shadow effect to create high-end visual depth.

### 3. Custom Branding & Watermark Layer Engine
- **Target Files:** `backend/services/overlay_engine.py`, `backend/models/models.py`
- Add database support for channel branding profiles (`watermark_url`, `brand_color_primary`, `brand_logo_position`).
- Composite channel logos smoothly into top-right or top-left corners of vertical clips with configurable opacity.

---

## 🧪 Verification & Acceptance Criteria

1. **Backdrop Blur Visual Quality:** Verify 16:9 videos rendered in `blur` mode display a smooth, non-pixelated background blur behind the centered video.
2. **Podcast Split-Screen Test:** Process a two-person interview video. Verify output displays Speaker 1 on top half and Speaker 2 on bottom half with crisp separator borders.
3. **Branding Overlay Test:** Upload a PNG logo. Confirm logo is overlaid at configured position and opacity without interfering with video content.
