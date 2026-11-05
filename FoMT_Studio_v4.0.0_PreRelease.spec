# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('Banco_de_Datos/INTegerGuard.dll', 'Banco_de_Datos'),
    ],
    datas=[
        ('Banco_de_Datos', 'Banco_de_Datos'),
        ('Consola_de_Comando', 'Consola_de_Comando'),
        ('Consola_de_Comando/Logo de Carga', 'Consola_de_Comando/Logo de Carga'),
        ('Nucleos_Positronicos/Nucleo_de_Sonido/gba-mus-ripper', 'Nucleos_Positronicos/Nucleo_de_Sonido/gba-mus-ripper'),
        ('Nucleos_Positronicos/Nucleo_de_Sonido/fluidsynth_bin', 'Nucleos_Positronicos/Nucleo_de_Sonido/fluidsynth_bin'),
        ('fomt_config.json', '.'),
    ],
    hiddenimports=[
        'Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine',
        'Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.repack_portraits',
        'Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits',
    ],
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
    name='FoMT_Studio_v4.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Icono_Fomt_Studio.ico'],
    version='version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FoMT_Studio_v4.0.0',
)
