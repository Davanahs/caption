# ⚡ ClipForge — Autonomous AI Video Repurposing & Multi-Destination Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.2.7-black.svg?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.2.4-blue.svg?style=flat&logo=react&logoColor=white)](https://react.dev/)
[![Celery](https://img.shields.io/badge/Celery-5.4.0-37814A.svg?style=flat&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-5.0.6-DC382D.svg?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-libx264-007808.svg?style=flat&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg?style=flat)]()

ClipForge is an enterprise-grade, self-hosted autonomous video repurposing and publishing platform. It ingests long-form content from YouTube streams, local storage, podcasts, and gameplay footage, uses AI moment scoring and computer vision to frame engaging 9:16 vertical shorts (1080×1920), attaches channel-specific outro branding, and automates multi-destination scheduling and publishing directly to YouTube Shorts.

---

## 🌟 The 4 Core Creative Studios

ClipForge provides four specialized video processing entrypoints engineered for specific content formats:

### 1. ⚡ Normal Clipping Studio (`/`)
* **Intelligent Moment Scoring:** Combines local Whisper speech-to-text with Cloud LLMs (OpenRouter, Groq, Nvidia NIM) to identify high-retention viral moments.
* **Flexible Generation Modes:**
  * **AI Highlights:** Automatically scans and scores viral hooks and dynamic dialogue peaks.
  * **Equal Split:** Divides the source video into evenly spaced segments for full episodic coverage.
* **Granular Controls:** Select clip duration (15s, 30s, 45s, 49s optimal, 60s max) and target clip counts (2, 3, 5, 8, 10, or custom).

### 2. 🎮 Dual-Region Gaming Studio (`/gaming`)
* **Real-Time Dual-ROI Framing:**
  * **Gameplay Region (Green Box):** Fixed 9:16 aspect ratio framing the core gameplay action.
  * **Facecam Region (Yellow Box):** Freely resizable bounding box isolating streamer reactions.
* **Live 60fps Composite Preview:** Real-time canvas preview mirrors live YouTube playback with customizable Picture-in-Picture (PiP) placement (top-left, top-right, bottom-left, bottom-right).
* **Minimalist Ergonomics:** Clean 3-zone layout with direct click-to-play manipulation and synchronized pause states.

### 3. 🎙️ Podcast & Interview Studio (`/podcasts`)
* **Dual Intake Sources:** Ingest via `[🔗 YouTube URL]` or `[📁 System Storage]` local file dropzone (MP4, MOV, MKV, WEBM).
* **Multi-Speaker Participant Tracking:** Draw and label multiple speaker regions (Speaker 1, Speaker 2, etc.) directly on the video viewport.
* **Dual Director Modes:**
  * **Standard (Continuous Camera Follower):** Smooth, continuous 9:16 panning and reframing tracking active speakers without abrupt shot cuts.
  * **AI Smart Director (Dynamic Cuts):** Autonomous cinematic cutting between Speaker A close-up, Speaker B close-up, and Side-by-Side (A + B) split with blurred ambient background.

### 4. 🎞️ Upload Studio (`/studio`)
* **Resumable Chunk Streaming:** RFC 7233 compliant chunked upload pipeline with single-writer lock fencing and storage reservation accounting.
* **Automatic 9:16 Shorts Reframing:** Automatically detects horizontal (16:9) uploads and reframes them to 1080×1920 vertical Shorts with a blurred background backdrop, ensuring YouTube categorizes them as Shorts.
* **Mid-Process Channel Locking:** Select multiple publishing destination channels before batch start. Once processing begins, channels are strictly locked (`🔒 Channels Locked (Processing Active)`) to protect downstream rendering integrity.

---

## 🎯 Multi-Destination Routing & Channel Outros (`/youtube-channels`)

* **Multi-Channel Management:** Connect and authenticate multiple YouTube destination channels via OAuth 2.0.
* **Custom Channel Outros:** Configure distinct outros per channel (video or image, 1–15 seconds duration, automatic 1080×1920 scaling, audio crossfading).
* **Simultaneous Batch Routing:** Route clips to multiple channels in a single pass. ClipForge renders destination-specific variants concatenated with each channel's configured outro.
* **Strict Quality & Safety Invariants:**
  * **Private Upload Default:** All automated uploads strictly enforce `privacy="private"` to prevent accidental public release.
  * **Zero-Caption Mandate (`-sn`):** Enforces `-sn` across all FFmpeg rendering commands to eliminate unwanted source subtitle burn-in.

---

## ⚙️ Concurrency Gate & Queue Management

* **5-Video Operational Limit:** Protects CPU, GPU, and RAM by enforcing a strict concurrency gate of 5 active manual video pipelines.
* **FIFO Queue Draining:** The 6th+ video is automatically queued with real-time UI indicators (`"Queued (#X in line - waiting for an active video to finish)"`).
* **Stale Job Recovery:** Celery Beat periodically sweeps and recovers orphaned or crashed worker tasks, guaranteeing zero stalled pipeline slots.

---

## 🏗️ Technical Architecture

```
                               ┌────────────────────────┐
                               │   Next.js 16 Frontend   │
                               │  (React 19, TypeScript)│
                               └───────────┬────────────┘
                                           │ HTTP / REST / SSE
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI Backend                                    │
│  ┌───────────────────────┬───────────────────────┬─────────────────────────────┐  │
│  │   Studio API Routes   │  Channels & Outros    │   Videos & Jobs API Routes  │  │
│  └───────────┬───────────┴───────────┬───────────┴──────────────┬──────────────┘  │
│              │                       │                          │                 │
│              ▼                       ▼                          ▼                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                     SQLAlchemy 2.0 + PostgreSQL 15                          │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │ Celery Tasks
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                Celery Worker Nodes                                │
│  ┌───────────────────────┬───────────────────────┬─────────────────────────────┐  │
│  │  yt-dlp Downloader    │  Local Whisper AI     │  FFmpeg Video Processing    │  │
│  │  (Full Audio/Video)   │  (Base Model / Words) │  (Libx264, AAC, -sn Filter) │  │
│  ├───────────────────────┼───────────────────────┼─────────────────────────────┤  │
│  │  MediaPipe Tracking   │  Outro Concatenator   │  YouTube Publisher Service  │  │
│  │  (Facial/Pose Focus)  │  (Multi-Target Split) │  (OAuth2, Quota Protection) │  │
│  └───────────────────────┴───────────────────────┴─────────────────────────────┘  │
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │ Broker & Results
                                           ▼
                               ┌────────────────────────┐
                               │   Redis 5.0 Caching    │
                               └────────────────────────┘
```

---

## 🚀 Quick Start Setup Guide

### System Prerequisites
* **Docker & Docker Compose** (Recommended), OR:
* **Python 3.11 or 3.12**
* **Node.js 18+ & npm**
* **FFmpeg** installed and accessible on system `PATH`
* **PostgreSQL 15+** and **Redis 5.0+**

---

### Step 1: Clone & Configure Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/Chinmaygouda/AutomationPipeline.git
   cd AutomationPipeline/clipforge
   ```

2. Copy the sample environment file:
   ```bash
   cp .env.example .env
   ```

3. Update `.env` with your API keys:
   ```env
   # Database & Redis
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/clipforge
   SYNC_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/clipforge
   REDIS_URL=redis://localhost:6379/0

   # Cloud AI Keys (At least one required for AI moment scoring)
   OPENROUTER_API_KEY=your_openrouter_api_key
   GROQ_API_KEY=your_groq_api_key

   # YouTube Data API Credentials (For publishing)
   YOUTUBE_CLIENT_ID=your_oauth_client_id.apps.googleusercontent.com
   YOUTUBE_CLIENT_SECRET=your_oauth_client_secret
   ```

---

### Step 2: Start with Docker Compose (Recommended)

Start the entire ClipForge stack (PostgreSQL, Redis, FastAPI Backend, Celery Worker, and Flower monitor) in detached mode:

```bash
docker compose up -d --build
```

Verify running containers:
```bash
docker compose ps
```

Services exposed:
* **FastAPI Backend:** `http://localhost:8000` (API Docs: `http://localhost:8000/docs`)
* **Flower Celery Monitor:** `http://localhost:5555`
* **Redis:** `localhost:6379`
* **PostgreSQL:** `localhost:5433`

---

### Step 3: Start Frontend Application

From the `clipforge/frontend` directory:

```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:3000`** in your browser.

---

### Step 4: Running Manually (Without Docker)

If running without Docker:

1. **Start Redis & PostgreSQL:**
   Ensure Redis is running on port 6379 and PostgreSQL is running on port 5433.

2. **Backend Setup:**
   ```bash
   cd clipforge/backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Celery Worker (In a separate terminal):**
   ```bash
   cd clipforge/backend
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   celery -A backend.tasks.celery_app worker --loglevel=info --concurrency=2 -P solo
   ```

4. **Celery Beat (Scheduler, in a separate terminal):**
   ```bash
   cd clipforge/backend
   source venv/bin/activate
   celery -A backend.tasks.celery_app beat --loglevel=info
   ```

---

## 🧪 Testing & Verification

ClipForge includes a comprehensive multi-tier test suite covering unit tests, integration pipelines, and browser end-to-end flows:

### 1. Backend Pytest Suites
```bash
# Upload Studio direct pipeline and vertical reframing tests (5 tests)
py -3.12 -m pytest backend/tests/test_upload_studio_direct_pipeline.py -v

# Multi-destination routing and outro rendering tests (26 tests)
py -3.12 -m pytest backend/tests/test_multi_destination_routing_and_outro_e2e.py backend/tests/test_publishing_destination_repair.py -v

# Comprehensive E2E test suite
py -3.12 -m pytest tests/e2e/ -v
```

### 2. Frontend Browser & Playwright Cross-Verification
```bash
cd frontend

# Verify Upload Studio destination channel locking
node test/verify_upload_studio_channel_lock.mjs

# Cross-verify all 3 primary studios (Dashboard, Gaming, Podcasts)
node test/cross_verify_all_3_studios.mjs

# Verify Podcast Studio system storage intake
node test/verify_podcast_system_storage.mjs
```

### 3. Frontend Type-Check & Production Build
```bash
cd frontend
npx tsc --noEmit
npm run build
```

---

## 📂 Project Directory Structure

```
clipforge/
├── backend/
│   ├── alembic/                # Database migrations (Alembic)
│   ├── api/routes/             # FastAPI route controllers (studio, videos, publish, channels)
│   ├── core/                   # Configuration, storage reservations, security
│   ├── models/                 # SQLAlchemy ORM models (video, clip, outro, destination)
│   ├── services/               # Core engines (downloader, reframe_engine, outro_service, publisher)
│   ├── tasks/                  # Celery worker tasks & scheduler
│   ├── tests/                  # Backend pytest test suites
│   ├── Dockerfile              # Production container definition
│   └── requirements.txt        # Backend dependencies
├── frontend/
│   ├── app/                    # Next.js App Router (dashboard, gaming, podcasts, studio, publish)
│   ├── components/             # Reusable UI components & modals (Gaming, Podcasts, ProcessVideo)
│   ├── lib/                    # API clients, coordinates maths, focus traps
│   ├── test/                   # Playwright and Node test scripts
│   └── package.json            # Frontend dependencies & scripts
├── docs/
│   └── engineering/            # Canonical architecture, freeze rules, API audits, status reports
├── tests/
│   └── e2e/                    # Multi-tier end-to-end test suites
├── docker-compose.yml          # Multi-container service orchestration
└── .env.example                # Sample environment variables
```

---

## 🛡️ Engineering Governance & Continuity

ClipForge enforces strict software engineering standards documented in `docs/engineering/`:
* **Logic Freeze Ledger:** Protected component baselines preventing regressions in verified domains.
* **Endpoint Inventories:** Continuous cross-layer mapping between backend routes and frontend controls ([BACKEND_ENDPOINT_INVENTORY.md](docs/engineering/api_audit/BACKEND_ENDPOINT_INVENTORY.md), [FRONTEND_INTERACTION_ENDPOINT_MAP.md](docs/engineering/api_audit/FRONTEND_INTERACTION_ENDPOINT_MAP.md)).
* **Implementation Status:** Evidence-backed implementation logs in [IMPLEMENTATION_STATUS.md](docs/engineering/IMPLEMENTATION_STATUS.md) and [PROJECT_CONTINUITY.md](docs/engineering/PROJECT_CONTINUITY.md).
