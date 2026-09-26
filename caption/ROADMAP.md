# Viral AI Caption Engine — Development Roadmap & Specifications

> **Goal:** Bridge the gap between basic STT captioning and viral short-form caption engines (Submagic, CapCut, Opus Clip) by introducing an LLM "Caption Director" pass, content-aware clustering, dynamic typography/animations, and audio cleanup.

---

## 📊 Honest Benchmark: Current Engine vs. Industry Leaders (Submagic / CapCut / Opus Clip)

| Feature / Capability | Trending AI Tools (Submagic, CapCut, Opus Clip) | Current Engine State | Gap & Targeted Solution |
| :--- | :--- | :--- | :--- |
| **Emphasis & Semantic Weighting** | LLM analyzes sentiment/context to highlight key words, numbers, and power phrases. | Highlights whatever word is currently playing — no semantic weighting. | **Phase 2**: Add Groq LLM "Caption Director" pass to score and tag `emphasisWords`. |
| **Emoji & SFX Stings** | Context-aware emoji insertion and punchline sound effect stings ("whoosh", "ding", "pop"). | None. | **Phase 2**: Prompt LLM to output contextual `emoji` and `sfx` cue tags per block. |
| **Animation Presets** | Dozens of switchable presets (Karaoke fill, Bounce, Typewriter, Glitch, Hormozi, MrBeast). | Single scale-pop animation only. | **Phase 3**: Refactor `renderer.js` into modular theme configs with 5+ preset styles. |
| **Auto Keyword Coloring** | Category-based auto-coloring (Money=Green, Warning=Red, Numbers=Yellow). | Static single accent color. | **Phase 2 & 3**: LLM assigns `colorTag` per block/word; renderer applies theme palettes. |
| **Clustering Quality** | Content-aware phrase splitting (natural linguistic breaks, 20-24 char limit). | Purely rule-based (4 words / 0.35s pause / punctuation). | **Phase 1**: POS-tagging-lite scoring function for natural phrase boundaries. |
| **Audio Cleanup & Trimming** | Auto silence cutting, filler word removal ("um", "uh"), background noise reduction. | Captioning only, no audio cleanup. | **Phase 4**: Silence gap auto-cutting & filler-word removal engine. |
| **Transcript Accuracy** | Near-perfect accuracy (95-99%) via post-correction LLM pass over raw Whisper. | Raw Whisper-v3 output without post-correction. | **Phase 5**: LLM proofreading pass with timestamp re-mapping algorithm. |
| **Packaging & Export** | Preset marketplace, brand kit, burnt-in MP4 export, JSON export. | Single hardcoded style, local canvas preview. | **Phase 6**: Brand kits, preset selector, FFmpeg video rendering & export. |

---

## 🚀 Phase-Wise Implementation Roadmap

```
[ Phase 1: Fix Clustering ] ──> [ Phase 2: LLM Director Pass ] ──> [ Phase 3: Style Engine ]
                                                                             │
[ Phase 6: Packaging ]     <── [ Phase 5: Accuracy Pass ]    <── [ Phase 4: Audio Cleanup ]
```

---

### 🔹 Phase 1 — Fix Clustering Quality & Readability (No New AI Calls)
* **Objective:** Replace static 4-word/0.35s rules with a multi-factor scoring function for phrase boundaries.
* **Key Tasks:**
  1. **POS-Tagging-Lite Scoring Function:**
     * Weight splits by natural speech breaks (conjunctions like *and, but, so*, prepositions like *in, on, at, to*, and punctuation).
     * Enforce a max character limit per line (~20–24 characters) to prevent awkward word wraps.
     * Factor in pause duration ($>0.25\text{s}$) alongside word length.
  2. **Whisper Text Sanitization:**
     * Add deterministic casing rules (capitalize proper nouns/I, normalize contractions).
     * Fix common transcript formatting bugs (e.g., isolated punctuation marks).

---

### 🔹 Phase 2 — LLM "Caption Director" Pass (Core Differentiator)
* **Objective:** Introduce an LLM inference pass over the transcription blocks to decide semantic emphasis, emojis, sound effects, and color themes.
* **Key Tasks:**
  1. **Groq LLM Integration:**
     * Call fast LLM (`llama-3.3-70b-versatile`) once per video transcription.
     * Send array of caption blocks with timing context.
  2. **Prompt Engineering & Schema Enforcement:**
     * System prompt instructs model to return JSON with:
       - `emphasisWords`: Array of target words for bold/scale emphasis.
       - `emoji`: Single relevant contextual emoji (capped at ~15% of blocks).
       - `sfx`: Sound cue tag (`whoosh`, `ding`, `pop`, `boom`, `cash`) for punchlines.
       - `colorTag`: `"neutral"` | `"highlight"` | `"warning"` | `"money"` | `"question"`.
  3. **Schema Schema Extension:**
     * Extend Unified Caption JSON format to store LLM director metadata per block.

---

