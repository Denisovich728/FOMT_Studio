import os
import sys

# Agregamos la ruta del proyecto para los imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Nucleos_de_Procesamiento.Nucleo_de_Datos.proyecto import FoMTProject

def test_audio():
    # Ruta de la ROM
    rom_path = r"D:\Matriz De Datos Principal\Proyectos De Programacion\Proyecto De Descompilacion GBA\Harvest Moon - Friends of Mineral Town (USA).gba"
    
    proj = FoMTProject()
    proj.step_1_detect_rom(rom_path)
    
    # Obtener el motor sappy
    sappy = proj.sappy_engine
    sappy.scan_songs()
    
    # Buscar una canción conocida, ej. 0x01 (Spring Farm)
    song = sappy.get_song_by_id(1)
    if not song:
        print("No se encontro la cancion ID 1")
        return
        
    print(f"Probando cancion ID: 1, Offset: {hex(song['offset'])}")
    
    out_wav = os.path.join(os.path.dirname(__file__), "test_out.wav")
    
    success = sappy.preview_song_natively(song, out_wav)
    print(f"Resultado preview_song_natively: {success}")
    
    if os.path.exists(out_wav):
        print(f"WAV creado: {out_wav}, size: {os.path.getsize(out_wav)}")
    else:
        print("WAV NO FUE CREADO.")

if __name__ == "__main__":
    test_audio()
