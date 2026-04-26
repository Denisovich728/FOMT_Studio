import struct

class BaseItem:
    def __init__(self, parser, index, offset):
        self.parser = parser
        self.index = index
        self.base_offset = offset
        self.name_str = "Desconocido"
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
            
        # Codificar nuevo nombre
        encoded = new_name.encode('windows-1252', errors='replace') + b'\x00'
        
        # Paso 1: Asignar espacio libre alineado a 4 bytes de forma centralizada
        new_offset = self.parser.project.allocate_free_space(len(encoded))
        self.parser.project.write_patch(new_offset, encoded)
        
        # Paso 2: Actualizar el puntero en la estructura del Item (Capa Virtual)
        # El name_ptr es el primer campo (4 bytes) en GenericItem y FoodItem
        gba_ptr = struct.pack("<I", new_offset | 0x08000000)
        self.parser.project.write_patch(self.base_offset, gba_ptr)
        
        self.name_str = new_name
        self.name_ptr = new_offset | 0x08000000
        
    def save_sell_price(self, new_price):
        if not self.product_offset: return
        data = list(self.parser.project.read_rom(self.product_offset, 4))
        # Price is bits 0-14, Kind is bit 15.
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
        pass # Base no hace nada

class GenericItem(BaseItem):
    SIZE = 12
    # Struct: name_ptr (4), icon (2), padding (2), desc_ptr (4) = 12 bytes
    def read_stats(self, category):
        self.category = category
        data = self.parser.project.read_rom(self.base_offset, self.SIZE)
        name_ptr, icon, desc_ptr = struct.unpack('<IHxxI', data)
        self.name_ptr = name_ptr
        self.icon_id = icon
        self.desc_ptr = desc_ptr
        self.name_str = self.parser.read_string(name_ptr)
        
        return {
            "ID": self.index,
            "Categoría": self.category,
            "Nombre": self.name_str,
            "Preción (G)": self.price,
            "Precio Compra (G)": self.buy_price,
            "Stamina": self.stamina,
            "Fatigue": self.fatigue,
            "Es Bebida": self.is_drink,
            "Icono ID": self.icon_id,
            "max_len": len(self.name_str.encode('windows-1252', errors='replace'))
        }

