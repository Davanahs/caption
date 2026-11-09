@echo off
echo ===================================================
echo ⚡ Starting ClipForge Platform via Docker Compose ⚡
echo ===================================================

echo [1/3] Building and starting Docker services (Backend, Celery Worker, Celery Beat, Redis, Flower)...
docker-compose up -d --build

echo.
echo [2/3] Checking Docker containers status...
docker-compose ps

echo.
echo ===================================================
echo 🔍 Handy Management Shortcuts:
echo   - View Worker Logs  : logs-worker.bat
echo   - View Backend Logs : logs-backend.bat
echo   - Stop All Services : stopall.bat
echo ===================================================
echo.

echo [3/3] Starting Next.js Frontend Dashboard...
cd frontend
npm run dev

echo.
echo ClipForge frontend stopped.
pause
