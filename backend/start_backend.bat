@echo off
REM Backend Server Startup Script (Windows Batch)
REM This script starts the FastAPI backend server

echo Starting PeerEval Pro Backend Server...
echo.

REM Check if we're in the backend directory
if not exist "main.py" (
    echo Error: main.py not found. Please run this script from the backend folder.
    pause
    exit /b 1
)

echo Starting server on http://127.0.0.1:8000
echo API Documentation will be available at: http://127.0.0.1:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause
