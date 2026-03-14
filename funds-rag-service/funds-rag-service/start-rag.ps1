# Запуск Funds RAG и индексация фондов
# Перед запуском: включи Docker Desktop и дождись полной загрузки

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Checking Docker..." -ForegroundColor Cyan
$dockerOk = $false
try {
    $ErrorActionPreference = "SilentlyContinue"
    $null = docker info 2>&1
    $dockerOk = ($LASTEXITCODE -eq 0)
} catch { }
$ErrorActionPreference = "Stop"
if (-not $dockerOk) {
    Write-Host ""
    Write-Host "Docker Desktop is not running." -ForegroundColor Red
    Write-Host ""
    Write-Host "Do this:" -ForegroundColor Yellow
    Write-Host "  1. Start Docker Desktop from the Start menu" -ForegroundColor White
    Write-Host "  2. Wait until the whale icon appears in the system tray (bottom-right)" -ForegroundColor White
    Write-Host "  3. Run this script again (start-rag.bat or start-rag.ps1)" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host "Starting containers..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Waiting for RAG to be ready (30 sec)..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

Write-Host "Indexing funds from funds_clean.jsonl..." -ForegroundColor Cyan
docker compose exec -T rag python -m scripts.index_funds --jsonl /app/funds_data/funds_clean.jsonl
if ($LASTEXITCODE -ne 0) {
    Write-Host "Indexing failed. Try again: docker compose exec rag python -m scripts.index_funds --jsonl /app/funds_data/funds_clean.jsonl" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Done. RAG is running at http://localhost:8100" -ForegroundColor Green
Write-Host "You can now use 'Find matching funds' on the site." -ForegroundColor Green
