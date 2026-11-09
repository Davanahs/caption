# Phase 12: Contextual AI B-Roll & Generative Visual Overlay Engine 🎨 (UNIQUE FEATURE)

## 🎯 Goal
Build a **Contextual AI B-Roll & Generative Visual Overlay Engine** that automatically detects abstract spoken concepts ("building a company", "space travel", "crypto collapse", "chart growth") and overlays relevant high-resolution stock video clips, micro-animations, or AI-generated diagrams/images—keeping visual engagement high throughout the video.

---

## 🛠️ Implementation Tasks

### 1. NLP Visual Concept Extractor & AI Image Fallback
- **Target Files:** `backend/services/broll_engine.py` (NEW), `backend/services/clip_cutter.py`
- Analyze transcription for visual entities and abstract concepts:
  - Identifies 3 to 6-second concept spans (e.g., "when I started investing in stocks...").
  - Queries local royalty-free HD stock video library (Pexels / Pixabay API integration).
  - **Generative AI Fallback:** If no stock video is found for rare technical or custom topics, automatically triggers an AI Image / Diagram Generation API (FLUX / Stable Diffusion) to synthesize a custom visual graphic overlay on the fly.

### 2. Multi-Layer PIP & Cutaway Video Compositor
- **Target Files:** `backend/services/broll_engine.py`, `backend/services/clip_cutter.py`
- Implement two visual overlay modes:
  - **Full B-Roll Cutaway:** Switches full video frame to B-roll footage for 2-3 seconds while keeping original speech audio uninterrupted.
  - **Top PIP Window (Picture-in-Picture):** Places a rounded 16:9 or 1:1 B-roll video box in the upper or lower corner of the vertical clip frame.
  - Applies smooth 200ms fade-in / fade-out alpha transitions to B-roll overlays.

---

## 🧪 Verification & Acceptance Criteria

1. **Generative Diagram Fallback Test:** Pass a technical concept ("quantum computing architecture"). Verify system synthesizes a clean AI diagram visual overlay when stock footage is unavailable.
2. **Contextual Relevance Test:** Verify speech talking about "money" or "stocks" triggers relevant financial stock footage overlays.
3. **Audio Continuity Test:** Ensure original speech audio remains 100% smooth and continuous during B-roll cutaway transitions.
