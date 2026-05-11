import struct

class BaseItem:
    def __init__(self, parser, index, offset):
        self.parser = parser
        self.index = index
        self.base_offset = offset
        self.name_str = "Desconocido"
        self.desc_str = "Sin descripción"
        self.name_ptr = 0
        self.desc_ptr = 0
        self.is_drink = False
        self.stamina = 0
        self.fatigue = 0
        self.price = 0
        self.buy_price = 0
        self.category = "Item"
        self.product_offset = None # Para parchear precios
        
    def save_name_in_place(self, new_name):
        if not hasattr(self, 'name_ptr') or self.name_ptr == 0:
            return
        
        encoded = new_name.encode('windows-1252', errors='replace') + b'\x00'
        old_off = self.name_ptr & 0x01FFFFFF
        old_size = self.parser.get_string_size(self.name_ptr)
        
        # Usar el Gestor de Memoria inteligente para reubicar y repuntear
        new_offset = self.parser.project.memory._re_point_generic_script(
            encoded,
            old_off,
            old_size,
            lambda off: self.parser.project.write_patch(self.base_offset, struct.pack("<I", off | 0x08000000))
        )
        
        self.name_str = new_name
        self.name_ptr = new_offset | 0x08000000
        print(f"DEBUG: Item {self.index} NAME Repoint -> 0x{new_offset:08X}")

    def save_desc_in_place(self, new_desc):
        if not hasattr(self, 'desc_ptr') or self.desc_ptr == 0:
            return
            
        # Usar el motor de escritura del parser para soportar comandos [0D], [n]
        encoded = self.parser.write_string(new_desc)
        old_off = self.desc_ptr & 0x01FFFFFF
        old_size = self.parser.get_string_size(self.desc_ptr)
        
        # Calcular el offset exacto según la categoría (Basado en la inspección de la ROM)
        if self.category == "Herramienta":
            desc_ptr_offset = self.base_offset + 8
        elif self.category == "Consumible/Comida":
            desc_ptr_offset = self.base_offset + 12
        else: # Artículo / Variado (Confirmado 12 bytes en esta ROM)
            desc_ptr_offset = self.base_offset + 8
        
        new_offset = self.parser.project.memory._re_point_generic_script(
            encoded,
            old_off,
            old_size,
            lambda off: self.parser.project.write_patch(desc_ptr_offset, struct.pack("<I", off | 0x08000000))
        )
        
        self.desc_str = new_desc
        self.desc_ptr = new_offset | 0x08000000
        print(f"DEBUG: Item {self.index} DESC Repoint -> 0x{new_offset:08X}")
        
    def save_sell_price(self, new_price):
        if not self.product_offset: return
        data = list(self.parser.project.read_rom(self.product_offset, 4))
        old_hword = struct.unpack('<H', bytes(data[0:2]))[0]
        kind_flag = old_hword & 0x8000
        new_hword = kind_flag | (new_price & 0x7FFF)
        data[0:2] = struct.pack('<H', new_hword)
        self.parser.project.write_patch(self.product_offset, bytes(data))
        self.price = new_price
        
    def save_buy_price(self, new_price):
        if hasattr(self, 'shop_entry') and self.shop_entry:
            self.shop_entry.save_price(new_price)
            self.buy_price = new_price
        
    def save_stats(self, stamina, fatigue, price):
        pass

class GenericItem(BaseItem):
    SIZE = 12
    # Estructura: NombrePtr (4), Datos (4), DescripcionPtr (4)
    def read_stats(self, category):
        self.category = category
        stride = 16 if self.category == "Consumible/Comida" else 12
        data = self.parser.project.read_rom(self.base_offset, stride)
        if not data or len(data) < stride: return
        
        # Herramientas: 12 bytes (PtrName, Info, PtrDesc)
        # Artículos: 8 bytes (PtrName, PtrDesc)
        if len(data) == 12:
            self.name_ptr, info, self.desc_ptr = struct.unpack('<III', data)
            self.real_id = info & 0xFFFF
        else:
            self.name_ptr, self.desc_ptr = struct.unpack('<II', data[:8])
            self.real_id = self.index
        
        self.name_str = self.parser.read_string(self.name_ptr)
        self.desc_str = self.parser.read_string(self.desc_ptr)
        
        return {
            "idx": f"0x{self.index:02X}",
            "Categoría": self.category,
            "Nombre": self.name_str,
            "Descripción": self.desc_str,
            "Preción (G)": self.price,
            "Precio Compra (G)": self.buy_price,
            "Stamina": self.stamina,
            "Fatigue": self.fatigue,
            "Es Bebida": self.is_drink,
        }

