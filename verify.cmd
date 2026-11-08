@echo off
setlocal
rem verify.cmd - deliverable self-check (ASCII only, CRLF)
rem usage: verify.cmd 2008-10-26

if "%~1"=="" goto :usage
set "PDATE=%~1"
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

set "PY="
if exist "C:\Users\34684\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=C:\Users\34684\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not "%PY%"=="" goto :havepy
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

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
