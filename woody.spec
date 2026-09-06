# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for Woody AI Operating System Layer.
Builds the standalone binary distribution including all VPet assets,
Command Center WebEngine renderer, config templates, and icon.
"""
import os
import sys
from pathlib import Path

block_cipher = None
ROOT_DIR = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(ROOT_DIR, "assets"), "assets"),
    (os.path.join(ROOT_DIR, "config"), "config"),
    (os.path.join(ROOT_DIR, "gifs"), "gifs"),
    (os.path.join(ROOT_DIR, "vpet"), "vpet"),
    (os.path.join(ROOT_DIR, "woody", "ui", "renderer"), os.path.join("woody", "ui", "renderer")),
]

hiddenimports = [
    # ASGI & FastAPI
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "fastapi.middleware.cors",
    "sse_starlette",
    "sse_starlette.sse",
    "starlette",
    "starlette.responses",
    "starlette.routing",
    # Qt & WebEngine
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    # UI & Hardware hooks
    "pynput",
    "pynput.keyboard",
    "pynput.mouse",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "tkinter",
    "tkinter.ttk",
    "psutil",
    # Woody internal modules
    "woody",
    "woody.agents",
    "woody.critic",
    "woody.ipc",
    "woody.ipc.fastapi_server",
    "woody.kernel",
    "woody.kernel.config",
    "woody.kernel.dispatch",
    "woody.kernel.kernel",
    "woody.memory",
    "woody.observability",
    "woody.perception",
    "woody.planner",
    "woody.synthesis",
    "woody.synthesis.synthesizer",
    "woody.tools",
    "woody.ui",
    "woody.ui.app",
    "woody.ui.desktop_pet",
    "woody.ui.vpet_engine",
    "woody.ui.vpet_graph",
    "woody.ui.web_overlay",
    "woody.utils",
    "woody.utils.groq_client",
    "woody.utils.hardware",
    "woody.utils.llm_factory",
    "woody.utils.logging",
    "woody.utils.paths",
    "woody.utils.shortcuts",
]

a = Analysis(
    ["main.py"],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "notebook", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="woody",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=os.path.join(ROOT_DIR, "assets", "woody.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="woody",
)
