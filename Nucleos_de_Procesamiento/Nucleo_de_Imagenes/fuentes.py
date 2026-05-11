# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.1.0)
# "The Imposibility Update"
# Desarrollado por: Denisovich728
# ============================================================
class FontEditor:
    """
    Módulo para la visualización y decodificación
    de la tipografía (fuentes) del juego.
    """
    def __init__(self, project):
        self.project = project
        self.font_data = []
        
    def load_font_table(self):
        """
        Identifica y lee los glifos (1bpp o 2bpp) a partir de los offsets principales.
        """
        pass