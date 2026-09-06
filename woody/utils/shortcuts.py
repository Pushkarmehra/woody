"""
Woody Desktop & Start Menu Shortcut Creator for Windows.

Creates .lnk shortcuts with the official Woody AI icon for:
  1. Woody AI Operating System (Full Native Mode)
  2. Woody AI Desktop Pet (--pet)
  3. Woody Command Center (--web-ui)
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

from woody.utils.logging import get_logger
from woody.utils.paths import get_assets_dir, get_root_dir

log = get_logger(__name__)


def create_windows_shortcut(
    target_path: str | Path,
    shortcut_path: str | Path,
    arguments: str = "",
    icon_path: str | Path | None = None,
    working_dir: str | Path | None = None,
    description: str = "Woody AI Operating System",
) -> bool:
    """Creates a Windows .lnk shortcut using PowerShell COM object."""
    target_path = Path(target_path).resolve()
    shortcut_path = Path(shortcut_path).resolve()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    working_dir = Path(working_dir).resolve() if working_dir else target_path.parent
    icon_str = str(Path(icon_path).resolve()) if icon_path and Path(icon_path).exists() else str(target_path)

    ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{str(shortcut_path)}')
$s.TargetPath = '{str(target_path)}'
$s.Arguments = '{arguments}'
$s.WorkingDirectory = '{str(working_dir)}'
$s.IconLocation = '{icon_str},0'
$s.Description = '{description}'
$s.Save()
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0 and shortcut_path.exists():
            log.info("shortcut.created", path=str(shortcut_path))
            return True
        else:
            log.warning("shortcut.failed", stderr=res.stderr)
            return False
    except Exception as e:
        log.warning("shortcut.error", error=str(e))
        return False


def install_all_shortcuts(desktop: bool = True, start_menu: bool = True) -> list[Path]:
    """
    Installs Woody desktop and start menu shortcuts with custom icons.
    """
    created: list[Path] = []
    
    # Determine executable target
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
        work_dir = exe_path.parent
    else:
        # Running from Python source / venv
        exe_path = Path(sys.executable)
        work_dir = get_root_dir()

    ico_path = get_assets_dir() / "woody.ico"
    if not ico_path.exists():
        ico_path = get_root_dir() / "assets" / "woody.ico"

    destinations: list[Path] = []
    if desktop:
        desktop_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        if desktop_dir.exists():
            destinations.append(desktop_dir)

    if start_menu:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            sm_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Woody AI"
            destinations.append(sm_dir)

    # Shortcut definitions: (Name, CLI args, Description)
    is_frozen = getattr(sys, "frozen", False)
    
    shortcuts = [
        (
            "Woody AI",
            "--pet" if is_frozen else "-m woody --pet",
            "Woody AI - Autonomous Windows Operating System & Animated Pet Companion",
        ),
    ]

    for base_dir in destinations:
        for name, args, desc in shortcuts:
            lnk_path = base_dir / f"{name}.lnk"
            ok = create_windows_shortcut(
                target_path=exe_path,
                shortcut_path=lnk_path,
                arguments=args,
                icon_path=ico_path,
                working_dir=work_dir,
                description=desc,
            )
            if ok:
                created.append(lnk_path)

    return created
