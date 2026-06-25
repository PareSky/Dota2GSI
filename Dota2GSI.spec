# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\server.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/speak.ps1', 'src'), ('config.yaml', '.'), ('AIPromt.md', '.'), ('gamestate_integration_gsi_config.cfg', '.'), ('Dota2MechanismOntology', 'Dota2MechanismOntology')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Dota2GSI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
