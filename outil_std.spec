# -*- mode: python ; coding: utf-8 -*-
"""
Spec PyInstaller pour Outil STD — Assemblage ingénierie.
Build : lancer build.bat
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files
from pathlib import Path

block_cipher = None

# ---- Dépendances Streamlit (hook officiel) ----
st_datas, st_binaries, st_hidden = collect_all("streamlit")

# ---- Dépendances Plotly ----
plotly_datas, plotly_binaries, plotly_hidden = collect_all("plotly")

# ---- Fichiers de l'application ----
app_datas = [
    ("app.py",   "."),
    ("views",    "views"),
    ("core",     "core"),
    ("export",   "export"),
    ("charts",   "charts"),
    ("assets",   "assets"),
    ("config",   "config"),
]

# ---- Fichiers kaleido (collect_data_files uniquement — le sous-module mocker
#      appelle argparse.parse_args() au niveau module et fait planter collect_all)
kaleido_datas = collect_data_files("kaleido")

all_datas    = st_datas + plotly_datas + kaleido_datas + app_datas
all_binaries = st_binaries + plotly_binaries
all_hidden   = st_hidden + plotly_hidden + [
    "kaleido",
    "kaleido._sync_server",
    "kaleido._page_generator",
    "kaleido._kaleido_tab",
    "kaleido._utils",
    "kaleido.kaleido",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "docx",
    "openpyxl",
    "PIL",
    "toml",
    "tkinter",
]

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "matplotlib", "scipy", "IPython", "notebook"],
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
    name="OuiSTD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,      # console visible pour voir les erreurs
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OuiSTD",
)
