@echo off
echo ===================================================
echo 📋 Viewing Live Celery Worker Logs (Ctrl+C to exit)
echo ===================================================
docker-compose logs -f worker
