# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.6.5)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from PIL import Image
from typing import List, Tuple

def export_gif(frames: List[List[List[Tuple[int, int, int]]]], output_path: str, duration: int = 100):
    """
    Exporta una lista de matrices RGB a un archivo GIF animado.
    frames: List[Matrix[RGB_Tuple]]
    """
    pil_frames = []
    for frame in frames:
        h, w = len(frame), len(frame[0])
        img = Image.new("RGB", (w, h))
        pixels = [p for row in frame for p in row]
        img.putdata(pixels)
        pil_frames.append(img)
    
    if pil_frames:
        pil_frames[0].save(
            output_path,
            save_all=True,
            append_images=pil_frames[1:],
            optimize=False,
            duration=duration,
            loop=0,
            disposal=2 # Transparencia limpia
        )

def export_spritesheet(frames: List[List[List[Tuple[int, int, int]]]], output_path: str, cols: int = 8):
    """
    Exporta una lista de frames a una sola imagen (hoja de sprites).
    """
    if not frames: return
    
    f_h, f_w = len(frames[0]), len(frames[0][0])
    rows = (len(frames) + cols - 1) // cols
    
    sheet = Image.new("RGB", (f_w * cols, f_h * rows))
    
    for i, frame in enumerate(frames):
        img = Image.new("RGB", (f_w, f_h))
        pixels = [p for row in frame for p in row]
        img.putdata(pixels)
        
        x = (i % cols) * f_w
        y = (i // cols) * f_h
        sheet.paste(img, (x, y))
    
    sheet.save(output_path)
