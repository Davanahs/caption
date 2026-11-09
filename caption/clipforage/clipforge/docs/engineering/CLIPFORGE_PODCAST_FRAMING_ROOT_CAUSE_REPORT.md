# ClipForge — Podcast Framing, Cropping & Live Output Preview Forensic Audit Report
**Phase A Deliverable: Root-Cause Forensic Audit**
**Date:** 2026-11-02  
**Branch:** `feature/layout`  
**Base Commit:** `68b9bcd7d3688c6bd8feb781d98df72d14351e97`  
**Engineer Roles:** Senior Video Processing Engineer, Computer Vision Engineer, Frontend/Backend Engineer, QA Architect  

---

## 1. Executive Summary

A comprehensive forensic audit of both ClipForge Podcast workflows (**Standard Podcast & Interview Manual Composition** and **Advanced Podcast Camera-Following / Visibility-Driven Composition**) was conducted across the backend layout engine, video reframing engine, Celery task pipelines, and frontend interactive components.

The investigation verified the mathematical and architectural root causes for all user-reported defects:
1. **Excessive Zoom & Participant Heads Cut Off (Standard Podcast):** Caused by `ScaleMode.CROP` in `LayoutEngine.create_podcast_plan()`, which triggers an FFmpeg `scale=...:force_original_aspect_ratio=increase,crop=w:h` cover-crop, double-cropping user-drawn bounding boxes and lopping off up to 330px from participant heads and chins.
2. **Missing Live 9:16 Output Preview:** The existing preview in `PodcastSelectionModal.tsx` was a decorative 64×96px thumbnail rendering generic color blocks with no coordinate projection, headroom indicators, or aspect ratio verification.
3. **Participant Duplication in Visibility-Driven Mode (Advanced Podcast):** Caused by uncertain/unassigned fallback defaulting to `SIDE_BY_SIDE` and default 0.5 HSV scores triggering double-panel splitting when only one participant is present.
4. **Participant Clipping in A+B Side-by-Side (Advanced Podcast):** Caused by hardcoded `side_crop_w = src_h * (540/1920) = 304px` in `advanced_podcast_engine.py`, creating an extreme 9:32 slit crop (only 15.8% of 1080p width) that shears off participants' shoulders and heads.
5. **Fixed Two-Person Center Cutoff (Advanced Podcast):** Caused by `calculate_two_person_fixed_boundary_crop()` centering a narrow 607px crop in the empty space between speakers when `required_span > crop_w`, cutting off both participants simultaneously.

---

## 2. Forensic Defect Matrix

| Defect | Subsystem / File & Line | Actual Root Cause | Mathematical / Render Evidence | Proposed Fix |
| :--- | :--- | :--- | :--- | :--- |
| **1. Heads cut off & excessive zoom** | `backend/services/layout_engine.py` (L209, L230, L251, L261) | `ScaleMode.CROP` forced `scale=...:force_original_aspect_ratio=increase,crop=w:h`. When user draws a portrait/square box (e.g. 400×600), scaling to cover 1080×960 expands height to 1620px, then crops 330px from top and bottom. | Top panel: $1080 \times 960$ ($1.125$ ratio). Source box $400 \times 600$ ($0.667$ ratio). Scale factor = $1080/400 = 2.7$. Resulting height = $1620$ px. Crop leaves $[(1620-960)/2] = 330$ px removed from head/chin. | Change `scale_mode` to `ScaleMode.CONTAIN` (`scale=...:force_original_aspect_ratio=decrease,pad=...:color=black`). Preserves 100% of user-selected rectangle and headroom with clean pillarbox padding. |
| **2. Missing live output preview** | `frontend/components/PodcastSelectionModal.tsx` (L980–L1056) | No real-time 9:16 composition renderer. Users saw only a static 64×96px colored box without actual framing geometry, safe margins, or scale readouts. | User draws rectangles on 16:9 canvas but cannot verify if $1080 \times 960$ stacked or $1080 \times 1920$ single focus will preserve participant headroom before generating clips. | Implement "Output Preview — Final 9:16 Composition" component with fixed 9:16 ratio, exact panel boundaries, safe headroom guides, real-time bounding box projection, and tight-crop geometry warnings. |
| **3. Person A duplicated in both panels** | `backend/services/advanced_podcast_engine.py` (L1176–L1182, L1312–L1331) | `classify_visibility_composition` fallback defaulted to `SIDE_BY_SIDE`. When face detection was absent or low-contrast, HSV default scores of 0.5 triggered `a_vis = True, b_vis = True`. `render_visibility_driven_video` then split input into two panels cropping the same person. | `score_a = 0.5`, `score_b = 0.5`. `a_vis = score_a >= 0.50` (True), `b_vis = score_b >= 0.50` (True) $\to$ `composition = "SIDE_BY_SIDE"`. Both left and right panel crops land on the only visible person. | Enforce mutually exclusive states: `A_ONLY`, `B_ONLY`, `A_AND_B`, `UNKNOWN_REVIEW`. Never default to `SIDE_BY_SIDE` when only one person is detected; fallback to safe solo shot or `UNKNOWN_REVIEW`. |
| **4. Both participants clipped in A+B** | `backend/services/advanced_podcast_engine.py` (L1288–L1291, L1328–L1329) | Hardcoded `side_crop_w = int(round(src_h * (540 / 1920))) = 304px`. Slicing 304px out of a 1080p frame (15.8% width) produces an extreme 9:32 aspect ratio column that cuts off participant shoulders, ears, and heads. | In 1920×1080 source, human subjects occupy ~450–650px width. Forcing `crop=304:1080` removes $>150$ px from each side of the participant. | Use independent 9:16 framing (`crop_a` and `crop_b`) preserving full participant bounds, then scale into $540 \times 1920$ panels with `force_original_aspect_ratio=decrease` and `pad` (aspect-ratio-preserving contain). |
| **5. Fixed two-person center cutoff** | `backend/services/advanced_podcast_engine.py` (L880, L897–L903) | When participant span exceeds 9:16 crop width (`required_span > crop_w`), the code centers a 607px crop in the middle between them, placing the crop in empty space and slicing off both participants. | Example: Person A at $x=200$, Person B at $x=1400$. `required_span = 1200` px. `crop_w = 606` px. Center at $x=800 \to$ crop $x \in [497, 1103]$. Both speakers are completely outside the crop. | When `required_span > crop_w`, scale the entire outer boundary into the 9:16 canvas with proportional aspect-preserving contain and padding rather than centering a narrow crop that clips both. |
| **6. Preview vs Renderer geometry divergence** | `frontend/lib/podcastCoordinates.ts` & `backend/services/layout_engine.py` | Frontend preview lacked shared geometry formula with backend FFmpeg filtergraph definitions. | Frontend CSS `object-fit: cover` vs backend FFmpeg `scale=...:increase,crop=...` diverged depending on container aspect ratio. | Create a shared geometry specification: normalized coordinates $\to$ aspect-preserving fit $\to$ panel placement. Ensure identical calculation in both TypeScript and Python. |

