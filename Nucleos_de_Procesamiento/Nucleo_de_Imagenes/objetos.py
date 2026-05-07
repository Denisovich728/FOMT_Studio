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
        new_offset = self.parser.project.allocate_free_space(len(encoded))
        self.parser.project.write_patch(new_offset, encoded)
        gba_ptr = struct.pack("<I", new_offset | 0x08000000)
        # El puntero al nombre está en el offset 0 de la estructura
        self.parser.project.write_patch(self.base_offset, gba_ptr)
        self.name_str = new_name
        self.name_ptr = new_offset | 0x08000000

    def save_desc_in_place(self, new_desc):
        if not hasattr(self, 'desc_ptr') or self.desc_ptr == 0:
            return
        # Codificar descripción (FoMT usa \n para saltos de línea en descripciones)
        encoded = new_desc.encode('windows-1252', errors='replace') + b'\x00'
        new_offset = self.parser.project.allocate_free_space(len(encoded))
        self.parser.project.write_patch(new_offset, encoded)
        gba_ptr = struct.pack("<I", new_offset | 0x08000000)
        
        # El puntero a la descripción está al final de la estructura (byte 8 en 12-byte, byte 12 en 16-byte)
        stride = 12 if self.category != "Consumible/Comida" else 16
        desc_ptr_offset = self.base_offset + (stride - 4)
        self.parser.project.write_patch(desc_ptr_offset, gba_ptr)
        
        self.desc_str = new_desc
        self.desc_ptr = new_offset | 0x08000000
        
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
        data = self.parser.project.read_rom(self.base_offset, 12)
        if not data or len(data) < 12: return
        
        # Estructura de 12 bytes: 4 PunteroNombre, 4 DatosInfo, 4 PunteroDesc
        self.name_ptr, info, self.desc_ptr = struct.unpack('<III', data)
        self.real_id = info & 0xFFFF
        
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
        self.tools_off = 0x10E9C4
        self.foods_off = 0x111B90
        self.articles_off = 0x113D8C
        self.products_off = 0x114200
        self.misc_off = 0
        
        self._anchor_hunt_item_tables()
        
    def _anchor_hunt_item_tables(self):
        """Escanea o toma del CSV los punteros."""
        cfg = self.project.super_lib.cfg
        if cfg["TOOLS_TABLE"][0] > 0: self.tools_off = cfg["TOOLS_TABLE"][0]
        if cfg["FOODS_TABLE"][0] > 0: self.foods_off = cfg["FOODS_TABLE"][0]
        if cfg["MISC_TABLE"][0] > 0: self.misc_off = cfg["MISC_TABLE"][0]
        
        # Intentar localizar tabla de productos (Precios de Venta) si no hay CSV
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

        # 3. Variados (12 bytes stride)
        start, end = cfg.get("MISC_TABLE", (0, 0))
        if start > 0:
            count = (end - start + 1) // 12
            for i in range(count):
                it = GenericItem(self, i, start + (i * 12))
                it.read_stats("Artículo") # Renombrado de Variados/Artículo/Semilla a solo Artículo
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
        
    def read_string(self, ptr):
        if ptr < 0x08000000 or ptr >= 0x09000000:
            return f"0x{ptr:08X}"
        offset = ptr & 0x01FFFFFF
        s_bytes = bytearray()
        
        while True:
            b = self.project.read_rom(offset, 1)
            if not b or b[0] == 0:
                break
            s_bytes.append(b[0])
            offset += 1
                
        try:
            return s_bytes.decode('windows-1252', errors='ignore').replace('\n', ' ').strip()
        except:
            return "DataErr"
