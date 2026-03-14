# CrackTheDeck: start frontend (5500) + backend (8000)
# Site: http://localhost:5500   API: http://localhost:8000

$root = $PSScriptRoot
$backend = Join-Path $root "crackthedeck-backend\crackthedeck-backend"
$frontend = Join-Path $root "crackthedeck-deploy"

# Free ports
foreach ($port in 8000, 5500) {
  Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2

# Start backend on 8000 in new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backend'; .\run_backend.ps1"

Start-Sleep -Seconds 3

# Start frontend on 5500 in this window
Set-Location $frontend
Write-Host "Frontend: http://localhost:5500"
Write-Host "Backend:  http://localhost:8000 (running in other window)"
python -m http.server 5500
