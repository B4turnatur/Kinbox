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
%PY% -m pip install --upgrade "yt-dlp[default]" gallery-dl flask waitress
if errorlevel 1 (
    echo [!] pip ist fehlgeschlagen. Siehe Meldungen oben.
    pause
    exit /b 1
)

rem ---- ffmpeg + deno -----------------------------------------------------
echo [3/4] Installiere ffmpeg und deno (fuer YouTube noetig) ...
where ffmpeg >nul 2>&1 || winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
where deno   >nul 2>&1 || winget install -e --id DenoLand.Deno --accept-source-agreements --accept-package-agreements

rem ---- Einsatzart ------------------------------------------------------
echo [4/4] Wie willst du Kinbox nutzen?
echo     1 = Nur auf diesem PC (Standalone: kein Netzwerk, startet bei der Anmeldung)
echo     2 = Als Server fuer alle Geraete im Heimnetz (Handy, andere PCs)
choice /c 12 /m "Auswahl"
if errorlevel 2 goto :lan

%PY% server.py --setup local
goto :done

:lan
net session >nul 2>&1
if %errorlevel%==0 (
    netsh advfirewall firewall delete rule name="Kinbox" >nul 2>&1
    netsh advfirewall firewall delete rule name="NAS-Downloader" >nul 2>&1
    netsh advfirewall firewall add rule name="Kinbox" dir=in action=allow protocol=TCP localport=8765 profile=private,domain >nul
    echo     Firewall-Regel angelegt ^(nur privates Netzwerk^).
) else (
    echo     [!] Keine Admin-Rechte - Firewall-Regel und Autostart uebersprungen.
    echo         Rechtsklick auf install.bat ^> "Als Administrator ausfuehren", um sie einzurichten.
)
%PY% server.py --setup lan
net session >nul 2>&1
if not %errorlevel%==0 goto :lanstart
echo.
choice /c JN /m "Autostart beim Hochfahren einrichten (auch ohne Anmeldung)"
if errorlevel 2 goto :lanstart
call autostart.bat
goto :done
:lanstart
echo.
echo   Starte den Server jetzt mit start.bat.

:done
echo.
echo ============================================================
echo   Fertig!
echo   Tipp: Nach der Installation von ffmpeg/deno einmal neu
echo   anmelden, damit Windows den PATH aktualisiert.
echo ============================================================
pause
