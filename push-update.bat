@echo off
set "GIT=C:/Users/DELL/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin/git.exe"
cd /d "C:/Users/DELL/WorkBuddy/2026-10-04-19-52-29/AI-Coding-JudgeX"
%GIT% add .
%GIT% commit -m "docs: add CI badge and contributing guide"
%GIT% push origin main
echo.
echo Exit code: %ERRORLEVEL%
pause
