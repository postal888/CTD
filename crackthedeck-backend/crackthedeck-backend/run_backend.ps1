# Kill anything on port 8000 (old backend), then start fresh
$port = 8000
$found = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($found) {
    $found | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host "Stopped process on port $port. Waiting 2s..."
    Start-Sleep -Seconds 2
}
$root = $PSScriptRoot
Set-Location $root
Write-Host "Starting backend from: $root"
Write-Host "Presentations will be saved to: $root\presentations"
Write-Host "Check http://localhost:8000/api/health — must show build: no-mock"
& python -m uvicorn main:app --host 0.0.0.0 --port 8000
