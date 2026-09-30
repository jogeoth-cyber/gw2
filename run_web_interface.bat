@echo off
setlocal enabledelayedexpansion
title GW2 Skins Web Interface Viewer

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
echo   GW2 Skins, Caisses, Teintures & Craft Web Interface
echo ========================================================
echo.

if not exist "gw2_skins_unlocks.json" if not exist "gw2_skins_unlocks.js" (
    echo [WARNING] Database files were not found!
    echo Please run run_scrape_skins.bat first to generate the database.
    echo.
)

echo Starting local web server on http://localhost:8080 ...
echo Opening http://localhost:8080/view_skins.html in your default browser...
echo.

start /B python -m http.server 8080 >nul 2>&1
timeout /t 2 >nul
start http://localhost:8080/view_skins.html

if %errorlevel% neq 0 (
    echo Opening local file view_skins.html...
    start "" "view_skins.html"
)

echo.
echo Server is running. Press any key to stop the server and close this window.
pause >nul
