# CrackTheDeck: local full stack — RAG (Docker) + backend (8000) + frontend (5500)
# Prerequisites: Docker Desktop, .env in funds-rag-service and crackthedeck-backend with OPENAI_API_KEY

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$ragDir = Join-Path $root "funds-rag-service\funds-rag-service"
$backendDir = Join-Path $root "crackthedeck-backend\crackthedeck-backend"
$frontendDir = Join-Path $root "crackthedeck-deploy"

# 1) Start Funds RAG (Docker)
if (Test-Path (Join-Path $ragDir ".env")) {
    Write-Host "Starting Funds RAG (Docker)..." -ForegroundColor Cyan
    Push-Location $ragDir
    try {
        docker compose up -d --build 2>&1
        $ragOk = $?
        if (-not $ragOk) { Write-Host "Docker compose failed (is Docker running?). Continuing without RAG." -ForegroundColor Yellow }
        Start-Sleep -Seconds 5
        $health = try { Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5 } catch { $null }
        if ($health) {
            Write-Host "RAG: OK (funds_indexed: $($health.funds_indexed))" -ForegroundColor Green
        } else {
            Write-Host "RAG: not ready yet. If first run, run: docker compose exec rag python -m scripts.index_funds --csv data/funds.csv" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "RAG: .env not found in funds-rag-service. Copy .env.example to .env and set OPENAI_API_KEY. Skipping RAG." -ForegroundColor Yellow
}

# 2) Free ports 8000, 5500
foreach ($port in 8000, 5500) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Write-Host "Freed port $port"
        Start-Sleep -Seconds 1
    }
}

# 3) Start backend in new window
Write-Host "Starting CTD backend on :8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; if (Test-Path .\run_backend.ps1) { .\run_backend.ps1 } else { python -m uvicorn main:app --host 0.0.0.0 --port 8000 }"

Start-Sleep -Seconds 4

# 4) Start frontend in this window
Write-Host ""
Write-Host "Frontend:  http://localhost:5500" -ForegroundColor Green
Write-Host "Backend:   http://localhost:8000" -ForegroundColor Green
Write-Host "RAG:       http://localhost:8100 (if Docker started)" -ForegroundColor Green
Write-Host ""
Set-Location $frontendDir
python -m http.server 5500