class FoodItem(GenericItem):
    SIZE = 16
    # Estructura: NombrePtr (4), Datos (8), DescripcionPtr (4)
    def read_stats(self, category):
        self.category = category
        data = self.parser.project.read_rom(self.base_offset, 16)
        if not data or len(data) < 16: return
        
        # Estructura de 16 bytes: 4 PunteroNombre, 8 DatosInfo, 4 PunteroDesc
        self.name_ptr = struct.unpack('<I', data[0:4])[0]
        # Para la comida, el ID real utilizado en los scripts (como Search_Food_Gift_Address)
        # es exactamente su índice en esta tabla.
        self.real_id = self.index
        self.desc_ptr = struct.unpack('<I', data[12:16])[0]
        
        self.name_str = self.parser.read_string(self.name_ptr)
        self.desc_str = self.parser.read_string(self.desc_ptr)
        
        # Datos de stamina/fatiga (suelen estar en los primeros 4 bytes del bloque de info)
        self.stamina = struct.unpack('<b', data[5:6])[0]
        self.fatigue = struct.unpack('<b', data[6:7])[0]
        self.is_drink = bool(data[4] & 1)
        
        return {
            "idx": f"0x{self.real_id:02X}",
            "Categoría": self.category,
            "Nombre": self.name_str,
            "Descripción": self.desc_str,
            "Preción (G)": self.price,
            "Precio Compra (G)": self.buy_price,
            "Stamina": self.stamina,
            "Fatigue": self.fatigue,
            "Es Bebida": self.is_drink,
        }

    def save_stats(self, stamina, fatigue, price):
        data = list(self.parser.project.read_rom(self.base_offset, self.SIZE))
        data[5] = struct.pack('<b', stamina)[0]
        data[6] = struct.pack('<b', fatigue)[0]
        self.parser.project.write_patch(self.base_offset, bytes(data))

