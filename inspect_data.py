def dump_offset():
    with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
        rom_data = f.read()
    
    off = 0xDBD59
    chunk = rom_data[off:off+32]
    hex_chunk = ' '.join(f"{b:02X}" for b in chunk)
    print(f"Data at 0x{off:06X}: {hex_chunk}")

if __name__ == '__main__':
    dump_offset()
