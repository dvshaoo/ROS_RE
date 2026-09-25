# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['tester_build_src/server/local_baseapp_capture.py'],
    pathex=['scratch/tester_build_src/server', 'scratch/tester_build_src/tools'],
    binaries=[],
    datas=[],
    hiddenimports=['load_table', 'Crypto.Cipher.Blowfish'],
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
    [],
    exclude_binaries=True,
    name='ROS_LAN_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ROS_LAN_Server',
)
