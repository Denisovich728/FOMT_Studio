# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
parche_splash.py - Inyector de Splash y Autoridad Central de Integridad de ROM
Garantiza que toda ROM procesada por FOMT Studio contenga la firma binaria
obligatoria 'CILIXES', el splash de inicio inyectado en hardware GBA y el
sello criptografico de autenticidad SHA-256 cifrado con Vigenere en offsets
exclusivos para FoMT y MFoMT.
"""

import ctypes
import hashlib
import os
import struct
from typing import Any, Dict, Optional, Union

from Banco_de_Datos.Utilidades.rutas import get_resource_path


class RomIntegrityError(RuntimeError):
    """Excepcion lanzada cuando una ROM o el entorno no cuenta con la firma de integridad obligatoria."""
    pass


# ============================================================
#  CARGADOR DE GUARDIAN BINARIO NATIVO (INTEGERGUARD.DLL)
#  Proteccion estricta de autoria bajo GPLv3 Seccion 7(b)
#  Handshake asimetrico RSA-1024 determinista (Marca Divina + Factores 7 y 2)
# ============================================================

RSA_1024_N = 0x52c96c320cd3df7931f4d50c70a68a65e468966f882bd6cbd4b53986089e136b6006830fcd0cbfa783812f85404d1af4684aab7156b841f6ac73a2a79356c0154aabd3671fbbcb195250c0c9b06c045c12b274b8160444c27527e23b7914d71d45a5a7b3d10e33440a07358dc2dd5ff270c0ac4933c933e98c470d51c53a5435
RSA_1024_E = 65537
GUARD_MAGIC_AUTH = 0xD728C111
_NATIVE_GUARD = None

def _get_native_guard():
    """Carga de forma estricta la libreria de maquina C 'INTegerGuard.dll'."""
    global _NATIVE_GUARD
    if _NATIVE_GUARD is not None:
        return _NATIVE_GUARD
    
    dll_path = os.path.join(os.path.dirname(__file__), "INTegerGuard.dll")
    if not os.path.exists(dll_path):
        dll_path = get_resource_path(os.path.join("Banco_de_Datos", "INTegerGuard.dll"))
    if not os.path.exists(dll_path):
        dll_path = get_resource_path("INTegerGuard.dll")
    if not os.path.exists(dll_path):
        raise RomIntegrityError(
            "[CRITICAL INTEGRITY FAILURE] Archivo de autoria y firma digital 'INTegerGuard.dll' no encontrado. "
            "FOMT Studio exige obligatoriamente la presencia de este binario inmutable de autor (Denisovich728) "
            "bajo la seccion 7(b) de la licencia GPLv3 para poder operar. Ejecucion bloqueada."
        )
    try:
        lib = ctypes.CDLL(dll_path)
        lib.integer_guard_ping.restype = ctypes.c_uint32
        lib.integer_guard_sign_rsa1024.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
        lib.integer_guard_sign_rsa1024.restype = ctypes.c_int
        lib.integer_guard_get_easter_egg.restype = ctypes.c_char_p
        lib.integer_guard_verify_rom.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
        lib.integer_guard_verify_rom.restype = ctypes.c_int

        if lib.integer_guard_ping() != GUARD_MAGIC_AUTH:
            raise RomIntegrityError(
                "[CRITICAL INTEGRITY FAILURE] 'INTegerGuard.dll' no paso el handshake de autenticidad. "
                "Binario modificado o incompatible."
            )
        _NATIVE_GUARD = lib
        return _NATIVE_GUARD
    except RomIntegrityError:
        raise
    except Exception as e:
        raise RomIntegrityError(
            f"[CRITICAL INTEGRITY FAILURE] No se pudo inicializar 'INTegerGuard.dll': {e}. "
            "Ejecucion bloqueada."
        )


def verify_rsa_handshake() -> bool:
    """
    Ejecuta un desafio criptografico aleatorio (Challenge-Response) RSA-1024
    contra INTegerGuard.dll. Valida matematicamente que la DLL posee la clave privada.
    """
    guard = _get_native_guard()
    rand_bytes = os.urandom(64)
    challenge_int = (int.from_bytes(rand_bytes, "big") % (RSA_1024_N - 1)) + 1
    
    c_words = (ctypes.c_uint32 * 32)(*[(challenge_int >> (32 * i)) & 0xFFFFFFFF for i in range(32)])
    s_words = (ctypes.c_uint32 * 32)()
    
    res = guard.integer_guard_sign_rsa1024(c_words, s_words)
    if res != 1:
        raise RomIntegrityError("[CRITICAL INTEGRITY FAILURE] Error en computacion interna RSA de INTegerGuard.dll.")
    
    sig_int = sum(s_words[i] << (32 * i) for i in range(32))
    recovered = pow(sig_int, RSA_1024_E, RSA_1024_N)
    
    if recovered != challenge_int:
        raise RomIntegrityError(
            "[CRITICAL INTEGRITY FAILURE] Desafio RSA-1024 rechazado por INTegerGuard.dll. "
            "Firma criptografica invalida o emulador detectado."
        )
    return True


def assert_native_guard_available():
    """
    Exige la presencia e integridad incondicional de 'INTegerGuard.dll'
    y supera el handshake asimetrico RSA.
    """
    _get_native_guard()
    verify_rsa_handshake()


# Validacion forzada inmediata al importar el modulo
assert_native_guard_available()


def get_cilixes_easter_egg() -> str:
    """Retorna el tributo y easter egg inmutable descifrado en memoria por INTegerGuard.dll."""
    guard = _get_native_guard()
    try:
        raw = guard.integer_guard_get_easter_egg()
        if raw:
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        pass
    return (
        "[FOMT STUDIO / CILIXES GUARDIAN - REVERSE ENGINEERING EASTER EGG]\n"
        "Creado y forjado por: Denisovich728 (Cilixes)\n"
        "Bajo la licencia GPLv3 Seccion 7(b), este sello de atribucion es inmutable."
    )


# ============================================================
#  CONSTANTES DE HARDWARE Y FIRMA BINARIA CLASICA
# ============================================================

SIGNATURE_OFFSET = 0x0013AA2C
SIGNATURE_BYTES  = b'CILIXES'
SIGNATURE_MAGIC  = b'CILIXES\x00'

# Punteros a los graficos del logo de intro en el bootloader del juego
BOOT_LOGO_PTR_1  = 0x00000FE8
BOOT_LOGO_PTR_2  = 0x00077990

# Punteros a la paleta BGR555 del logo de intro
BOOT_PAL_PTR_1   = 0x00000FEC
BOOT_PAL_PTR_2   = 0x00077998


# ============================================================
#  CONSTANTES CRIPTOGRAFICAS (HERMES / DENISOVICH728 SEAL)
# ============================================================

CRYPTO_KEY = "FOMTANDFIOSOFTBYD728"
CRYPTO_PHRASE = (
    "EL FIN DEL IMPOSIBLE INICIA AQUI CUALQUIERA QUE OSTENTE EL PODER "
    "DE LOS DIOSES DEBERA ACEPTAR SU MARCA DIVINA SOLO ASI LAS PUERTAS "
    "AL PARAISO SERAN ABIERTAS"
)
CRYPTO_MAGIC = b"D728_SEAL\x00"

# Offsets dedicados en zona virgen de padding (0xFF)
CRYPTO_OFFSET_FOMT       = 0x007FE000   # FoMT (8 MB - libre desde 0x75FF20 hasta 0x7FFFFF)
CRYPTO_OFFSET_MFOMT      = 0x00FFE000   # MFoMT (16 MB - libre desde 0x9D98C8 hasta 0xFFFFFF)
CRYPTO_OFFSET_MFOMT_8MB  = 0x007FE000   # MFoMT en formato recortado a 8 MB


# ============================================================
#  MOTOR CRIPTOGRAFICO: VIGENERE + SHA-256
# ============================================================

def vigenere_encrypt(text: str, key: str = CRYPTO_KEY) -> str:
    """
    Aplica cifrado Vigenere alfabetico estandar sobre letras A-Z / a-z,
    preservando espacios y signos de puntuacion.
    """
    k_clean = [ord(c.upper()) - ord('A') for c in key if c.isalpha()]
    if not k_clean:
        raise ValueError("[Crypto] La clave Vigenere no contiene caracteres alfabeticos validos.")
    
    result = []
    k_idx = 0
    for ch in text:
        if 'A' <= ch <= 'Z':
            shift = k_clean[k_idx % len(k_clean)]
            result.append(chr((ord(ch) - ord('A') + shift) % 26 + ord('A')))
            k_idx += 1
        elif 'a' <= ch <= 'z':
            shift = k_clean[k_idx % len(k_clean)]
            result.append(chr((ord(ch) - ord('a') + shift) % 26 + ord('a')))
            k_idx += 1
        else:
            result.append(ch)
    return "".join(result)


def vigenere_decrypt(ciphertext: str, key: str = CRYPTO_KEY) -> str:
    """
    Descifra un texto cifrado con Vigenere usando la clave especificada.
    """
    k_clean = [ord(c.upper()) - ord('A') for c in key if c.isalpha()]
    if not k_clean:
        raise ValueError("[Crypto] La clave Vigenere no contiene caracteres alfabeticos validos.")
    
    result = []
    k_idx = 0
    for ch in ciphertext:
        if 'A' <= ch <= 'Z':
            shift = k_clean[k_idx % len(k_clean)]
            result.append(chr((ord(ch) - ord('A') - shift) % 26 + ord('A')))
            k_idx += 1
        elif 'a' <= ch <= 'z':
            shift = k_clean[k_idx % len(k_clean)]
            result.append(chr((ord(ch) - ord('a') - shift) % 26 + ord('a')))
            k_idx += 1
        else:
            result.append(ch)
    return "".join(result)


def get_crypto_ciphertext() -> str:
    """Retorna la frase de Denisovich728 cifrada con Vigenere."""
    return vigenere_encrypt(CRYPTO_PHRASE, CRYPTO_KEY)


def get_crypto_sha256_digest() -> bytes:
    """Retorna el hash SHA-256 binario crudo (32 bytes) del texto cifrado."""
    cipher_bytes = get_crypto_ciphertext().encode('ascii')
    return hashlib.sha256(cipher_bytes).digest()


def get_crypto_sha256_hex() -> str:
    """Retorna el hash SHA-256 en formato hexadecimal ASCII (64 caracteres)."""
    cipher_bytes = get_crypto_ciphertext().encode('ascii')
    return hashlib.sha256(cipher_bytes).hexdigest()


def get_crypto_seal_payload() -> bytes:
    """
    Construye el payload binario completo del sello de Denisovich728:
    - Magic header: D728_SEAL\\0 (10 bytes)
    - Ciphertext Vigenere (156 bytes ASCII)
    - Separador nulo \\0 (1 byte)
    - Digest SHA-256 binario crudo (32 bytes)
    - String SHA-256 en formato hex ASCII (64 bytes)
    - Terminador nulo \\0 (1 byte)
    Total: 264 bytes.
    """
    cipher_bytes = get_crypto_ciphertext().encode('ascii')
    sha_raw = get_crypto_sha256_digest()
    sha_hex = get_crypto_sha256_hex().encode('ascii')
    return CRYPTO_MAGIC + cipher_bytes + b"\x00" + sha_raw + sha_hex + b"\x00"


def get_crypto_offset_for_rom(rom_or_project: Any) -> int:
    """
    Determina el offset donde debe ubicarse el sello criptografico:
    - FoMT (8 MB): 0x007FE000
    - MFoMT (16 MB): 0x00FFE000
    - MFoMT (8 MB): 0x007FE000
    """
    buffer = None
    is_mfomt = None

    if hasattr(rom_or_project, 'virtual_rom') and rom_or_project.virtual_rom:
        buffer = rom_or_project.virtual_rom
    elif hasattr(rom_or_project, 'base_rom_data') and rom_or_project.base_rom_data:
        buffer = rom_or_project.base_rom_data
    elif isinstance(rom_or_project, (bytes, bytearray)):
        buffer = rom_or_project

    if hasattr(rom_or_project, 'is_mfomt'):
        is_mfomt = bool(rom_or_project.is_mfomt)

    buf_len = len(buffer) if buffer else 0

    if is_mfomt is None and buffer and buf_len >= 0xB0:
        header_16 = bytes(buffer[0xA0:0xB0])
        if b"HM MFOM USA" in header_16 or b"BFGE" in header_16:
            is_mfomt = True
        elif b"HARVESTMOGBA" in header_16 or b"A4NE" in header_16:
            is_mfomt = False

    if is_mfomt:
        if buf_len >= 0x1000000:
            return CRYPTO_OFFSET_MFOMT
        return CRYPTO_OFFSET_MFOMT_8MB

    return CRYPTO_OFFSET_FOMT


def is_crypto_seal_present(rom_or_project: Any) -> bool:
    """
    Verifica si el sello criptografico SHA-256 y la frase cifrada con Vigenere
    estan presentes e intactos en el offset asignado para la ROM.
    """
    buffer = None
    if hasattr(rom_or_project, 'virtual_rom') and rom_or_project.virtual_rom:
        buffer = rom_or_project.virtual_rom
    elif hasattr(rom_or_project, 'base_rom_data') and rom_or_project.base_rom_data:
        buffer = rom_or_project.base_rom_data
    elif isinstance(rom_or_project, (bytes, bytearray)):
        buffer = rom_or_project

    if not buffer:
        return False

    offset = get_crypto_offset_for_rom(rom_or_project)
    magic_len = len(CRYPTO_MAGIC)
    cipher_len = len(CRYPTO_PHRASE)
    expected_sha = get_crypto_sha256_digest()

    if len(buffer) < offset + magic_len + cipher_len + 1 + 32:
        return False

    magic = bytes(buffer[offset : offset + magic_len])
    if magic != CRYPTO_MAGIC:
        return False

    cipher_bytes = bytes(buffer[offset + magic_len : offset + magic_len + cipher_len])
    stored_sha = bytes(buffer[offset + magic_len + cipher_len + 1 : offset + magic_len + cipher_len + 1 + 32])

    calc_sha = hashlib.sha256(cipher_bytes).digest()
    return calc_sha == stored_sha == expected_sha


def inyectar_sello_criptografico(project: Any) -> Dict[str, Any]:
    """
    Inyecta el sello criptografico SHA-256 cifrado con Vigenere
    en el offset exclusivo de la ROM virtual del proyecto.
    """
    if not hasattr(project, 'virtual_rom') or not project.virtual_rom:
        raise RomIntegrityError("[Crypto Enforcer] El proyecto no tiene virtual_rom inicializada.")

    offset = get_crypto_offset_for_rom(project)
    payload = get_crypto_seal_payload()

    if hasattr(project, 'write_patch'):
        project.write_patch(offset, payload)
    else:
        project.virtual_rom[offset : offset + len(payload)] = payload

    return {
        "status": "crypto_sealed",
        "offset": offset,
        "payload_length": len(payload),
        "sha256": get_crypto_sha256_hex()
    }


def assert_crypto_seal_present(rom_or_project: Any, module_name: str = "Operacion"):
    """
    Exige la presencia del sello criptografico. Lanza RomIntegrityError si falla.
    """
    if not is_crypto_seal_present(rom_or_project):
        offset = get_crypto_offset_for_rom(rom_or_project)
        raise RomIntegrityError(
            f"[CONTROL DE INTEGRIDAD] Acceso denegado en '{module_name}': "
            f"Falta el sello criptografico obligatorio SHA-256 en 0x{offset:08X}."
        )


# ============================================================
#  VERIFICACION DE FIRMA BINARIA GLOBAL EN ROM
# ============================================================

def is_cilixes_signed(rom_or_project: Any) -> bool:
    """Comprueba unicamente la firma clasica CILIXES en 0x0013AA2C."""
    if rom_or_project is None:
        return False

    buffer = None
    if hasattr(rom_or_project, 'virtual_rom') and rom_or_project.virtual_rom:
        buffer = rom_or_project.virtual_rom
    elif hasattr(rom_or_project, 'base_rom_data') and rom_or_project.base_rom_data:
        buffer = rom_or_project.base_rom_data
    elif isinstance(rom_or_project, (bytes, bytearray)):
        buffer = rom_or_project

    if not buffer or len(buffer) < SIGNATURE_OFFSET + len(SIGNATURE_BYTES):
        return False

    current = bytes(buffer[SIGNATURE_OFFSET : SIGNATURE_OFFSET + len(SIGNATURE_BYTES)])
    return current == SIGNATURE_BYTES


def is_rom_signed(rom_or_project: Any) -> bool:
    """
    Comprueba si una ROM o proyecto tiene inyectadas AMBAS firmas:
    1. La firma binaria CILIXES en 0x0013AA2C.
    2. El sello criptografico SHA-256 en su offset hardcodeado (0x007FE000 / 0x00FFE000).
    Ejecuta el handshake RSA asimetrico y la verificacion en codigo maquina (INTegerGuard.dll).
    """
    verify_rsa_handshake()
    guard = _get_native_guard()
    buffer = None
    if hasattr(rom_or_project, 'virtual_rom') and rom_or_project.virtual_rom:
        buffer = rom_or_project.virtual_rom
    elif hasattr(rom_or_project, 'base_rom_data') and rom_or_project.base_rom_data:
        buffer = rom_or_project.base_rom_data
    elif isinstance(rom_or_project, (bytes, bytearray)):
        buffer = rom_or_project
    
    if buffer:
        is_mfomt = 0
        if hasattr(rom_or_project, 'is_mfomt'):
            is_mfomt = 1 if rom_or_project.is_mfomt else 0
        elif len(buffer) >= 0xB0:
            header = bytes(buffer[0xA0:0xB0])
            if b"HM MFOM USA" in header or b"BFGE" in header:
                is_mfomt = 1
        raw_bytes = bytes(buffer)
        res = guard.integer_guard_verify_rom(raw_bytes, len(raw_bytes), is_mfomt)
        return res == 1

    return is_cilixes_signed(rom_or_project) and is_crypto_seal_present(rom_or_project)


def assert_rom_signed(rom_or_project: Any, module_name: str = "Operacion"):
    """
    Exige de manera estricta que la ROM contenga ambas firmas obligatorias.
    Lanza RomIntegrityError si no se cumple la condicion.
    """
    if not is_cilixes_signed(rom_or_project):
        raise RomIntegrityError(
            f"[CONTROL DE INTEGRIDAD] Acceso denegado en '{module_name}': "
            f"La ROM no contiene la firma binaria obligatoria 'CILIXES' en 0x{SIGNATURE_OFFSET:06X}."
        )

    if not is_crypto_seal_present(rom_or_project):
        offset = get_crypto_offset_for_rom(rom_or_project)
        raise RomIntegrityError(
            f"[CONTROL DE INTEGRIDAD] Acceso denegado en '{module_name}': "
            f"La ROM no contiene el sello criptografico SHA-256 en 0x{offset:08X}."
        )


def require_rom_signature(rom_or_project: Any, auto_sign: bool = True, module_name: str = "Modulo") -> bool:
    """
    Valida la firma de la ROM. Si no esta firmada y auto_sign es True y se proporciona
    una instancia de proyecto, inyecta el splash y ambas firmas automaticamente.
    """
    if is_rom_signed(rom_or_project):
        return True

    # Si se paso un proyecto, intentar auto-firmar
    if auto_sign and hasattr(rom_or_project, 'allocate_free_space') and hasattr(rom_or_project, 'write_patch'):
        inyectar_splash_y_firmar(rom_or_project)
        return is_rom_signed(rom_or_project)

    assert_rom_signed(rom_or_project, module_name)
    return True


# ============================================================
#  RUTINA DE INSERCION DE SPLASH Y AMBAS FIRMAS
# ============================================================

def inyectar_splash_y_firmar(project: Any, force: bool = False) -> Dict[str, Any]:
    """
    Inyecta los graficos del splash logo, su paleta, redirige los punteros de booteo,
    estampa la firma binaria CILIXES y escribe el sello criptografico SHA-256 con
    cifrado Vigenere en el offset hardcodeado de FoMT o MFoMT.
    """
    if not hasattr(project, 'virtual_rom') or not project.virtual_rom:
        raise RomIntegrityError("[Splash Enforcer] Error critico: El proyecto no tiene virtual_rom inicializada.")

    crypto_offset = get_crypto_offset_for_rom(project)

    # 1. Comprobar si ya estan ambas firmas inyectadas
    if not force and is_rom_signed(project):
        return {
            "status": "already_signed",
            "message": "La ROM ya cuenta con la firma binaria CILIXES y el sello criptografico.",
            "signature_offset": SIGNATURE_OFFSET,
            "crypto_offset": crypto_offset,
            "crypto_sha256": get_crypto_sha256_hex()
        }

    # 2. Inyectar splash logo solo si la firma clasica CILIXES falta
    new_offset = None
    new_pointer_gba = None
    pal_offset = None

    if force or not is_cilixes_signed(project):
        asset_path = get_resource_path(os.path.join("Banco_de_Datos", "assets", "splash_logo.bin"))
        if not os.path.exists(asset_path):
            raise RomIntegrityError(
                f"[Splash Enforcer] Falta el binario obligatorio de splash: '{asset_path}'. "
                "No se puede certificar la integridad de la ROM."
            )

        with open(asset_path, "rb") as f:
            splash_data = f.read()

        # Asignar espacio libre e inyectar logo
        new_offset = project.allocate_free_space(len(splash_data))
        project.write_patch(new_offset, splash_data)

        # Redirigir punteros de booteo de la intro (Logo de inicio)
        new_pointer_gba = new_offset | 0x08000000
        ptr_bytes = struct.pack("<I", new_pointer_gba)
        project.write_patch(BOOT_LOGO_PTR_1, ptr_bytes)
        project.write_patch(BOOT_LOGO_PTR_2, ptr_bytes)

        # Cargar e inyectar paleta BGR555 del splash
        pal_path = get_resource_path(os.path.join("Banco_de_Datos", "assets", "splash.pal"))
        if os.path.exists(pal_path):
            with open(pal_path, "rb") as f:
                pal_data = f.read()

            pal_offset = project.allocate_free_space(len(pal_data))
            project.write_patch(pal_offset, pal_data)

            new_pal_gba = pal_offset | 0x08000000
            pal_ptr_bytes = struct.pack("<I", new_pal_gba)
            project.write_patch(BOOT_PAL_PTR_1, pal_ptr_bytes)
            project.write_patch(BOOT_PAL_PTR_2, pal_ptr_bytes)

        # Estampar la firma binaria CILIXES permanente en la ROM
        project.write_patch(SIGNATURE_OFFSET, SIGNATURE_MAGIC)

    # 3. Estampar el sello criptografico SHA-256 en su offset hardcodeado
    crypto_res = inyectar_sello_criptografico(project)

    result = {
        "status": "injected_and_signed",
        "logo_rom_offset": new_offset,
        "logo_gba_pointer": new_pointer_gba,
        "pal_rom_offset": pal_offset,
        "signature_offset": SIGNATURE_OFFSET,
        "signature_bytes": SIGNATURE_MAGIC,
        "crypto_offset": crypto_res["offset"],
        "crypto_payload_length": crypto_res["payload_length"],
        "crypto_sha256": crypto_res["sha256"]
    }

    print(
        f"[Splash Enforcer] Integridad validada: Splash inyectado en 0x{new_offset or 0:08X}, "
        f"Paleta en 0x{pal_offset or 0:08X}, firmado con '{SIGNATURE_BYTES.decode('ascii')}' en 0x{SIGNATURE_OFFSET:06X}, "
        f"y sello SHA-256 inyectado en 0x{crypto_res['offset']:08X}."
    )
    return result


def validar_e_inyectar_splash(project: Any) -> bool:
    """Alias para compatibilidad de llamadas previas."""
    res = inyectar_splash_y_firmar(project)
    return res.get("status") in ("already_signed", "injected_and_signed")
