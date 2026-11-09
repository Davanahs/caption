# Phase 11: Multimodal Sound Effects (SFX) & Audio Reaction Engine 🎧 (UNIQUE FEATURE)

## 🎯 Goal
Build an **AI Audio Reaction & Auto-SFX Engine** that analyzes speech inflections, emotional hooks, and transcript keywords to automatically place subtle, trending audio cues (whooshes, pops, vinyl scratches, risers, bass drops, subtle chimes) in sync with the video—plus support custom user SFX pack uploads for branded audio identity.

---

## 🛠️ Implementation Tasks

### 1. Contextual Audio Cue Classifier
- **Target Files:** `backend/services/sfx_engine.py` (NEW), `backend/services/overlay_engine.py`
- Analyze speech stream and subtitle tokens for SFX placement triggers:
  - **Text Pop / Word Entry:** High-impact keyword entry $\rightarrow$ Subtle `pop.wav` or `whoosh_fast.wav` (-18dB volume ducking).
  - **Surprise / Reveal Words:** ("secret", "boom", "crazy", "unbelievable") $\rightarrow$ `riser_impact.wav` or `bass_drop.wav`.
  - **Question / Curiosity:** ("why?", "how?", "what if?") $\rightarrow$ `chime_accent.wav`.

### 2. Custom User SFX Pack Upload & Management API
- **Target Files:** `backend/api/routes/sfx.py` (NEW), `backend/services/sfx_engine.py`
- Build an API endpoint (`POST /api/sfx/upload`) allowing creators to upload custom branded sound effect packs (`.wav` / `.mp3`).
- Custom audio samples can be mapped to trigger events (e.g. custom brand whoosh on title intro).

### 3. High-Precision Sub-Frame Audio Mixing Engine
- **Target Files:** `backend/services/sfx_engine.py`, `backend/services/clip_cutter.py`
- Build multi-track audio compositor:
  - Mixes royalty-free SFX samples onto the original audio track at exact word timestamps $[t_{word\_start}]$.
  - Implements dynamic audio ducking: Automatically lowers original speech volume by 1.5dB during heavy impact audio accents to maintain speech clarity.
  - Generates final mixed audio stream via FFmpeg `amix` / `adelay` filter graph.

---

## 🧪 Verification & Acceptance Criteria

1. **Custom SFX Upload Test:** Upload custom `.wav` sound effect. Verify engine triggers custom audio accent on phrase entry cleanly.
2. **Audio Sync Accuracy:** Verify sound effect accents play within $\pm 20\text{ms}$ of subtitle word highlights.
3. **Audio Clarity Inspection:** Ensure original voice speech remains crisp and 100% intelligible.
