Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "⚡ Starting ClipForge Platform via Docker Compose ⚡" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Building and starting Docker services (Backend, Celery Worker, Celery Beat, Redis, Flower)..." -ForegroundColor Yellow
docker-compose up -d --build

Write-Host "`n[2/3] Checking Docker containers status..." -ForegroundColor Yellow
docker-compose ps

Write-Host "`n[3/3] Starting Next.js Frontend Dashboard..." -ForegroundColor Yellow
Set-Location -Path "frontend"
npm run dev
