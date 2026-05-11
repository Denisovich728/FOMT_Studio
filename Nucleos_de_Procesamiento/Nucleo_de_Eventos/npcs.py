# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.1)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct
from Perifericos.Traducciones.i18n import tr

# Límite de bytes para nombres de NPC (escritura) — Ampliado a 10 para Repunteo
NPC_NAME_MAX_BYTES = 10

class Npc:
    def __init__(self, parser, index, base_offset):
        self.parser = parser
        self.index = index
        self.base_offset = base_offset
        self.name_str = "Desconocido"
        self.name_ptr = 0
        self.personality_ptr = 0
        self.routine_size = 64
        self.portrait_offset = -1
        self.sprite_offset = -1
        # Bytes [04] y [05] después del puntero de nombre
        self.flag_byte_1 = 0   # data[4]
        self.flag_byte_2 = 0   # data[5]
        self.extra_flags = 0   # Los 4 bytes [04-07] completos para compat
        self._role_key = "role_villager"

    @property
    def is_candidate(self):
        """
        Regla Maestra: Si el segundo byte después del puntero (byte[05])
        tiene un valor diferente a 0x00, el NPC es candidato.
        No importa el nombre.
        """
        return self.flag_byte_2 != 0x00

    def read_stats(self, lang='es'):
        return {
            "idx": f"0x{self.index + 1:02X}",
            "Nombre": self.name_str,
            "Rol": tr(self.role_key, lang),
            "Candidata": "Sí" if self.is_candidate else "No",
            "Ptr_Nombre": f"0x{self.name_ptr:08X}",
            "Flags": f"{self.flag_byte_1:02X} {self.flag_byte_2:02X}",
            "Ptr_Personalidad": f"0x{self.personality_ptr:08X}",
            "Portrait": f"0x{self.portrait_offset:06X}" if self.portrait_offset > 0 else "-",
            "Sprite": f"0x{self.sprite_offset:06X}" if self.sprite_offset > 0 else "-",
            "max_len": NPC_NAME_MAX_BYTES
        }

    @property
    def role_key(self):
        """
        Rol basado 100% en la regla del segundo byte.
        Si byte[05] != 0x00 → candidato.
        """
        is_mfomt = self.parser.project.is_mfomt
        if self.is_candidate:
            # En FoMT (Male) los candidatos son Bachelorettes (Candidatas)
            # En MFoMT (Female) son Bachelors (Candidatos)
            return "role_bachelor" if is_mfomt else "role_bachelorette"
        return "role_villager"

    def save_name_in_place(self, new_name):
        if not self.name_ptr: return
        
        # Codificar nuevo nombre — LÍMITE FORZADO A 8 BYTES
        encoded = new_name.encode('windows-1252', errors='replace')
        if len(encoded) > NPC_NAME_MAX_BYTES:
            encoded = encoded[:NPC_NAME_MAX_BYTES]
        encoded = encoded + b'\x00'
        
        # Paso 1: Asignar espacio libre alineado a 4 bytes
        new_offset = self.parser.project.allocate_free_space(len(encoded))
        self.parser.project.overwrite_rom_directly(new_offset, encoded)
        
        # Paso 2: Actualizar el puntero en la tabla de nombres
        self.parser.project.memory.re_point_name(self.index, new_offset)
        
        self.name_str = new_name[:NPC_NAME_MAX_BYTES]
        self.name_ptr = new_offset | 0x08000000

    def get_translated_role(self, lang='es'):
        is_mfomt = self.parser.project.is_mfomt
        suffix = " (MFoMT)" if is_mfomt else " (FoMT)"
        base_role = tr(self.role_key, lang)
        if suffix not in base_role:
            return base_role + suffix
        return base_role

