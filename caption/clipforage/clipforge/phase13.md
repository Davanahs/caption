# Phase 13: 3-Second AI Kinetic Curiosity Hook Generator ⚡ (UNIQUE FEATURE)

## 🎯 Goal
Build an **AI Kinetic Curiosity Hook Generator** that analyzes the video's core punchline or climax and automatically creates a high-impact 3-second animated intro teaser (curiosity question, fast teaser flash, kinetic headline font, and energetic AI voiceover teaser) at the very start of the Short—maximizing initial viewer hook rates and stopping the scroll instantly.

---

## 🛠️ Implementation Tasks

### 1. Climax & Curiosity Hook Summarizer
- **Target Files:** `backend/services/hook_generator.py` (NEW), `backend/services/clip_scorer.py`
- Analyze the selected clip's transcript to generate 3 high-converting curiosity hooks:
  - Pattern 1 (Curiosity Question): *"Why 99% of people fail at X..."*
  - Pattern 2 (The Secret Reveal): *"The 1 secret nobody tells you about Y..."*
  - Pattern 3 (Bold Statement): *"This changes everything about Z..."*

### 2. Kinetic Intro Visual & AI Voiceover Engine
- **Target Files:** `backend/services/hook_generator.py`, `backend/services/overlay_engine.py`
- Render a dynamic 3-second visual teaser intro:
  - **Kinetic Text Animating In:** Large bold typography with spring scale pop and vibrant glow.
  - **AI Voiceover Hook Teaser:** Generates a 2-second fast energetic AI voiceover reading the hook title intro (using ElevenLabs / EdgeTTS) blended smoothly into the main speech track.
  - **Quick Teaser Flash:** 0.5-second black-and-white flash preview of the clip's peak emotional moment.

---

## 🧪 Verification & Acceptance Criteria

1. **AI Voiceover Teaser Test:** Play 3-second hook intro. Verify energetic AI voiceover reads hook question with crisp audio alignment before main clip audio begins.
2. **Scroll-Stop Impact Test:** Verify 3-second hook intro renders smoothly at $t=0.0\text{s}$.
3. **Pacing Inspection:** Ensure transition from 3-second hook intro to main clip speech is seamless and uninterrupted.
