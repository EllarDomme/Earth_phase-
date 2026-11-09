@echo off
setlocal

rem run.cmd - one-command poster builder (ASCII only; see AGENTS.md)
rem usage: run.cmd 2003-09-23 [legacy|noboost|keep-tmp|boostlast]
rem default = uniform + boost-first
rem   Doubao only sharpens the Earth disc; the moon is never touched

if "%~1"=="" goto :usage
set "PDATE=%~1"
set "MODE=%~2"
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

set "PY="
if exist "%HERE%\python.txt" for /f "usebackq delims=" %%i in ("%HERE%\python.txt") do if not defined PY set "PY=%%i"
if defined PY goto :havepy
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if defined PY goto :havepy
for /d %%v in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if not defined PY if exist "%%~v\python.exe" set "PY=%%~v\python.exe"
if defined PY goto :havepy
for /d %%v in ("%ProgramFiles%\Python3*") do if not defined PY if exist "%%~v\python.exe" set "PY=%%~v\python.exe"
:havepy
if not defined PY goto :nopy

if "%MODE%"=="check" goto :docheck

powershell -NoProfile -Command "try{Invoke-WebRequest 'http://127.0.0.1:9225/json/version' -TimeoutSec 3 -UseBasicParsing|Out-Null;exit 0}catch{exit 1}" >nul 2>nul
if errorlevel 1 goto :nocdp

:runfull
echo.
echo === poster %PDATE% (mode: %MODE%) ===
echo python: %PY%
if "%MODE%"=="legacy" goto :run_legacy
if "%MODE%"=="noboost" goto :run_noboost
if "%MODE%"=="keep-tmp" goto :run_keeptmp
if "%MODE%"=="boostfirst" goto :run_uniform
if "%MODE%"=="boostlast" goto :run_uniform_last
goto :run_uniform

:run_legacy
"%PY%" "%HERE%\make_earth_full.py" %PDATE% --size 2048 --polish --archive --moon --boost --boost-last
goto :after

:run_noboost
"%PY%" "%HERE%\make_earth_full.py" %PDATE% --size 2048 --polish --archive --moon --uniform
goto :after

:run_keeptmp
"%PY%" "%HERE%\make_earth_full.py" %PDATE% --size 2048 --polish --archive --moon --boost --uniform --no-clean
goto :after

:run_uniform_last
"%PY%" "%HERE%\make_earth_full.py" %PDATE% --size 2048 --polish --archive --moon --boost --boost-last --uniform
exit /b %errorlevel%


:run_uniform
"%PY%" "%HERE%\make_earth_full.py" %PDATE% --size 2048 --polish --archive --moon --boost --uniform
goto :after

:docheck
"%PY%" "%HERE%\make_earth_full.py" %PDATE% --check
exit /b %errorlevel%

:after
set "RC=%errorlevel%"
if not "%RC%"=="0" goto :failed
echo.
echo === outputs ===
for %%f in ("%HERE%\??\%PDATE%*.png") do echo   %%~nxf  %%~zf bytes
exit /b 0

:usage
echo usage: run.cmd ^<YYYY-MM-DD^> [legacy^|noboost^|keep-tmp^|uniform]
echo   boostlast = OLD order (Doubao re-polishes the moon; not recommended)
echo   default = uniform (recommended)
exit /b 1

:nopy
echo [ERROR] python not found
exit /b 1

:nocdp
echo.
echo [WARN] Doubao is not running with the debug port (9225).
echo        This pipeline needs it for the two polish rounds.
echo.
echo   Step 1  close Doubao completely (a fresh start is required):
echo             taskkill /F /IM Doubao.exe
echo.
echo   Step 2  print the exact path + start command:
echo             python config.py
echo.
echo   Step 3  run that Start-Process line, then re-run this command.
echo.
echo   (No admin rights needed. An already-running Doubao will NOT
echo    open the port, so step 1 is not optional.)
echo.
exit /b 1

:failed
echo.
echo [FAILED] exit code %RC% - do not use intermediate files as deliverables
exit /b %RC%
