# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.4.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
class FishEditor:
    """
    Módulo dedicado para editar mecánicas, atributos y localizaciones 
    de pesca, emulando la funcionalidad de HM-Studio.
    """
    def __init__(self, project):
        self.project = project
        self.fishes = []
        
    def scan_fish_data(self):
        """
        Escanea y recopila la información de los peces. 
        Depende del item_parser para identificar los ítems clasificados como peces 
        (Small Fish, Medium Fish, Large Fish, Ancient Fish Fossil, etc.)
        """
        if not hasattr(self.project, 'item_parser') or not self.project.item_parser: 
            return []
            
        self.fishes = []
        # Códigos de 16-bits para peces según lib_mfomt.txt
        fish_ids = [0xA000, 0xA100, 0xA200, 0x3701]
        
        for item in getattr(self.project.item_parser, 'items', []):
            # Comparamos el index interno (ID) o el ID convertido
            if hasattr(item, 'index') and item.index in fish_ids:
                self.fishes.append(item)
                
        return self.fishes
