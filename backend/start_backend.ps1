# Backend Server Startup Script
# This script starts the FastAPI backend server

Write-Host "Starting PeerEval Pro Backend Server..." -ForegroundColor Green
Write-Host ""

# Check if we're in the backend directory
if (-not (Test-Path "main.py")) {
    Write-Host "Error: main.py not found. Please run this script from the backend folder." -ForegroundColor Red
    exit 1
}

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "Warning: Virtual environment not detected." -ForegroundColor Yellow
    Write-Host "It's recommended to activate your virtual environment first." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To activate virtual environment, run:" -ForegroundColor Cyan
    Write-Host "  ..\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host ""
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne "y") {
        exit 0
    }
}

Write-Host "Starting server on http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "API Documentation will be available at: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
