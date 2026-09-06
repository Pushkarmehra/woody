@echo off
title Woody AI - Desktop Shortcut Installer
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\create_shortcuts.ps1"
pause
