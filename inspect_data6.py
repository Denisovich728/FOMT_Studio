def decompress_popuri(data: bytes, offset: int = 0) -> bytes:
    if offset >= len(data): return b''
    header = data[offset]
    if header != 0x70: return b''
    
    import struct
    decomp_size = struct.unpack_from('<I', data, offset)[0] >> 8
    out = bytearray(decomp_size)
    out_pos = 0
    in_pos = offset + 4

    while out_pos < decomp_size and in_pos < len(data):
        b = data[in_pos]; in_pos += 1
        if b & 0x80:
            count = (b & 0x7F) + 1
            val = data[in_pos]; in_pos += 1
            for _ in range(count):
                if out_pos < decomp_size:
                    out[out_pos] = val; out_pos += 1
        else:
            count = b + 1
            for _ in range(count):
                if out_pos < decomp_size and in_pos < len(data):
                    out[out_pos] = data[in_pos]; out_pos += 1; in_pos += 1
    return bytes(out)

def test_decompress():
    with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
        rom_data = f.read()
    
    comp_data = rom_data[0x6A0098:0x6A0098+256]
    decomp = decompress_popuri(comp_data, 0)
    
    print(f"Header: {decomp[0]:02X} {decomp[1]:02X} {decomp[2]:02X} {decomp[3]:02X}")
    print(f"Warps: {decomp[0]}, Scripts: {decomp[1]}")
    
    base = 4
    for i in range(decomp[0]):
        chunk = decomp[base + i*8 : base + (i+1)*8]
        hex_chunk = ' '.join(f"{b:02X}" for b in chunk)
        print(f"Warp {i}: {hex_chunk}")
        
    base += decomp[0] * 8
    for i in range(decomp[1]):
        chunk = decomp[base + i*8 : base + (i+1)*8]
        hex_chunk = ' '.join(f"{b:02X}" for b in chunk)
        print(f"Script {i}: {hex_chunk}")

if __name__ == '__main__':
    test_decompress()
