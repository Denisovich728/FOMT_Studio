import struct

def diagnose_event_1011():
    rom_path = 'j:/Repositorios/fomt_studio/Modded_FoMT3.gba'
    with open(rom_path, 'rb') as f:
        rom = f.read()
    
    # Buscamos el evento 1011.
    # El índice de eventos suele estar en 0x080F89D8 (según el CSV)
    idx_off = 0x0F89D8
    event_ptr_off = idx_off + (1011 * 4)
    event_ptr = struct.unpack('<I', rom[event_ptr_off:event_ptr_off+4])[0]
    event_off = event_ptr & 0x1ffffff
    
    print(f"Evento 1011 en offset: {hex(event_off)}")
    
    # Escaneamos el bytecode buscando el switch
    # El bytecode de switch suele ser 0x0B (Switch)
    # Seguido de SwitchID (2) y número de casos (2)?
    # O tal vez el decompiler usa algo más.
    
    # Vamos a buscar la secuencia de casos que el usuario mostró.
    # case "0x20080EC1" -> 20 08 0E C1
    
    # Busquemos 20 08 0E C1 en el bytecode cerca del evento 1011.
    target = b'\x20\x08\x0E\xC1'
    pos = rom.find(target, event_off, event_off + 0x2000)
    if pos != -1:
        print(f"Encontrado 20 08 0E C1 en {hex(pos)}")
        # Ver qué hay alrededor
        dump = rom[pos-16:pos+64]
        print(f"Dump: {dump.hex(' ')}")
    else:
        print("No se encontró 20 08 0E C1")

diagnose_event_1011()
