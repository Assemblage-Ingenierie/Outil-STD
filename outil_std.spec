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

# ---- Fenêtre native (pywebview + pythonnet/clr) ----
# pywebview embarque des ressources JS/HTML ; le backend Windows (winforms)
# passe par pythonnet (clr_loader). collect_all récupère datas + binaires +
# sous-modules. À VALIDER au build : si la fenêtre native échoue, l'app retombe
# automatiquement sur le navigateur (cf. run_app.py).
webview_datas, webview_binaries, webview_hidden = collect_all("webview")
clr_datas, clr_binaries, clr_hidden = collect_all("clr_loader")

# ---- Fichiers de l'application ----
app_datas = [
    ("app.py",   "."),
    ("views",    "views"),
    ("core",     "core"),
    ("export",   "export"),
    ("charts",   "charts"),
    ("assets",   "assets"),
    ("config",   "config"),
    (".streamlit", ".streamlit"),   # config.toml (toolbarMode minimal, thème…)
]

# ---- Fichiers kaleido (collect_data_files uniquement — le sous-module mocker
#      appelle argparse.parse_args() au niveau module et fait planter collect_all)
kaleido_datas = collect_data_files("kaleido")

all_datas    = st_datas + plotly_datas + kaleido_datas + webview_datas + clr_datas + app_datas
all_binaries = st_binaries + plotly_binaries + webview_binaries + clr_binaries
all_hidden   = st_hidden + plotly_hidden + webview_hidden + clr_hidden + [
    "kaleido",
    "kaleido._sync_server",
    "kaleido._page_generator",
    "kaleido._kaleido_tab",
    "kaleido._utils",
    "kaleido.kaleido",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "docx",
    "PIL",
    "toml",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.ttk",
    # Fenêtre native
    "webview",
    "webview.platforms.winforms",
    "clr",
    "clr_loader",
    "bottle",
    "proxy_tools",
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
    excludes=["pytest", "scipy", "IPython", "notebook"],
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
    name="Outil STD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,     # terminal masqué (logs → %LOCALAPPDATA%/OutilSTD/*.log)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/sigle_Ai.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Outil STD",
)
