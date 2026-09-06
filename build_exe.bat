@echo off
title Woody AI - Windows Executable Builder
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\build_exe.ps1"
pause
