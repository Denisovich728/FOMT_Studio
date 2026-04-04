import struct
from Perifericos.Traducciones.i18n import tr

class Npc:
    def __init__(self, parser, index, base_offset):
        self.parser = parser
        self.index = index
        self.base_offset = base_offset
        self.name_str = "Desconocido"
        self.name_ptr = 0
        self.personality_ptr = 0
        self.routine_size = 64
        self._role_key = "role_villager"

    def read_stats(self, lang='es'):
        return {
            "ID": self.index,
            "Nombre": self.name_str,
            "Rol": tr(self.role_key, lang),
            "Ptr_Personalidad": f"0x{self.personality_ptr:08X}",
            "max_len": len(self.name_str.encode('windows-1252', errors='replace'))
        }

    @property
    def role_key(self):
        name = self.name_str.strip('\x00').strip()
        is_mfomt = self.parser.project.is_mfomt
        
        # Mapping de Nombres a Claves de Rol
        bachelorettes = ["Ann", "Elli", "Karen", "Mary", "Popuri", "Goddess"]
        bachelors = ["Cliff", "Doctor", "Kai", "Gray", "Rick"]
        sprites = ["Chef", "Nappy", "Hoggy", "Bold", "Staid", "Aqua", "Timmid"]
        
        if any(b.lower() in name.lower() for b in bachelorettes):
            return "role_bachelorette" if not is_mfomt else "role_rival"
        if any(b.lower() in name.lower() for b in bachelors):
            return "role_bachelor" if is_mfomt else "role_rival"
        if any(s.lower() in name.lower() for s in sprites):
            return "role_special"
            
        return "role_villager"

    def save_name_in_place(self, new_name):
        if not self.name_ptr: return
        real_offset = self.name_ptr & 0x01FFFFFF
        max_len = len(self.name_str.encode('windows-1252', errors='replace'))
        encoded = new_name.encode('windows-1252', errors='ignore')
        
        if len(encoded) > max_len:
            encoded = encoded[:max_len]
        else:
            encoded += b'\x00' * (max_len - len(encoded))
            
        self.parser.project.write_patch(real_offset, encoded)
        self.name_str = encoded.decode('windows-1252').strip('\x00')

    def get_translated_role(self, lang='es'):
        """ Returns the translated role based on the current language. """
        return tr(self.role_key, lang)

class NpcParser:
    """ Parser minimalista que sigue la lógica de punteros por delimitación. """
    def __init__(self, project):
        self.project = project
        self.npcs = []
        self.npc_table_off = 0x104270 # Tabla principal de personajes
        
    def scan_npcs(self):
        self.npcs = []
        for i in range(110):
            base = self.npc_table_off + (i * 8)
            data = self.project.read_rom(base, 8)
            if not data or len(data) < 8: break
            
            # [28 41 10 08 | 4C 00 00 00]
            name_ptr, sched_id = struct.unpack('<II', data)
            if name_ptr < 0x08000000 or name_ptr > 0x09000000: break
            
            # Buscamos el nombre
            name = self._read_name(name_ptr)
            
            # Lógica: El ID es el índice en la tabla de punteros de eventos/scripts (Master Table 0x0F89D4)
            # O directamente la dirección si es un offset (0x08... no, aquí son IDs 0x4C, etc.)
            # Para determinar el ptr real usamos el índice en la tabla maestra
            ptr_off = 0xF89D4 + (sched_id * 4)
            ptr_data = self.project.read_rom(ptr_off & 0x01FFFFFF, 4)
            if ptr_data:
                real_ptr = struct.unpack('<I', ptr_data)[0]
            else:
                real_ptr = 0
                
            npc = Npc(self, i, base)
            npc.name_str = name
            npc.name_ptr = name_ptr
            npc.personality_ptr = real_ptr
            
            self.npcs.append(npc)
            
        # LÓGICA DE TOPES (Delimitación): Calculamos el tamaño por la distancia al siguiente puntero
        # Ordenamos los NPCs por su dirección de script (personality_ptr)
        sorted_scripts = sorted([n for n in self.npcs if n.personality_ptr > 0x08000000], key=lambda x: x.personality_ptr)
        
        # Enriquecemos cada NPC con su tamaño de routine
        for i in range(len(sorted_scripts)):
            curr = sorted_scripts[i]
            if i + 1 < len(sorted_scripts):
                nxt = sorted_scripts[i+1]
                curr.routine_size = nxt.personality_ptr - curr.personality_ptr
            else:
                curr.routine_size = 128 # Fallback por si es el último
                
        return self.npcs

    def _read_name(self, ptr):
        off = ptr & 0x01FFFFFF
        s = bytearray()
        for _ in range(32):
            b = self.project.read_rom(off, 1)
            if not b or b[0] == 0: break
            s.append(b[0])
            off += 1
        return s.decode('windows-1252', errors='ignore')