---

## 3. Mathematical Proof of Defect 1 (Standard Podcast Double Crop)

In `backend/services/layout_engine.py`:
```python
# Destination Panel: 1080 x 960 (Aspect ratio = 1.125)
# User-drawn Speaker 1 region: x=0.06, y=0.12, w=0.40, h=0.76 in 1920x1080 source
cx = int(0.06 * 1920) = 114
cy = int(0.12 * 1080) = 128
cw = int(0.40 * 1920) = 768
ch = int(0.76 * 1080) = 820
# Selected region aspect ratio = 768 / 820 = 0.9366 (taller than panel 1.125)
```
With `ScaleMode.CROP` (cover mode):
$$\text{scale factor} = \max\left(\frac{1080}{768}, \frac{960}{820}\right) = \max(1.406, 1.171) = 1.406$$
The scaled width becomes $768 \times 1.406 = 1080$ px.  
The scaled height becomes $820 \times 1.406 = 1153$ px.  
The secondary crop then takes $1080 \times 960$ centered from $1080 \times 1153$:
$$\text{Height cut off} = 1153 - 960 = 193\text{ px}$$
$$\text{Top cut off (headroom)} = \frac{193}{2} = 96.5\text{ px}$$
Because the user selected the region tightly around the head, losing 96.5 px cuts right through the forehead or hair.

When `ScaleMode.CONTAIN` is used:
$$\text{scale factor} = \min\left(\frac{1080}{768}, \frac{960}{820}\right) = \min(1.406, 1.171) = 1.171$$
Scaled width = $768 \times 1.171 = 899$ px.  
Scaled height = $820 \times 1.171 = 960$ px.  
Horizontal padding = $(1080 - 899) / 2 = 90.5$ px on left and right.  
Vertical cut = $0$ px.  
**Result:** 100% of the participant's head, face, and body are preserved with zero unintentional clipping.

---

## 4. Architectural Implementation Strategy

The fix will be delivered in four isolated phases:
1. **Phase B (Shared Framing & Safe Geometry):**
   - Update `backend/services/layout_engine.py` to use `ScaleMode.CONTAIN` for `stacked`, `single_region`, and related compositions.
   - Preserve deterministic selection semantics: `single_region` continues to select Area 1 (primary region, index 0).
   - Ensure even-pixel alignment for all dimensions.
2. **Phase C (Standard Podcast Live 9:16 Output Preview):**
   - Add "Output Preview — Final 9:16 Composition" to `frontend/components/PodcastSelectionModal.tsx`.
   - Update `frontend/lib/podcastCoordinates.ts` with exact geometry calculation functions mirroring the backend contain logic.
   - Add real-time visual feedback, safe headroom margin guides, and tight-crop warning indicators.
3. **Phase D (Advanced Podcast Visibility-Driven Composition Correction):**
   - Update `backend/services/advanced_podcast_engine.py` to strictly enforce `A_ONLY`, `B_ONLY`, `A_AND_B`, `UNKNOWN_REVIEW`.
   - Eliminate duplicate participant rendering on uncertain/fallback states.
   - Replace 304px slit crop with aspect-preserving contain framing for $540 \times 1920$ side-by-side panels.
4. **Phase E (Fixed Two-Person Camera-Following Correction):**
   - In `calculate_two_person_fixed_boundary_crop()`, add aspect-preserving contain/scale when `required_span > crop_w`.

---
*Report certified by QA & Video Processing Engineering Team.*
