# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.3.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
import os
import json
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QLineEdit, QPushButton, QLabel, QGroupBox, 
    QComboBox, QProgressBar, QMessageBox, QFrame, QScrollArea, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QTextCursor

class GeminiAIThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, api_key, model_name, prompt, messages):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.prompt = prompt
        self.messages = messages # List of (id, text)
        self.pi_decimals = "141592653589793238" # Decimales de Pi para el handshake
        
    def run(self):
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            
            # --- PROTOCOLO ARCHIMEDES (Handshake de Pi) ---
            self.status.emit("Sincronizando nexo mediante Protocolo Archimedes...")
            if not self.perform_handshake(model, "3.1415", "92"): return
            if not self.perform_handshake(model, "3.14159265", "35"): return
            if not self.perform_handshake(model, "3.141592653589", "79"): return
            
            self.status.emit("Conexión segura. Enviando lote de traducción...")

            # Preparar el lote de mensajes
            batch_text = "\n".join([f"{mid} >>> {text}" for mid, text in self.messages])
            
            full_prompt = rf"""{self.prompt}

            DEVUELVE ÚNICAMENTE UN ARRAY JSON DE ARRAYS con este formato:
            [
              ["ID_1", "Traducción 1"],
              ["ID_2", "Traducción 2"]
            ]

            MENSAJES:
            {batch_text}

            NO des explicaciones ni añadas texto extra fuera del JSON."""

            self.status.emit("IA procesando el lote (esto puede tardar unos segundos)...")
            response = model.generate_content(full_prompt)
            raw_response = response.text.strip()
            
            # Procesar la respuesta (extraer JSON)
            import re
            match = re.search(r'(\[.*\])', response.text, re.DOTALL)
            if match:
                result_json = match.group(1)
                
                # --- SANITIZACIÓN DE ESCAPES SLIPSPACE ---
                # Gemini envía \xFF, \n, etc. Para json.loads esto es inválido.
                # Escapamos los backslashes que no sean escapes válidos de JSON.
                def fix_escapes(m):
                    text = m.group(0)
                    # Escapamos todos los backslashes para que json.loads los vea como literales
                    return text.replace('\\', '\\\\')
                
                # Buscamos contenido entre comillas y escapamos sus backslashes
                sanitized_json = re.sub(r'(".*?")', fix_escapes, result_json, flags=re.DOTALL)
                
                # Validar y emitir
                json.loads(sanitized_json)
                self.finished.emit(sanitized_json)
            else:
                self.error.emit("No se detectó el bloque JSON en la respuesta.")
        except Exception as e:
            self.error.emit(str(e))

    def perform_handshake(self, model, challenge, expected):
        """Ejecuta un paso del apretón de manos con la IA."""
        try:
            handshake_prompt = f"PROTOCOL ARCHIMEDES: Sequence [{challenge}]. Respond ONLY with the next 2 decimals of Pi. NO EXPLANATIONS."
            response = model.generate_content(handshake_prompt)
            answer = response.text.strip().replace(".", "") # Limpiar posibles puntos que la IA añada
            # A veces Gemini responde 'The next two decimals are 92'. Forzamos solo los últimos 2 caracteres si es necesario
            if len(answer) > 2: answer = answer[-2:]
            
            self.status.emit(f"  > IA respondió: '{answer}'")
            if answer != expected:
                self.error.emit(f"HANDSHAKE FAILED: Sent {challenge}, expected {expected}, received {answer}")
                return False
            return True
        except Exception as e:
            self.error.emit(f"Handshake API Error: {str(e)}")
            return False

class GeminiEditorWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.settings = QSettings("FoMTStudio", "GeminiAI")
        self.current_context = "bulk" # Valor por defecto
        self.target_widget = None
        self.setMinimumWidth(350) # Ancho más amable para evitar errores de geometría
        self.mega_stop_requested = False
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        # Usar un ScrollArea para evitar que el widget fuerce un tamaño gigante
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # --- Grupo de Configuración ---
        config_group = QGroupBox("CONFIGURACIÓN DEL NEXO")
        config_layout = QVBoxLayout(config_group)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "gemini-3-flash-preview",
            "gemini-1.5-flash", 
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ])
        config_layout.addWidget(QLabel("Modelo:"))
        config_layout.addWidget(self.model_combo)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("API KEY")
        config_layout.addWidget(QLabel("API Key:"))
        config_layout.addWidget(self.api_key_edit)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Español", "English", "Português", "Français", "Deutsch", "Italiano"])
        config_layout.addWidget(QLabel("Idioma Destino:"))
        config_layout.addWidget(self.lang_combo)
        
        layout.addWidget(config_group)
        
        # --- Consola de Salida ---
        console_group = QGroupBox("AETHER TERMINAL OUTPUT")
        console_layout = QVBoxLayout(console_group)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #000a12; color: #00ffff; font-family: 'Courier New'; font-size: 10pt;")
        self.console.setMinimumHeight(200)
        console_layout.addWidget(self.console)
        layout.addWidget(console_group)
        
        # --- Controles ---
        self.btn_translate = QPushButton("INICIAR OMNISCIENCIA")
        self.btn_translate.clicked.connect(self.start_translation_flow)
        self.btn_translate.setStyleSheet("height: 40px; font-weight: bold; background-color: #004d40; color: white;")
        layout.addWidget(self.btn_translate)
        
        self.progress = QProgressBar()
        self.progress.setFixedHeight(10)
        layout.addWidget(self.progress)
        
        self.lbl_context = QLabel("Contexto detectado: Ninguno")
        self.lbl_context.setStyleSheet("color: #00ffff; font-weight: bold;")
        layout.addWidget(self.lbl_context)
        
        self.btn_refresh = QPushButton("REFRESCAR CONTEXTO")
        self.btn_refresh.clicked.connect(self.refresh_context)
        layout.addWidget(self.btn_refresh)

        # --- MEGA BATCH CONTROLS ---
        mega_group = QGroupBox("MODO OMNISCIENCIA MASIVA (BETA)")
        mega_layout = QVBoxLayout(mega_group)
        
        range_layout = QHBoxLayout()
        self.spin_start = QSpinBox()
        self.spin_start.setRange(1, 2000)
        self.spin_end = QSpinBox()
        self.spin_end.setRange(1, 2000)
        self.spin_end.setValue(100)
        
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 50)
        self.spin_batch.setValue(10)
        self.spin_batch.setToolTip("Tamaño del lote (Items por cada envío a la IA)")
        
        range_layout.addWidget(QLabel("Desde:"))
        range_layout.addWidget(self.spin_start)
        range_layout.addWidget(QLabel("Hasta:"))
        range_layout.addWidget(self.spin_end)
        range_layout.addWidget(QLabel("Lote:"))
        range_layout.addWidget(self.spin_batch)
        mega_layout.addLayout(range_layout)
        
        self.btn_mega_events = QPushButton("AUTO-TRADUCIR RANGO DE EVENTOS")
        self.btn_mega_events.clicked.connect(self.start_mega_event_batch)
        self.btn_mega_events.setStyleSheet("background-color: #311b92; color: white; font-weight: bold;")
        mega_layout.addWidget(self.btn_mega_events)
        
        self.btn_mega_items = QPushButton("AUTO-TRADUCIR TODOS LOS ÍTEMS")
        self.btn_mega_items.clicked.connect(self.start_mega_item_batch)
        self.btn_mega_items.setStyleSheet("background-color: #1a237e; color: white; font-weight: bold;")
        mega_layout.addWidget(self.btn_mega_items)

        self.btn_stop_mega = QPushButton("DETENER OMNISCIENCIA")
        self.btn_stop_mega.clicked.connect(self.stop_mega_batch)
        self.btn_stop_mega.setStyleSheet("background-color: #b71c1c; color: white; font-weight: bold;")
        self.btn_stop_mega.setEnabled(False)
        mega_layout.addWidget(self.btn_stop_mega)
        
        layout.addWidget(mega_group)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Tamaño sugerido para el panel lateral
        self.setMinimumWidth(250)

    def refresh_context(self):
        """Detecta qué editor está activo para ajustar la omnisciencia."""
        main_win = self.window()
        if not hasattr(main_win, 'tabs'): return
        
        w = main_win.tabs.currentWidget()
        from Perifericos.Interfaz_Usuario.widgets.script_ide import ScriptIDEWidget
        from Perifericos.Interfaz_Usuario.widgets.item_editor import ItemEditorWidget
        from Perifericos.Interfaz_Usuario.widgets.npc_editor import NpcEditorWidget
        
        if isinstance(w, ScriptIDEWidget):
            self.lbl_context.setText("Contexto detectado: Script (SlipSpace IDE)")
            self.current_context = "script"
        elif isinstance(w, ItemEditorWidget):
            self.lbl_context.setText("Contexto detectado: Editor de Ítems")
            self.current_context = "item"
        elif isinstance(w, NpcEditorWidget):
            self.lbl_context.setText("Contexto detectado: Editor de Personajes")
            self.current_context = "npc"
        else:
            self.lbl_context.setText("Contexto detectado: General (Omnisciencia activada)")
            self.current_context = "bulk"

    def load_settings(self):
        """Carga la configuración guardada de la sesión anterior."""
        self.api_key_edit.setText(self.settings.value("api_key", ""))
        self.model_combo.setCurrentText(self.settings.value("model", "gemini-1.5-pro"))
        self.lang_combo.setCurrentText(self.settings.value("language", "Español"))

    def save_settings(self):
        """Guarda la configuración actual para la próxima sesión."""
        self.settings.setValue("api_key", self.api_key_edit.text())
        self.settings.setValue("model", self.model_combo.currentText())
        self.settings.setValue("language", self.lang_combo.currentText())

    def log(self, message):
        self.console.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        # Auto-scroll al final (PyQt6 style)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def stop_mega_batch(self):
        self.mega_stop_requested = True
        self.log("[SISTEMA] Solicitud de detención enviada. Terminando lote actual...")
        self.btn_stop_mega.setEnabled(False)

    def start_mega_event_batch(self):
        """Inicia el carrusel de traducción de eventos uno por uno."""
        self.mega_stop_requested = False
        self.btn_stop_mega.setEnabled(True)
        self.current_mega_id = self.spin_start.value()
        self.mega_end_id = self.spin_end.value()
        self.mega_mode = "events"
        self.log(f"Iniciando MEGABATCH de EVENTOS: {self.current_mega_id} -> {self.mega_end_id}")
        self.process_next_mega_item()

    def start_mega_item_batch(self):
        """Inicia la traducción masiva de todos los ítems."""
        self.mega_stop_requested = False
        self.btn_stop_mega.setEnabled(True)
        self.current_mega_id = 0
        self.mega_mode = "items"
        self.mega_items = self.project.item_parser.scan_foods()
        self.mega_end_id = len(self.mega_items) - 1
        self.log(f"Iniciando MEGABATCH de ÍTEMS: Total {len(self.mega_items)}")
        self.process_next_mega_item()

    def process_next_mega_item(self):
        if self.mega_stop_requested:
            self.log("[SISTEMA] Omnisciencia DETENIDA por el usuario.")
            self.btn_stop_mega.setEnabled(False)
            return

        if self.current_mega_id > self.mega_end_id:
            self.log("MEGABATCH FINALIZADO CON ÉXITO.")
            self.btn_stop_mega.setEnabled(False)
            return

        api_key = self.api_key_edit.text()
        if not api_key: return

        matches = []
        system_prompt = ""
        
        if self.mega_mode == "events":
            # Descompilar el evento actual
            hint, off = self.project.event_parser.get_event_name_and_offset(self.current_mega_id)
            if off:
                code, _ = self.project.event_parser.decompile_to_ui(self.current_mega_id)
                import re
                pattern = re.compile(r'const\s+(MESSAGE_(?:0x)?[A-Fa-f0-9]+)\s*=\s*"(.*?)(?<!\\)"', re.IGNORECASE | re.DOTALL)
                matches = pattern.findall(code)
                
                if not matches:
                    self.log(f"[LOGIC] Evento {self.current_mega_id} omitido (Sin diálogos).")
                    self.current_mega_id += 1
                    self.process_next_mega_item()
                    return

                self.log(f"[IA] Procesando Evento {self.current_mega_id} ({hint}) - {len(matches)} diálogos encontrados.")
                
                system_prompt = rf"""Eres un experto en Harvest Moon y SlipSpace Engine. 
                Traduce estos diálogos del evento {self.current_mega_id} ({hint}). 
                ID 0 es PLAYER. Mantén \xFF, \r\n y \BRK. NO des explicaciones hasta el final."""
            else:
                self.current_mega_id += 1
                self.process_next_mega_item()
                return

        elif self.mega_mode == "items":
            batch_size = self.spin_batch.value()
            end_idx = min(self.current_mega_id + batch_size, self.mega_end_id + 1)
            
            for i in range(self.current_mega_id, end_idx):
                item = self.mega_items[i]
                matches.append((f"ITEM_{i}_NAME", item.name_str))
                matches.append((f"ITEM_{i}_DESC", item.desc_str))
            
            self.log(f"[IA] Procesando LOTE de {end_idx - self.current_mega_id} ÍTEMS (ID {self.current_mega_id} al {end_idx-1})...")
            
            system_prompt = rf"""Traduce y CORRIGE estos {end_idx - self.current_mega_id} ítems de Harvest Moon.
            
            ¡¡¡ REGLA CRÍTICA DE ORO (CORRECCIÓN DE ERRORES) !!!:
            - SIEMPRE que veas "Sickle" (o si el texto dice "Azada" pero se refiere a una "Hoz"), DEBES traducirlo como "HOZ".
            - "Sickle" = "Hoz". NUNCA, bajo ningún concepto, uses "Azada" para una "Hoz".
            - "Hoe" = "Azada".
            - Si el texto de entrada ya está en español pero dice "Azada" para un ítem que debería ser "Hoz", ¡CORRÍGELO!
            
            GLOSARIO:
            - Copper/Silver/Gold/Mystrile Sickle -> Hoz de Cobre/Plata/Oro/Mistrilo
            - Cursed/Blessed/Mythic Sickle -> Hoz Maldita/Bendita/Mítica
            
            FORMATO:
            - ITEM_N_NAME: Nombre corto.
            - ITEM_N_DESC: Máximo 2 líneas. 
            USA SALTOS DE LÍNEA NORMALES. NO des explicaciones."""
            
            self.current_batch_end = end_idx

        if not matches:
            self.current_mega_id += 1
            self.process_next_mega_item()
            return

        if not hasattr(self, "_active_threads"):
            self._active_threads = []

        thread = GeminiAIThread(api_key, self.model_combo.currentText(), system_prompt, matches)
        self._active_threads.append(thread)
        
        thread.finished.connect(self.on_mega_success)
        thread.finished.connect(lambda: self._active_threads.remove(self.sender()) if self.sender() in self._active_threads else None)
        thread.error.connect(lambda e: self.log(f"Error en ID {self.current_mega_id}: {e}"))
        thread.start()

    def on_mega_success(self, result_json):
        try:
            results = json.loads(result_json)
        except Exception as e:
            self.log(f"[ERROR] JSON Inválido de IA: {e}")
            self.current_mega_id += 1
            self.process_next_mega_item()
            return

        if isinstance(results, dict):
            results = list(results.items())

        # PREPARAR COLA DE PROCESAMIENTO ATÓMICO
        self.repoint_queue = results
        self.queue_index = 0
        self.log(f"[SISTEMA] Lote recibido. Iniciando inyección secuencial de {len(results)} elementos...")
        
        # Usar un temporizador para procesar uno a uno sin bloquear la UI
        from PyQt6.QtCore import QTimer
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_step)
        self.queue_timer.start(50) # 50ms entre cada repunteo para estabilidad

    def process_queue_step(self):
        if self.queue_index >= len(self.repoint_queue):
            self.queue_timer.stop()
            self.log("[SISTEMA] Lote inyectado y sincronizado correctamente.")
            
            if self.mega_mode == "items":
                self.current_mega_id = self.current_batch_end
                self.process_next_mega_item()
            else:
                self.current_mega_id += 1
                self.process_next_mega_item()
            return

        key, trans = self.repoint_queue[self.queue_index]
        self.queue_index += 1

        if self.mega_mode == "events":
            # Para eventos, el lote suele ser el script completo recompilado
            # así que lo manejamos en el primer paso y terminamos
            hint, off = self.project.event_parser.get_event_name_and_offset(self.current_mega_id)
            code, _ = self.project.event_parser.decompile_to_ui(self.current_mega_id)
            
            import re
            for msg_id, t_text in self.repoint_queue:
                safe = t_text.replace('"', '\\"')
                pattern = re.compile(rf'(const\s+{msg_id}\s*=\s*").*?(?<!\\)(")', re.IGNORECASE | re.DOTALL)
                code = pattern.sub(lambda m: m.group(1) + safe + m.group(2), code)
            
            try:
                bin_data = self.project.event_parser.compile_text_to_bytecode(code)
                old_size = self.project.event_parser.get_last_scanned_size(self.current_mega_id)
                self.project.event_parser.super_lib.repoint_and_write_event(self.current_mega_id, bin_data, old_size)
                self.log(f"  > Evento {self.current_mega_id} ({hint}) REPUNTEADO TOTAL [OK]")
            except Exception as e:
                self.log(f"  > [ERROR] Fallo en Evento {self.current_mega_id}: {e}")
            
            self.queue_index = len(self.repoint_queue) # Terminar cola de este evento
            
        elif self.mega_mode == "items":
            import re
            match = re.search(r'ITEM_(\d+)_(NAME|DESC)', key.upper())
            if match:
                idx = int(match.group(1))
                if idx < len(self.mega_items):
                    target_item = self.mega_items[idx]
                    if "NAME" in key.upper():
                        target_item.save_name_in_place(trans)
                        self.log(f"  > [0x{idx:02X}] Nombre inyectado...")
                    elif "DESC" in key.upper():
                        target_item.save_desc_in_place(trans)
                        self.log(f"  > [0x{idx:02X}] Desc. inyectada...")
            
            # Guardar ROM cada 5 ítems para no saturar disco pero mantener seguridad
            if self.queue_index % 5 == 0:
                self.project.save_rom()

    def start_translation_flow(self):
        api_key = self.api_key_edit.text()
        if not api_key:
            QMessageBox.warning(self, "Error", "Se requiere una API Key de Gemini.")
            return
            
        self.save_settings()
        self.refresh_context()
        
        main_win = self.window()
        matches = []
        
        if self.current_context == "script":
            # Lógica existente para scripts
            ide = main_win.tabs.currentWidget()
            script_text = ide.editor.toPlainText()
            import re
            pattern = re.compile(r'const\s+(MESSAGE_(?:0x)?[A-Fa-f0-9]+)\s*=\s*"(.*?)(?<!\\)"', re.IGNORECASE | re.DOTALL)
            matches = pattern.findall(script_text)
            self.target_widget = ide
        elif self.current_context == "item":
            # Traducir el ítem seleccionado actualmente
            editor = main_win.tabs.currentWidget()
            item = editor.current_item
            if item:
                matches = [("ITEM_NAME", item.name_str), ("ITEM_DESC", item.desc_str)]
                self.target_widget = editor
        elif self.current_context == "bulk":
            # OMNISCIENCIA: Traducir todos los nombres de ítems
            self.log("Activando Omnisciencia: Escaneando base de datos de Ítems y Herramientas...")
            items = self.project.item_parser.scan_foods()
            matches = [(f"ITEM_NAME_{i}", itm.name_str) for i, itm in enumerate(items)]
            self.target_widget = "bulk_items"
        
        if not matches:
            self.log("No se detectaron datos válidos para traducir en este contexto.")
            return

        self.log(f"Omnisciencia Iniciada: Procesando {len(matches)} entradas...")
        self.log(f"Modo: {self.current_context.upper()}")
        
        system_prompt = rf"""Hola Gemini. Necesito ayuda con estas traducciones desde un IDE personalizado (SlipSpace Engine) que no entiende otra forma de devolver el texto. Soy una persona que no entiende inglés y está algo ocupada, ¿podrías ayudarme?

        Eres un traductor experto en ROMHacking para GBA (Harvest Moon). 
        Debes traducir el texto al {self.lang_combo.currentText()} manteniendo la esencia original.

        ¡¡¡ REGLA CRÍTICA DE ORO (HERRAMIENTAS) !!!:
        - "Sickle" = "Hoz". NUNCA uses "Azada" para una hoz.
        - "Hoe" = "Azada".
        - Si el texto original dice "Azada" pero se refiere a una "Sickle" (Hoz), ¡CORRÍGELO!

        REGLAS TÉCNICAS OBLIGATORIAS (Sintaxis SlipSpace):
        1. COMANDOS DE CONTROL: Mantén intactos \xFF, \r\n, \BRK y \WAIT_CLICK.
        2. NO ESCAPES: Usa UN SOLO BACKSLASH en tu respuesta. No uses doble barra (\\).
        3. ENTIDADES: Respeta el carácter que sigue a \xFF (ej: \xFF!, \xFF\", \xFF%).
        4. LÓGICA DE SCRIPTS: En comandos como SetEntityPosition, el primer argumento es el ID: 0 siempre es el PLAYER, los demás corresponden a la tabla de NPCs (Lillia=0, Rick=1, Popuri=2, etc.).
        5. REGLA DE SALIDA: Devuelve solo los strings legibles para el IDE sin dar explicaciones hasta el final. Si existen sugerencias de optimización, incluirlas al final del listado JSON."""
        
        self.progress.setMaximum(len(matches))
        self.progress.setValue(0)
        
        self.thread = GeminiAIThread(api_key, self.model_combo.currentText(), system_prompt, matches)
        self.thread.finished.connect(lambda r: self.on_translation_success(r, self.target_widget))
        self.thread.status.connect(self.log)
        self.thread.error.connect(lambda e: QMessageBox.critical(self, "Error IA", e))
        self.thread.start()

    def on_translation_success(self, result_json, target):
        import json
        import re
        results = json.loads(result_json)
        
        self.log("Traducción completada. Aplicando omnisciencia...")
        
        if self.current_context == "script":
            ide = target
            script_text = ide.editor.toPlainText()
            for msg_id, translated_text in results:
                # Escapamos comillas para que el .script sea válido, pero usamos lambda para el re.sub
                safe_text = translated_text.replace('"', '\\"')
                pattern = re.compile(rf'(const\s+{msg_id}\s*=\s*").*?(?<!\\)(")', re.IGNORECASE | re.DOTALL)
                script_text = pattern.sub(lambda m: m.group(1) + safe_text + m.group(2), script_text)
            ide.editor.setPlainText(script_text)
            ide.on_compile_clicked()
            
        elif self.current_context == "item":
            editor = target
            # Aplicar al ítem actual
            for key, text in results:
                if key == "ITEM_NAME": editor.name_edit.setText(text)
                if key == "ITEM_DESC": editor.desc_edit.setPlainText(text)
            self.log("Datos del ítem actualizados. Pulsa 'Compilar' para repuntear.")
            
        elif self.current_context == "bulk":
            # OMNISCIENCIA: Aplicar a toda la lista (esto requiere un bucle de repunteo)
            self.log("ADVERTENCIA: Aplicando traducción masiva a la ROM...")
            items = self.project.item_parser.scan_foods()
            for i, itm in enumerate(items):
                key = f"ITEM_NAME_{i}"
                # Buscar resultado
                for r_key, r_text in results:
                    if r_key == key:
                        itm.name_str = r_text
                        # Aquí se podría disparar itm.save_name_in_place(r_text) si se desea automático
                        break
            self.log("Omnisciencia aplicada a la base de datos de Ítems.")
            
        self.log("PROCESO FINALIZADO. La omnisciencia ha sido satisfecha.")
