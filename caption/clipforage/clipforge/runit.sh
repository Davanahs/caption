#!/bin/bash

echo "==================================================="
echo "⚡ Starting ClipForge Platform via Docker Compose ⚡"
echo "==================================================="

echo "[1/3] Building and starting Docker services (Backend, Celery Worker, Celery Beat, Redis, Flower)..."
docker-compose up -d --build

echo ""
echo "[2/3] Checking Docker containers status..."
docker-compose ps

echo ""
echo "==================================================="
echo "🔍 Handy Management Commands:"
echo "  - View Worker Logs  : docker-compose logs -f worker"
echo "  - View Backend Logs : docker-compose logs -f backend"
echo "  - Stop All Services : docker-compose down"
echo "==================================================="
echo ""

echo "[3/3] Starting Next.js Frontend Dashboard..."
cd frontend || exit 1
npm run dev
