@echo off
setlocal
chcp 65001 >nul
title Kinbox - Autostart einrichten
cd /d "%~dp0"

net session >nul 2>&1
if not %errorlevel%==0 (
    echo Bitte mit Rechtsklick ^> "Als Administrator ausfuehren" starten.
    pause
    exit /b 1
)

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
for /f "delims=" %%i in ('%PY% -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%i"
if not exist "%PYW%" (
    echo [!] pythonw.exe nicht gefunden: %PYW%
    pause
    exit /b 1
)

echo Der Server startet danach automatisch beim Hochfahren dieses PCs -
echo auch ohne dass jemand angemeldet ist. Dafuer fragt Windows jetzt
echo nach dem Passwort deines Benutzerkontos (%USERDOMAIN%\%USERNAME%).
echo.
schtasks /Delete /TN "Kinbox" /F >nul 2>&1
schtasks /Delete /TN "NAS-Downloader" /F >nul 2>&1
schtasks /Create /TN "Kinbox" /SC ONSTART /DELAY 0001:00 /RL HIGHEST ^
  /RU "%USERDOMAIN%\%USERNAME%" /RP * ^
  /TR "\"%PYW%\" \"%~dp0server.py\""
if errorlevel 1 (
    echo [!] Aufgabe konnte nicht angelegt werden.
    pause
    exit /b 1
)
echo.
echo Fertig. Jetzt direkt starten? (Aufgabe laeuft unsichtbar im Hintergrund)
choice /c JN /m "Starten"
if errorlevel 2 goto :eof
schtasks /Run /TN "Kinbox"
echo Gestartet. Zum Beenden: Aufgabenplanung ^> Kinbox ^> Beenden
pause
