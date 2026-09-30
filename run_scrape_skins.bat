@echo off
setlocal
title GW2 Skins & Legendary Craft Database Generator

rem Handle UNC network paths (e.g. \\JOJO\share\...)
pushd "%~dp0"

echo ========================================================
echo   GW2 Skins, Caisses & Legendary Craft Scraper
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3 and try again.
    popd
    pause
    exit /b 1
)

echo Starting modular extraction across all categories...
python scrape_all.py --workers 20 --lang fr

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred during extraction.
    popd
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

popd
pause
