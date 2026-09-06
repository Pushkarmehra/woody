# ==============================================================================
# Woody AI — Windows Desktop & Start Menu Shortcut Generator
# Creates .lnk shortcuts with the official Woody AI icon for:
#   1. Woody AI Operating System
#   2. Woody AI Desktop Pet (--pet)
#   3. Woody Command Center (--web-ui)
# ==============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$AssetsDir = Join-Path $RootDir "assets"
$IconPath = Join-Path $AssetsDir "woody.ico"

# Find Python executable
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$SystemPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source

$PythonExe = if (Test-Path $VenvPython) { $VenvPython } elseif ($SystemPython) { $SystemPython } else { "python.exe" }

$DesktopDir = [Environment]::GetFolderPath("Desktop")
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("ApplicationData")) "Microsoft\Windows\Start Menu\Programs\Woody AI"

if (-not (Test-Path $StartMenuDir)) {
    New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
}

$Shortcuts = @(
    @{
        Name = "Woody AI"
        Args = "-m woody --pet"
        Desc = "Woody AI - Autonomous Windows Operating System & Animated Pet Companion"
    }
)

$WsShell = New-Object -ComObject WScript.Shell

Write-Host "`n🌟 Creating Woody AI Desktop & Start Menu Shortcuts..." -ForegroundColor Cyan

foreach ($dest in @($DesktopDir, $StartMenuDir)) {
    foreach ($sc in $Shortcuts) {
        $lnkPath = Join-Path $dest "$($sc.Name).lnk"
        $shortcut = $WsShell.CreateShortcut($lnkPath)
        $shortcut.TargetPath = $PythonExe
        $shortcut.Arguments = $sc.Args
        $shortcut.WorkingDirectory = $RootDir
        if (Test-Path $IconPath) {
            $shortcut.IconLocation = "$IconPath,0"
        }
        $shortcut.Description = $sc.Desc
        $shortcut.Save()
        Write-Host "  [+] Created: $lnkPath" -ForegroundColor Green
    }
}

Write-Host "`n✨ All desktop shortcuts and start menu entries installed successfully!`n" -ForegroundColor Cyan
