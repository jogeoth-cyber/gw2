@echo off
setlocal
title GW2 Skins Web Interface Viewer

rem Handle UNC network paths (e.g. \\JOJO\share\...)
pushd "%~dp0"

echo ========================================================
echo   GW2 Skins & Legendary Craft Web Interface
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

popd