class FoodItem(BaseItem):
    SIZE = 16
    def read_stats(self, category):
        self.category = category
        data = self.parser.project.read_rom(self.base_offset, self.SIZE)
        name_ptr, flags, stamina, fatigue, unk, icon, desc_ptr = struct.unpack('<IBbbBHxxI', data)
        self.name_ptr = name_ptr
        self.is_drink = bool(flags & 1)
        self.stamina = stamina
        self.fatigue = fatigue
        self.icon_id = icon
        self.desc_ptr = desc_ptr
        self.name_str = self.parser.read_string(name_ptr)
        
        return {
            "ID": self.index,
            "Categoría": self.category,
            "Nombre": self.name_str,
            "Preción (G)": self.price,
            "Precio Compra (G)": self.buy_price,
            "Stamina": self.stamina,
            "Fatigue": self.fatigue,
            "Es Bebida": self.is_drink,
            "Icono ID": self.icon_id,
            "max_len": len(self.name_str.encode('windows-1252', errors='replace'))
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
        
        # Offsets por defecto (Stanhash USA), usados solo como fallback si el escáner falla.
        # En US: Tools(0x10E9C4), Foods(0x111B90), Articles(0x113D8C), Products(0x114200)
        self.tools_off = 0x10E9C4
        self.foods_off = 0x111B90
        self.articles_off = 0x113D8C
        self.products_off = 0x114200
        
        # Iniciar rastreador para anclar las localizaciones reales en Mfomt/Fomt custom roms!
        self._anchor_hunt_item_tables()
        
    def _find_table_anchor(self, magic_string: bytes, expect_stride: int):
        """ Busca un string en la ROM, empaqueta su puntero y busca qué tabla lo referencia """
        rom_data = self.project.base_rom_data
        if not rom_data: return None
        
        str_idx = rom_data.find(magic_string)
        if str_idx == -1: return None
        
        # Crear puntero GBA little endian
        ptr = struct.pack('<I', str_idx | 0x08000000)
        
        # Buscar ese puntero a lo largo de la ROM entera
        # Como es el "Primer" item de su respectiva tabla (Tools/ID0), la direccion donde hallemos
        # este pointer es *exactamente* el Offset inicial de la tabla entera!
        table_idx = rom_data.find(ptr)
        if table_idx == -1: return None
        
        return table_idx & 0x01FFFFFF

    def _anchor_hunt_item_tables(self):
        """ Escáner principal estilo SlipSpace_Engine Dinámico """
        # Tool ID 0 es siempre Iron Sickle
        tools_found = self._find_table_anchor(b"Iron Sickle\0", 12)
        if tools_found: self.tools_off = tools_found
        
        # Food ID 0 es Turnip (Nabo) PERO en USA el Food 0 es también Turnip? Wait, no. Food 0 es qué?
        # En item.hh de stanhash, Food_Turnip es Food_Turnip, pero name es Turnip?
        # En la Biblia C++, Food_Turnip se llama "Turnip" y Article_Turnip se llama también "Turnip".
        # Mejor buscamos "Moon Drop Grass" que es el Article 0 (Article\item.def)
        articles_found = self._find_table_anchor(b"Moon Drop Grass\0", 12)
        if articles_found: 
            self.articles_off = articles_found
            # Y Sabemos mágicamente que Products sigue directamente a Articles en memoria
            # Limite Articles = 95. Stride = 12. Total = 1140 (0x474) bytes
            self.products_off = self.articles_off + (95 * 12)
        
        # Food ID 0 en la JAP era algo distinto? En US es "Turnip"
        # Usaré una comida exótica como el "French Fries" o "SUGUDZA_APPLE" para no chocar con articulo.
        # "SUGDW Apple\0" es la comida 1, "Turnip\0" es Food 0. 
        # Intentemos hallar la tabla de "Apple\0"
        apple_str = b"Apple\0"
        rom = self.project.base_rom_data
        if rom:
            ptr_apple = struct.pack('<I', rom.find(apple_str) | 0x08000000)
            # Find all references. The one in a 16-stride table is the Food Apple (ID 9).
            idx = rom.find(ptr_apple)
            if idx != -1:
                # If we assume it's food 9, base is idx - (9*16)
                # Too heuristic, let's stick to standard offset discovery or fallback.
                # Actually Turnip\0 is fine, it will find the Food table usually or Article table.
                turnip = struct.pack('<I', rom.find(b"Turnip\0") | 0x08000000)
                matches = []
                cursor = 0
                while True:
                    cursor = rom.find(turnip, cursor)
                    if cursor == -1: break
                    matches.append(cursor)
                    cursor += 1
                
                # The first might be Article, second might be Food. Or viceversa.
                for m in matches:
                    if m != articles_found: # It must be the other!
                        # En la comida, "Turnip" NO está en índice 0!
                        pass
        
        # Ajuste Fino FoMT/MFoMT Delta si Anchor falla
        if not tools_found and not articles_found:
            is_mfomt = self.project.is_mfomt
            delta = 0 if not is_mfomt else 0x2BD58 # Heurístico simple MFoMT delta
            self.tools_off = (0x10E9C4 + delta) & 0x01FFFFFF
            self.foods_off = (0x111B90 + delta) & 0x01FFFFFF
            self.articles_off = (0x113D8C + delta) & 0x01FFFFFF
            self.products_off = (0x114200 + delta) & 0x01FFFFFF
            
        # Parche Mágico Heurístico: Si hallé Article y Tools, y Food falló, calculemos interpolando:
        if articles_found and tools_found:
            # En GBA, Food está entre Tools y Articles.
            # USA: Tools(10E9C4) ..[0x31CC].. Foods(111B90) ..[0x21FC].. Articles(113D8C)
            # La diferencia Tools->Foods es enorme por otras cosas. Sin embargo, en MFoMT 
            # también están relativos. Usaré el Delta desde Tools:
            delta_math = articles_found - 0x113D8C
            self.foods_off = 0x111B90 + delta_math
        
    def scan_foods(self):
        """Retorna TODO el armamento cruzado con precios! (Ex-scan_foods)"""
        self.items.clear()
        
        # 1. Cargar Tools (81 limit)
        for i in range(81):
            tool = GenericItem(self, i, self.tools_off + (i * 12))
            try:
                tool.read_stats("Herramienta")
                self.items.append(tool)
            except Exception: pass
            
        # 2. Cargar Foods (171 limit)
        for i in range(171):
            food = FoodItem(self, i, self.foods_off + (i * 16))
            try:
                food.read_stats("Consumible/Comida")
                self.items.append(food)
            except Exception: pass
            
        # 3. Cargar Articles (95 limit)
        for i in range(95):
            art = GenericItem(self, i, self.articles_off + (i * 12))
            try:
                art.read_stats("Artículo/Semilla")
                self.items.append(art)
            except Exception: pass
            
        # 4. Cruzar Tabla de Precios (ProductInfo - 103 items)
        for i in range(103):
            data = self.project.read_rom(self.products_off + (i * 4), 4)
            if not data or len(data) < 4: continue
            
            # ProductInfo: price (15 bit), kind (1 bit), item_id (8 bit layout in padding)
            hword = struct.unpack('<H', data[0:2])[0]
            price = hword & 0x7FFF
            kind_is_article = bool(hword & 0x8000)
            item_id = struct.unpack('<B', data[2:3])[0]
            
            # Matchear el item subyacente para inyectarle el precio de venta en caja!
            for itm in self.items:
                if kind_is_article and itm.category == "Artículo/Semilla" and itm.index == item_id:
                    itm.price = price
                    itm.product_offset = self.products_off + (i * 4)
                elif not kind_is_article and itm.category == "Consumible/Comida" and itm.index == item_id:
                    itm.price = price
                    itm.product_offset = self.products_off + (i * 4)
                    
        # 5. Mapeado de Precios de Compra (Tiendas y Supermercado)
        # Delegamos completamente la responsabilidad al analizador de Tiendas
        if self.project.shop_parser:
            self.project.shop_parser.link_items_to_shops(self.items)
            
        return self.items
                
        return self.items
        
    def read_string(self, ptr):
        if ptr < 0x08000000 or ptr >= 0x09000000:
            return "Unknown"
        offset = ptr & 0x01FFFFFF
        s_bytes = bytearray()
        
        while True:
            b = self.project.read_rom(offset, 1)
            if not b or b[0] == 0:
                break
            s_bytes.append(b[0])
            offset += 1
            if len(s_bytes) > 50: # safety limit
                break
                
        try:
            # Los juegos de USA usan CP1252/ASCII extendido para inglés. Tratamos de limpiar caracteres raros.
            return s_bytes.decode('windows-1252', errors='ignore').replace('\n', ' ')
        except:
            return "DataErr"
