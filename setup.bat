@echo off
REM ============================================================================
REM  Sentinel - one-shot local setup (Windows)
REM
REM  Mirrors sentinel-solution/README.md's "Running locally" section. Creates
REM  the backend virtualenv, installs dependencies INTO THAT VENV (never the
REM  global interpreter - ultralytics/torch and paddleocr/paddlepaddle pull
REM  large, version-sensitive trees that will silently downgrade packages other
REM  tools rely on), seeds .env from the example, and installs frontend deps.
REM
REM  Usage:
REM    setup.bat              backend + frontend, stub detector/OCR
REM    setup.bat --with-ml    also install real YOLOv8 + PaddleOCR (large)
REM    setup.bat --backend    backend only, skip the frontend
REM
REM  Safe to re-run: every step is skipped if already satisfied, and an
REM  existing .env is never overwritten.
REM ============================================================================

setlocal enabledelayedexpansion
set "REPO_ROOT=%~dp0"
set "SOLUTION=%REPO_ROOT%sentinel-solution"
set "BACKEND=%SOLUTION%\backend"
set "FRONTEND=%SOLUTION%\frontend"
set "VENV=%BACKEND%\.venv"
set "VENV_PY=%VENV%\Scripts\python.exe"

set "WITH_ML=0"
set "SKIP_FRONTEND=0"
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--with-ml"  set "WITH_ML=1"
if /i "%~1"=="--backend"  set "SKIP_FRONTEND=1"
if /i "%~1"=="--help"     goto usage
if /i "%~1"=="-h"         goto usage
shift
goto parse_args
:args_done

echo.
echo ================================================================
echo  Sentinel local setup
echo ================================================================
echo.

REM ---------------------------------------------------------------- python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Install Python 3.11+ from https://www.python.org/downloads/
    echo         and make sure "Add python.exe to PATH" is ticked.
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VERSION=%%v"
echo [1/6] Python !PY_VERSION! found.

REM ------------------------------------------------------------------ venv
if exist "%VENV_PY%" (
    echo [2/6] Virtualenv already exists at backend\.venv - reusing.
) else (
    echo [2/6] Creating virtualenv at backend\.venv ...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtualenv.
        exit /b 1
    )
)
if not exist "%VENV_PY%" (
    echo [ERROR] Virtualenv python missing at "%VENV_PY%".
    exit /b 1
)

REM -------------------------------------------------------------- backend deps
echo [3/6] Installing backend dependencies into the venv ...
"%VENV_PY%" -m pip install --upgrade pip --quiet
"%VENV_PY%" -m pip install -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Backend dependency install failed - see the pip output above.
    exit /b 1
)

if "%WITH_ML%"=="1" (
    echo       Installing ML extras ^(YOLOv8 + PaddleOCR, this is a large download^) ...
    "%VENV_PY%" -m pip install -r "%BACKEND%\requirements-ml.txt"
    if errorlevel 1 (
        echo [WARN] ML extras failed to install. The backend still runs, but
        echo        main.py will fall back to the honest no-op stubs: it logs a
        echo        loud warning at startup and never produces detections or
        echo        plate reads. Re-run with --with-ml once the cause is fixed.
    )
) else (
    echo       Skipping ML extras. Without them the detector/OCR run as honest
    echo       no-op stubs ^(loud startup warning, no detections ever^).
    echo       Re-run as "setup.bat --with-ml" to enable real ANPR.
)

REM ------------------------------------------------------------------- .env
echo [4/6] Checking configuration ...
if exist "%SOLUTION%\.env" (
    echo       .env already present - left untouched.
) else (
    if exist "%SOLUTION%\.env.example" (
        copy /y "%SOLUTION%\.env.example" "%SOLUTION%\.env" >nul
        echo       Created sentinel-solution\.env from .env.example.
        echo       EDIT IT before connecting to the real sandbox - it needs
        echo       SENTINEL_CDN_HOST, SENTINEL_STREAM_HOST and SENTINEL_ACCESS_TOKEN.
    ) else (
        echo [WARN] No .env.example found - skipping .env creation.
    )
)

REM --------------------------------------------------------------- db + tests
echo [5/6] Verifying the install ^(schema migration + test suite^) ...
pushd "%BACKEND%" >nul
"%VENV_PY%" -m pytest tests -q
if errorlevel 1 (
    echo [WARN] Some backend tests failed. The environment is installed, but
    echo        review the failures above before trusting a demo run.
) else (
    echo       Backend test suite passed.
)
popd >nul

REM ---------------------------------------------------------------- frontend
if "%SKIP_FRONTEND%"=="1" (
    echo [6/6] Skipping frontend ^(--backend^).
    goto done
)

echo [6/6] Setting up the frontend ...
where node >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found on PATH - skipping the frontend.
    echo        Install Node 22.12 or newer, then run:
    echo            cd sentinel-solution\frontend ^&^& npm install
    goto done
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do set "NODE_VERSION=%%v"
echo       Node !NODE_VERSION! found.
REM vite/rolldown and oxlint ship native bindings that require >= 22.12.0.
REM 22.11 and below install fine and then fail at lint/build time, which is
REM a confusing failure to hit later - warn about it now instead.
for /f "tokens=1,2 delims=v." %%a in ("!NODE_VERSION!") do (
    set "NODE_MAJOR=%%a"
    set "NODE_MINOR=%%b"
)
if !NODE_MAJOR! LSS 22 (
    echo [WARN] Node !NODE_VERSION! is below 22.12.0. "npm run lint" and
    echo        "npm run build" will fail on missing native bindings.
) else (
    if !NODE_MAJOR! EQU 22 if !NODE_MINOR! LSS 12 (
        echo [WARN] Node !NODE_VERSION! is below 22.12.0. "npm run lint" and
        echo        "npm run build" will fail on missing native bindings.
    )
)

pushd "%FRONTEND%" >nul
call npm install
if errorlevel 1 (
    echo [WARN] npm install failed - the backend is still usable on its own.
) else (
    echo       Frontend dependencies installed.
)
popd >nul

:done
echo.
echo ================================================================
echo  Setup complete
echo ================================================================
echo.
echo  Start the backend:
echo     cd sentinel-solution\backend
echo     .venv\Scripts\python.exe -m app.main
echo.
echo  Start the frontend ^(separate terminal^):
echo     cd sentinel-solution\frontend
echo     npm run dev
echo.
echo  First backend start with an empty database mints a bootstrap admin
echo  API key and logs it ONCE - copy it from the startup log, then paste
echo  it into the frontend's API-key bar. Every endpoint except /health
echo  requires the X-Sentinel-API-Key header.
echo.
echo  Health check:  http://localhost:8000/health
echo  API docs:      http://localhost:8000/docs
echo.
exit /b 0

:usage
echo Usage: setup.bat [--with-ml] [--backend] [--help]
echo.
echo   --with-ml    also install real YOLOv8 + PaddleOCR (large download)
echo   --backend    backend only, skip the frontend
exit /b 0
