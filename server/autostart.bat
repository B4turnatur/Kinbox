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

rem Python wirklich starten statt nur "where": der Microsoft-Store-Platzhalter "python.exe" ist immer da
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if defined PY goto :havepy
echo [!] Python nicht gefunden. Bitte zuerst install.bat ausfuehren.
pause
exit /b 1
:havepy
rem UTF-8, passend zu chcp 65001 - sonst kommen Umlaute im Pfad (C:\Users\Juergen mit ue) kaputt an
set "PYTHONIOENCODING=utf-8"
set "PYW="
for /f "delims=" %%i in ('%PY% -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%i"
rem Kein if-Block mit %PYW%: Klammern im Pfad, z. B. "Program Files (x86)", beenden ihn sonst vorzeitig
if exist "%PYW%" goto :havepyw
echo [!] pythonw.exe nicht gefunden: "%PYW%"
pause
exit /b 1
:havepyw

echo Der Server startet danach automatisch beim Hochfahren dieses PCs -
echo auch ohne dass jemand angemeldet ist. Dafuer fragt Windows jetzt
echo nach dem Passwort deines Benutzerkontos (%USERDOMAIN%\%USERNAME%).
echo.
rem Aufgabe per XML: nur so lassen sich das 72-Stunden-Limit und "Bei Akkubetrieb beenden" abschalten.
rem Ohne Admin-Rechte (LeastPrivilege) - die Firewall-Regel legt install.bat separat an.
set "XML=%TEMP%\kinbox-task.xml"
set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"
call :writexml
schtasks /Delete /TN "Kinbox" /F >nul 2>&1
schtasks /Delete /TN "NAS-Downloader" /F >nul 2>&1
schtasks /Create /TN "Kinbox" /XML "%XML%" /RU "%USERDOMAIN%\%USERNAME%" /RP *
if errorlevel 1 goto :createfail
del "%XML%" >nul 2>&1
echo.
echo Fertig. Jetzt direkt starten? (Aufgabe laeuft unsichtbar im Hintergrund)
choice /c JN /m "Starten"
if errorlevel 2 exit /b 0
schtasks /Run /TN "Kinbox"
echo Gestartet. Zum Beenden: Aufgabenplanung ^> Kinbox ^> Beenden
pause
exit /b 0

:createfail
del "%XML%" >nul 2>&1
echo [!] Aufgabe konnte nicht angelegt werden.
pause
exit /b 1

rem ---- Aufgabe als XML (UTF-8, passend zu chcp 65001) ----------------------
rem Verzoegerte Erweiterung (!VAR!) nur hier: Pfade mit Klammern oder "&" brechen so nichts auf.
:writexml
setlocal EnableDelayedExpansion
set "C=!PYW:&=&amp;!"
set "A=!DIR:&=&amp;!"
> "%XML%" (
  echo ^<?xml version="1.0" encoding="UTF-8"?^>
  echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
  echo   ^<RegistrationInfo^>^<Description^>Kinbox-Server^</Description^>^</RegistrationInfo^>
  echo   ^<Triggers^>^<BootTrigger^>^<Enabled^>true^</Enabled^>^<Delay^>PT1M^</Delay^>^</BootTrigger^>^</Triggers^>
  echo   ^<Principals^>^<Principal id="Author"^>^<LogonType^>Password^</LogonType^>^<RunLevel^>LeastPrivilege^</RunLevel^>^</Principal^>^</Principals^>
  echo   ^<Settings^>
  echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
  echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
  echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
  echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
  echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
  echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
  echo     ^<Enabled^>true^</Enabled^>
  echo   ^</Settings^>
  echo   ^<Actions Context="Author"^>^<Exec^>
  echo     ^<Command^>!C!^</Command^>
  echo     ^<Arguments^>"!A!\server.py"^</Arguments^>
  echo     ^<WorkingDirectory^>!A!^</WorkingDirectory^>
  echo   ^</Exec^>^</Actions^>
  echo ^</Task^>
)
endlocal
exit /b 0
