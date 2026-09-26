# ⚡ Standalone Caption Engine MVP

A standalone, modular caption generation and visual styling engine. Built to generate accurate, readable, highly stylized captions with custom typography, double-stroke containers, active word scale animations, and particle motion FX — ready to be integrated into **ClipForge**.

---

## 📸 Reference Visual Style: "Lightning Comic"

The engine renders high-impact animated captions matching the **Lightning Comic** visual signature:
* **Typography**: All-Caps distressed heavy brush font (*Bangers* / *Permanent Marker*).
* **Badge Container**: Slanted geometry ($-6^\circ$ skew) with deep purple fill (`#1B1233`) and jagged lightning cuts.
* **Double Outline Stroke**: Sharp 4px white inner stroke + electric neon purple outer glow contour (`#8B5CF6`).
* **Active Word Animation**: Scale-up spring bounce ($1.0 \rightarrow 1.18$) with glowing yellow highlight (`#FFE600`) and comic speed line FX.

---

## 📁 Repository Structure

```
d:\startup\caption/
├── backend/
│   ├── .env                 # API Key Configuration file
│   ├── .env.example         # Template for environment variables
│   ├── package.json         # Backend dependencies & scripts
│   └── server.js            # Express API server & static frontend host (Port 5000)
├── frontend/
│   ├── css/
│   │   └── styles.css        # Lightning Comic Design Tokens & Glassmorphism UI
│   ├── js/
│   │   ├── normalizer.js     # Text normalization (trims whitespace, preserves wording)
│   │   ├── segmenter.js      # Rule-based block chunking into Unified JSON Schema
│   │   ├── renderer.js       # Lightning Comic Canvas Renderer
│   │   └── app.js            # UI controller, playback scrubber, inline editor, export
│   └── index.html            # Main web application dashboard
├── .env                     # Root API Key configuration placeholder
├── .env.example             # Root environment template
├── PHASE1_CHECKLIST.md       # Detailed Phase 1 implementation checklist
└── ROADMAP.md                # Multi-phase development roadmap & specs
```

---

## 🔑 Environment Variables Configuration

Copy `.env.example` to `.env` in the `backend/` directory or root:

```bash
# In backend/.env
PORT=5000

# Primary STT Provider for Phase 2 (Recommended - Word-level timestamps)
# Get key: https://console.groq.com/keys
GROQ_API_KEY=your_groq_api_key_here

# Alternative STT Provider
# Get key: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# Optional LLM Provider (For filler word removal)
# Get key: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 🚀 How to Run

### 1. Install & Start Backend (Includes Static Frontend Host)

Open your terminal in `d:\startup\caption`:

```bash
# Navigate to backend folder
cd backend

# Install dependencies
npm install

# Start backend server
npm start
```

* The server will launch on **`http://localhost:5000`**.
* Open **`http://localhost:5000`** in your browser to access the full application!

### 2. Live Development Mode (Auto-Reloading Server)

```bash
cd backend
npm run dev
```

---

## ⚡ How to Use Phase 1 (Text-to-Captions)

1. **Paste Script**: Enter your text into the **Paste Your Script Text** area.
2. **Adjust Controls**: Use the sliders to adjust **Max Words Per Block** (2–6 words) and **Reading Speed (WPM)**.
3. **Generate Captions**: Click **⚡ Generate & Segment Captions**.
4. **Live Canvas Preview**: Use the play/pause button `▶` or drag the timeline scrubber to preview the **Lightning Comic** animated captions.
5. **Inline Editing**: Click any block in the left sidebar list to edit text inline, or click **✂️ Split Block** / **🗑️ Delete Block**.
6. **Export Output**:
   * **📄 Export JSON Data**: Download the Unified Caption JSON file.
   * **📸 Export Frame Image**: Download a high-res PNG snapshot of the currently rendered canvas frame.

---

## 🛣️ Multi-Phase Roadmap Overview

| Phase | Status | Input | Key Feature |
| :--- | :--- | :--- | :--- |
| **Phase 1: Text Engine** | **✅ COMPLETED & FROZEN** | Raw text script | Text normalization, chunking, Lightning Comic canvas player, inline editor, JSON/PNG export. |
| **Phase 2: Audio Engine** | ⏳ Next Phase | `.mp3` / `.wav` audio | Speech-to-text with Whisper API, word-level timestamps, pause-based segmentation, transcript editor. |
| **Phase 3: Video Engine** | ⏳ Pending | `.mp4` / `.mov` video | Audio track extraction, video-caption sync overlay, burned-in video export. |

---

## 🧪 API Health Check

Verify backend server status by visiting:
```
http://localhost:5000/api/health
```

Expected Response:
```json
{
  "status": "online",
  "phase": "Phase 1 - Text Caption Engine",
  "timestamp": "2026-08-01T06:12:20.302Z"
}
```
