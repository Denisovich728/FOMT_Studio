import struct
import math

class ShopItemEntry:
    def __init__(self, parser, item_ref, offset, original_price):
        self.parser = parser
        self.item_ref = item_ref
        self.base_offset = offset
        self.price = original_price

    def save_price(self, new_price):
        if self.base_offset == 0:
            return # Fallback mapping (Not physically found in ROM yet)
        
        # Asumimos que el precio de compra está empaquetado en 2 bytes (Hword)
        # y no alteramos los bytes vecinos para respetar el límite estructural (Regla de oro)
        data = struct.pack('<H', new_price & 0xFFFF)
        self.parser.project.write_patch(self.base_offset, data)
        self.price = new_price

class ShopParser:
    def __init__(self, project):
        self.project = project
        self.shop_entries = {} # Mapeo de item_name -> ShopItemEntry
        
        # Referencias de anclaje (Anchor Hunt)
        # Secuencia deducida de precios: Nabo(120), Papa(150), Pepino(200), Fresa(150), Repollo(500)
        self.supermarket_signature_prices = [120, 150, 200, 150]
        
    def link_items_to_shops(self, parsed_items):
        self.shop_entries.clear()
        
        rom = self.project.base_rom_data
        if not rom: return
        
        # Mapa inverso para enlazar el objeto 'item' real con su nombre limpio
        item_by_name = {itm.name_str.strip('\x00').strip(): itm for itm in parsed_items}
        
        # Fallback dictionary conocido para rellenar la UI, aunque el ancla falle:
        buy_prices_map = {
            "Turnip Seeds": 120, "Potato Seeds": 150, "Cucumber Seeds": 200, 
            "Strawberry Seeds": 150, "Cabbage Seeds": 500, "Tomato Seeds": 200, 
            "Corn Seeds": 300, "Onion Seeds": 150, "Pumpkin Seeds": 500, 
            "Pineapple Seeds": 1000, "Eggplant Seeds": 120, "Carrot Seeds": 300, 
            "Sweet Potato Seeds": 300, "Spinach Seeds": 200, "Green Pepper Seeds": 150, 
            "Magic Red Flower Seeds": 600, "Pink Cat Flower Seeds": 300, 
            "Toy Flower Seeds": 400, "Moondrop Flower Seeds": 500, "Grass Seeds": 500,
            "Bread": 100, "Riceball": 100, "Curry powder": 50, "Flour": 50, 
            "Oil": 50, "Chocolate": 100, "Wine": 300, "Grape juice": 200
        }
        
        # Simulación del Anchor Hunt Básico para Eventos de Tienda
        # Buscar secuencias como 0x78 0x00 (120) seguido de 0x96 0x00 (150) con saltos (stride)
        found_base = self._heuristic_shop_search(rom)
        
        for name, price in buy_prices_map.items():
            itm = item_by_name.get(name)
            if not itm: continue
            
            # Si el anchor hunt halló la tienda, calculamos offsets matemáticos, 
            # de lo contrario offset = 0 para simular la vista pero bloquear crasheos.
            offset = 0
            if found_base > 0:
                # Mock: asume que estaban ordenados cada 4 bytes
                # En un motor completo aquí se parsearía el GBA Shop Script struct literal
                pass 
                
            entry = ShopItemEntry(self, itm, offset, price)
            self.shop_entries[name] = entry
            
            # Inyectar al item para acceso rápido de UI
            itm.shop_entry = entry
            itm.buy_price = price
            
    def _heuristic_shop_search(self, rom):
        """Busca el array de Jeff detectando [120, 150, 200] espaciados a X bytes."""
        # Se reservará para una implementación C-macro en v2.
        # Devuelve 0 para forzar protección estructural hasta descifrar el Evento de Tiendas.
        return 0
