# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
import struct

class NpcParser:
    def __init__(self, project):
        self.project = project
        self.npcs = []
        is_mfomt = getattr(self.project, 'is_mfomt', False)
        delta = 0 if not is_mfomt else 0x2BD58
        self.npc_table_off = 0x104260 + delta 
        
        # BANCO DE RETRATOS (Fijado por ID 80 en 0x556CBC)
        self.portrait_base = 0x556CBC
        self.portrait_stride = 2048
        self.portrait_id_offset = 80 # ID 80 es el primero en este banco
        
        # BANCO DE PALETAS (Fijado por el usuario)
        self.palette_base = 0x58B0A0
        self.palette_stride = 32

    def scan_npcs(self):
        self.npcs = []
        rom = self.project.base_rom_data
        
        for i in range(42): # Límite de la Lista Madre
            base = self.npc_table_off + (i * 8)
            data = rom[base : base + 8]
            ptr, extra = struct.unpack("<II", data)
            
            # Detección de Rol por Bytes (Regla Maestra - Universal)
            # Pattern XX XX 00 00: El segundo byte es no-nulo, y los últimos dos son 0.
            # Esto identifica candidatos de matrimonio en todas las versiones.
            byte_1 = (extra >> 8) & 0xFF
            byte_2 = (extra >> 16) & 0xFF
            byte_3 = (extra >> 24) & 0xFF
            
            is_candidate = (byte_1 != 0) and (byte_2 == 0) and (byte_3 == 0)
            role = "Candidato" if is_candidate else "Aldeano"
            
            # Nombre (Referencia)
            name_off = ptr & 0x01FFFFFF
            name_bytes = bytearray()
            for j in range(32):
                b = rom[name_off + j]
                if b == 0: break
                name_bytes.append(b)
            name = name_bytes.decode('windows-1252', errors='ignore')
            
            # Excepción especial para Sprites (aunque sigan patrón de aldeano)
            # El usuario mencionó que siguen la lógica de aldeanos en bytes, 
            # pero podemos refinarlos por nombre si es necesario.
            sprites = ["Chef", "Nappy", "Hoggy", "Bold", "Staid", "Aqua", "Timmid"]
            if not is_candidate and any(s in name for s in sprites):
                role = "Harvest Sprite"
            
            self.npcs.append({
                "id": i,
                "name": name,
                "role": role,
                "raw": data.hex(' ').upper()
            })
            print(f"ID [{i:03d}] {name.ljust(15)} | Rol: {role.ljust(15)} | Struct: {data.hex(' ').upper()}")
            
        return self.npcs

    def get_npc_graphics(self, npc_id):
        """Calcula los offsets exactos para un NPC ID dado."""
        # Mapeo de ID de Personaje a Portrait
        # Basado en la evidencia: ID 82 (Ann) -> 0x557CBC
        # 0x557CBC = 0x556CBC + (82 - 80) * 2048. CORRECTO.
        port_off = self.portrait_base + (npc_id - self.portrait_id_offset) * self.portrait_stride
        
        # Mapeo de Paleta
        # Ann (ID 82) suele usar la paleta 12 o similar en este banco.
        # Por ahora usaremos un mapeo lineal o dejaremos que el usuario ajuste.
        pal_off = self.palette_base + (npc_id % 50) * self.palette_stride
        
        return port_off, pal_off