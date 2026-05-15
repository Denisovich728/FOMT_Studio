# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import struct
import json
import os

class ScriptRebuilder:
    """
    Motor de Reconstrucción de Scripts para FOMT.
    Automatiza el cálculo de offsets (repunteo) y la gestión de espacio libre.
    """
    def __init__(self, project=None):
        self.project = project
        self.empty_space_start = 0x75C244
        self.header_marker = b'STR'

    def rebuild_dialogue_block(self, lines, base_id=0x98):
        """
        Reconstruye un bloque de diálogos con su tabla de índices STR.
        
        Args:
            lines (list): Lista de strings (diálogos).
            base_id (int): ID base del script (ej. 0x98 para Ann).
            
        Returns:
            bytes: El bloque binario completo listo para ser insertado.
        """
        # 1. Codificar las líneas de texto
        encoded_lines = []
        for line in lines:
            # Asegurar terminador 00
            data = line.encode('windows-1252', errors='replace') + b'\x00'
            encoded_lines.append(data)
            
        # 2. Calcular tabla de offsets
        # El primer offset suele ser 00 00 00 si es el inicio del bloque
        # Pero según el TXT, editamos el "primer HEX que no sea 00"
        
        current_offset = 0
        offsets = []
        for line_data in encoded_lines:
            offsets.append(current_offset)
            current_offset += len(line_data)
            
        # 3. Construir el Header STR
        # Estructura según TXT: STR [ID HEX] [00 00 00] [00] [Tabla...]
        header = self.header_marker
        header += struct.pack('B', base_id)
        header += b'\x00\x00\x00\x00' # Relleno inicial
        
        # 4. Construir la Tabla de Índices
        # Patrón: [Offset XX] [ID YY] [ZZ=00] [Break=00]
        index_table = b""
        for i, off in enumerate(offsets):
            # Nota: Esto es una simplificación del patrón XX YY ZZ 00
            # XX = Offset relativo
            # YY = ID de línea (incremental)
            # ZZ = 00
            # 00 = Break
            index_table += struct.pack('<HBB', off, base_id + i, 0x00)
            index_table += b'\x00'
            
        # 5. Ensamblar todo
        # [Header] [Tabla de Índices] [Datos de Texto]
        full_block = header + index_table + b"".join(encoded_lines)
        return full_block

    def suggest_new_offset(self, current_offset, old_size, new_size):
        """
        Decide si el script cabe en su lugar original o necesita repunteo.
        Siempre alinea a múltiplo de 4 bytes.
        """
        if new_size <= old_size:
            return current_offset, "In-Place"
        else:
            # Deberíamos buscar en una base de datos de espacio libre real
            if self.project and hasattr(self.project, 'next_free_space'):
                # Alinear a múltiplo de 4
                aligned = (self.project.next_free_space + 3) & ~3
                return aligned, "Repointed"
            aligned = (self.empty_space_start + 3) & ~3
            return aligned, "Repointed"

    def repoint_event_data(self, event_id, new_data):
        """
        Repunteo completo de un evento:
        1. Asigna espacio alineado a múltiplo de 4
        2. Escribe los datos en la nueva dirección
        3. Convierte el offset a puntero GBA Little Endian
        4. Actualiza la Master Table
        
        Returns:
            (new_offset, gba_pointer_hex) — El offset asignado y el puntero GBA en hex
        """
        if not self.project:
            raise RuntimeError("ScriptRebuilder requiere un proyecto válido")
        
        # Paso 1: Asignar espacio alineado a 4 bytes
        new_offset = self.project.allocate_free_space(len(new_data))
        
        # Paso 2: Escribir datos en el nuevo offset
        self.project.overwrite_rom_directly(new_offset, new_data)
        
        # Paso 3: Actualizar puntero en la Master Table (offset → GBA LE)
        self.project.memory.re_point_event(event_id, new_offset)
        
        # Paso 4: Calcular representación del puntero para log
        import struct
        gba_addr = new_offset | 0x08000000
        gba_le = struct.pack('<I', gba_addr)
        gba_hex = gba_le.hex(' ').upper()
        
        print(f"Repoint Event {event_id}: 0x{new_offset:08X} → GBA LE: [{gba_hex}]")
        return new_offset, gba_hex

# Ejemplo de uso simulado
if __name__ == "__main__":
    rebuilder = ScriptRebuilder()
    dialogos_ann = [
        "Natascha: ¡Hola! Soy nueva en el pueblo.",
        "El aire se siente tan bien aquí por la mañana.",
        "¿Tú también estás aquí, Denis?"
    ]
    
    binario = rebuilder.rebuild_dialogue_block(dialogos_ann)
    print(f"Bloque generado: {len(binario)} bytes")
    print(f"Header: {binario[:10].hex(' ')}")
