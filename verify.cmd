@echo off
setlocal
rem verify.cmd - deliverable self-check (ASCII only, CRLF)
rem usage: verify.cmd 2008-10-26

if "%~1"=="" goto :usage
set "PDATE=%~1"
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
if "%PY%"=="" goto :nopy
"%PY%" "%HERE%\verify.py" %PDATE%
exit /b %errorlevel%

:usage
echo usage: verify.cmd ^<YYYY-MM-DD^>
exit /b 1

:nopy
echo [ERROR] python not found
exit /b 1
