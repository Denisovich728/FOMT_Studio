import sys
sys.path.append('j:\\Repositorios\\fomt_studio')
from Nucleos_de_Procesamiento.Nucleo_de_Imagenes.mapas import MapParser

class FakeProj:
    def __init__(self):
        with open('j:\\Repositorios\\fomt_studio\\Modded_FoMT.gba', 'rb') as f:
            self.base_rom_data = f.read()

p = FakeProj()
mp = MapParser(p)
mp.scan_maps()
