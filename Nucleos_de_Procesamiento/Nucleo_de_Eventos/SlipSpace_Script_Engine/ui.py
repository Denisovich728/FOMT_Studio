import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import sys
import os

from SlipSpace_Script_Engine.extractor import extract_all_resources

class SlipSpace_EngineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SlipSpace_Engine GBA Extractor")
        self.root.geometry("600x500")
        self.root.configure(padx=10, pady=10)
        
        # Paths
        self.rom_path = tk.StringVar()
        self.library_path = tk.StringVar(value="goodies/lib_fomt.txt")
        self.output_dir = tk.StringVar()
        
        # UI Elements
        # ROM Selection
        tk.Label(root, text="ROM de GameBoy (.gba):", font=("Arial", 10, "bold")).pack(anchor="w")
        rom_frame = tk.Frame(root)
        rom_frame.pack(fill="x", pady=5)
        tk.Entry(rom_frame, textvariable=self.rom_path, width=60).pack(side="left", padx=(0, 10))
        tk.Button(rom_frame, text="Buscar...", command=self.browse_rom).pack(side="left")
        
        # Library Selection
        tk.Label(root, text="Librería de Firmas (.txt) (Opcional):", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
        lib_frame = tk.Frame(root)
        lib_frame.pack(fill="x", pady=5)
        tk.Entry(lib_frame, textvariable=self.library_path, width=60).pack(side="left", padx=(0, 10))
        tk.Button(lib_frame, text="Buscar...", command=self.browse_library).pack(side="left")
        
        # Output Directory
        tk.Label(root, text="Carpeta de Salida:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
        out_frame = tk.Frame(root)
        out_frame.pack(fill="x", pady=5)
        tk.Entry(out_frame, textvariable=self.output_dir, width=60).pack(side="left", padx=(0, 10))
        tk.Button(out_frame, text="Buscar...", command=self.browse_output).pack(side="left")
        
        # Extraction Button
        self.extract_btn = tk.Button(root, text="EXTRAER RECURSOS (Eventos y Tablas)", font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", command=self.start_extraction)
        self.extract_btn.pack(fill="x", pady=20, ipady=10)
        
        # Console Log
        tk.Label(root, text="Registro de Consola:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.log_text = tk.Text(root, height=10, bg="#f4f4f4", font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill="both", expand=True)
        
    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def browse_rom(self):
        filename = filedialog.askopenfilename(title="Seleccionar ROM GBA", filetypes=[("GBA ROM", "*.gba"), ("Todos", "*.*")])
        if filename:
            self.rom_path.set(filename)
            
    def browse_library(self):
        filename = filedialog.askopenfilename(title="Seleccionar Librería", filetypes=[("Archivos TXT", "*.txt"), ("Todos", "*.*")])
        if filename:
            self.library_path.set(filename)
            
    def browse_output(self):
        dirname = filedialog.askdirectory(title="Seleccionar Carpeta Destino")
        if dirname:
            self.output_dir.set(dirname)

    def start_extraction(self):
        if not self.rom_path.get() or not self.output_dir.get():
            messagebox.showwarning("Faltan rutas", "Debes seleccionar la ROM y la carpeta de destino.")
            return

        self.extract_btn.config(state="disabled", text="Extrayendo... (Espera por favor)")
        self.log("---- Iniciando Extracción ----")
        
        # Run extraction in separate thread to not freeze UI
        thread = threading.Thread(target=self._run_extraction)
        thread.daemon = True
        thread.start()
        
    def _run_extraction(self):
        try:
            success = extract_all_resources(
                self.rom_path.get(), 
                self.output_dir.get(), 
                self.library_path.get(), 
                update_callback=self.log
            )
            if success:
                self.log("Extracción Completada con Éxito.")
                messagebox.showinfo("Éxito", "Todos los recursos fueron extraídos correctamente.")
            else:
                self.log("Fallo en la extracción.")
                messagebox.showerror("Error", "Hubo un problema durante la extracción.")
        except Exception as e:
            self.log(f"Unhandled Exception: {e}")
            messagebox.showerror("Fatal Error", str(e))
        finally:
            self.extract_btn.config(state="normal", text="EXTRAER RECURSOS (Eventos y Tablas)")

def launch_gui():
    root = tk.Tk()
    app = SlipSpace_EngineGUI(root)
    
    # Try setting icon if exists
    try:
        pass # Placeholder for icon
    except:
        pass
        
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
