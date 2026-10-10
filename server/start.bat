@echo off
chcp 65001 >nul
title Kinbox
cd /d "%~dp0"
set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
%PY% server.py
echo.
echo Server wurde beendet.
pause
