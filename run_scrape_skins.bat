@echo off
chcp 65001 >nul

:: Verification si lance depuis un dossier reseau / chemin UNC
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\" (
    if exist Y:\ net use Y: /delete /yes >nul 2>&1
    net use Y: "%~dp0..\.." /persistent:no >nul 2>&1
    Z:
    cd \
) else (
    cd /d "%~dp0..\.."
setlocal
title GW2 Skins Unlocks Database Generator

echo ========================================================
echo   GW2 Skins Unlocks Scraper (gw2.app)
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3 and try again.
    pause
    exit /b 1
)

echo Starting skin unlock extraction...
echo.

python scrape_gw2_skins.py --workers 20 --lang fr

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] An error occurred while executing scrape_gw2_skins.py.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo Extraction completed successfully!
echo SQLite database: gw2_skins_unlocks.db
echo JSON file:       gw2_skins_unlocks.json
echo ========================================================
echo.
pause