### 🔹 Phase 3 — Modular Style & Animation Engine
* **Objective:** Decouple canvas rendering from hardcoded logic so animation, typography, and colors are driven by dynamic style configs.
* **Key Tasks:**
  1. **Style Config Architecture (`renderer.js`):**
     * Create style registration system accepting `styleId` configs (fonts, strokes, backgrounds, animations).
  2. **5 Core Animation Presets:**
     * `karaoke-fill`: Progressively fills word text fill color as audio plays.
     * `bounce-pop`: Spring-loaded scale pop on active/emphasized words.
     * `typewriter`: Character-by-character reveal synced to word timestamps.
     * `bold-static`: Clean, high-impact bold typography (Alex Hormozi style).
     * `glitch-cyber`: Neon outline displacement and high-contrast color shifts.
  3. **Color Tag Palette Mapping:**
     * Render active words using `colorTag` mapping (e.g., `money` $\rightarrow$ `#22C55E`, `warning` $\rightarrow$ `#EF4444`, `highlight` $\rightarrow$ `#EAB308`).

---

### 🔹 Phase 4 — Audio Cleanup & Silence Trimming
* **Objective:** Clean audio speech track and remove unwanted pauses/fillers to match short-form pacing.
* **Key Tasks:**
  1. **Silence Cutting Engine:**
     * Detect gaps where $W_{i+1}.\text{start} - W_i.\text{end} > \text{threshold}$ (e.g., $>0.5\text{s}$).
     * Provide auto-trim timings list for frontend timeline & backend FFmpeg splicing.
  2. **Filler Word Removal:**
     * Flag disfluencies ("um", "uh", "er", "like") via regex wordlist + optional LLM verification.
     * Allow user to one-click strip filler words and shift trailing word timestamps seamlessly.

---

### 🔹 Phase 5 — Accuracy & Proofreading Pass
* **Objective:** Elevate transcription accuracy to 99% by correcting misheard words, homophones, and grammar.
* **Key Tasks:**
  1. **LLM Proofreading Prompt:**
     * Send raw full-text transcript to LLM requesting grammar, spelling, casing, and homophone fixes.
  2. **Timestamp Index Re-Mapping:**
     * Align corrected text tokens back to the original word timestamp boundaries.
     * Handle cases where word count changes (1-to-2 or 2-to-1 word corrections) by distributing time ranges proportionally.

---

### 🔹 Phase 6 — Packaging, Export & Marketplace
* **Objective:** Provide end-to-end publishing capabilities.
* **Key Tasks:**
  1. **Preset Selector & User Brand Kit:**
     * UI dropdown for instant 1-click style swapping.
     * Custom user settings persistence (saved font choices, primary/accent colors).
  2. **Export Engine:**
     * Native JSON export/import for session saving.
     * FFmpeg backend rendering to burn animated captions into final `.mp4` video exports.

---

## 🛠 Unified Caption Schema Specification (v2.0)

```json
{
  "version": "2.0",
  "styleId": "lightning-comic",
  "metadata": {
    "totalDuration": 12.4,
    "wordCount": 38,
    "silenceCuts": [{ "start": 3.2, "end": 4.1 }]
  },
  "blocks": [
    {
      "id": "block_001",
      "text": "MAKE $10,000 THIS MONTH",
      "start": 0.12,
      "end": 1.45,
      "colorTag": "money",
      "emoji": "💰",
      "sfx": "cash_register",
      "emphasisWords": ["$10,000"],
      "words": [
        { "word": "MAKE", "start": 0.12, "end": 0.35, "isEmphasis": false },
        { "word": "$10,000", "start": 0.38, "end": 0.85, "isEmphasis": true, "colorOverride": "#22C55E" },
        { "word": "THIS", "start": 0.88, "end": 1.10, "isEmphasis": false },
        { "word": "MONTH", "start": 1.12, "end": 1.45, "isEmphasis": false }
      ]
    }
  ]
}
```

---

## 📌 Implementation Checklist & Status

- [ ] **Phase 1: Fix Clustering Quality**
  - [ ] POS-tagging phrase scoring algorithm
  - [ ] Max 20-24 char limit per line
  - [ ] Text sanitization & casing fixes
- [ ] **Phase 2: LLM Caption Director Pass**
  - [ ] Groq LLM integration (`llama-3.3-70b-versatile`)
  - [ ] Prompt engineering for emphasis, emoji, sfx, and colorTag
  - [ ] Schema update & integration with server endpoints
- [ ] **Phase 3: Modular Style & Animation Engine**
  - [ ] Config-driven theme system in `renderer.js`
  - [ ] Implement 5 presets: Karaoke, Bounce, Typewriter, Bold, Glitch
  - [ ] Render dynamic word colors based on `colorTag` & `emphasisWords`
- [ ] **Phase 4: Audio Cleanup & Silence Trimming**
  - [ ] Silence gap detector ($>0.5\text{s}$)
  - [ ] Filler word removal algorithm
- [ ] **Phase 5: Accuracy & Proofreading Pass**
  - [ ] LLM proofreader for transcript text
  - [ ] Timestamp re-mapping index algorithm
- [ ] **Phase 6: Packaging & Export**
  - [ ] Preset marketplace UI & user Brand Kit
  - [ ] FFmpeg MP4 burn-in video renderer
