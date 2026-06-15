# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('Banco_de_Datos/Cilixes', 'Banco_de_Datos/Cilixes'), ('Banco_de_Datos/Listas_de_Nombres', 'Banco_de_Datos/Listas_de_Nombres'), ('Banco_de_Datos/assets', 'Banco_de_Datos/assets'), ('Consola_de_Comando', 'Consola_de_Comando'), ('Consola_de_Comando/Logo de Carga', 'Consola_de_Comando/Logo de Carga'), ('Nucleos_Positronicos/Nucleo_de_Sonido/gba-mus-ripper', 'Nucleos_Positronicos/Nucleo_de_Sonido/gba-mus-ripper'), ('Nucleos_Positronicos/Nucleo_de_Sonido/fluidsynth_bin', 'Nucleos_Positronicos/Nucleo_de_Sonido/fluidsynth_bin')],
    hiddenimports=['Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine', 'Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.repack_portraits', 'Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits'],
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
    name='FoMT_Studio_v4.0.0_PreRelease',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FoMT_Studio_v4.0.0_PreRelease',
)