class ItemParser:
    def __init__(self, project):
        self.project = project
        self.items = []
        
        # Punteros por defecto (USA) como respaldo
        # Punteros por defecto (USA) como respaldo si el CSV falla
        self.tools_off = 0x10E9C4
        self.foods_off = 0x111B90
        self.articles_off = 0x113D8C
        self.products_off = 0x114200
        self.misc_off = 0
        
        self._anchor_hunt_item_tables()
        self.scan_foods() # Escanear todo al inicio para tener la lista maestra lista
        
    def _anchor_hunt_item_tables(self):
        """Sincroniza los punteros usando la Tabla Maestra si está disponible."""
        cfg = self.project.super_lib.cfg
        master_off = cfg.get("MASTER_TABLE_OFFSET", 0x0F89D4)
        
        # Ejemplo: Si sabemos que el puntero a Tools está en Master + 0x20
        # self.tools_off = self.project.read_pointer(master_off + 0x20)
        
        if "TOOLS_TABLE" in cfg and cfg["TOOLS_TABLE"][0] > 0: 
            self.tools_off = cfg["TOOLS_TABLE"][0]
        if "FOODS_TABLE" in cfg and cfg["FOODS_TABLE"][0] > 0: 
            self.foods_off = cfg["FOODS_TABLE"][0]
        if "MISC_TABLE" in cfg and cfg["MISC_TABLE"][0] > 0: 
            self.articles_off = cfg["MISC_TABLE"][0]
        
        if self.project.is_mfomt:
             self.products_off = 0x114200 + 0x2BD58

    def scan_foods(self):
        """Pobla la lista de items dividida por categorías."""
        self.items.clear()
        cfg = self.project.super_lib.cfg
        
        # 1. Herramientas (12 bytes stride)
        start, end = cfg.get("TOOLS_TABLE", (0, 0))
        if start > 0:
            count = (end - start + 1) // 12
            for i in range(count):
                it = GenericItem(self, i, start + (i * 12))
                it.read_stats("Herramienta")
                self.items.append(it)
        
        # 2. Comestibles (16 bytes stride)
        start, end = cfg.get("FOODS_TABLE", (0, 0))
        if start > 0:
            count = (end - start + 1) // 16
            for i in range(count):
                it = FoodItem(self, i, start + (i * 16))
                it.read_stats("Consumible/Comida")
                self.items.append(it)

        # 3. Variados/Artículos (12 bytes stride - CONFIRMADO POR INSPECCIÓN)
        start, end = cfg.get("MISC_TABLE", (0, 0))
        if start > 0:
            # En esta ROM, los artículos son de 12 bytes con Desc @ +8
            count = (end - start + 1) // 12
            for i in range(count):
                it = GenericItem(self, i, start + (i * 12))
                it.read_stats("Artículo")
                self.items.append(it)
            
        # 4. Cruzar Tabla de Precios (ProductInfo - 103 items aprox)
        # Esta tabla asocia el ID real del objeto con su precio de venta en caja.
        for i in range(150): # Escaneo extendido por si acaso
            data = self.project.read_rom(self.products_off + (i * 4), 4)
            if not data or len(data) < 4: break
            
            hword = struct.unpack('<H', data[0:2])[0]
            price = hword & 0x7FFF
            kind_is_misc = bool(hword & 0x8000)
            item_id = struct.unpack('<B', data[2:3])[0]
            
            if price == 0 and item_id == 0: continue # Entrada vacía

            for itm in self.items:
                # El cruce se hace por el ID real extraído de la estructura, no por el índice de la tabla
                if kind_is_misc and itm.category == "Artículo" and itm.real_id == item_id:
                    itm.price = price
                    itm.product_offset = self.products_off + (i * 4)
                elif not kind_is_misc and itm.category == "Consumible/Comida" and itm.real_id == item_id:
                    itm.price = price
                    itm.product_offset = self.products_off + (i * 4)
                    
        # 5. Mapeado de Precios de Compra
        if self.project.shop_parser:
            self.project.shop_parser.link_items_to_shops(self.items)
            
        return self.items
                    
        # 5. Mapeado de Precios de Compra (Tiendas y Supermercado)
        if self.project.shop_parser:
            self.project.shop_parser.link_items_to_shops(self.items)
            
        return self.items
                
        return self.items
        
    def inject_from_csv_row(self, ptr_name, text_name, ptr_desc, text_desc):
        """Inyecta una fila de CSV aplicando la lógica de repunteo atómico SlipSpace."""
        from Nucleos_de_Procesamiento.Nucleo_de_Datos.gestor_memoria import MemoryManager
        manager = MemoryManager(self.project)
        
        results = []
        # 1. Inyectar Nombre
        if ptr_name and text_name:
            data_name = self.write_string(text_name)
            # Para nombres, solemos tener poco espacio, el repunteo es vital
            success, new_gba = manager.repoint_and_write(ptr_name, data_name, cleaning_limit=0)
            results.append(success)
            
        # 2. Inyectar Descripción
        if ptr_desc and text_desc:
            data_desc = self.write_string(text_desc)
            # En descripciones, intentamos limpiar hasta el siguiente puntero si es posible
            # (El manager ya maneja esto si le pasamos 0)
            success, new_gba = manager.repoint_and_write(ptr_desc, data_desc, cleaning_limit=0)
            results.append(success)
            
        return all(results)

    def read_string(self, gba_addr):
        """Lectura Robusta SlipSpace con soporte de Ñ mapeada (B1/B2)."""
        offset = gba_addr & 0x1FFFFFF
        s = ""
        while offset < len(self.project.virtual_rom):
            b = self.project.virtual_rom[offset]
            if b == 0: break
            
            # Mapeo de Ñ (Glifos B1/B2)
            if b == 0xB1: s += "ñ"
            elif b == 0xB2: s += "Ñ"
            elif 32 <= b <= 126:
                s += chr(b)
            elif b == 10:
                s += "[n]"
            else:
                s += f"[{b:02x}]"
            offset += 1
        return s

    def write_string(self, text):
        """Convierte texto de la UI a bytes de ROM con soporte de Ñ (B1/B2)."""
        import re
        
        # Pre-procesar Ñ para el mapeo de glifos
        text = text.replace("ñ", "[b1]").replace("Ñ", "[b2]")
        
        output = bytearray()
        tokens = re.split(r'(\[[0-9A-Fa-f]{2}\]|\[n\])', text)
        
        for token in tokens:
            if not token: continue
            
            if token == "[n]":
                output.append(0x0A)
            elif re.match(r'\[[0-9A-Fa-f]{2}\]', token):
                hex_val = int(token[1:3], 16)
                output.append(hex_val)
            else:
                output.extend(token.encode('windows-1252', errors='replace'))
        
        output.append(0x00)
        return bytes(output)

    def get_string_size(self, ptr):
        """Calcula el tamaño de una string (incluyendo \0) en ROM."""
        if ptr < 0x08000000 or ptr >= 0x09000000: return 0
        offset = ptr & 0x01FFFFFF
        size = 0
        while True:
            b = self.project.read_rom(offset + size, 1)
            size += 1
            if not b or b[0] == 0: break
        return size
