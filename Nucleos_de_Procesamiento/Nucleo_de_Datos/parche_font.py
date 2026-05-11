import os

# Offsets and Sizes
FONT_START = 0x4F97EC
CHAR_SIZE = 12

def shift_down(char_data, pixels=1):
    """Shifts a 12-byte character down by N pixels."""
    new_data = bytearray([0] * 12)
    for i in range(12 - pixels):
        new_data[i + pixels] = char_data[i]
    return bytes(new_data)

def apply_font_patch(project):
    """
    Standardizes the entire font alignment:
    - Uppercase (A-Z): Shifted down 2 pixels (starts at Row 2).
    - Lowercase (a-z): Shifted down 1 pixel (starts at Row 4 approx).
    - Tilde Pattern: 0x0C, 0x10.
    """
    # 1. Read original font (51 chars: A-N, P-Z, a-z)
    original_data = project.read_rom(FONT_START, 51 * CHAR_SIZE)
    chars = [original_data[i*12:(i+1)*12] for i in range(51)]
    
    new_chars = []
    
    # 2. Process ALL Uppercase (A-Z) - Shift down 2 pixels
    # Indices 0-25 in the new list (A-N, then O will be skipped, then P-Z)
    # Wait, in the original read data (51 chars), A-N is 0-13, P-Z is 14-24.
    for i in range(25):
        new_chars.append(shift_down(chars[i], pixels=2))
        
    # 3. Process ALL Lowercase (a-z) - Shift down 1 pixel to stay aligned
    # Indices 25-50 in original data
    for i in range(25, 51):
        new_chars.append(shift_down(chars[i], pixels=1))
        
    # 4. Create Accented Vowels and Ñ/ñ
    spanish_chars_dict = {}
    TILDE_R0 = 0x0C
    TILDE_R1 = 0x10
    
    # Ñ (Custom pattern) - Tilde at 1, 2
    ene_mayus = bytearray(new_chars[13])
    ene_mayus[1] = 0x36; ene_mayus[2] = 0x49
    spanish_chars_dict["Ñ"] = bytes(ene_mayus)
    
    # ñ (Custom pattern) - Tilde at 3, 4
    ene_min = bytearray(new_chars[38])
    ene_min[3] = 0x36; ene_min[4] = 0x49
    spanish_chars_dict["ñ"] = bytes(ene_min)

    # Vocales (ORDEN ESTRICTO: A E I O U)
    # Mayúsculas: Á(0x7B), É(0x7C), Í(0x7D), Ó(0x7E), Ú(0x7F)
    # Minúsculas: á(0x80), é(0x81), í(0x82), ó(0x83), ú(0x84)
    vowels_seq = ["Á", "É", "Í", "Ó", "Ú", "á", "é", "í", "ó", "ú"]
    
    # Mapeo de índices de origen en new_chars
    vowel_src_indices = {
        "Á": 0, "É": 4, "Í": 8, "Ó": "SPECIAL", "Ú": 19,
        "á": 25, "é": 29, "í": 33, "ó": 39, "ú": 45
    }

    for char_name in vowels_seq:
        src_idx = vowel_src_indices[char_name]
        if src_idx == "SPECIAL":
            # Caso Ó (Base Q original at 15)
            q_data = chars[15]
            o_base = bytearray(q_data)
            o_base[7]=0x44; o_base[8]=0x44; o_base[9]=0x38
            o_base = shift_down(o_base, pixels=2)
            o_base = bytearray(o_base)
            o_base[0] = TILDE_R0; o_base[1] = TILDE_R1
            spanish_chars_dict[char_name] = bytes(o_base)
        else:
            base = bytearray(new_chars[src_idx])
            # Tilde en Row 0,1 para Mayús, Row 2,3 para Minús
            base[0 if char_name.isupper() else 2] = TILDE_R0
            base[1 if char_name.isupper() else 3] = TILDE_R1
            spanish_chars_dict[char_name] = bytes(base)

    # 5. Final Write
    # Mapeo de 1-Byte (Rango Anti-Kanji 0xF0-0xFB)
    # 100% estable, evita mezclas de caracteres y optimiza espacio en scripts.
    vowel_map = {
        "Á": (0x4F9D5C, 0xF0),
        "É": (0x4F9D68, 0xF1),
        "Í": (0x4F9D74, 0xF2),
        "Ó": (0x4F9D80, 0xF3),
        "Ú": (0x4F9D8C, 0xF4),
        "á": (0x4F9D98, 0xF5),
        "é": (0x4F9DA4, 0xF6),
        "í": (0x4F9DB0, 0xF7),
        "ó": (0x4F9DBC, 0xF8),
        "ú": (0x4F9DC8, 0xF9),
        "Ñ": (0x4F921C + 0x2B * 12, 0x2B),
        "ñ": (0x4F921C + 0x2D * 12, 0x2D)
    }
    
    for char, (off, cid) in vowel_map.items():
        project.write_patch(off, spanish_chars_dict[char])
    
    final_ids = {c: cid for c, (off, cid) in vowel_map.items()}
    return final_ids
