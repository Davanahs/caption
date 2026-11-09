# Phase 10: AI Retention Heatmap & Virality Simulator Engine 🚀 (UNIQUE FEATURE)

## 🎯 Goal
Build a world-first **AI Audience Retention Heatmap & Virality Predictor** that analyzes audio cadence, visual movement, emotion spikes, and transcript hooks to plot a second-by-second predicted retention graph. It automatically identifies "drop-off risk zones" and features a 1-click **"Auto-Fix All Retention Risks"** button that applies micro-edits (zoom pushes, SFX drops, dynamic text pops) across all drop-off seconds simultaneously to keep viewer retention above 85%.

---

## 🛠️ Implementation Tasks

### 1. Second-by-Second Retention Predictor Model
- **Target Files:** `backend/services/virality_predictor.py` (NEW), `backend/api/routes/clips.py`
- Create a multi-factor retention analyzer:
  - **Audio Energy & Pitch Variance Analysis:** Detects monotone audio stretches (>4s without pitch inflection).
  - **Visual Motion Metric:** Tracks face movement variance and scene cuts.
  - **Speech Cadence & Pause Index:** Highlights long silence gaps or slow speech rates (<120 words/minute).
  - Output: A 0-100 retention curve dataset per second: `[{"second": 1, "retention": 98}, {"second": 2, "retention": 94}, ...]`.

### 2. Retention Heatmap Visualization & 1-Click Auto-Fix UI
- **Target Files:** `frontend/components/RetentionHeatmap.tsx` (NEW), `frontend/app/clips/page.tsx`
- Render an interactive SVG/Canvas timeline below the clip preview player:
  - **Green Zones (High Retention >85%):** Engaging hooks, fast pacing, high emotion.
  - **Yellow/Red Zones (Drop-off Risk <70%):** Slow pauses, lack of visual movement.
  - **1-Click "⚡ Auto-Fix All Risks" Button:** One click automatically scans all red zones, inserts dynamic zooms at monotone pauses, adds impact SFX accents at surprise words, and splits long subtitle chunks—instantly boosting predicted retention score above 85%.

---

## 3. Verification & Acceptance Criteria

1. **Auto-Fix Benchmark:** Click "⚡ Auto-Fix All Risks" on a low-scoring clip. Confirm system automatically applies camera zooms and SFX accents, re-evaluating predicted retention score above 85%.
2. **Prediction Graph Accuracy:** Verify retention scores update dynamically based on video transcript pacing and camera motion metrics.
