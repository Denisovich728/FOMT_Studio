# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.1)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
class Animator:
    """
    Sistema para interactuar con la Object Attribute Memory (OAM)
    y decodificar secuencias de animación.
    """
    def __init__(self, project):
        self.project = project
        self.animations = []
        
    def load_animations(self):
        """
        Consulta la SuperLibrary en busca de bloques clasificados como OAM_ENTRY.
        """
        if not hasattr(self.project, 'super_lib') or not self.project.super_lib:
            return []
            
        self.animations.clear()
        
        # Iterar sobre los bancos detectados heurísticamente
        for offset, bank_info in self.project.super_lib.data_banks.items():
            if bank_info.get("type") == "OAM_ENTRY":
                self.animations.append({
                    "offset": offset,
                    "info": bank_info
                })
                
        return self.animations