@echo off
setlocal
title GW2 Skins Unlocks & Legendary Craft Database Generator

rem Handle UNC network paths (e.g. \\JOJO\share\...)
pushd "%~dp0"

echo ========================================================
echo   GW2 Skins & Legendary Craft Scraper (gw2.app)
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

echo Starting skin unlock and legendary crafting extraction...
echo.

python scrape_gw2_skins.py --workers 20 --lang fr

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred while executing scrape_gw2_skins.py.
    popd
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo Extraction completed successfully!
echo SQLite database: gw2_skins_unlocks.db
echo JSON file:       gw2_skins_unlocks.json
echo Web interface:   view_skins.html
echo ========================================================
echo.

echo Opening web interface in your browser...
start "" "view_skins.html"

popd
pause
