class MemoryManager:
    """
    Gestor de Memoria Virtual para parches en ROM.
    Coordina la lectura entre la ROM base y los parches definidos en el proyecto.
    Usa offsets del CSV para tablas de punteros.
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

    def _align_to_4(self, offset):
        """Alinea un offset a múltiplo de 4 bytes."""
        return (offset + 3) & ~3

    def _offset_to_gba_le(self, offset):
        """
        Convierte un offset ROM a puntero GBA en Little Endian.
        Offset big endian → OR con 0x08000000 → struct.pack('<I') = Little Endian.
        """
        import struct
        gba_addr = offset | 0x08000000
        return struct.pack("<I", gba_addr)

    def re_point_event(self, event_id, new_offset):
        """
        Repuntea un evento en la Master Table.
        Convierte el offset a GBA LE y lo alinea a múltiplo de 4.
        """
        import struct
        # Alineación forzada a múltiplo de 4
        new_offset = self._align_to_4(new_offset)
        
        table_base = self.proyecto.super_lib.table_offset
        ptr_location = table_base + (event_id * 4)
        
        # Escribir puntero en formato GBA Little Endian
        gba_le_bytes = self._offset_to_gba_le(new_offset)
        self.proyecto.write_patch(ptr_location, gba_le_bytes)
        return ptr_location

    def re_point_name(self, npc_index, new_offset):
        """
        Repuntea un nombre de NPC en la tabla maestra (offset del CSV).
        Filas de 8 bytes. El puntero de nombre está en bytes [00-03].
        """
        import struct
        table_base = self.proyecto.super_lib.npc_table_offset
        npc_limit = self.proyecto.super_lib.npc_limit
        
        if npc_index >= npc_limit:
            print(f"Error: Índice de NPC {npc_index} fuera del límite (máx {npc_limit - 1}).")
            return None

        # Cada entrada es 8 bytes, puntero de nombre en offset 0
        ptr_location = table_base + (npc_index * 8)
        
        # Alineación forzada a 4 bytes
        new_offset = self._align_to_4(new_offset)
        
        # Escribir puntero GBA en Little Endian
        gba_le_bytes = self._offset_to_gba_le(new_offset)
        self.proyecto.write_patch(ptr_location, gba_le_bytes)
        return ptr_location

    def re_point_npc_script(self, npc_index, new_offset):
        """
        Repuntea el script de diálogo de un NPC.
        La tabla de scripts está en 0xF9940 (separada de la tabla NPC).
        """
        import struct
        table_base = 0xF9940
        
        ptr_location = table_base + (npc_index * 4)
        
        # Alineación forzada a 4 bytes para el destino
        new_offset = self._align_to_4(new_offset)
        
        # Escribir puntero GBA en Little Endian
        gba_le_bytes = self._offset_to_gba_le(new_offset)
        self.proyecto.write_patch(ptr_location, gba_le_bytes)
        return ptr_location

    def repoint_with_alignment(self, ptr_location, new_data_offset):
        """
        Repunteo genérico con alineación:
        1. Alinea new_data_offset a múltiplo de 4
        2. Convierte a GBA pointer (OR 0x08000000)
        3. Escribe en Little Endian en ptr_location
        """
        aligned_offset = self._align_to_4(new_data_offset)
        gba_le_bytes = self._offset_to_gba_le(aligned_offset)
        self.proyecto.write_patch(ptr_location, gba_le_bytes)
        print(f"Repoint Virtual: 0x{ptr_location:08X} → 0x{aligned_offset:08X}")
        return aligned_offset

    def re_point_master_event(self, event_id: int, old_offset: int, old_size: int, new_data: bytes) -> int:
        """Repuntea un evento de la Master Table."""
        return self._re_point_generic_script(
            new_data, 
            old_offset, 
            old_size, 
            lambda off: self.re_point_event(event_id, off)
        )

    def re_point_map_script(self, map_id: int, old_offset: int, old_size: int, new_data: bytes) -> int:
        """Repuntea el script de un mapa (Room)."""
        import struct
        def update_header(off):
            m = self.proyecto.map_parser.get_map_by_id(map_id)
            if m:
                # El puntero al script está en el offset 12 de la cabecera (24 bytes)
                ptr_loc = m.offset + 12
                gba_le = self._offset_to_gba_le(off)
                self.proyecto.write_patch(ptr_loc, gba_le)
                m.p_script = struct.unpack('<I', gba_le)[0]
                print(f"🗺️ [MapScript] Repunteado Mapa {map_id} a 0x{off:06X} (VIRTUAL)")

        return self._re_point_generic_script(new_data, old_offset, old_size, update_header)

    def _re_point_generic_script(self, new_data: bytes, old_offset: int, old_size: int, repoint_callback, cleaning_limit: int = 0) -> int:
        """Lógica de repunteo quirúrgica: solo limpia hasta el cleaning_limit si se provee."""
        
        # FORZAR ALINEACIÓN A 4 BYTES (Padding)
        remainder = len(new_data) % 4
        if remainder > 0:
            new_data += b'\x00' * (4 - remainder)
            
        new_size = len(new_data)
        
        # 0. Verificación de escritura In-Place (SÓLO SI ESTÁ ALINEADO)
        # Si la dirección original es IMPAR, forzamos el repunteo a un bloque nuevo 0,4,8,C
        is_aligned = (old_offset % 4 == 0) if old_offset else False
        
        if old_offset and is_aligned and new_size <= old_size:
            print(f"🎯 [In-Place-Aligned] Sobrescribiendo en 0x{old_offset:06X}")
            # Si hay un límite definido (siguiente puntero), limpiamos hasta allí
            if cleaning_limit > old_offset:
                total_space = cleaning_limit - old_offset
                padding_needed = total_space - new_size
                if padding_needed > 0:
                    self.proyecto.write_patch(old_offset, new_data + (b'\xFF' * padding_needed))
                else:
                    self.proyecto.write_patch(old_offset, new_data)
            else:
                self.proyecto.write_patch(old_offset, new_data)
            
            repoint_callback(old_offset)
            return old_offset
            
        if old_offset and not is_aligned:
            print(f"🚀 [Forcing-Repoint] Dirección original 0x{old_offset:06X} no alineada. Buscando bloque 0,4,8,C...")

        # 1. Limpieza Quirúrgica (Hasta el siguiente puntero si existe)
        if old_offset:
            limit = old_size
            if cleaning_limit > old_offset:
                limit = cleaning_limit - old_offset
            
            max_limit = min(limit, len(self.proyecto.virtual_rom) - old_offset)
            self.proyecto.write_patch(old_offset, b'\xFF' * max_limit)
            print(f"🧹 [Surgical-Clean] 0x{old_offset:06X} -> 0x{old_offset + max_limit:06X}")

        # 2. Búsqueda de hueco de 0xFF en el buffer virtual
        new_offset = self._find_free_space(new_size)
        
        if not new_offset:
            # Fallback: Usar el puntero de espacio libre al final de la ROM
            new_offset = self.proyecto.allocate_free_space(new_size)
            print(f"📦 [Virtual-Asignación] Usando nuevo espacio al final en 0x{new_offset:06X}")
        else:
            print(f"♻️ [Virtual-Reciclaje] Reutilizando hueco de FF en 0x{new_offset:06X}")
        
        # 3. Escritura y Ejecución del callback de repunteo
        self.proyecto.write_patch(new_offset, new_data)
        repoint_callback(new_offset)
        
        return new_offset

    def _find_free_space(self, size: int) -> int:
        """Busca un bloque contiguo de bytes 0xFF en el buffer virtual."""
        rom_data = self.proyecto.virtual_rom
        if not rom_data: return 0
        
        target = b'\xFF' * size
        # Empezar búsqueda después de la firma N_MODE para evitar tocar tablas vitales
        start_search = 0x13AA30 
        
        idx = rom_data.find(target, start_search)
        while idx != -1:
            # Validar alineación a 4 bytes para GBA
            if idx % 4 == 0:
                return idx
            idx = rom_data.find(target, idx + 1)
            
        return 0

    def toggle_debug_mode(self):
        """
        Busca el script del calendario en la casa del jugador y lo cambia por el menú debug (0x080E).
        """
        import struct
        NORMAL_SCRIPT = 0x020B
        DEBUG_SCRIPT = 0x080E
        
        if not self.proyecto.map_parser or not self.proyecto.map_parser.maps:
            self.proyecto.map_parser.scan_maps()
            
        farm_house = self.proyecto.map_parser.get_map_by_id(1)
        if not farm_house:
            return False, False
            
        self.proyecto.map_parser.load_map_data(farm_house)
        
        target_script = None
        for s in farm_house.scripts:
            if s.script_id == NORMAL_SCRIPT or s.script_id == DEBUG_SCRIPT:
                target_script = s
                break
                
        if target_script:
            new_id = DEBUG_SCRIPT if target_script.script_id == NORMAL_SCRIPT else NORMAL_SCRIPT
            is_enabled = (new_id == DEBUG_SCRIPT)
            script_id_offset = target_script.rom_offset + 4
            self.proyecto.write_patch(script_id_offset, struct.pack('<H', new_id))
            target_script.script_id = new_id
            return True, is_enabled
        else:
            candidates = [0x103748, 0x105550]
            rom_data = self.proyecto.virtual_rom
            for addr in candidates:
                if addr + 2 > len(rom_data): continue
                current_id = struct.unpack_from('<H', rom_data, addr)[0]
                if current_id == NORMAL_SCRIPT or current_id == DEBUG_SCRIPT:
                    new_id = DEBUG_SCRIPT if current_id == NORMAL_SCRIPT else NORMAL_SCRIPT
                    self.proyecto.write_patch(addr, struct.pack('<H', new_id))
                    return True, (new_id == DEBUG_SCRIPT)
            return False, False

    def relocate_master_event_table(self, new_capacity: int):
        """
        Reubica la tabla maestra de eventos a un nuevo espacio libre.
        Copia los punteros existentes y actualiza el puntero del motor (0x03F89C en FoMT).
        Retorna el nuevo offset y un mensaje de estado.
        """
        if self.proyecto.is_mfomt:
            return None, "Reubicación de tabla no soportada aún para MFoMT (falta puntero del motor)."
            
        engine_ptr_offset = 0x03F89C
        old_table_offset = self.proyecto.super_lib.table_offset
        old_limit = self.proyecto.super_lib.event_limit
        
        if new_capacity <= old_limit:
            return None, f"La nueva capacidad ({new_capacity}) debe ser mayor que la actual ({old_limit})."
            
        new_size = new_capacity * 4
        new_offset = self._find_free_space(new_size)
        
        if new_offset == 0:
            return None, "No se encontró espacio libre suficiente en la ROM para reubicar la tabla."
            
        # 1. Copiar la tabla antigua al nuevo espacio
        old_table_data = self.proyecto.read_rom(old_table_offset, old_limit * 4)
        
        # Rellenar el resto de la nueva tabla con 0x00000000 (punteros nulos)
        padding_size = (new_capacity - old_limit) * 4
        new_table_data = old_table_data + (b'\x00' * padding_size)
        
        self.proyecto.write_patch(new_offset, new_table_data)
        
        # 2. Actualizar el puntero del motor para que use la nueva tabla
        # Aplicamos la lógica de la Base Fantasma: New_Ghost_Base = New_Free_Space - 4
        ghost_base = new_offset - 4
        self.repoint_with_alignment(engine_ptr_offset, ghost_base)
        
        # 3. Limpiar la tabla antigua (0xFF) para recuperar el espacio
        self.proyecto.write_patch(old_table_offset, b'\xFF' * (old_limit * 4))
        
        # 4. Actualizar estado de SuperLibrary
        self.proyecto.super_lib.cfg["MASTER_TABLE_OFFSET"] = new_offset
        self.proyecto.super_lib.cfg["EVENT_LIMIT"] = new_capacity
        
        return new_offset, f"Tabla de Eventos reubicada a 0x{new_offset:06X}. Límite expandido de {old_limit} a {new_capacity} eventos."
