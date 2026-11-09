# ⚡ ClipForge — AI YouTube Automation Platform

ClipForge is an industry-ready, self-hosted platform that automatically monitors YouTube channels, detects new uploads, clips them into highly engaging short-form videos (9:16) using Cloud AI models, and publishes/schedules them directly to YouTube Shorts.

---

## ✨ Features

- **Automated YouTube Channel Monitoring**: 24/7 scanning of added channels for new uploads.
- **AI moment detection**: Local Whisper audio transcription combined with Cloud AI (OpenRouter, Groq, Nvidia NIM) to detect high-retention viral moments.
- **Smart 9:16 Reframing**: Automated center crop with fallback letterbox to fit portrait format (1080x1920).
- **Auto Transcription**: Word-level Whisper timestamps generated for content analysis and reframing logic.
- **YouTube Shorts Publishing & Scheduling**: Directly upload your clips instantly or schedule them.
- **Smart Auto-Publisher (Cron)**: Background scheduler that automatically uploads queued videos at their exact scheduled time.
- **Performance Tracker**: Automatically polls YouTube API every 12 hours for 3 days to calculate a custom View Score for published clips.
- **AI Auto-Optimizer**: If a clip underperforms (View Score < 8.0) after 3 days, AI rewrites the SEO title and description and silently updates the live YouTube video.
- **Extremely Clean Dashboard**: Built with Next.js and premium dark glassmorphism styling.

---

## 🏗️ Architecture

- **Frontend**: Next.js 14+ (React 18/19, TypeScript, Vanilla/Tailwind CSS)
- **Backend API**: Python FastAPI (Async, PostgreSQL 15, SQLAlchemy, Alembic)
- **Task Queue**: Celery + Redis
- **AI / ML**: Local Whisper (base model) + Cloud AI providers (OpenRouter, Groq Cloud Audio, Nvidia NIM)
- **Video engine**: FFmpeg + OpenCV + yt-dlp

---

## 🚀 Quick Start Setup Guide

### Prerequisites
Before starting, ensure you have:
1. **Cloud AI API Key(s)** (OpenRouter, Groq, or Nvidia NIM) configured in your environment.
2. **Docker & Docker Compose** installed (recommended for simplified execution).
3. Alternatively, you can run services manually on Windows with **FFmpeg** and **Python 3.11/3.12** installed.

---

### Step 1: Set up Cloud AI API Keys
ClipForge uses Cloud AI models for intelligent moment detection, hook planning, and auto-optimization:
- **OpenRouter** (Recommended, supports free models): [openrouter.ai](https://openrouter.ai/)
- **Groq Cloud** (Fast Whisper & LLM): [console.groq.com](https://console.groq.com/)
- **Nvidia NIM**: [build.nvidia.com](https://build.nvidia.com/)

Configure your API key(s) in `.env` (e.g. `OPENROUTER_API_KEY=...` or `GROQ_API_KEY=...`).


---

### Step 2: Set up YouTube Data API Credentials
To publish clips directly from the dashboard, you need YouTube OAuth Client Credentials:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Search for and enable the **YouTube Data API v3**.
4. Click **Credentials** -> **Create Credentials** -> **OAuth Client ID**.
5. Set application type to **Web Application** or **Desktop Application**.
6. Set redirect URIs to:
   - `http://localhost:8080`
   - `http://localhost`
7. Copy the **Client ID** and **Client Secret**.

---

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` in the root of the project:
```bash
cp .env.example .env
```
Fill in the YouTube credentials you created:
```env
YOUTUBE_CLIENT_ID=your_client_id_here
YOUTUBE_CLIENT_SECRET=your_client_secret_here
```

---

### Step 4: Start the Services

#### Option A: Running with Docker Compose (Highly Recommended)
Launch the entire system (Redis, DB, backend, worker, flower monitor) in one command:
```bash
docker-compose up -d --build
```

```bash
docker-compose logs -f worker
```

This starts:
- **FastAPI API Server** on `http://localhost:8000`
- **Flower (Celery Monitor)** on `http://localhost:5555`
- **Redis** on `http://localhost:6379`

#### Option B: Running Manually (Locally)
If you prefer not to use Docker, run these services in separate terminal windows:

**1. Redis (Required)**
Ensure Redis is running on port 6379.

**2. Backend Server**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**3. Celery Worker (In another terminal)**
```bash
cd backend
venv\Scripts\activate
celery -A backend.tasks.process_video.celery_app worker --loglevel=info --concurrency=1
```

---

### Step 5: Start the Frontend App
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:3000`** in your browser.

---

## 🎯 Verification and Test Case

To verify your installation and make sure the whole pipeline works end-to-end:
1. Open the dashboard at `http://localhost:3000`.
2. Ensure the status indicator shows **Backend online** in the sidebar.
3. Paste a YouTube URL (e.g. `https://youtu.be/pjGsjYbaSVg`) and click **⚡ Generate**.
4. Check the **Pipeline Status** panel. You will see real-time updates as the video is downloaded, transcribed, scored, and reframed.
5. Go to the **Clips Library** page to see, play, download, or schedule the generated clips.

---

## 🛠️ Folder Structure
- `/backend`: Core FastAPI endpoints, schemas, database models.
- `/backend/services`: Downloader, Whisper, AI Scorer, FFmpeg Cutter, Publisher, Optimizer.
- `/backend/tasks`: Celery queues, background jobs, and Cron auto-publishers.
- `/frontend`: Next.js dashboard and responsive design elements.
