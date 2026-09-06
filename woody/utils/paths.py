"""
Woody Path & Resource Resolution Utilities.

Handles dynamic path resolution across:
  • Development source trees (editable / git repo)
  • Installed site-packages distributions
  • PyInstaller frozen onefile / onedir binary bundles (sys._MEIPASS)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def get_root_dir() -> Path:
    """
    Returns the root directory containing project assets, config, and data files.
    """
    # 1. PyInstaller temporary extraction folder or bundle dir
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent

    # 2. Source repository root (woody/utils/paths.py -> 3 levels up)
    return Path(__file__).resolve().parent.parent.parent


def get_config_dir() -> Path:
    """Returns the config directory."""
    root = get_root_dir()
    cfg_dir = root / "config"
    if cfg_dir.exists():
        return cfg_dir
    # Fallback to current working directory
    return Path.cwd() / "config"


def get_default_config_path() -> Path:
    """Returns the default woody_config.yaml path."""
    return get_config_dir() / "woody_config.yaml"


def get_assets_dir() -> Path:
    """Returns the assets directory."""
    root = get_root_dir()
    assets = root / "assets"
    if assets.exists():
        return assets
    return Path.cwd() / "assets"


def get_vpet_dir() -> Path:
    """Returns the VPet simulation assets root directory."""
    root = get_root_dir()
    vpet = root / "vpet"
    if vpet.exists():
        return vpet
    return Path.cwd() / "vpet"


def get_vpet_vup_dir() -> Path:
    """Returns the official VPet core pet sprite frames directory."""
    return get_vpet_dir() / "VPet-main" / "VPet-Simulator.Windows" / "mod" / "0000_core" / "pet" / "vup"


def get_gifs_dir() -> Path:
    """Returns the fallback gifs directory."""
    root = get_root_dir()
    gifs = root / "gifs"
    if gifs.exists():
        return gifs
    return Path.cwd() / "gifs"


def get_renderer_dir() -> Path:
    """Returns the WebEngine HTML/CSS/JS renderer directory."""
    # First check internal package path
    pkg_renderer = Path(__file__).resolve().parent.parent / "ui" / "renderer"
    if pkg_renderer.exists():
        return pkg_renderer
    # Check root bundle path
    root_renderer = get_root_dir() / "woody" / "ui" / "renderer"
    if root_renderer.exists():
        return root_renderer
    return Path.cwd() / "woody" / "ui" / "renderer"
