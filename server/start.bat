@echo off
chcp 65001 >nul
title Kinbox
cd /d "%~dp0"
rem Python wirklich starten statt nur "where": der Microsoft-Store-Platzhalter "python.exe" ist immer da
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if defined PY goto :run
echo [!] Python nicht gefunden. Bitte zuerst install.bat ausfuehren.
pause
exit /b 1
:run
%PY% server.py
echo.
echo Server wurde beendet.
pause
