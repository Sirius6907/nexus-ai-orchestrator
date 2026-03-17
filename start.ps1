Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Starting Nexus AI Platform..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Start Docker Infrastructure
Write-Host "-> Starting Docker containers (Postgres, Redis, Qdrant)..." -ForegroundColor Yellow
docker-compose up -d

# 2. Start Celery Worker (Background Thread)
Write-Host "-> Starting Celery Background Worker (Autoscale: 10,2)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command", ".\venv\Scripts\activate.ps1; celery -A api.worker.celery_app worker --loglevel=info -P gevent --autoscale=10,2"

# 3. Start FastAPI Backend with HOT RELOAD (Background Thread)
Write-Host "-> Starting FastAPI Backend (Port 8000) with hot-reload..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command", ".\venv\Scripts\activate.ps1; uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir api"

# 4. Start Next.js Frontend (Foreground)
Write-Host "-> Starting Next.js UI (Port 3000)..." -ForegroundColor Yellow
Set-Location -Path web
npm run dev

# Cleanup on exit
Write-Host "Shutting down services..." -ForegroundColor Red
docker-compose stop
