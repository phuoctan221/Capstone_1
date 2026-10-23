@echo off
chcp 65001 >nul
title SmartVOCAB AI
cd /d "%~dp0"

echo ========================================
echo   SmartVOCAB AI - Dang khoi dong...
echo ========================================
echo.

:: --- Kiem tra cong cu dung ---
where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Cai Python 3.11+ tu https://python.org
    pause
    exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Node.js. Cai Node.js 18+ tu https://nodejs.org
    pause
    exit /b 1
)

:: --- 1. Backend ---
echo [1/3] Khoi dong Backend (port 8000)...
if not exist "backend\.env" (
    echo       + Tao backend\.env tu .env.example...
    copy "backend\.env.example" "backend\.env" >nul
    echo       [QUAN TRONG] Dien MONGO_URI cua MongoDB Atlas vao backend\.env
    echo                     truoc khi dung. Xem README.md phan "Chay du an".
)
if not exist "backend\.venv\Scripts\python.exe" (
    echo       + Tao virtualenv...
    python -m venv "backend\.venv"
    if errorlevel 1 (
        echo [LOI] Khong tao duoc virtualenv.
        pause
        exit /b 1
    )
)
echo       + Cai dat requirements...
backend\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip >nul
backend\.venv\Scripts\python.exe -m pip install --quiet -r "backend\requirements.txt"
if errorlevel 1 (
    echo [LOI] Cai dat requirements that bai.
    pause
    exit /b 1
)

:: --- 2. Frontend ---
echo [2/3] Khoi dong Frontend (port 5173)...
if not exist "frontend\node_modules" (
    echo       + Cai dat npm packages...
    pushd "frontend"
    call npm install
    popd
)

:: --- 3. Chay ---
echo       + Backend : http://localhost:8000/docs
echo       + Frontend: http://localhost:5173
start "SmartVOCAB Backend" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
start "SmartVOCAB Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

:: --- 4. Cho backend san sang roi mo trinh duyet ---
echo [3/3] Cho backend khoi dong...
where curl >nul 2>nul
if errorlevel 1 (
    timeout /t 5 /nobreak >nul
    goto open_browser
)
set /a _wait=0
:wait_backend
curl -s -o nul http://localhost:8000/health 2>nul
if not errorlevel 1 goto open_browser
set /a _wait+=1
if %_wait% geq 30 goto open_browser
timeout /t 1 /nobreak >nul
goto wait_backend

:open_browser
start http://localhost:5173

echo.
echo ========================================
echo   Tat ca da san sang!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000/docs
echo   Database: MongoDB Atlas (dung chung ca team)
echo ========================================
echo.
pause
