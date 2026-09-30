@echo off
setlocal enabledelayedexpansion
title GW2 Skins & Legendary Craft Database Generator

rem ========================================================
rem UNC Network Share Mapping Routine (Drive Y: strictly)
rem ========================================================
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

rem Check if executed from UNC network path (starts with \\)
if "!SCRIPT_DIR:~0,2!"=="\\" (
    echo [NETWORK] UNC network path detected: !SCRIPT_DIR!

    rem Check if Y: is already mounted to another folder
    if exist Y:\ (
        net use Y: 2>nul | findstr /i /c:"!SCRIPT_DIR!" >nul
        if errorlevel 1 (
            echo [NETWORK] Y: is currently mapped to a different directory. Unmapping Y:...
            net use Y: /delete /y >nul 2>&1
            subst Y: /d >nul 2>&1
        )
    )

    rem Map Y: to current script directory if not mounted
    if not exist Y:\ (
        echo [NETWORK] Mounting network drive Y: to !SCRIPT_DIR!
        net use Y: "!SCRIPT_DIR!" >nul 2>&1
        if errorlevel 1 (
            pushd "!SCRIPT_DIR!"
        ) else (
            Y:
            cd \
        )
    ) else (
        Y:
        cd \
    )
) else (
    cd /d "!SCRIPT_DIR!"
)

echo ========================================================
echo   GW2 Skins, Caisses, Teintures & Craft Generator
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3 and try again.
    pause
    exit /b 1
)

echo Starting modular extraction across all categories...
python scrape_all.py --workers 20 --lang fr

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred during extraction.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo Extraction completed successfully!
echo SQLite database: gw2_skins_unlocks.db
echo JSON file:       gw2_skins_unlocks.json
echo JS file:         gw2_skins_unlocks.js
echo ========================================================
echo.
echo You can now launch run_web_interface.bat to open the web UI.
echo.

pause