class NpcParser:
    """
    Motor de NPCs basado en CSV.
    Lee la tabla NPC con filas de 8 bytes:
      [00-03] Puntero nombre (Little Endian, formato GBA 08XXXXXX)
      [04]    Flag byte 1 (script/schedule ID)
      [05]    Flag byte 2 (si ≠ 0x00 → candidata de matrimonio)
      [06-07] Reservado (siempre 00 00)

    Ejemplo real de la ROM:
      28 41 10 08  4C 00 00 00  → Ptr=0x08104128, Flags=4C 00, NO candidata
      38 41 10 08  0D 29 00 00  → Ptr=0x08104138, Flags=0D 29, SÍ candidata (29≠00)
      7C 41 10 08  53 5F 00 00  → Ptr=0x0810417C, Flags=53 5F, SÍ candidata (5F≠00)
    """
    NPC_ROW_SIZE = 8  # Cada entrada NPC ocupa 8 bytes
    
    def __init__(self, project):
        self.project = project
        # Offsets desde CSV via SuperLibrary
        self.npc_table_start = project.super_lib.npc_table_offset
        self.npc_limit = project.super_lib.npc_limit
        self.npcs = []
        
        # MOTOR DE GRÁFICOS RAW (Basado en Piedra Rosetta / BlueSpider)
        self.raw_bank_base = 0x53F7BC
        self.raw_portrait_size = 2048
        self.raw_sprite_size = 4096
        self.master_palette_off = 0x58B3E0

    def scan_npcs(self):
        self.npcs = []
        
        print(f"\nRastreo NPC (CSV-Driven, filas de {self.NPC_ROW_SIZE} bytes)")
        print(f"Tabla NPC: 0x{self.npc_table_start:06X}")
        print(f"Cantidad de índices: {self.npc_limit}")
        print("-" * 60)

        for i in range(self.npc_limit):
            base = self.npc_table_start + (i * self.NPC_ROW_SIZE)
            data = self.project.read_rom(base, self.NPC_ROW_SIZE)
            if not data or len(data) < self.NPC_ROW_SIZE: break
            
            # [00-03] Puntero nombre en Little Endian (formato GBA)
            name_ptr = struct.unpack_from('<I', data, 0)[0]
            # [04] y [05] — bytes post-puntero
            flag_b1 = data[4]
            flag_b2 = data[5]
            
            # Leer nombre desde puntero GBA
            if name_ptr < 0x08000000 or name_ptr > 0x09000000: 
                name = "" 
            else:
                name = self._read_name(name_ptr)
            
            # Regla Maestra: byte[05] ≠ 0x00 = candidata
            is_cand = flag_b2 != 0x00
            cand_mark = " [CANDIDATA]" if is_cand else ""
            
            raw_hex = " ".join([f"{b:02X}" for b in data])
            print(f"ID [{i:03d}] {name.ljust(15)} | Flags: {flag_b1:02X} {flag_b2:02X} | Raw: [{raw_hex}]{cand_mark}")

            # Resolver puntero de personalidad desde la tabla de scripts
            # La tabla maestra de scripts para FoMT está en 0xF89D4
            ptr_off = 0xF89D4 + (flag_b1 * 4)
            ptr_data = self.project.read_rom(ptr_off & 0x01FFFFFF, 4)
            real_ptr = struct.unpack('<I', ptr_data)[0] if ptr_data else 0

            npc = Npc(self, i, base)
            npc.name_str = name
            npc.name_ptr = name_ptr
            npc.flag_byte_1 = flag_b1
            npc.flag_byte_2 = flag_b2
            npc.extra_flags = struct.unpack_from('<I', data, 4)[0]
            npc.personality_ptr = real_ptr
            
            # ASIGNACIÓN DE GRÁFICOS RAW
            stride = (0x557CBC - 0x53F7BC) // 24
            npc.portrait_offset = self.raw_bank_base + (i * stride)
            npc.sprite_offset = npc.portrait_offset + 2048 
            
            self.npcs.append(npc)
            
        # Calcular tamaños de rutinas por proximidad
        sorted_scripts = sorted(
            [n for n in self.npcs if n.personality_ptr > 0x08000000],
            key=lambda x: x.personality_ptr
        )
        for i in range(len(sorted_scripts)):
            curr = sorted_scripts[i]
            if i + 1 < len(sorted_scripts):
                nxt = sorted_scripts[i+1]
                curr.routine_size = nxt.personality_ptr - curr.personality_ptr
            else:
                curr.routine_size = 128
                
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