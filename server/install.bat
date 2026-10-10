@echo off
setlocal
chcp 65001 >nul
title Kinbox - Installation
cd /d "%~dp0"

echo ============================================================
echo   Kinbox - Installation
echo ============================================================
echo.

rem ---- Python ------------------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if defined PY goto :havepy
echo [1/4] Python fehlt - installiere Python 3.12 ueber winget ...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
echo.
echo Python wurde installiert. Bitte dieses Fenster schliessen und install.bat NOCHMAL starten.
pause
exit /b 0
:havepy
echo [1/4] Python gefunden (%PY%).

rem ---- Python-Pakete -----------------------------------------------------
echo [2/4] Installiere yt-dlp, Flask und Waitress ...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install --upgrade "yt-dlp[default]" flask waitress
if errorlevel 1 (
    echo [!] pip ist fehlgeschlagen. Siehe Meldungen oben.
    pause
    exit /b 1
)

rem ---- ffmpeg + deno -----------------------------------------------------
echo [3/4] Installiere ffmpeg und deno (fuer YouTube noetig) ...
where ffmpeg >nul 2>&1 || winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
where deno   >nul 2>&1 || winget install -e --id DenoLand.Deno --accept-source-agreements --accept-package-agreements

rem ---- Firewall ----------------------------------------------------------
echo [4/4] Oeffne Port 8765 in der Windows-Firewall (nur privates Netzwerk) ...
net session >nul 2>&1
if %errorlevel%==0 (
    netsh advfirewall firewall delete rule name="Kinbox" >nul 2>&1
    netsh advfirewall firewall delete rule name="NAS-Downloader" >nul 2>&1
    netsh advfirewall firewall add rule name="Kinbox" dir=in action=allow protocol=TCP localport=8765 profile=private,domain >nul
    echo     Firewall-Regel angelegt.
) else (
    echo     [!] Keine Admin-Rechte - Firewall-Regel uebersprungen.
    echo         Rechtsklick auf install.bat ^> "Als Administrator ausfuehren", um sie anzulegen.
)

echo.
echo ============================================================
echo   Fertig! Starte jetzt start.bat.
echo   Beim ersten Start wird ein Token erzeugt und angezeigt -
echo   den traegst du in der Browser-Erweiterung ein.
echo   Tipp: Nach der Installation von ffmpeg/deno einmal neu
echo   anmelden, damit Windows den PATH aktualisiert.
echo ============================================================
pause
