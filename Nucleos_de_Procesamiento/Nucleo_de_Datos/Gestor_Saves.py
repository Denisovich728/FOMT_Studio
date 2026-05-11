# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import struct
import os

class GestorSaves:
    """
    Módulo para la manipulación y lectura de partidas guardadas (.sav).
    En la GBA, los archivos Flash de 64KB o SRAM serializan los datos 
    de la WRAM (0x02000000) a estructuras empaquetadas.
    """
    def __init__(self, project):
        self.project = project
        self.is_mfomt = getattr(self.project, 'is_mfomt', False)
        self.save_data = bytearray()
        
    def load_save(self, path):
        if not os.path.exists(path): return False
        with open(path, 'rb') as f:
            self.save_data = bytearray(f.read())
        # Verifica que sea un archivo de guardado estándar (SRAM/Flash 64KB)
        return len(self.save_data) >= 65536
        
    def save_save(self, path):
        if not self.save_data: return False
        with open(path, 'wb') as f:
            f.write(self.save_data)
        return True

    def _read_uint32(self, offset):
        if offset + 4 > len(self.save_data): return 0
        return struct.unpack('<I', self.save_data[offset:offset+4])[0]

    def _write_uint32(self, offset, value):
        if offset + 4 <= len(self.save_data):
            self.save_data[offset:offset+4] = struct.pack('<I', value)
            
    def _read_uint16(self, offset):
        if offset + 2 > len(self.save_data): return 0
        return struct.unpack('<H', self.save_data[offset:offset+2])[0]
        
    def _read_uint8(self, offset):
        if offset + 1 > len(self.save_data): return 0
        return self.save_data[offset]
        
    def _write_uint8(self, offset, value):
        if offset + 1 <= len(self.save_data):
            self.save_data[offset] = value
            
    def get_sram_offset(self, ram_address):
        """ Convierte la WRAM (0x02000000) a un offset lineal de SRAM """
        return ram_address - 0x02000000
        
    # ==========================================
    # EDICIÓN DE PERSONAJE (STATE EDITOR)
    # ==========================================
    
    def get_player_gold(self):
        return self._read_uint32(self.get_sram_offset(0x02004090))
        
    def set_player_gold(self, gold):
        # Limite teórico 999,999,999
        val = max(0, min(999999999, gold))
        self._write_uint32(self.get_sram_offset(0x02004090), val)
        
    def get_player_stamina(self):
        return self._read_uint8(self.get_sram_offset(0x02004205))
        
    def set_player_stamina(self, stamina):
        # En el juego base 0 es desmayo, ~255 es máximo absoluto de un byte
        val = max(0, min(255, stamina))
        self._write_uint8(self.get_sram_offset(0x02004205), val)
        
    def get_player_fatigue(self):
        return self._read_uint8(self.get_sram_offset(0x02004206))
        
    def set_player_fatigue(self, fatigue):
        # Cuidado: 100 de fatiga normalmente causa desmayo en FoMT/MFoMT
        val = max(0, min(255, fatigue))
        self._write_uint8(self.get_sram_offset(0x02004206), val)
        
    def get_rucksack_level(self):
        return self._read_uint8(self.get_sram_offset(0x02004234))
        
    def set_rucksack_level(self, level):
        # 0=Chica, 1=Mediana, 2=Grande
        val = max(0, min(2, level))
        self._write_uint8(self.get_sram_offset(0x02004234), val)
        
    def get_house_size(self):
        return self._read_uint8(self.get_sram_offset(0x020027CC))
        
    def set_house_size(self, size):
        # 0=Sucia, 1=Pequeña, 2=Mediana, 3=Grande
        val = max(0, min(3, size))
        self._write_uint8(self.get_sram_offset(0x020027CC), val)