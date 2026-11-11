@echo off
setlocal
chcp 65001 >nul
title Kinbox - Installation
cd /d "%~dp0"

echo ============================================================
echo   Kinbox - Installation
echo ============================================================
echo.

set "WARN="
set "WINGET="
where winget >nul 2>&1 && set "WINGET=1"

rem ---- Python ------------------------------------------------------------
rem Python wirklich starten statt nur "where": der Microsoft-Store-Platzhalter "python.exe" ist immer da
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if defined PY goto :havepy
if defined WINGET goto :wingetpy
echo [!] Python fehlt und winget ist auf diesem PC nicht vorhanden.
echo     Bitte Python 3.12 von https://www.python.org/downloads/ installieren
echo     (dabei den Haken bei "Add python.exe to PATH" setzen) und install.bat danach NOCHMAL starten.
pause
exit /b 1
:wingetpy
echo [1/4] Python fehlt - installiere Python 3.12 ueber winget ...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
if not errorlevel 1 goto :pyinstalled
echo.
echo [!] Python konnte nicht ueber winget installiert werden (siehe Meldungen oben).
echo     Bitte Python 3.12 von https://www.python.org/downloads/ installieren
echo     (Haken bei "Add python.exe to PATH") und install.bat danach NOCHMAL starten.
pause
exit /b 1
:pyinstalled
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
if defined WINGET goto :wingettools
where ffmpeg >nul 2>&1 && where deno >nul 2>&1 && goto :toolsdone
echo     [!] winget fehlt - ffmpeg und deno bitte von Hand installieren:
echo         https://www.gyan.dev/ffmpeg/builds/  und  https://deno.com
set "WARN=1"
goto :toolsdone
:wingettools
where ffmpeg >nul 2>&1 || winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements || set "WARN=1"
where deno   >nul 2>&1 || winget install -e --id DenoLand.Deno --accept-source-agreements --accept-package-agreements || set "WARN=1"
:toolsdone

rem ---- Einsatzart ------------------------------------------------------
echo [4/4] Wie willst du Kinbox nutzen?
echo     1 = Nur auf diesem PC (Standalone: kein Netzwerk, startet bei der Anmeldung)
echo     2 = Als Server fuer alle Geraete im Heimnetz (Handy, andere PCs)
choice /c 12 /m "Auswahl"
if errorlevel 2 goto :lan

%PY% server.py --setup local
if errorlevel 1 goto :setupfail
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
if errorlevel 1 goto :setupfail
net session >nul 2>&1
if not %errorlevel%==0 goto :lanstart
echo.
choice /c JN /m "Autostart beim Hochfahren einrichten (auch ohne Anmeldung)"
if errorlevel 2 goto :lanstart
call autostart.bat
if errorlevel 1 set "WARN=1"
goto :done
:lanstart
echo.
echo   Starte den Server jetzt mit start.bat.

:done
echo.
echo ============================================================
if defined WARN (
    echo   Fertig - aber mit Warnungen, siehe Meldungen oben.
) else (
    echo   Fertig!
)
echo   Tipp: Nach der Installation von ffmpeg/deno einmal neu
echo   anmelden, damit Windows den PATH aktualisiert.
echo ============================================================
pause
exit /b 0

:setupfail
echo.
echo ============================================================
echo   [!] Einrichtung fehlgeschlagen (server.py --setup).
echo       Siehe Fehlermeldung oben. Meist fehlt ein Python-Paket:
echo       install.bat nochmal starten.
echo ============================================================
pause
exit /b 1
