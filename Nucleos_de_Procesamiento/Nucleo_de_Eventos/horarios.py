import struct
from Perifericos.Traducciones.i18n import tr

class EventScheduleNode:
    def __init__(self, raw_bytes):
        self.hour, self.minute, self.map_id, _, self.x, self.y, self.anim, _ = struct.unpack('<BBBBBBBB', raw_bytes[:8])
        self.valid = (self.hour <= 24 and self.map_id < 0x80)

class ScheduleParser:
    def __init__(self, project):
        self.project = project

    def decode_npc_schedule(self, npc, lang='es'):
        """ Copia y traduce todo desde el puntero hasta el inicio del siguiente (Lógica de Delimitación). """
        ptr = getattr(npc, "personality_ptr", 0)
        size = getattr(npc, "routine_size", 64)
        name = getattr(npc, "name_str", "Unknown").upper()
        
        if ptr < 0x08000000 or ptr >= 0x09000000:
            return ("// [Error] Invalid Pointer", "// Sched Data Missing")
            
        real_offset = ptr & 0x01FFFFFF
        # Copia todo el tramo hasta el siguiente puntero
        raw_data = self.project.read_rom(real_offset, size)
        
        cpp_lines = [f"// SCHEDULE: {name} @ 0x{ptr:08X} (Largo: {size} bytes)"]
        pseudo_lines = [f"=== {tr('lbl_routine', lang)} {name} ===\n"]
        
        for i in range(0, len(raw_data), 8):
            block = raw_data[i:i+8]
            if len(block) < 8: break
            
            node = EventScheduleNode(block)
            if not node.valid: # Si choca con datos inválidos o terminador
                 cpp_lines.append(f"evnt_sched_end(); // 00 00 00 00 Block")
                 break
            
            # Traducción cruda a Macros GBA y Resumen
            cpp_lines.append(f"evnt_npc_sched(TIME_{node.hour}H_{node.minute}M, MAP_{node.map_id:02X}, X:{node.x}, Y:{node.y}, ANIM_{node.anim});")
            
            travel_str = tr('sched_travel', lang).format(time=f"{node.hour:02d}:{node.minute:02d}", map=f"ID {node.map_id:02X}")
            pos_str = tr('sched_pos', lang).format(x=node.x, y=node.y)
            anim_str = tr('sched_anim', lang).format(anim=node.anim)
            
            pseudo_lines.append(f"{travel_str}\n{pos_str}\n{anim_str}\n")
            
        pseudo_lines.append(tr('sched_end', lang))
        return ("\n".join(cpp_lines), "\n".join(pseudo_lines))
