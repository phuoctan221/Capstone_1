@echo off
chcp 65001 >nul
title SmartVOCAB AI

echo ========================================
echo   SmartVOCAB AI - Dang khoi dong...
echo ========================================
echo.

:: 1. Khoi dong MongoDB bang Docker
echo [1/4] Khoi dong MongoDB...
docker ps --filter name=smartvocab-mongo --format "{{.Names}}" | findstr smartvocab-mongo >nul
if %errorlevel% neq 0 (
    docker run -d --name smartvocab-mongo -p 27017:27017 -v smartvocab-mongo-data:/data/db mongo:7 >nul
    echo       + MongoDB da chay tren port 27017
) else (
    docker start smartvocab-mongo >nul
    echo       + MongoDB da chay san
)

:: 2. Khoi dong Backend
echo [2/4] Khoi dong Backend (port 8000)...
start "SmartVOCAB Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"

:: 3. Khoi dong Frontend
echo [3/4] Khoi dong Frontend (port 5173)...
start "SmartVOCAB Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: 4. Mo browser
echo [4/4] Mo trinh duyet...
timeout /t 5 /nobreak >nul
start http://localhost:5173

echo.
echo ========================================
echo   Tat ca da san sang!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000/docs
echo   Mongo:    localhost:27017
echo ========================================
echo.
pause
