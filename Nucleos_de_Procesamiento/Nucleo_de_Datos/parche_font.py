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
        
    # 4. Create Accented Vowels
    vowels = []
    TILDE_R0 = 0x0C
    TILDE_R1 = 0x10
    
    # Uppercase Á, É, Í (Indices 0, 4, 8)
    for idx in [0, 4, 8]:
        base = bytearray(new_chars[idx])
        base[0] = TILDE_R0; base[1] = TILDE_R1
        vowels.append(bytes(base))
        
    # Ó (Base Q original at 15, shifted 2)
    q_data = chars[15]
    o_base = bytearray(q_data)
    o_base[7]=0x44; o_base[8]=0x44; o_base[9]=0x38 # No tail
    o_base = shift_down(o_base, pixels=2)
    o_base = bytearray(o_base)
    o_base[0] = TILDE_R0; o_base[1] = TILDE_R1
    vowels.append(bytes(o_base))
    
    # Ú (Index 19)
    base = bytearray(new_chars[19])
    base[0] = TILDE_R0; base[1] = TILDE_R1
    vowels.append(bytes(base))
    
    # Lowercase á, é, í, ó, ú (Indices 25, 29, 33, 39, 45)
    # They were shifted by 1. Original top was Row 3 -> Now Row 4.
    # Tilde at Row 2, 3? Or Row 1, 2?
    # Let's use Row 2, 3 to keep it close to Row 4.
    for idx in [25, 29, 33, 39, 45]:
        base = bytearray(new_chars[idx])
        base[2] = TILDE_R0
        base[3] = TILDE_R1
        vowels.append(bytes(base))
        
    # 5. Final Write
    final_payload = b"".join(new_chars) + b"".join(vowels)
    project.write_patch(FONT_START, final_payload)
    
    return {
        "Á": 0x7B, "É": 0x7C, "Í": 0x7D, "Ó": 0x7E, "Ú": 0x7F,
        "á": 0x80, "é": 0x81, "í": 0x82, "ó": 0x83, "ú": 0x84
    }
