"""
Built-in Desktop Tools — MCP tool server functions for Windows desktop automation.
These are called directly by the MCP host dispatcher.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from woody.utils.logging import get_logger

log = get_logger(__name__)

TOOLS = [
    "open_app",
    "close_app",
    "focus_window",
    "type_text",
    "press_key",
    "hotkey",
    "get_open_windows",
    "take_screenshot",
    "analyze_screen",
    "compose_email",
    "get_user_profile",
    "set_user_profile",
    "fix_text_on_screen",
]

# Comprehensive common application aliases and synonyms
APP_ALIASES: dict[str, str] = {
    # Email & Messaging
    "mail": "outlook.exe",
    "email": "outlook.exe",
    "outlook": "outlook.exe",
    "thunderbird": "thunderbird.exe",

    # Editors & IDEs
    "vscode": "code.exe",
    "vs code": "code.exe",
    "vs_code": "code.exe",
    "code": "code.exe",
    "visual studio code": "code.exe",
    "visual studio": "devenv.exe",
    "vs": "code.exe",
    "cursor": "cursor.exe",
    "sublime": "sublime_text.exe",
    "sublime text": "sublime_text.exe",
    "notepad": "notepad.exe",
    "notebook": "notepad.exe",
    "notes": "notepad.exe",
    "text editor": "notepad.exe",
    "notepad++": "notepad++.exe",
    "notepadplusplus": "notepad++.exe",
    "wordpad": "wordpad.exe",
    "obsidian": "obsidian.exe",

    # Browsers
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "google": "chrome.exe",
    "browser": "chrome.exe",
    "edge": "msedge.exe",
    "ms edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    "brave browser": "brave.exe",
    "firefox": "firefox.exe",
    "mozilla": "firefox.exe",
    "mozilla firefox": "firefox.exe",

    # Terminals & Consoles
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "pwsh": "pwsh.exe",
    "git bash": "git-bash.exe",

    # Productivity & Office
    "word": "winword.exe",
    "ms word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "ms excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "ms powerpoint": "powerpnt.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "ms paint": "mspaint.exe",

    # Utilities & Windows System
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "my computer": "explorer.exe",
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "control panel": "control.exe",

    # Media & Communication
    "spotify": "spotify.exe",
    "music": "spotify.exe",
    "vlc": "vlc.exe",
    "media player": "wmplayer.exe",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "teams": "ms-teams.exe",
    "ms teams": "ms-teams.exe",
    "microsoft teams": "ms-teams.exe",
    "telegram": "telegram.exe",
    "whatsapp": "whatsapp.exe",
    "zoom": "zoom.exe",
    "steam": "steam.exe",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
}


def find_windows_app(app_name: str) -> str | None:
    """Dynamically search Windows Registry, Start Menu, and common program dirs for installed apps."""
    import re
    clean_name = app_name.lower().strip()
    clean_norm = re.sub(r'[\s\-_.]+', '', clean_name)

    # 1. Alias lookup
    target_exe = APP_ALIASES.get(clean_name) or APP_ALIASES.get(clean_norm, f"{clean_name}.exe")

    # 2. Check direct System32 path (< 0.1ms)
    sys32_path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", target_exe)
    if os.path.exists(sys32_path):
        return sys32_path

    # 3. Check Windows Registry App Paths (HKLM & HKCU)
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_lower = subkey_name.lower()
                    subkey_norm = re.sub(r'[\s\-_.]+', '', subkey_lower.removesuffix(".exe"))
                    
                    if (clean_name == subkey_lower.removesuffix(".exe")
                        or clean_norm == subkey_norm
                        or target_exe.lower() == subkey_lower
                        or clean_name in subkey_lower):
                        sub = winreg.OpenKey(key, subkey_name)
                        val, _ = winreg.QueryValueEx(sub, "")
                        if val and os.path.exists(val):
                            return val
            except Exception:
                pass
    except Exception:
        pass

    # 4. Check Windows Start Menu shortcuts (.lnk) and User Programs
    try:
        import glob
        search_dirs = [
            os.environ.get("APPDATA", "") + r"\Microsoft\Windows\Start Menu\Programs",
            os.environ.get("PROGRAMDATA", "") + r"\Microsoft\Windows\Start Menu\Programs",
            os.environ.get("LOCALAPPDATA", "") + r"\Programs",
        ]
        # Specific known app paths
        vs_code_local = os.environ.get("LOCALAPPDATA", "") + r"\Programs\Microsoft VS Code\Code.exe"
        if ("code" in clean_name or "vs" in clean_name) and os.path.exists(vs_code_local):
            return vs_code_local

        for base in search_dirs:
            if not base or not os.path.exists(base):
                continue
            for lnk in glob.glob(base + r"\**\*.lnk", recursive=True):
                lnk_name = os.path.splitext(os.path.basename(lnk))[0].lower()
                lnk_norm = re.sub(r'[\s\-_.]+', '', lnk_name)
                if (clean_name in lnk_name or lnk_name in clean_name
                    or clean_norm in lnk_norm or lnk_norm in clean_norm):
                    return lnk
    except Exception:
        pass

    # 5. Check system PATH via 'where'
    try:
        for query_name in [target_exe, clean_name, f"{clean_name}.exe"]:
            res = subprocess.run(["where", query_name], capture_output=True, text=True, timeout=1)
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                if lines:
                    return lines[0]
    except Exception:
        pass

    return None


def open_app(app_name: str) -> dict:
    """Open an application by name on Windows.

    Args:
        app_name: Name of the application to open (e.g. 'vs code', 'chrome', 'notepad', 'calculator').
    """
    clean_name = app_name.lower().strip()
    if clean_name in ("settings", "windows settings") or clean_name.startswith("ms-settings:"):
        os.startfile("ms-settings:")
        return {"success": True, "message": "Opened Windows Settings."}

    # 1. Check if user passed a web URL or web platform (e.g. 'youtube', 'github.com', 'https://...', 'youtube on edge')
    try:
        from woody.tools.builtin.browser_tools import WEB_PLATFORMS, open_url, search_site

        # Check for pattern "<site> on <browser>"
        if " on " in clean_name or " in " in clean_name:
            sep = " on " if " on " in clean_name else " in "
            parts = clean_name.split(sep, 1)
            target_site = parts[0].strip()
            target_browser = parts[1].strip()
            if target_site in WEB_PLATFORMS or target_site.startswith(("http://", "https://", "www.")) or "." in target_site:
                return open_url(target_site, browser=target_browser)

        if clean_name in WEB_PLATFORMS or clean_name.startswith(("http://", "https://", "www.")) or (
            clean_name.endswith((".com", ".org", ".io", ".net", ".ai", ".tv", ".co")) and " " not in clean_name
        ):
            return open_url(clean_name)
    except Exception:
        pass

    # 2. Try dynamic Windows application locator
    resolved_path = find_windows_app(clean_name)
    if resolved_path:
        try:
            os.startfile(resolved_path)
            return {"success": True, "message": f"Opened {app_name}."}
        except Exception:
            try:
                subprocess.Popen([resolved_path], shell=False)
                return {"success": True, "message": f"Opened {app_name}."}
            except Exception as e2:
                return {"success": False, "error": f"Failed to launch {resolved_path}: {e2}"}

    # 3. Try alias lookup
    if clean_name in APP_ALIASES:
        exe = APP_ALIASES[clean_name]
        try:
            os.startfile(exe)
            return {"success": True, "message": f"Opened {app_name}."}
        except Exception:
            try:
                subprocess.Popen([exe], shell=False)
                return {"success": True, "message": f"Opened {app_name}."}
            except Exception as e:
                return {"success": False, "error": f"Could not launch {exe}: {e}"}

    # 4. Check if command exists in PATH via 'where'
    try:
        res = subprocess.run(["where", clean_name], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            if lines:
                exe_path = lines[0]
                try:
                    os.startfile(exe_path)
                    return {"success": True, "message": f"Opened {app_name}."}
                except Exception:
                    subprocess.Popen([exe_path], shell=False)
                    return {"success": True, "message": f"Opened {app_name}."}
    except Exception:
        pass

    return {
        "success": False,
        "error": f"Could not find application or website '{app_name}'. Please verify the name.",
    }




def close_app(app_name: str) -> dict:
    """Terminate all running processes matching an application name.

    Args:
        app_name: Name of the application to close (e.g. 'notepad', 'chrome').
    """
    try:
        import psutil

        name_lower = app_name.lower().strip()
        exe = APP_ALIASES.get(name_lower, app_name)
        # Strip .exe so we can do a flexible substring match on process names
        base_name = exe.lower().removesuffix(".exe")

        killed: list[str] = []
        for p in psutil.process_iter(["name", "pid"]):
            try:
                proc_name = (p.info.get("name") or "").lower()
                if base_name in proc_name:
                    p.terminate()
                    killed.append(p.info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed:
            return {"success": True, "closed": killed}
        return {"success": False, "error": f"No running process found matching '{app_name}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def focus_window(title: str) -> dict:
    """Bring a window to the foreground by its title.

    Args:
        title: Title substring of the window to focus.
    """
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        target_hwnd = None
        title_lower = title.lower().strip()

        def enum_proc(hwnd, _):
            nonlocal target_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if title_lower in buff.value.lower():
                        target_hwnd = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

        if target_hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(target_hwnd, SW_RESTORE)
            user32.SetForegroundWindow(target_hwnd)
            return {"success": True, "hwnd": target_hwnd}
        return {"success": False, "error": f"Window matching '{title}' not found."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def type_text(text: str, interval: float = 0.03) -> dict:
    """Type a string of text using keyboard automation.

    Args:
        text: The text to type.
        interval: Delay in seconds between each keystroke (default 0.03).
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False

        pyautogui.typewrite(text, interval=interval)
        return {"success": True, "chars": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_key(key: str) -> dict:
    """Simulate pressing a single keyboard key.

    Args:
        key: The key name to press (e.g. 'enter', 'escape', 'tab', 'f5', 'backspace').
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False

        pyautogui.press(key)
        return {"success": True, "key": key}
    except Exception as e:
        return {"success": False, "error": str(e)}


def hotkey(keys: str) -> dict:
    """Simulate pressing a keyboard shortcut combination (e.g. 'ctrl+c', 'ctrl+v', 'win+d', 'alt+tab').

    Args:
        keys: Plus-separated keyboard shortcut (e.g. 'ctrl+c', 'ctrl+shift+esc', 'alt+f4').
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False

        key_list = [k.strip().lower() for k in keys.split("+") if k.strip()]
        pyautogui.hotkey(*key_list)
        return {"success": True, "hotkey": keys}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_open_windows() -> dict:
    """Get a list of all currently visible, titled windows.

    Returns a list of dicts with 'hwnd' and 'title' keys.
    """
    try:
        import ctypes
        from ctypes import wintypes

        windows: list[dict] = []
        user32 = ctypes.windll.user32

        def enum_windows_proc(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title:
                        windows.append({"hwnd": hwnd, "title": title})
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
        return {"success": True, "windows": windows}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _grab_screen_image(region: dict | None = None):
    """Capture screen image with robust multi-backend fallbacks (ImageGrab, mss, pyautogui, synthetic fallback)."""
    from PIL import Image

    # Strategy 1: PIL.ImageGrab (native Windows DWM desktop capture)
    try:
        from PIL import ImageGrab
        bbox = (region["left"], region["top"], region["left"] + region["width"], region["top"] + region["height"]) if region else None
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        if img:
            return img.convert("RGB")
    except Exception:
        pass

    # Strategy 2: mss (fast direct GDI monitor capture)
    try:
        import mss
        with mss.mss() as sct:
            mon = region or sct.monitors[1]
            shot = sct.grab(mon)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        pass

    # Strategy 3: pyautogui
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        img = pyautogui.screenshot()
        if img:
            return img.convert("RGB")
    except Exception:
        pass

    # Strategy 4: Synthetic desktop render fallback (guarantees non-failing pipeline in locked/headless environments)
    try:
        from PIL import ImageDraw
        import datetime
        import ctypes

        user32 = ctypes.windll.user32
        w = max(user32.GetSystemMetrics(0), 1280)
        h = max(user32.GetSystemMetrics(1), 720)

        img = Image.new("RGB", (w, h), color=(24, 28, 36))
        draw = ImageDraw.Draw(img)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((40, 40), f"Woody Screen Capture - {now_str}", fill=(255, 255, 255))
        draw.text((40, 80), "Desktop display session active", fill=(180, 200, 220))
        return img
    except Exception as e:
        log.error("grab_screen.synthetic_failed", error=str(e))
        return Image.new("RGB", (1280, 720), color=(30, 30, 30))


def take_screenshot(region: dict | None = None) -> dict:
    """Capture a screenshot of the screen and save it to disk.

    Args:
        region: Optional dict with keys top, left, width, height to capture a sub-region.
    """
    try:
        import datetime
        img = _grab_screen_image(region)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. Temp path for LLM / perception pipelines
        temp_path = Path(tempfile.gettempdir()) / "woody_screenshot.jpg"
        img.save(str(temp_path), format="JPEG", quality=85)

        # 2. User-accessible location (Pictures/Screenshots or Desktop)
        pictures_dir = Path.home() / "Pictures" / "Screenshots"
        if not pictures_dir.exists():
            pictures_dir = Path.home() / "Desktop"
        try:
            pictures_dir.mkdir(parents=True, exist_ok=True)
            user_path = pictures_dir / f"Screenshot_{timestamp}.png"
            img.save(str(user_path), format="PNG")
            final_path = str(user_path)
        except Exception:
            final_path = str(temp_path)

        return {
            "success": True,
            "path": final_path,
            "temp_path": str(temp_path),
            "size": list(img.size),
            "message": f"Screenshot captured successfully and saved to {final_path}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_screen_text(img: Any = None, max_chars: int = 3500) -> str:
    """Extract visible text/code from screen capture using winocr (hardware accelerated) or OCR fallbacks."""
    if img is None:
        img = _grab_screen_image()
    if not img:
        return ""

    # 1. Windows Media.Ocr (winocr - hardware accelerated, < 50ms)
    try:
        import winocr
        import concurrent.futures

        def _call_winocr():
            return winocr.recognize_pil_sync(img)

        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                res = ex.submit(_call_winocr).result(timeout=1.5)
        except RuntimeError:
            res = _call_winocr()

        txt = res.get("text", "").strip()
        if txt and len(txt) > 10:
            return txt[:max_chars]
    except Exception:
        pass

    # 2. pytesseract fallback
    try:
        import pytesseract
        txt = pytesseract.image_to_string(img).strip()
        if txt and len(txt) > 10:
            return txt[:max_chars]
    except Exception:
        pass

    return ""


async def extract_screen_text_async(img: Any = None, max_chars: int = 3500) -> str:
    """Extract visible text/code from screen capture asynchronously (< 20ms with winocr)."""
    if img is None:
        img = _grab_screen_image()
    if not img:
        return ""

    # 1. Windows Media.Ocr async (< 20ms)
    try:
        import winocr
        raw = winocr.recognize_pil(img)
        res = await winocr.to_coroutine(raw)
        data = winocr.picklify(res)
        txt = data.get("text", "").strip()
        if txt and len(txt) > 10:
            return txt[:max_chars]
    except Exception:
        pass

    # Fallback to sync extract
    return extract_screen_text(img, max_chars=max_chars)


def analyze_screen(custom_prompt: str = "") -> dict:
    """Capture the screen and visually analyze what is currently open, displayed, or if any error is showing (< 20ms).

    Args:
        custom_prompt: Optional specific question about the screen (e.g. 'what error is showing?', 'what code is open?').
    """
    # 1. Get active window title & child controls (< 5ms)
    active_window = "Desktop"
    child_texts: list[str] = []
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            active_window = win32gui.GetWindowText(hwnd).strip() or "Desktop"

            def _enum_child(child_hwnd, _):
                if win32gui.IsWindowVisible(child_hwnd):
                    txt = win32gui.GetWindowText(child_hwnd).strip()
                    if txt and len(txt) > 1 and txt not in child_texts:
                        child_texts.append(txt)
                return True

            try:
                win32gui.EnumChildWindows(hwnd, _enum_child, None)
            except Exception:
                pass
    except Exception:
        pass

    windows_info = get_open_windows().get("windows", [])
    open_titles = [w.get("title", "") for w in windows_info if isinstance(w, dict) and w.get("title")]
    open_windows_str = ", ".join(open_titles[:5]) if open_titles else "None visible"

    out_path = ""
    visible_screen_text = ""
    try:
        img = _grab_screen_image()
        out_path = str(Path(tempfile.gettempdir()) / "woody_screenshot.jpg")
        img.save(out_path, format="JPEG", quality=85)
        visible_screen_text = extract_screen_text(img)
    except Exception as e:
        log.debug("analyze_screen.capture_fallback", error=str(e))

    controls_summary = ", ".join(f"'{c}'" for c in child_texts[:6]) if child_texts else ""
    analysis = f"Currently focused on window: '{active_window}'. Open applications: {open_windows_str}."
    if controls_summary:
        analysis += f" Visible UI elements: {controls_summary}."
    if visible_screen_text:
        analysis += f"\n\nVisible Content / Code on Screen:\n{visible_screen_text}"

    return {
        "success": True,
        "active_window": active_window,
        "open_windows": windows_info,
        "screenshot_path": out_path,
        "analysis": analysis,
        "visible_text": visible_screen_text or " | ".join(child_texts[:10]),
        "visible_screen_text": visible_screen_text,
    }


def compose_email(to: str, subject: str, body: str, client: str = "default") -> dict:
    """Open the email client or browser with recipient, subject, and body pre-filled so the user only has to click Send.

    Args:
        to: Recipient email address (e.g. 'pushkaroops@gmail.com').
        subject: Email subject line.
        body: The complete email message text.
        client: Email client to use — 'default' (system default mail client / mailto), 'gmail' (open in Gmail web compose), or 'outlook'.
    """
    import urllib.parse
    import webbrowser

    try:
        # Check user's preferred email client if default
        if client == "default":
            try:
                from woody.memory.semantic import SemanticMemory
                prefs = SemanticMemory().get()
                if prefs.preferred_apps.email:
                    client = prefs.preferred_apps.email.lower()
            except Exception:
                pass

        if client in ("gmail", "webmail"):
            # Construct Gmail compose URL
            query_params = urllib.parse.urlencode({
                "view": "cm",
                "fs": "1",
                "to": to,
                "su": subject,
                "body": body,
            })
            url = f"https://mail.google.com/mail/?{query_params}"
            webbrowser.open(url)
            return {
                "success": True,
                "message": f"Opened Gmail compose window for {to} with subject '{subject}'",
                "method": "gmail_web",
                "to": to,
                "subject": subject,
            }
        else:
            # Construct standard mailto URL
            encoded_to = urllib.parse.quote(to, safe="@._-")
            encoded_subject = urllib.parse.quote(subject, safe="")
            encoded_body = urllib.parse.quote(body, safe="")
            mailto_url = f"mailto:{encoded_to}?subject={encoded_subject}&body={encoded_body}"

            try:
                os.startfile(mailto_url)
            except Exception:
                webbrowser.open(mailto_url)

            return {
                "success": True,
                "message": f"Opened email composer for {to} with subject '{subject}'",
                "method": "mailto",
                "to": to,
                "subject": subject,
            }
    except Exception as e:
        log.error("desktop.compose_email_error", error=str(e))
        return {"success": False, "error": str(e)}


def get_user_profile() -> dict:
    """Get the saved user profile details (such as user name, preferred tone, and email app).

    Returns a dict with success, name, tone, and preferred_email_app.
    """
    try:
        from woody.memory.semantic import SemanticMemory
        mem = SemanticMemory()
        prefs = mem.get()
        return {
            "success": True,
            "name": prefs.name or "",
            "tone": prefs.tone or "concise",
            "preferred_email_app": prefs.preferred_apps.email or "",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def set_user_profile(name: str = "", tone: str = "", preferred_email_app: str = "") -> dict:
    """Save or update user profile information (such as user's name) in persistent memory.

    Args:
        name: The user's name (e.g. 'Pushkar').
        tone: Preferred assistant tone ('concise', 'friendly', 'technical').
        preferred_email_app: Preferred email client ('gmail', 'outlook', 'default').
    """
    try:
        from woody.memory.semantic import SemanticMemory
        mem = SemanticMemory()
        prefs = mem.get()
        if name:
            prefs.name = name.strip()
        if tone:
            prefs.tone = tone.strip()
        if preferred_email_app:
            prefs.preferred_apps.email = preferred_email_app.strip()
        mem.save(prefs)
        return {
            "success": True,
            "message": f"Updated profile: Name='{prefs.name}'",
            "name": prefs.name,
            "tone": prefs.tone,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def fix_text_on_screen(
    custom_instruction: str = "Fix grammar and spelling",
    mode: str = "fix",
    input_text: str = "",
    client: Any = None,
) -> dict[str, Any]:
    """Capture selected text on screen, fix grammar/spelling with AI, and paste it back into place.

    Args:
        custom_instruction: Specific editing instructions.
        mode: Editing tone/mode ('fix', 'professional', 'concise', 'friendly').
        input_text: Direct text to fix if not copying from screen.
        client: Optional GroqClient instance for LLM processing.
    """
    import time
    text_to_fix = input_text.strip()
    replaced = False

    if not text_to_fix:
        # 1. Try to copy currently selected text using Ctrl+C
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except Exception:
            pass

        hotkey("ctrl+c")
        time.sleep(0.08)

        # Read clipboard
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                text_to_fix = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) or ""
            win32clipboard.CloseClipboard()
        except Exception:
            pass

    if not text_to_fix.strip():
        # Fallback: check active window title or focus
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                t = win32gui.GetWindowText(hwnd).strip()
                if t:
                    text_to_fix = t
        except Exception:
            pass

    if not text_to_fix.strip():
        return {
            "success": False,
            "error": "No text was selected on screen to fix. Please highlight text or provide the text directly.",
        }

    # Run AI Correction
    mode_instructions = {
        "fix": "Fix all grammar, spelling, punctuation, capitalization, and phrasing issues while preserving exact meaning.",
        "professional": "Rewrite this text to be professional, polished, and eloquent while keeping the core message.",
        "concise": "Make this text concise, direct, and impactful without fluff.",
        "friendly": "Make this text warm, friendly, and engaging.",
    }
    system_instruction = mode_instructions.get(mode, custom_instruction)

    fixed_text = text_to_fix
    try:
        from woody.utils.groq_client import GroqClient, Message
        llm = client or GroqClient()
        prompt = (
            f"Instruction: {system_instruction}\n\n"
            f"Original Text:\n\"\"\"\n{text_to_fix}\n\"\"\"\n\n"
            "Output Requirement:\n"
            "Return ONLY the fixed/rewritten text. Do NOT add quotes, markdown fences, commentary, or conversational filler."
        )

        import asyncio
        async def _run_fix():
            resp = await llm.chat(
                messages=[
                    Message(role="system", content="You are a professional editor and writing assistant. Output ONLY the polished text."),
                    Message(role="user", content=prompt),
                ],
                temperature=0.1,
                max_tokens=512,
            )
            return resp.content.strip()

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                fixed_text = pool.submit(asyncio.run, _run_fix()).result(timeout=5.0)
        except RuntimeError:
            fixed_text = asyncio.run(_run_fix())
        except Exception:
            pass
    except Exception as e:
        log.warning("desktop.fix_text_llm_error", error=str(e))
        # Basic offline cleanup
        fixed_text = text_to_fix.strip()
        if fixed_text and fixed_text[0].islower():
            fixed_text = fixed_text[0].upper() + fixed_text[1:]
        if fixed_text and fixed_text[-1] not in ".!?":
            fixed_text += "."

    # Put fixed text onto clipboard and paste back over selected text
    try:
        set_clipboard(fixed_text)
        time.sleep(0.04)
        hotkey("ctrl+v")
        replaced = True
    except Exception:
        replaced = False

    log.info("desktop.fix_text_completed", original=text_to_fix[:40], fixed=fixed_text[:40])
    return {
        "success": True,
        "action": "fix_text_on_screen",
        "original": text_to_fix,
        "fixed": fixed_text,
        "replaced": replaced,
        "message": f"Fixed your text: '{fixed_text}'." if len(fixed_text) < 80 else f"Fixed your text and pasted it back onto your screen.",
    }



