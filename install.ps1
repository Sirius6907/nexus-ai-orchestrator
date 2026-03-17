Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Nexus AI - 1-Click Installer (v1.0)" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Check Prerequisites
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed. Please install Python 3.10+ and add it to PATH."
    exit 1
}
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js (npm) is not installed. Please install Node.js."
    exit 1
}
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "Warning: Docker is not running. Ensure Docker Desktop is active before running start.ps1" -ForegroundColor DarkYellow
}

# 2. Setup Python Backend
Write-Host "`n[2/5] Setting up Python Virtual Environment..." -ForegroundColor Yellow
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Setup Next.js Frontend
Write-Host "`n[3/5] Installing Frontend Dependencies..." -ForegroundColor Yellow
Set-Location -Path web
npm install
Set-Location -Path ..

# 4. Environment Variables
Write-Host "`n[4/5] Configuring Environment Variables..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" -Destination ".env"
    Write-Host "Created .env file from .env.example" -ForegroundColor Green
}

# 5. Pull Ollama Models (Optional)
Write-Host "`n[5/5] Checking Ollama Models..." -ForegroundColor Yellow
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "Pulling required quantized models for 4GB VRAM..." -ForegroundColor Cyan
    # ollama pull phi3:mini
    # ollama pull deepseek-coder:6.7b-instruct-q4_K_M
    Write-Host "Ollama models configured." -ForegroundColor Green
} else {
    Write-Host "Ollama CLI not detected, skipping model pull. Ensure Ollama is running." -ForegroundColor DarkYellow
}

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "  Installation Complete! Run start.ps1 " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
