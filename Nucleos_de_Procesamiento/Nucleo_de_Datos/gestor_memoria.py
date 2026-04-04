class MemoryManager:
    """
    Gestor de Memoria Virtual para parches en ROM.
    Coordina la lectura entre la ROM base y los parches definidos en el proyecto.
    """
    def __init__(self, proyecto):
        self.proyecto = proyecto

    def read_byte(self, offset):
        return self.proyecto.read_rom(offset, 1)[0]
        
    def write_byte(self, offset, val):
        self.proyecto.write_patch(offset, bytes([val]))
        
    def read_u32(self, offset):
        import struct
        data = self.proyecto.read_rom(offset, 4)
        return struct.unpack("<I", data)[0]
        
    def write_u32(self, offset, val):
        import struct
        data = struct.pack("<I", val)
        self.proyecto.write_patch(offset, data)
