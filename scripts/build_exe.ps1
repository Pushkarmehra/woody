# ==============================================================================
# Woody AI - Automated Windows Executable (.exe) and Installer Builder
# ==============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Woody v3.0 - Windows Executable and Installer Build   " -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# 1. Check Python
$PythonCmd = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonCmd) {
    Write-Host "[!] Error: python.exe not found in PATH." -ForegroundColor Red
    Exit 1
}
Write-Host "[+] Using Python: $PythonCmd" -ForegroundColor Green

# 2. Check / Install PyInstaller
Write-Host "`n[+] Checking PyInstaller..." -ForegroundColor Yellow
$HasPyInstaller = python -c "import PyInstaller; print('ok')" 2>$null
if ($HasPyInstaller -ne "ok") {
    Write-Host "[+] Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install --upgrade pyinstaller --trusted-host pypi.org --trusted-host files.pythonhosted.org
}

# 3. Ensure official app icon exists
$IcoPath = Join-Path $RootDir "assets\woody.ico"
if (-not (Test-Path $IcoPath)) {
    Write-Host "[!] Warning: $IcoPath not found." -ForegroundColor Yellow
} else {
    Write-Host "[+] App icon verified: $IcoPath" -ForegroundColor Green
}

# 4. Clean previous dist/build
Write-Host "`n[+] Cleaning previous build artifacts..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist\woody") { Remove-Item -Recurse -Force "dist\woody" }

# 5. Run PyInstaller
Write-Host "`n[+] Building Woody Standalone Windows Distribution with PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller woody.spec --clean --noconfirm

$ExeTarget = Join-Path $RootDir "dist\woody\woody.exe"
if (-not (Test-Path $ExeTarget)) {
    Write-Host "`n[!] PyInstaller build failed: $ExeTarget not found." -ForegroundColor Red
    Exit 1
}

Write-Host "`n[+] Standalone Executable built successfully at: $ExeTarget" -ForegroundColor Green

# 6. Create Desktop Shortcuts for the compiled executable
Write-Host "`n[+] Creating Desktop Shortcuts for compiled binary..." -ForegroundColor Cyan
$WsShell = New-Object -ComObject WScript.Shell
$DesktopDir = [Environment]::GetFolderPath("Desktop")

$Shortcuts = @(
    @{
        Name = "Woody AI"
        Args = "--pet"
        Desc = "Woody AI - Autonomous Windows Operating System & Animated Pet Companion"
    }
)

foreach ($sc in $Shortcuts) {
    $lnkPath = Join-Path $DesktopDir "$($sc.Name).lnk"
    $shortcut = $WsShell.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $ExeTarget
    $shortcut.Arguments = $sc.Args
    $shortcut.WorkingDirectory = (Split-Path -Parent $ExeTarget)
    if (Test-Path $IcoPath) {
        $shortcut.IconLocation = "$IcoPath,0"
    }
    $shortcut.Description = $sc.Desc
    $shortcut.Save()
    Write-Host "  [+] Desktop Shortcut: $lnkPath" -ForegroundColor Green
}

# 7. Check for Inno Setup (ISCC.exe) to build Setup Wizard installer
$InnoCompiler = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $InnoCompiler)) {
    $InnoCompiler = "C:\Program Files\Inno Setup 6\ISCC.exe"
}

if (Test-Path $InnoCompiler) {
    Write-Host "`n[+] Inno Setup detected. Compiling single-file Windows Installer (Woody_Setup_v3.0.exe)..." -ForegroundColor Cyan
    & $InnoCompiler "scripts\woody_installer.iss"
    $SetupExe = Join-Path $RootDir "dist\Woody_Setup_v3.0.exe"
    if (Test-Path $SetupExe) {
        Write-Host "  [+] Single-File Installer built: $SetupExe" -ForegroundColor Green
    }
} else {
    Write-Host "`n[i] Note: Inno Setup not detected (optional). Standalone executable folder is ready in dist\woody\." -ForegroundColor DarkGray
    Write-Host "    To generate Woody_Setup_v3.0.exe, install Inno Setup 6 from https://jrsoftware.org/isdl.php" -ForegroundColor DarkGray
}

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE! Woody is ready on your Desktop.       " -ForegroundColor Green
Write-Host "========================================================`n" -ForegroundColor Green
