# -*- mode: python ; coding: utf-8 -*-

import os
import customtkinter

block_cipher = None

# Путь к ресурсам customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['vita_main.pyw'],
    pathex=[],
    binaries=[],
    datas=[
        ('commands.json', '.'),
        ('websites.json', '.'),
        ('enter.wav', '.'),
        ('error.wav', '.'),
        ('input.wav', '.'),
        ('open.wav', '.'),
        ('unknow_command.wav', '.'),
        (ctk_path, 'customtkinter'),
    ],
    hiddenimports=[
        'customtkinter',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._win32',
        'pywinstyles',
        'PIL',
        'PIL._imagingtk',
        'winsound',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Vitan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)