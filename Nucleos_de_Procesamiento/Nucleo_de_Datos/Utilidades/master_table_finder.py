# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.4.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct
import os

class MasterTableFinder:
    """
    Motor de búsqueda de tablas maestras para FOMT.
    Permite identificar dinámicamente las listas de punteros mencionadas en 'conocimientos arcanos'.
    """
    def __init__(self, rom_path):
        self.rom_path = rom_path
        self.rom_data = None
        self._load_rom()

    def _load_rom(self):
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()

    def find_script_table(self):
        """
        Busca la tabla maestra de eventos/scripts.
        En FoMT US (USA) está en 0x0F89D4.
        """
        # Ann's daily script pointer is a known anchor
        target_ptr = 0x083D0D44
        target_bytes = struct.pack('<I', target_ptr)
        
        # Encontramos todas las referencias al script de Ann
        pos = self.rom_data.find(target_bytes)
        if pos != -1:
            # Si Ann es el evento 1011 (como calculamos), restamos 1011 * 4
            table_start = pos - (1011 * 4)
            return table_start
        return None

    def find_npc_name_table(self):
        """
        Busca la tabla de nombres de NPC.
        Anchor: Lillia (4c 69 6c 6c 69 61 00)
        """
        anchor = b"Lillia\x00"
        data_pos = self.rom_data.find(anchor)
        if data_pos != -1:
            # Buscamos el puntero a esta dirección
            ptr = struct.pack('<I', data_pos | 0x08000000)
            ptr_pos = self.rom_data.find(ptr)
            return ptr_pos, data_pos
        return None, None

if __name__ == "__main__":
    ROM = r"D:\Repositorios\Harvest Moon - Friends of Mineral Town (USA).gba"
    finder = MasterTableFinder(ROM)
    
    s_table = finder.find_script_table()
    n_table_ptr, n_table_data = finder.find_npc_name_table()
    
    print(f"--- Análisis de Tablas Maestras ---")
    if s_table:
        print(f"[+] Tabla Maestra de Scripts encontrada en: 0x{s_table:X}")
    if n_table_ptr:
        print(f"[+] Tabla de Punteros de Nombres encontrada en: 0x{n_table_ptr:X}")
        print(f"[+] Datos de Nombres (Lillia) en: 0x{n_table_data:X}")
