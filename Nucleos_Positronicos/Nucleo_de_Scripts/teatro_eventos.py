# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v4.0.0)
# "The Greatest Show - Final Release"
# Desarrollado por: Denisovich728
# ============================================================
"""
NUCLEO DE TEATRO DE EVENTOS (TEATROEVENTOS)
Arquitectura de Maquina Virtual e Interprete de Instrucciones Binarias.
Carga scripts de eventos directamente desde los bloques RIFF/Bytecode de la ROM
y ejecuta secuencialmente cada instruccion (Warp_Player, SetEntityPosition,
Set_Portrait, TalkMessage, PlayBGM, etc.), trayendo y almacenando dinamicamente
los assets (mapas, sprites, retratos 4bpp, audio Sappy) en memoria RAM.
"""

import os
import sys
import struct
import copy
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QSlider, QFrame, QSplitter, QCheckBox,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QTabWidget, QListWidget, QListWidgetItem, QTextEdit, QScrollArea,
    QMessageBox, QDialog, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush, QFont,
    QPainterPath, QTransform, QIcon
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from Consola_de_Comando.i18n import t as _t

from Nucleos_Positronicos.Nucleo_de_Mapas.fomt_mapdata import FomtMapRenderer
from Nucleos_Positronicos.Nucleo_de_Rutinas_AI.routine_codec import NPC_NAMES, NPC_COUNT
from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.ast import (
    StmtCall, StmtMessage, StmtVars, ExprInt, ExprStr
)
from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.decompiler.formatter import format_script
from Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits import (
    get_bundle_headers, read_hword, decode_palette, OAM_DIMS
)
from Nucleos_Positronicos.Nucleo_de_Sprites.visor_sprites import SymphonySpriteEngine

# ============================================================
# 1. CATALOGOS DE AUDIO DE LA ROM (SAPPY MOTOR)
# ============================================================
FOMT_BGM_CATALOG = [
    (0x00, "Silencio (Sin BGM)"),
    (0x01, "Tema Principal de Mineral Town"),
    (0x02, "Granja en Primavera"),
    (0x03, "Granja en Verano"),
    (0x04, "Granja en Otono"),
    (0x05, "Granja en Invierno"),
    (0x06, "Festival de Primavera"),
    (0x07, "Carrera de Caballos"),
    (0x08, "Festival de Verano / Playa"),
    (0x09, "Festival del Fuego"),
    (0x0A, "Festival de Musica"),
    (0x0B, "Festival de la Cosecha"),
    (0x0C, "Playa y Mar de Mineral Town"),
    (0x0D, "Interior de Casas y Tiendas"),
    (0x0E, "Taberna / Noche en el Pueblo"),
    (0x0F, "Iglesia de Mineral Town"),
    (0x10, "Cueva y Minas"),
    (0x11, "Supermercado de Jeff"),
    (0x12, "Clinica del Doctor"),
    (0x13, "Madereria de Gotz"),
    (0x14, "Granja Avicola de Popuri"),
    (0x15, "Granja Yodel de Barley"),
    (0x16, "Herreria de Saibara"),
    (0x17, "Vinedo Aja"),
    (0x18, "Evento Romantico (Corazon Negro/Azul)"),
    (0x19, "Evento Romantico (Corazon Verde/Amarillo)"),
    (0x1A, "Evento Triste / Melancolia"),
    (0x1B, "Evento Alegre / Comico"),
    (0x1C, "Boda y Matrimonio"),
    (0x1D, "Final y Creditos"),
]

FOMT_SFX_CATALOG = [
    (0x00, "Sin Efecto (SFX 0x00)"),
    (0x01, "Paso de Hierba"),
    (0x02, "Paso de Tierra"),
    (0x03, "Paso de Madera"),
    (0x04, "Uso de Herramienta"),
    (0x05, "Silbato de Perro"),
    (0x06, "Silbato de Caballo"),
    (0x07, "Canto de Gallo"),
    (0x08, "Mugido de Vaca"),
    (0x09, "Balido de Oveja"),
    (0x0A, "Ladrido de Perro"),
    (0x0B, "Maullido de Gato"),
    (0x0C, "Campanilla de Animales"),
    (0x0D, "Exclamacion Sorpresa"),
    (0x0E, "Corazon Romantico"),
    (0x0F, "Gota de Sudor"),
    (0x10, "Pregunta / Duda"),
    (0x11, "Abrir Puerta"),
    (0x12, "Cerrar Puerta"),
    (0x13, "Campanilla de Tienda"),
    (0x14, "Objeto Recogido"),
    (0x15, "Objeto Lanzado"),
    (0x16, "Dinero y Monedas"),
    (0x17, "Nivel de Herramienta Subido"),
]


# ============================================================
# 2. MODELOS DE DATOS DEL TEATRO Y MAQUINA VIRTUAL
# ============================================================
class TheaterActor:
    """Representa a un actor (jugador o NPC) posicionado en el escenario."""
    def __init__(self, actor_id: str, npc_id: int, x: int = 120, y: int = 100,
                 facing: str = "Down", anim_id: int = 0, emote: str = "none"):
        self.actor_id = actor_id
        self.npc_id = npc_id
        self.name = NPC_NAMES.get(npc_id, f"NPC #{npc_id}")
        self.x = int(x)
        self.y = int(y)
        self.facing = facing
        self.anim_id = int(anim_id)
        self.emote = emote

    def copy(self) -> 'TheaterActor':
        return TheaterActor(
            self.actor_id, self.npc_id, self.x, self.y,
            self.facing, self.anim_id, self.emote
        )


class TheaterDialogue:
    """Estado del cuadro de dialogo en un punto de ejecucion de la VM."""
    def __init__(self, active: bool = False, speaker_id: int = 0, speaker_name: str = "",
                 portrait_id: int = 0, portrait_pixmap: Optional[QPixmap] = None, text: str = ""):
        self.active = active
        self.speaker_id = speaker_id
        self.speaker_name = speaker_name
        self.portrait_id = portrait_id
        self.portrait_pixmap = portrait_pixmap
        self.text = text

    def copy(self) -> 'TheaterDialogue':
        return TheaterDialogue(
            self.active, self.speaker_id, self.speaker_name,
            self.portrait_id, self.portrait_pixmap, self.text
        )


class TheaterStep:
    """
    Paso de ejecucion cinemática generado al interpretar una instruccion.
    Captura una instantanea completa de la escena para scrubbing instantaneo en RAM.
    """
    def __init__(self, step_idx: int, stmt_idx: int, action_type: str, summary: str,
                 map_id: int = 0, bgm_id: int = 1, sfx_id: int = 0, fade: str = "Normal"):
        self.step_idx = step_idx
        self.stmt_idx = stmt_idx
        self.action_type = action_type
        self.summary = summary
        self.map_id = map_id
        self.bgm_id = bgm_id
        self.sfx_id = sfx_id
        self.fade = fade
        self.actors: Dict[str, TheaterActor] = {}
        self.dialogue: TheaterDialogue = TheaterDialogue()
        self.stmt_ref: Any = None # Referencia viva al objeto Stmt


# ============================================================
# 3. BANCO CENTRALIZADO DE ASSETS EN RAM (EVENTASSETBANK)
# ============================================================
class EventAssetBank:
    """
    Banco de memoria centralizado que extrae los recursos directamente de la ROM
    (mapas GBA, retratos 4bpp OAM, tokens de aldeanos, tablas Sappy) y los conserva
    en memoria RAM para ejecucion en microsegundos sin accesos a disco.
    """
    def __init__(self, project=None):
        self.project = project
        self.bgm_catalog = FOMT_BGM_CATALOG
        self.sfx_catalog = FOMT_SFX_CATALOG
        self._maps_cache: Dict[int, QPixmap] = {}
        self._map_dimensions: Dict[int, Tuple[int, int]] = {}
        self._tokens_cache: Dict[Tuple[int, str, str], QPixmap] = {}
        self._portraits_cache: Dict[int, QPixmap] = {}
        self._renderer = None
        self._sprite_engine = None
        self._portrait_counts = None
        self._portrait_ptrs = None

        self._init_renderer()
        self._init_portraits_bundle()
        self._init_sprite_engine()

    def _init_sprite_engine(self):
        try:
            rom_data = self._get_rom_bytes()
            if rom_data:
                self._sprite_engine = SymphonySpriteEngine(rom_data)
        except Exception as e:
            print(f"[EventAssetBank] Aviso: No se pudo instanciar SymphonySpriteEngine: {e}")

    def _get_rom_bytes(self) -> Optional[bytes]:
        if not self.project:
            return None
        if hasattr(self.project, 'virtual_rom') and self.project.virtual_rom:
            return bytes(self.project.virtual_rom)
        if hasattr(self.project, 'base_rom_data') and self.project.base_rom_data:
            return bytes(self.project.base_rom_data)
        if hasattr(self.project, 'base_rom_path') and self.project.base_rom_path and os.path.exists(self.project.base_rom_path):
            try:
                with open(self.project.base_rom_path, 'rb') as f:
                    return f.read()
            except Exception:
                pass
        if hasattr(self.project, 'rom_path') and self.project.rom_path and os.path.exists(self.project.rom_path):
            try:
                with open(self.project.rom_path, 'rb') as f:
                    return f.read()
            except Exception:
                pass
        return None

    def _init_renderer(self):
        try:
            rom_data = self._get_rom_bytes()
            if rom_data:
                self._renderer = FomtMapRenderer(rom_data)
        except Exception as e:
            print(f"[EventAssetBank] Aviso: No se pudo instanciar FomtMapRenderer: {e}")

    def _init_portraits_bundle(self):
        try:
            rom_data = self._get_rom_bytes()
            if rom_data:
                self._portrait_counts, self._portrait_ptrs = get_bundle_headers(rom_data)
        except Exception as e:
            print(f"[EventAssetBank] Aviso: Error obteniendo cabecera de retratos: {e}")

    # --- MAPAS ---
    def get_map_pixmap(self, map_id: int) -> Tuple[QPixmap, int, int]:
        """Obtiene el mapa de la ROM renderizado en QPixmap y sus dimensiones en tiles."""
        if map_id in self._maps_cache:
            w_t, h_t = self._map_dimensions.get(map_id, (30, 20))
            return self._maps_cache[map_id], w_t, h_t

        if self._renderer and self.project and hasattr(self.project, 'map_parser') and self.project.map_parser:
            try:
                if not self.project.map_parser.maps:
                    self.project.map_parser.scan_maps()
                header = self.project.map_parser.get_map_by_id(map_id)
                if header and self._renderer.load_map(header):
                    img = self._renderer.render()
                    if img:
                        if img.mode != "RGBA":
                            img = img.convert("RGBA")
                        data = img.tobytes("raw", "RGBA")
                        qim = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                        pix = QPixmap.fromImage(qim)
                        w_tiles = img.width // 8
                        h_tiles = img.height // 8
                        self._maps_cache[map_id] = pix
                        self._map_dimensions[map_id] = (w_tiles, h_tiles)
                        return pix, w_tiles, h_tiles
            except Exception as e:
                print(f"[EventAssetBank] Error decodificando mapa 0x{map_id:02X} de la ROM: {e}")

        # Fallback sintético
        pix = self._create_synthetic_map(map_id)
        self._maps_cache[map_id] = pix
        self._map_dimensions[map_id] = (30, 20)
        return pix, 30, 20

    def _create_synthetic_map(self, map_id: int) -> QPixmap:
        w, h = 480, 320
        pix = QPixmap(w, h)
        pix.fill(QColor("#1E232A"))
        p = QPainter(pix)
        p.setPen(QPen(QColor("#2B323C"), 1, Qt.PenStyle.DashLine))
        for x in range(0, w, 16): p.drawLine(x, 0, x, h)
        for y in range(0, h, 16): p.drawLine(0, y, w, y)
        p.setPen(QColor("#8B949E"))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        p.drawText(20, 35, f"Mapa GBA 0x{map_id:02X} (Lienzo de Teatro)")
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(20, 55, "Cuadricula metrica 16x16 px - Arrastra los actores para posicionar")
        p.end()
        return pix

    # --- RETRATOS (4BPP OAM DESDE LA ROM O PORTRAITS DUMP) ---
    SPEAKER_DEFAULT_PORTRAITS = {
        'rick': 0x00,
        'popuri': 0x07,
        'lillia': 0x0E, 'lilia': 0x0E,
        'baby': 0x12,
        'cliff': 0x17,
        'zack': 0x1F,
        'doctor': 0x23,
        'staid': 0x2A,
        'nappy': 0x2C,
        'bold': 0x2E,
        'chef': 0x30,
        'aqua': 0x32,
        'hoggy': 0x34,
        'timid': 0x36,
        'gourmet': 0x38,
        'barley': 0x3A,
        'may': 0x3F,
        'saibara': 0x43,
        'gray': 0x47,
        'karen': 0x48,
        'duke': 0x4E,
        'manna': 0x51,
        'basil': 0x54,
        'anna': 0x56,
        'ann': 0x57,
        'doug': 0x5C,
        'mary': 0x60,
        'ellen': 0x64,
        'stu': 0x68,
        'jeff': 0x6C,
        'sasha': 0x71,
        'thomas': 0x75,
        'harris': 0x79,
        'carter': 0x7C,
        'kai': 0x80,
        'gotz': 0x84,
        'won': 0x87,
        'goddess': 0x89, 'h. goddess': 0x89,
        'kappa': 0x90,
        'ruby': 0x92, 'lu': 0x92,
        'lou': 0x93
    }

    def get_portrait_pixmap(self, portrait_id: int) -> QPixmap:
        """Obtiene el retrato desde portraits_dump o decodifica de la ROM nativa."""
        if portrait_id in self._portraits_cache:
            return self._portraits_cache[portrait_id]

        # 1. Intentar cargar desde portraits_dump de forma multiplataforma
        candidates_dump = [
            os.path.join(os.getcwd(), "portraits_dump"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "portraits_dump")),
            r"J:\Laboratorio\FOMT_Studio\portraits_dump"
        ]
        dump_dir = next((d for d in candidates_dump if os.path.exists(d)), "portraits_dump")
        if os.path.exists(dump_dir):
            prefix = f"{portrait_id:02X}_"
            for f in os.listdir(dump_dir):
                if f.upper().startswith(prefix.upper()) and f.endswith(".png"):
                    full_p = os.path.join(dump_dir, f)
                    pix = QPixmap(full_p)
                    if not pix.isNull():
                        self._portraits_cache[portrait_id] = pix
                        return pix

        # 2. Si no esta en disco, decodificar en RAM directamente via Melody Portrait Engine
        rom_data = self._get_rom_bytes()
        if rom_data:
            try:
                from Nucleos_Positronicos.Nucleo_de_Portraits.Melody_Portrait_Engine.dump_portraits import decode_portrait_pixmap
                pix = decode_portrait_pixmap(rom_data, portrait_id, self._portrait_counts, self._portrait_ptrs)
                if pix and not pix.isNull():
                    self._portraits_cache[portrait_id] = pix
                    return pix
            except Exception as e:
                print(f"[EventAssetBank] Error decodificando retrato 0x{portrait_id:02X} via Melody: {e}")

        # Fallback de retrato sintetico
        fb_pix = QPixmap(64, 72)
        fb_pix.fill(QColor("#21262D"))
        p = QPainter(fb_pix)
        p.setPen(QColor("#58A6FF"))
        p.drawRect(1, 1, 62, 70)
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        p.drawText(QRectF(0, 20, 64, 20), Qt.AlignmentFlag.AlignCenter, f"0x{portrait_id:02X}")
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QRectF(0, 40, 64, 20), Qt.AlignmentFlag.AlignCenter, "Portrait")
        p.end()
        self._portraits_cache[portrait_id] = fb_pix
        return fb_pix

    # --- TOKENS Y SPRITES REALES DE ALDEANOS ---
    def get_actor_token_pixmap(self, npc_id: int, facing: str, emote: str = "none") -> QPixmap:
        """Extrae el sprite real decodificado por SymphonySpriteEngine o genera token estilizado."""
        key = (npc_id, facing, emote)
        if key in self._tokens_cache:
            return self._tokens_cache[key]

        # 1. Intentar renderizar sprite real desde SymphonySpriteEngine
        if not self._sprite_engine:
            self._init_sprite_engine()

        if self._sprite_engine:
            raw_name = self.get_npc_name(npc_id)
            npc_name = raw_name.split(' (')[0].strip().lower()
            anim_db_map = {
                'player': 0x3D,
                'lillia': 0x25F, 'lilia': 0x25F,
                'rick': 0x213,
                'popuri': 0x22F,
                'barley': 0x9EF,
                'may': 0x9E7,
                'saibara': 0x9A1,
                'gray': 0x989,
                'duke': 0x8C0,
                'manna': 0x8D0,
                'basil': 0x80B,
                'anna': 0x84B,
                'mary': 0x817,
                'thomas': 0x85F,
                'harris': 0x8E4,
                'ellen': 0x685,
                'stu': 0x8B8,
                'jeff': 0x689,
                'sasha': 0x6C5,
                'karen': 0x691,
                'doctor': 0x31F,
                'elli': 0x884, 'ellie': 0x884,
                'carter': 0x8EC,
                'cliff': 0x27B, 'clif': 0x27B,
                'doug': 0x7B6,
                'ann': 0x7C2,
                'kai': 0x902,
                'gotz': 0x9D3,
                'zack': 0x318,
                'won': 0x857,
                'gourmet': 0x679,
                'kappa': 0x7FE,
                'lou': 0x8D8,
                'lu': 0x7F2,
                'staid': 0x3F3,
                'nappy': 0x498,
                'bold': 0x4EC,
                'chef': 0x540,
                'aqua': 0x594,
                'hoggy': 0x5D8,
                'timid': 0x444
            }
            aid = anim_db_map.get(npc_name)
            if aid is not None:
                try:
                    anim_data = self._sprite_engine.render_animation_data(aid)
                    if anim_data and anim_data.get('frames'):
                        pil_frame = anim_data['frames'][0]
                        # Flip horizontal si mira a la izquierda
                        if facing == "Left":
                            pil_frame = pil_frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                        # Recortar bounding box de transparencia para que quede centrado
                        bbox = pil_frame.getbbox()
                        if bbox:
                            cropped = pil_frame.crop(bbox)
                        else:
                            cropped = pil_frame

                        # Escalar proporcional para el canvas de teatro (max 32x40)
                        sc_w = min(1.0, 32.0 / cropped.width) if cropped.width > 32 else 1.0
                        sc_h = min(1.0, 40.0 / cropped.height) if cropped.height > 40 else 1.0
                        sc = min(sc_w, sc_h)
                        final_w = max(16, int(cropped.width * sc))
                        final_h = max(16, int(cropped.height * sc))
                        resized = cropped.resize((final_w, final_h), Image.Resampling.NEAREST)

                        if resized.mode != "RGBA":
                            resized = resized.convert("RGBA")
                        data = resized.tobytes("raw", "RGBA")
                        qim = QImage(data, resized.width, resized.height, QImage.Format.Format_RGBA8888)
                        
                        # Dibujar sobre un canvas con sombra y emote si aplica
                        spr_pix = QPixmap(max(32, final_w), max(40, final_h + 4))
                        spr_pix.fill(Qt.GlobalColor.transparent)
                        p = QPainter(spr_pix)
                        # Sombra
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QColor(0, 0, 0, 90))
                        p.drawEllipse(2, spr_pix.height() - 8, spr_pix.width() - 4, 6)
                        # Sprite
                        p.drawImage((spr_pix.width() - final_w) // 2, spr_pix.height() - final_h - 4, qim)
                        # Emote
                        if emote and emote != "none":
                            self._draw_emote_bubble(p, spr_pix.width() - 14, 0, emote)
                        p.end()

                        self._tokens_cache[key] = spr_pix
                        return spr_pix
                except Exception as e:
                    print(f"[EventAssetBank] Error renderizando sprite nativo para {npc_name}: {e}")



        # 2. Fallback de token sintético
        w, h = 32, 40
        pix = QPixmap(w, h)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Paleta distintiva de aldeanos
        PALETTES = [
            ("#238636", "#2EA043"), # 0: Player
            ("#F85149", "#FF7B72"), # 1: Popuri
            ("#388BFD", "#58A6FF"), # 2: Elli
            ("#A371F7", "#BC8CFF"), # 3: Karen
            ("#D29922", "#E3B341"), # 4: Ann
            ("#3FB950", "#56D364"), # 5: Mary
        ]
        col_primary, col_accent = PALETTES[npc_id % len(PALETTES)]

        # Sombra en el suelo
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawEllipse(4, 28, 24, 10)

        # Cuerpo del actor
        p.setPen(QPen(QColor("#0D1117"), 1.5))
        p.setBrush(QColor(col_primary))
        p.drawRoundedRect(6, 12, 20, 18, 4, 4)

        # Cabeza
        p.setBrush(QColor("#FFE0BD"))
        p.drawEllipse(8, 4, 16, 15)

        # Cabello / Sombrero
        p.setBrush(QColor(col_accent))
        p.drawPie(7, 2, 18, 12, 0, 180 * 16)

        # Flecha de orientacion
        p.setPen(QPen(QColor("#FFFFFF"), 2))
        cx, cy = 16, 21
        if facing == "Up":
            p.drawLine(cx, cy + 3, cx, cy - 3)
            p.drawLine(cx, cy - 3, cx - 2, cy - 1)
            p.drawLine(cx, cy - 3, cx + 2, cy - 1)
        elif facing == "Down":
            p.drawLine(cx, cy - 3, cx, cy + 3)
            p.drawLine(cx, cy + 3, cx - 2, cy + 1)
            p.drawLine(cx, cy + 3, cx + 2, cy + 1)
        elif facing == "Left":
            p.drawLine(cx + 3, cy, cx - 3, cy)
            p.drawLine(cx - 3, cy, cx - 1, cy - 2)
            p.drawLine(cx - 3, cy, cx - 1, cy + 2)
        elif facing == "Right":
            p.drawLine(cx - 3, cy, cx + 3, cy)
            p.drawLine(cx + 3, cy, cx + 1, cy - 2)
            p.drawLine(cx + 3, cy, cx + 1, cy + 2)

        # Globo de reaccion (Emote)
        if emote and emote != "none":
            self._draw_emote_bubble(p, 18, 0, emote)

        p.end()
        self._tokens_cache[key] = pix
        return pix

    def _draw_emote_bubble(self, p: QPainter, bx: int, by: int, emote: str):
        p.setPen(QPen(QColor("#30363D"), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(bx, by, 12, 12)

        p.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        if "exclamation" in emote:
            p.setPen(QColor("#F85149"))
            p.drawText(bx, by + 1, 12, 11, Qt.AlignmentFlag.AlignCenter, "!")
        elif "heart" in emote:
            p.setPen(QColor("#FF7B72"))
            p.drawText(bx, by + 1, 12, 11, Qt.AlignmentFlag.AlignCenter, "H")
        elif "sweat" in emote:
            p.setPen(QColor("#58A6FF"))
            p.drawText(bx, by + 1, 12, 11, Qt.AlignmentFlag.AlignCenter, "~")
        elif "music" in emote:
            p.setPen(QColor("#A371F7"))
            p.drawText(bx, by + 1, 12, 11, Qt.AlignmentFlag.AlignCenter, "M")
        elif "question" in emote:
            p.setPen(QColor("#D29922"))
            p.drawText(bx, by + 1, 12, 11, Qt.AlignmentFlag.AlignCenter, "?")

    # --- METADATOS Y NOMBRES ---
    def get_npc_name(self, npc_id: int) -> str:
        if npc_id == 0:
            return "Player"
        return NPC_NAMES.get(npc_id, f"NPC #{npc_id}")

    def get_portrait_name(self, portrait_id: int) -> str:
        if self.project and hasattr(self.project, 'super_lib') and self.project.super_lib:
            for k, v in self.project.super_lib.portrait_map.items():
                if v == portrait_id:
                    return k
        return f"Retrato 0x{portrait_id:02X}"


# ============================================================
# 4. MAQUINA VIRTUAL E INTERPRETE DE INSTRUCCIONES (THEATERVM)
# ============================================================
class TheaterInstructionVM:
    """
    Interpreta el flujo secuencial de instrucciones binarias (AST Stmts) del script
    y genera la cronologia interactiva de pasos cinematograficos, sincronizando
    dinamicamente los assets de la ROM en memoria RAM.
    """
    def __init__(self, asset_bank: EventAssetBank):
        self.asset_bank = asset_bank
        self.stmts: List[Any] = []
        self.strings: Dict[int, str] = {}
        self.steps: List[TheaterStep] = []
        self.current_event_id: int = 1

    def load_event(self, event_id: int) -> List[TheaterStep]:
        """Carga y descompila el evento desde la ROM, interpretando sus instrucciones binarias."""
        self.current_event_id = event_id
        project = self.asset_bank.project
        if project:
            if not getattr(project, 'event_parser', None):
                from Nucleos_Positronicos.Nucleo_de_Scripts.eventos import FoMTEventParser
                project.event_parser = FoMTEventParser(project)
            try:
                code, stmts = project.event_parser.decompile_to_ui(event_id)
                if stmts:
                    return self.execute_statements(stmts)
            except Exception as e:
                print(f"[TheaterInstructionVM] Error descompilando evento {event_id}: {e}")

        # Intentar leer el archivo decompilado en disco si existe
        local_path = os.path.join(r"J:\Laboratorio\FOMT_Studio\Extraccion\Recursos\Eventos", f"evento_{event_id:04d}.txt")
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                return self.load_from_script_text(f.read())

        return self._create_blank_fallback()

    def load_from_script_text(self, script_text: str) -> List[TheaterStep]:
        """Interpreta codigo de script textual extrayendo sus llamadas e instrucciones."""
        project = self.asset_bank.project
        if project and project.event_parser:
            try:
                # Compilar a bytecode y descompilar para obtener el AST exacto
                bytecode = project.event_parser.compile_text_to_bytecode(script_text)
                if bytecode:
                    from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.bytecode.decoder import decode_script
                    from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.decompiler.ins_decompiler import decompile_instructions
                    ast_s = decode_script(bytecode)
                    stmts = decompile_instructions(ast_s.instructions, project.super_lib.known_callables)
                    return self.execute_statements(stmts)
            except Exception as e:
                print(f"[TheaterInstructionVM] Fallback en compilador: {e}")

        # Fallback de parser sintactico directo a AST
        return self._parse_text_to_vm_steps(script_text)

    def execute_statements(self, stmts: List[Any]) -> List[TheaterStep]:
        """
        Nucleo de la Maquina Virtual:
        Itera ordenadamente sobre cada instruccion/sentencia binaria,
        ejecutando sus efectos en el estado del escenario y trayendo los assets de la ROM.
        """
        self.stmts = stmts
        self.strings.clear()
        self.steps.clear()

        # 1. Extraer tabla de cadenas binarias
        for s in stmts:
            if isinstance(s, StmtMessage):
                raw = s.text.decode('latin1', errors='ignore')
                clean = raw.replace('\r\n', ' ').replace('\x05', ' ').replace('\x0c', '').replace('\xff!', 'Player').strip()
                self.strings[s.index] = clean

        # 2. Estado de la Maquina Virtual
        curr_map = 0x00
        curr_bgm = 0x01
        curr_sfx = 0x00
        curr_fade = "Normal"
        curr_portrait = 0
        curr_speaker = 0
        dialogue_open = False
        actors_state: Dict[str, TheaterActor] = {
            "player": TheaterActor("player", 0, 120, 100, "Down")
        }

        # Paso inicial 0
        step_0 = TheaterStep(1, 0, "Init", "Inicio de Escenario", curr_map, curr_bgm, curr_sfx, curr_fade)
        step_0.actors = {k: v.copy() for k, v in actors_state.items()}
        self.steps.append(step_0)

        def safe_int(v, default=0):
            if hasattr(v, 'value'): v = v.value
            if isinstance(v, (int, float)): return int(v)
            if isinstance(v, bytes): v = v.decode('latin1', errors='ignore')
            if isinstance(v, str):
                v_clean = v.strip()
                try: return int(v_clean, 0)
                except ValueError:
                    import re
                    m = re.search(r'\d+', v_clean)
                    return int(m.group()) if m else default
            return default

        for stmt_idx, stmt in enumerate(stmts):
            if not isinstance(stmt, StmtCall):
                continue

            fn = stmt.invoke.func
            args = [getattr(a, 'value', a) for a in stmt.invoke.args]

            # ── WARP_PLAYER(map, x, y) ───────────────────────────
            if fn == 'Warp_Player' and len(args) >= 3:
                curr_map = safe_int(args[0], curr_map)
                px = safe_int(args[1], 120)
                py = safe_int(args[2], 100)
                actors_state["player"].x = px
                actors_state["player"].y = py

                # Forzar carga y cache del mapa en RAM
                self.asset_bank.get_map_pixmap(curr_map)

                st = TheaterStep(len(self.steps) + 1, stmt_idx, fn, f"Warp Player a Mapa 0x{curr_map:02X} ({px}, {py})", curr_map, curr_bgm, curr_sfx, curr_fade)
                st.actors = {k: v.copy() for k, v in actors_state.items()}
                st.stmt_ref = stmt
                self.steps.append(st)

            # ── PLAYBGM(channel, song_id) ────────────────────────
            elif fn == 'PlayBGM' and len(args) >= 2:
                curr_bgm = safe_int(args[1], curr_bgm)
                if self.steps:
                    self.steps[-1].bgm_id = curr_bgm

            # ── PLAYSFX / PLAY_SE_ID(sfx_id) ─────────────────────
            elif fn in ('PlaySFX', 'Play_SE_ID') and len(args) >= 1:
                curr_sfx = safe_int(args[0], curr_sfx)
                if self.steps:
                    self.steps[-1].sfx_id = curr_sfx

            # ── SETENTITYPOSITION(entity, x, y, facing) ───────────
            elif fn == 'SetEntityPosition' and len(args) >= 3:
                eid = safe_int(args[0], 0)
                ex = safe_int(args[1], 120)
                ey = safe_int(args[2], 100)
                facing_arg = args[3] if len(args) >= 4 else 0
                facing = self._resolve_facing(facing_arg)
                aid = "player" if eid == 0 else f"npc_{eid}"
                nid = 0 if eid == 0 else (eid % 32)

                actors_state[aid] = TheaterActor(aid, nid, ex, ey, facing)
                # Cachear token en RAM
                self.asset_bank.get_actor_token_pixmap(nid, facing, "none")

                st = TheaterStep(len(self.steps) + 1, stmt_idx, fn, f"Posicionar {aid} en ({ex}, {ey}) mirando {facing}", curr_map, curr_bgm, curr_sfx, curr_fade)
                st.actors = {k: v.copy() for k, v in actors_state.items()}
                st.stmt_ref = stmt
                self.steps.append(st)

            # ── SETENTITYFACING(entity, facing) ───────────────────
            elif fn == 'SetEntityFacing' and len(args) >= 2:
                eid = safe_int(args[0], 0)
                facing = self._resolve_facing(args[1])
                aid = "player" if eid == 0 else f"npc_{eid}"
                if aid in actors_state:
                    actors_state[aid].facing = facing
                    st = TheaterStep(len(self.steps) + 1, stmt_idx, fn, f"Girar {aid} hacia {facing}", curr_map, curr_bgm, curr_sfx, curr_fade)
                    st.actors = {k: v.copy() for k, v in actors_state.items()}
                    st.stmt_ref = stmt
                    self.steps.append(st)

            # ── SETENTITYANIM(entity, anim_id) ────────────────────
            elif fn == 'SetEntityAnim' and len(args) >= 2:
                eid = safe_int(args[0], 0)
                anim_id = safe_int(args[1], 0)
                aid = "player" if eid == 0 else f"npc_{eid}"
                if aid in actors_state:
                    actors_state[aid].anim_id = anim_id

            # ── SHOW_EMOTE(entity, emote_id, param) ───────────────
            elif fn == 'Show_Emote' and len(args) >= 2:
                eid = safe_int(args[0], 0)
                em_val = safe_int(args[1], 1)
                em_name = "exclamation" if em_val == 1 else "heart" if em_val == 2 else "sweat"
                aid = "player" if eid == 0 else f"npc_{eid}"
                if aid in actors_state:
                    actors_state[aid].emote = em_name
                    st = TheaterStep(len(self.steps) + 1, stmt_idx, fn, f"Emocion {aid} [{em_name}]", curr_map, curr_bgm, curr_sfx, curr_fade)
                    st.actors = {k: v.copy() for k, v in actors_state.items()}
                    st.stmt_ref = stmt
                    self.steps.append(st)

            # ── SET_PORTRAIT(portrait_id) ─────────────────────────
            elif fn == 'Set_Portrait' and len(args) >= 1:
                curr_portrait = safe_int(args[0], 0)
                # Forzar decodificacion OAM directa de la ROM a RAM
                self.asset_bank.get_portrait_pixmap(curr_portrait)

            # ── SET_NAME_WINDOW(speaker_id) ───────────────────────
            elif fn == 'Set_Name_Window' and len(args) >= 1:
                curr_speaker = safe_int(args[0], 0)

            # ── TALKOPEN / TALKCLOSE ──────────────────────────────
            elif fn == 'TalkOpen':
                dialogue_open = True
            elif fn == 'TalkClose':
                dialogue_open = False
                # Limpiar emotes transitorios
                for act in actors_state.values():
                    act.emote = "none"

            # ── TALKMESSAGE(msg_idx) ──────────────────────────────
            elif fn in ('TalkMessage', 'TalkMessageSlow') and len(args) >= 1:
                midx = safe_int(args[0], 0)
                msg_text = self.strings.get(midx, f"Mensaje index #{midx}")
                spk_name = self.asset_bank.get_npc_name(curr_speaker)
                
                # Auto-resolver portrait neutral si no se especifico Set_Portrait explícitamente
                eff_portrait = curr_portrait
                if eff_portrait == 0 and curr_speaker > 0:
                    spk_clean = spk_name.split(' (')[0].strip().lower()
                    eff_portrait = self.asset_bank.SPEAKER_DEFAULT_PORTRAITS.get(spk_clean, 0)
                port_pix = self.asset_bank.get_portrait_pixmap(eff_portrait)

                st = TheaterStep(len(self.steps) + 1, stmt_idx, fn, f"Dialogo {spk_name}: \"{msg_text[:35]}...\"", curr_map, curr_bgm, curr_sfx, curr_fade)
                st.actors = {k: v.copy() for k, v in actors_state.items()}
                st.dialogue = TheaterDialogue(
                    active=True, speaker_id=curr_speaker, speaker_name=spk_name,
                    portrait_id=eff_portrait, portrait_pixmap=port_pix, text=msg_text
                )
                st.stmt_ref = stmt
                self.steps.append(st)

            # ── FADE_IN / FADE_OUT ────────────────────────────────
            elif fn == 'Fade_In':
                curr_fade = "Fade In"
                if self.steps: self.steps[-1].fade = "Fade In"
            elif fn == 'Fade_Out':
                curr_fade = "Fade Out"
                if self.steps: self.steps[-1].fade = "Fade Out"

        if not self.steps:
            return self._create_blank_fallback()

        return self.steps

    def _resolve_facing(self, val: Any) -> str:
        if isinstance(val, bytes):
            val = val.decode('latin1')
        if isinstance(val, str):
            if val in ("Up", "Down", "Left", "Right"):
                return val
            try: val = int(val, 0)
            except: return "Down"
        mapping = {0: "Down", 1: "Up", 2: "Left", 3: "Right"}
        return mapping.get(int(val), "Down")

    def _create_blank_fallback(self) -> List[TheaterStep]:
        st = TheaterStep(1, 0, "Init", "Escena 1 - Vacia", 0x00, 0x01, 0x00, "Normal")
        st.actors["player"] = TheaterActor("player", 0, 120, 100, "Down")
        self.steps = [st]
        return self.steps

    def _parse_text_to_vm_steps(self, text: str) -> List[TheaterStep]:
        """Parsea codigo C++ cuando no hay AST binario cargado."""
        import re
        raw_messages: Dict[int, str] = {}
        for m in re.finditer(r'const\s+MESSAGE_(\d+)\s*=\s*"([^"]*)";', text):
            idx = int(m.group(1))
            clean = m.group(2).replace(r'\r\n', ' ').replace(r'\BRK', ' ').replace(r'\WAIT_CLICK', '').replace(r'\xFF!', 'Player')
            raw_messages[idx] = clean.strip()
        self.strings = raw_messages

        # Construir stmts sinteticos
        stmts = []
        for line in text.splitlines():
            line = line.strip()
            m_call = re.match(r'(\w+)\s*\((.*?)\);', line)
            if m_call:
                fn = m_call.group(1)
                args_str = m_call.group(2).split(',') if m_call.group(2).strip() else []
                call_args = []
                for a in args_str:
                    a = a.strip().strip('"').strip("'")
                    try:
                        val = int(a, 0)
                        call_args.append(ExprInt(value=val))
                    except:
                        call_args.append(ExprStr(value=a.encode('latin1')))
                from Nucleos_Positronicos.Nucleo_de_Scripts.SlipSpace_Script_Engine.ast import Invoke
                stmts.append(StmtCall(invoke=Invoke(func=fn, args=call_args)))
        return self.execute_statements(stmts)

    def update_actor_position(self, step_idx: int, actor_id: str, new_x: int, new_y: int):
        """Actualiza las coordenadas en la instantanea y muta los argumentos de la instruccion AST."""
        if not (0 <= step_idx < len(self.steps)):
            return
        step = self.steps[step_idx]
        if actor_id in step.actors:
            step.actors[actor_id].x = new_x
            step.actors[actor_id].y = new_y

        # Mutar el StmtCall subyacente si coincide
        if step.stmt_ref and isinstance(step.stmt_ref, StmtCall):
            fn = step.stmt_ref.invoke.func
            if fn in ('Warp_Player', 'SetEntityPosition') and len(step.stmt_ref.invoke.args) >= 3:
                step.stmt_ref.invoke.args[1].value = new_x
                step.stmt_ref.invoke.args[2].value = new_y

    def update_actor_facing(self, step_idx: int, actor_id: str, new_facing: str):
        if not (0 <= step_idx < len(self.steps)):
            return
        step = self.steps[step_idx]
        if actor_id in step.actors:
            step.actors[actor_id].facing = new_facing

        if step.stmt_ref and isinstance(step.stmt_ref, StmtCall):
            fn = step.stmt_ref.invoke.func
            if fn == 'SetEntityPosition' and len(step.stmt_ref.invoke.args) >= 4:
                step.stmt_ref.invoke.args[3] = ExprStr(value=new_facing.encode('latin1'))
            elif fn == 'SetEntityFacing' and len(step.stmt_ref.invoke.args) >= 2:
                step.stmt_ref.invoke.args[1] = ExprStr(value=new_facing.encode('latin1'))

    def export_script_code(self) -> str:
        """Formatea las sentencias vivas del AST a codigo C++ autentico de FoMT."""
        if self.stmts:
            try:
                c_code = format_script(self.stmts)
                lib_name = "Fomt_Lib.src"
                lines = [
                    f"// Script {self.current_event_id:04d} - Generado por FoMT Studio Teatro de Eventos",
                    f'#include "{lib_name}"',
                    "",
                    f"script {self.current_event_id} Event_{self.current_event_id:04d} {{",
                ]
                for l in c_code.splitlines():
                    lines.append("    " + l)
                lines.append("}")
                return "\n".join(lines)
            except Exception as e:
                print(f"[TheaterInstructionVM] Error formateando con format_script: {e}")

        # Fallback de generacion directa
        lines = [
            f"// Script {self.current_event_id:04d}",
            '#include "Fomt_Lib.src"',
            "",
            f"script {self.current_event_id} Event_{self.current_event_id:04d} {{"
        ]
        msg_idx = 0
        for s in self.steps:
            if s.dialogue.active and s.dialogue.text.strip():
                lines.append(f'    const MESSAGE_{msg_idx} = "{s.dialogue.text}\\BRK";')
                msg_idx += 1
        lines.append("")
        for s in self.steps:
            lines.append(f"    // [{s.summary}]")
            if s.action_type == "Warp_Player":
                act = s.actors.get("player")
                px, py = (act.x, act.y) if act else (120, 100)
                lines.append(f"    Warp_Player(0x{s.map_id:X}, {px}, {py});")
            elif s.action_type == "SetEntityPosition":
                for aid, act in s.actors.items():
                    eid = 0 if aid == "player" else act.npc_id
                    lines.append(f'    SetEntityPosition({eid}, {act.x}, {act.y}, "{act.facing}");')
        lines.append("    exit;")
        lines.append("}")
        return "\n".join(lines)


# ============================================================
# 5. ITEM Y LIENZO DE TEATRO (THEATERACTORITEM & CANVAS)
# ============================================================
class TheaterActorItem(QGraphicsItem):
    """Representacion interactiva y arrastrable de un actor sobre el mapa."""
    def __init__(self, actor: TheaterActor, asset_bank: EventAssetBank, parent=None):
        super().__init__(parent)
        self.actor = actor
        self.asset_bank = asset_bank
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setPos(actor.x, actor.y)
        self.grid_snap = 8

    def boundingRect(self) -> QRectF:
        return QRectF(-16, -30, 32, 40)

    def paint(self, painter: QPainter, option, widget=None):
        # Halo si esta seleccionado
        if self.isSelected():
            painter.setPen(QPen(QColor("#58A6FF"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(88, 166, 255, 40))
            painter.drawRoundedRect(-17, -31, 34, 42, 6, 6)

        # Dibujar token desde la RAM
        pix = self.asset_bank.get_actor_token_pixmap(self.actor.npc_id, self.actor.facing, self.actor.emote)
        painter.drawPixmap(-16, -30, pix)

        # Etiqueta con nombre
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(QColor("#0D1117"))
        painter.setBrush(QColor(255, 255, 255, 200))
        text = self.actor.name.split()[0]
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        painter.drawRoundedRect(int(-tw / 2 - 3), 11, tw + 6, 12, 3, 3)
        painter.drawText(int(-tw / 2), 20, text)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            # Snapping a rejilla
            if self.grid_snap > 1:
                gx = round(new_pos.x() / self.grid_snap) * self.grid_snap
                gy = round(new_pos.y() / self.grid_snap) * self.grid_snap
                new_pos = QPointF(gx, gy)
            self.actor.x = int(new_pos.x())
            self.actor.y = int(new_pos.y())
            view = self.scene().views()[0] if self.scene().views() else None
            if view and hasattr(view, '_on_actor_item_dragged'):
                view._on_actor_item_dragged(self.actor.actor_id, self.actor.x, self.actor.y)
            return new_pos
        return super().itemChange(change, value)


class TheaterStageCanvas(QGraphicsView):
    """Lienzo central con mapa de la ROM, camara GBA y superposicion de dialogo."""
    actorMoved = pyqtSignal(str, int, int)
    actorSelected = pyqtSignal(str)

    def __init__(self, asset_bank: EventAssetBank, parent=None):
        super().__init__(parent)
        self.asset_bank = asset_bank
        self.stage_scene = QGraphicsScene(self)
        self.setScene(self.stage_scene)

        self.map_item = QGraphicsPixmapItem()
        self.stage_scene.addItem(self.map_item)

        # Cuadro de camara GBA (240x160 px)
        self.camera_box = QGraphicsRectItem(0, 0, 240, 160)
        self.camera_box.setPen(QPen(QColor("#F0883E"), 1.5, Qt.PenStyle.DashDotLine))
        self.camera_box.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.camera_box.setZValue(99)
        self.stage_scene.addItem(self.camera_box)

        # Superposicion HUD de Dialogo GBA
        self.hud_dialogue_group = None

        self.actor_items: Dict[str, TheaterActorItem] = {}
        self.current_step: Optional[TheaterStep] = None
        self.zoom_level = 1.5

        self.setBackgroundBrush(QBrush(QColor("#0D1117")))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.apply_zoom()

    def apply_zoom(self):
        t = QTransform()
        t.scale(self.zoom_level, self.zoom_level)
        self.setTransform(t)

    def load_step_state(self, step: TheaterStep):
        """Aplica la instantanea del paso al escenario visual trayendo los assets de la ROM."""
        self.current_step = step

        # 1. Mapa GBA
        map_pix, _, _ = self.asset_bank.get_map_pixmap(step.map_id)
        self.map_item.setPixmap(map_pix)
        self.stage_scene.setSceneRect(0, 0, map_pix.width(), map_pix.height())

        # 2. Centrar camara en el jugador
        p_act = step.actors.get("player")
        cam_x = max(0, min(map_pix.width() - 240, (p_act.x - 120) if p_act else 0))
        cam_y = max(0, min(map_pix.height() - 160, (p_act.y - 80) if p_act else 0))
        self.camera_box.setRect(cam_x, cam_y, 240, 160)

        # 3. Sincronizar Actores
        for aid in list(self.actor_items.keys()):
            if aid not in step.actors:
                self.stage_scene.removeItem(self.actor_items[aid])
                del self.actor_items[aid]

        for aid, actor in step.actors.items():
            if aid in self.actor_items:
                item = self.actor_items[aid]
                item.actor = actor
                item.setPos(actor.x, actor.y)
                item.update()
            else:
                item = TheaterActorItem(actor, self.asset_bank)
                self.stage_scene.addItem(item)
                self.actor_items[aid] = item

        # 4. Superposicion de Dialogo y Retrato
        self._update_dialogue_hud(step.dialogue, cam_x, cam_y)

    def _update_dialogue_hud(self, dial: TheaterDialogue, cam_x: int, cam_y: int):
        """Dibuja el cuadro de diálogo auténtico de FoMT en el tercio inferior de la cámara GBA."""
        if hasattr(self, '_dialogue_items'):
            for itm in self._dialogue_items:
                try:
                    self.stage_scene.removeItem(itm)
                except Exception:
                    pass
        self._dialogue_items = []

        if not dial.active or not dial.text.strip():
            return

        box_x = cam_x + 6
        box_y = cam_y + 98
        box_w = 228
        box_h = 56

        # 1. Borde Exterior Estilo FoMT (Doble marco retro)
        outer_frame = QGraphicsRectItem(box_x, box_y, box_w, box_h)
        outer_frame.setPen(QPen(QColor("#C89B3C"), 1.5))
        outer_frame.setBrush(QBrush(QColor(12, 18, 30, 240)))
        outer_frame.setZValue(100)
        self.stage_scene.addItem(outer_frame)
        self._dialogue_items.append(outer_frame)

        # Borde Interior Fino
        inner_frame = QGraphicsRectItem(box_x + 2, box_y + 2, box_w - 4, box_h - 4)
        inner_frame.setPen(QPen(QColor("#4A607A"), 1.0))
        inner_frame.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        inner_frame.setZValue(101)
        self.stage_scene.addItem(inner_frame)
        self._dialogue_items.append(inner_frame)

        has_portrait = False
        text_x = box_x + 10
        text_w = box_w - 20

        # 2. Retrato del Hablante
        port_pix = dial.portrait_pixmap
        if (not port_pix or port_pix.isNull()) and dial.portrait_id is not None:
            port_pix = self.asset_bank.get_portrait_pixmap(dial.portrait_id)

        if port_pix and not port_pix.isNull():
            has_portrait = True
            # Recuadro contenedor del retrato
            port_frame = QGraphicsRectItem(box_x + 4, box_y + 4, 48, 48)
            port_frame.setPen(QPen(QColor("#1F3A5F"), 1.0))
            port_frame.setBrush(QBrush(QColor("#060A10")))
            port_frame.setZValue(102)
            self.stage_scene.addItem(port_frame)
            self._dialogue_items.append(port_frame)

            port_item = QGraphicsPixmapItem()
            # Escala pixel art nítida (FastTransformation) para 48x48
            scaled_port = port_pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            port_item.setPixmap(scaled_port)
            px_off = box_x + 4 + (48 - scaled_port.width()) // 2
            py_off = box_y + 4 + (48 - scaled_port.height()) // 2
            port_item.setPos(px_off, py_off)
            port_item.setZValue(103)
            self.stage_scene.addItem(port_item)
            self._dialogue_items.append(port_item)

            text_x = box_x + 58
            text_w = box_w - 68

        # 3. Nombre del Personaje Hablante
        speaker_name = dial.speaker_name or ""
        if speaker_name:
            # Placa de nombre con estilo FoMT (Dorado/Ámbar con sombra)
            name_shadow = QGraphicsTextItem(f"{speaker_name}")
            name_shadow.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            name_shadow.setDefaultTextColor(QColor("#000000"))
            name_shadow.setPos(text_x + 1, box_y + 3)
            name_shadow.setZValue(103)
            self.stage_scene.addItem(name_shadow)
            self._dialogue_items.append(name_shadow)

            name_item = QGraphicsTextItem(f"{speaker_name}")
            name_item.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            name_item.setDefaultTextColor(QColor("#FAD02C"))
            name_item.setPos(text_x, box_y + 2)
            name_item.setZValue(104)
            self.stage_scene.addItem(name_item)
            self._dialogue_items.append(name_item)

        # 4. Texto del Diálogo con Word-Wrap y Sombra Retro
        txt_y = box_y + (16 if speaker_name else 4)
        
        # Sombra del texto
        msg_shadow = QGraphicsTextItem()
        msg_shadow.setPlainText(dial.text)
        msg_shadow.setTextWidth(text_w)
        msg_shadow.setFont(QFont("Segoe UI", 7))
        msg_shadow.setDefaultTextColor(QColor(0, 0, 0, 220))
        msg_shadow.setPos(text_x + 1, txt_y + 1)
        msg_shadow.setZValue(103)
        self.stage_scene.addItem(msg_shadow)
        self._dialogue_items.append(msg_shadow)

        # Texto frontal blanco nítido
        msg_item = QGraphicsTextItem()
        msg_item.setPlainText(dial.text)
        msg_item.setTextWidth(text_w)
        msg_item.setFont(QFont("Segoe UI", 7))
        msg_item.setDefaultTextColor(QColor("#FFFFFF"))
        msg_item.setPos(text_x, txt_y)
        msg_item.setZValue(104)
        self.stage_scene.addItem(msg_item)
        self._dialogue_items.append(msg_item)

        # 5. Indicador de Continuación Clásico de FoMT (Flecha ▼ Dorada)
        arrow = QGraphicsTextItem("▼")
        arrow.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        arrow.setDefaultTextColor(QColor("#FAD02C"))
        arrow.setPos(box_x + box_w - 14, box_y + box_h - 14)
        arrow.setZValue(105)
        self.stage_scene.addItem(arrow)
        self._dialogue_items.append(arrow)

    def _on_actor_item_dragged(self, actor_id: str, x: int, y: int):
        self.actorMoved.emit(actor_id, x, y)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, TheaterActorItem):
            self.actorSelected.emit(item.actor.actor_id)
        super().mousePressEvent(event)

    def zoom_in(self):
        self.zoom_level = min(4.0, self.zoom_level + 0.25)
        self.apply_zoom()

    def zoom_out(self):
        self.zoom_level = max(0.5, self.zoom_level - 0.25)
        self.apply_zoom()

    def zoom_fit(self):
        self.zoom_level = 1.0
        self.apply_zoom()


# ============================================================
# 6. WIDGET PRINCIPAL: TEATRO DE EVENTOS (TEATROEVENTOSWIDGET)
# ============================================================
class TeatroEventosWidget(QWidget):
    """
    Panel integral de direccion de escenas y ejecucion de scripts.
    Carga el script binario de la ROM, ejecuta sus instrucciones secuencialmente,
    y permite modificar posiciones con drag & drop y reexportar codigo C++.
    """
    def __init__(self, project=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.asset_bank = EventAssetBank(self.project)
        self.vm = TheaterInstructionVM(self.asset_bank)

        self.current_event_id = 20
        self.current_step_idx = 0
        self.selected_actor_id = "player"

        # Timer de reproduccion de cinemática
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._on_play_step)
        self.play_speed_ms = 1000

        self._setup_ui()
        self.load_event(self.current_event_id)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # ── 1. BARRA SUPERIOR DE CONTROL ─────────────────────────────
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #161B22; border-radius: 4px; padding: 4px;")
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(6, 4, 6, 4)
        top_lay.setSpacing(8)

        lbl_ev = QLabel(_t("thr_event"))
        lbl_ev.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_ev.setStyleSheet("color: #58A6FF;")
        top_lay.addWidget(lbl_ev)

        self.combo_events = QComboBox()
        self.combo_events.setMinimumWidth(260)
        self._populate_events_combo()
        self.combo_events.currentIndexChanged.connect(self._on_event_combo_changed)
        top_lay.addWidget(self.combo_events)

        btn_load_rom = QPushButton(_t("thr_btn_load_rom"))
        btn_load_rom.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 4px 10px;")
        btn_load_rom.clicked.connect(self._on_reload_from_rom)
        top_lay.addWidget(btn_load_rom)

        btn_export = QPushButton(_t("thr_btn_export"))
        btn_export.setStyleSheet("background-color: #1F6FEB; color: white; font-weight: bold; padding: 4px 10px;")
        btn_export.clicked.connect(lambda: self._on_export_script(show_dialog=True))
        top_lay.addWidget(btn_export)

        top_lay.addStretch()

        btn_zin = QPushButton("+")
        btn_zin.setFixedWidth(28)
        btn_zin.clicked.connect(lambda: self.canvas.zoom_in())
        top_lay.addWidget(btn_zin)

        btn_zout = QPushButton("-")
        btn_zout.setFixedWidth(28)
        btn_zout.clicked.connect(lambda: self.canvas.zoom_out())
        top_lay.addWidget(btn_zout)

        btn_zfit = QPushButton("1:1")
        btn_zfit.setFixedWidth(36)
        btn_zfit.clicked.connect(lambda: self.canvas.zoom_fit())
        top_lay.addWidget(btn_zfit)

        main_layout.addWidget(top_bar)

        # ── 2. BANNER DE INSTRUCCION ACTIVA (HUD) ────────────────────
        self.hud_banner = QFrame()
        self.hud_banner.setStyleSheet("background-color: #0D1117; border: 1px solid #30363D; border-radius: 4px; padding: 4px 8px;")
        hud_lay = QHBoxLayout(self.hud_banner)
        hud_lay.setContentsMargins(6, 2, 6, 2)

        self.lbl_step_num = QLabel(_t("thr_step_empty"))
        self.lbl_step_num.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self.lbl_step_num.setStyleSheet("color: #E3B341;")
        hud_lay.addWidget(self.lbl_step_num)

        hud_lay.addWidget(QLabel("|"))

        self.lbl_ins_desc = QLabel(_t("thr_ins_none"))
        self.lbl_ins_desc.setFont(QFont("Consolas", 9))
        self.lbl_ins_desc.setStyleSheet("color: #58A6FF;")
        hud_lay.addWidget(self.lbl_ins_desc, 1)

        self.lbl_map_bgm_info = QLabel(_t("thr_map_bgm_empty"))
        self.lbl_map_bgm_info.setFont(QFont("Segoe UI", 8))
        self.lbl_map_bgm_info.setStyleSheet("color: #8B949E;")
        hud_lay.addWidget(self.lbl_map_bgm_info)

        main_layout.addWidget(self.hud_banner)

        # ── 3. SPLITTER PRINCIPAL: LIENZO Y PANEL LATERAL ────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lienzo Central
        self.canvas = TheaterStageCanvas(self.asset_bank, self)
        self.canvas.actorMoved.connect(self._on_actor_moved_on_stage)
        self.canvas.actorSelected.connect(self._on_actor_selected_on_stage)
        splitter.addWidget(self.canvas)

        # Panel Lateral de Pestañas
        side_panel = QFrame()
        side_panel.setMinimumWidth(360)
        side_panel.setMaximumWidth(460)
        side_lay = QVBoxLayout(side_panel)
        side_lay.setContentsMargins(0, 0, 0, 0)

        self.tabs_side = QTabWidget()

        # Pestaña 1: Secuencia de Instrucciones
        tab_ins = QWidget()
        lay_tab_ins = QVBoxLayout(tab_ins)
        lay_tab_ins.setContentsMargins(4, 4, 4, 4)
        self.list_instructions = QListWidget()
        self.list_instructions.setFont(QFont("Consolas", 8))
        self.list_instructions.setStyleSheet("background-color: #0D1117; color: #C9D1D9;")
        self.list_instructions.currentRowChanged.connect(self._on_ins_list_row_changed)
        lay_tab_ins.addWidget(self.list_instructions)
        self.tabs_side.addTab(tab_ins, _t("thr_tab_instructions"))

        # Pestaña 2: Actor Seleccionado
        tab_act = QWidget()
        lay_tab_act = QVBoxLayout(tab_act)
        lay_tab_act.setContentsMargins(6, 6, 6, 6)

        lay_tab_act.addWidget(QLabel(_t("thr_active_actor")))
        self.combo_actor_list = QComboBox()
        self.combo_actor_list.currentIndexChanged.connect(self._on_actor_combo_changed)
        lay_tab_act.addWidget(self.combo_actor_list)

        pos_box = QHBoxLayout()
        pos_box.addWidget(QLabel(_t("thr_coord_x")))
        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 2048)
        self.spin_x.valueChanged.connect(self._on_actor_spin_changed)
        pos_box.addWidget(self.spin_x)
        pos_box.addWidget(QLabel(_t("thr_coord_y")))
        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 2048)
        self.spin_y.valueChanged.connect(self._on_actor_spin_changed)
        pos_box.addWidget(self.spin_y)
        lay_tab_act.addLayout(pos_box)

        lay_tab_act.addWidget(QLabel(_t("thr_facing")))
        self.combo_facing = QComboBox()
        self.combo_facing.addItems(["Down", "Up", "Left", "Right"])
        self.combo_facing.currentIndexChanged.connect(self._on_facing_changed)
        lay_tab_act.addWidget(self.combo_facing)

        lay_tab_act.addWidget(QLabel(_t("thr_emote")))
        self.combo_emote = QComboBox()
        self.combo_emote.addItem(_t("thr_emote_none"), "none")
        self.combo_emote.addItem(_t("thr_emote_excl"), "exclamation")
        self.combo_emote.addItem(_t("thr_emote_heart"), "heart")
        self.combo_emote.addItem(_t("thr_emote_sweat"), "sweat")
        self.combo_emote.addItem(_t("thr_emote_music"), "music")
        self.combo_emote.addItem(_t("thr_emote_question"), "question")
        self.combo_emote.currentIndexChanged.connect(self._on_emote_changed)
        lay_tab_act.addWidget(self.combo_emote)

        lay_tab_act.addStretch()
        self.tabs_side.addTab(tab_act, _t("thr_tab_actor"))

        # Pestaña 3: Escenario & Audio
        tab_stage = QWidget()
        lay_tab_stage = QVBoxLayout(tab_stage)
        lay_tab_stage.setContentsMargins(6, 6, 6, 6)

        lay_tab_stage.addWidget(QLabel(_t("thr_gba_map")))
        self.combo_map = QComboBox()
        self._populate_maps_combo()
        self.combo_map.currentIndexChanged.connect(self._on_map_changed)
        lay_tab_stage.addWidget(self.combo_map)

        lay_tab_stage.addWidget(QLabel(_t("thr_bgm")))
        self.combo_bgm = QComboBox()
        for bid, bname in self.asset_bank.bgm_catalog:
            self.combo_bgm.addItem(f"0x{bid:02X} - {bname}", bid)
        self.combo_bgm.currentIndexChanged.connect(self._on_bgm_changed)
        lay_tab_stage.addWidget(self.combo_bgm)

        lay_tab_stage.addWidget(QLabel(_t("thr_sfx")))
        self.combo_sfx = QComboBox()
        for sid, sname in self.asset_bank.sfx_catalog:
            self.combo_sfx.addItem(f"0x{sid:02X} - {sname}", sid)
        self.combo_sfx.currentIndexChanged.connect(self._on_sfx_changed)
        lay_tab_stage.addWidget(self.combo_sfx)

        lay_tab_stage.addWidget(QLabel(_t("thr_transition")))
        self.combo_fade = QComboBox()
        self.combo_fade.addItems(["Normal", "Fade In", "Fade Out"])
        lay_tab_stage.addWidget(self.combo_fade)

        lay_tab_stage.addStretch()
        self.tabs_side.addTab(tab_stage, _t("thr_tab_stage"))

        # Pestaña 4: Diálogo & Retrato
        tab_dial = QWidget()
        lay_tab_dial = QVBoxLayout(tab_dial)
        lay_tab_dial.setContentsMargins(6, 6, 6, 6)
        lay_tab_dial.setSpacing(6)

        self.chk_dialogue_active = QCheckBox(_t("thr_dialogue_active"))
        self.chk_dialogue_active.setStyleSheet("color: #7EE787; font-weight: bold;")
        self.chk_dialogue_active.toggled.connect(self._on_dialogue_active_toggled)
        lay_tab_dial.addWidget(self.chk_dialogue_active)

        # Preview del retrato decodificado de la ROM
        port_box = QHBoxLayout()
        self.lbl_portrait_preview = QLabel()
        self.lbl_portrait_preview.setFixedSize(64, 72)
        self.lbl_portrait_preview.setStyleSheet("background-color: #0D1117; border: 1px solid #30363D; border-radius: 4px;")
        self.lbl_portrait_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        port_box.addWidget(self.lbl_portrait_preview)

        port_meta = QVBoxLayout()
        self.lbl_portrait_name = QLabel(_t("thr_no_portrait"))
        self.lbl_portrait_name.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.lbl_portrait_name.setStyleSheet("color: #58A6FF;")
        port_meta.addWidget(self.lbl_portrait_name)

        self.lbl_speaker_name = QLabel(_t("thr_speaker", name=_t("thr_nobody")))
        self.lbl_speaker_name.setFont(QFont("Segoe UI", 8))
        port_meta.addWidget(self.lbl_speaker_name)

        self.btn_edit_melody = QPushButton(_t("thr_btn_edit_melody"))
        self.btn_edit_melody.setStyleSheet("background-color: #1F3A5F; color: #58A6FF; border: 1px solid #388BFD; padding: 4px; border-radius: 4px; font-weight: bold;")
        self.btn_edit_melody.clicked.connect(self._on_open_melody_editor)
        port_meta.addWidget(self.btn_edit_melody)

        port_box.addLayout(port_meta)
        lay_tab_dial.addLayout(port_box)

        lay_tab_dial.addWidget(QLabel(_t("thr_rom_message")))
        self.txt_dialogue = QTextEdit()
        self.txt_dialogue.setFont(QFont("Segoe UI", 9))
        self.txt_dialogue.textChanged.connect(self._on_dialogue_text_edited)
        lay_tab_dial.addWidget(self.txt_dialogue)

        self.tabs_side.addTab(tab_dial, _t("thr_tab_dialogue"))

        side_lay.addWidget(self.tabs_side)
        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # ── 4. BARRA DE TRANSPORTE Y CRONOLOGIA (TIMELINE) ───────────
        transport = QFrame()
        transport.setStyleSheet("background-color: #161B22; border-radius: 4px; padding: 4px;")
        t_lay = QHBoxLayout(transport)
        t_lay.setContentsMargins(6, 4, 6, 4)
        t_lay.setSpacing(6)

        btn_first = QPushButton("<<")
        btn_first.setFixedWidth(32)
        btn_first.clicked.connect(self._go_first_step)
        t_lay.addWidget(btn_first)

        btn_prev = QPushButton("<")
        btn_prev.setFixedWidth(32)
        btn_prev.clicked.connect(self._go_prev_step)
        t_lay.addWidget(btn_prev)

        self.btn_play = QPushButton(_t("thr_play"))
        self.btn_play.setFixedWidth(64)
        self.btn_play.setStyleSheet("background-color: #238636; color: white; font-weight: bold;")
        self.btn_play.clicked.connect(self._toggle_playback)
        t_lay.addWidget(self.btn_play)

        btn_next = QPushButton(">")
        btn_next.setFixedWidth(32)
        btn_next.clicked.connect(self._go_next_step)
        t_lay.addWidget(btn_next)

        btn_last = QPushButton(">>")
        btn_last.setFixedWidth(32)
        btn_last.clicked.connect(self._go_last_step)
        t_lay.addWidget(btn_last)

        self.slider_steps = QSlider(Qt.Orientation.Horizontal)
        self.slider_steps.setRange(0, 0)
        self.slider_steps.valueChanged.connect(self._on_slider_moved)
        t_lay.addWidget(self.slider_steps, 1)

        main_layout.addWidget(transport)

    # ── CARGA Y SINCRONIZACION DE EVENTOS ────────────────────────
    def _populate_events_combo(self):
        self.combo_events.blockSignals(True)
        self.combo_events.clear()
        max_events = 1328
        for i in range(1, max_events + 1):
            name = f"Evento {i:04d}"
            if self.project and hasattr(self.project, 'super_lib') and self.project.super_lib:
                hint = self.project.super_lib.get_event_name_hint(i)
                if hint: name = f"Ev {i:04d}: {hint}"
            self.combo_events.addItem(name, i)
        self.combo_events.blockSignals(False)

    def _populate_maps_combo(self):
        self.combo_map.blockSignals(True)
        self.combo_map.clear()
        for i in range(0x43):
            name = f"0x{i:02X} - Mapa #{i}"
            if self.project and hasattr(self.project, 'super_lib') and self.project.super_lib:
                for k, v in self.project.super_lib.map_map.items():
                    if v == i:
                        name = f"0x{i:02X} - {k}"
                        break
            self.combo_map.addItem(name, i)
        self.combo_map.blockSignals(False)

    def load_event(self, event_id: int):
        """Carga y descompila el evento desde la ROM ejecutando sus instrucciones binarias."""
        self.current_event_id = event_id
        for i in range(self.combo_events.count()):
            if self.combo_events.itemData(i) == event_id:
                self.combo_events.blockSignals(True)
                self.combo_events.setCurrentIndex(i)
                self.combo_events.blockSignals(False)
                break

        steps = self.vm.load_event(event_id)
        self.current_step_idx = 0

        # Actualizar lista de instrucciones del panel lateral
        self.list_instructions.blockSignals(True)
        self.list_instructions.clear()
        for st in steps:
            item = QListWidgetItem(f"[{st.step_idx:02d}] {st.summary}")
            self.list_instructions.addItem(item)
        self.list_instructions.blockSignals(False)

        self.slider_steps.blockSignals(True)
        self.slider_steps.setRange(0, max(0, len(steps) - 1))
        self.slider_steps.setValue(0)
        self.slider_steps.blockSignals(False)

        self._sync_ui_with_current_step()

    @property
    def current_scene(self) -> Optional[TheaterStep]:
        if self.vm.steps and 0 <= self.current_step_idx < len(self.vm.steps):
            return self.vm.steps[self.current_step_idx]
        return None

    @property
    def scenes(self) -> List[TheaterStep]:
        return self.vm.steps

    def _sync_ui_with_current_step(self):
        """Sincroniza todos los controles, el HUD y el lienzo con el paso activo."""
        steps = self.vm.steps
        if not steps:
            return

        self.current_step_idx = max(0, min(self.current_step_idx, len(steps) - 1))
        step = steps[self.current_step_idx]

        # 1. Actualizar HUD
        self.lbl_step_num.setText(_t("thr_step", cur=f"{step.step_idx:02d}", total=f"{len(steps):02d}"))
        self.lbl_ins_desc.setText(_t("thr_ins", summary=step.summary))
        self.lbl_map_bgm_info.setText(_t("thr_map_bgm", map=f"0x{step.map_id:02X}", bgm=f"0x{step.bgm_id:02X}", sfx=f"0x{step.sfx_id:02X}"))

        # 2. Sincronizar Lienzo
        self.canvas.load_step_state(step)

        # 3. Sincronizar Lista de Instrucciones
        self.list_instructions.blockSignals(True)
        self.list_instructions.setCurrentRow(self.current_step_idx)
        self.list_instructions.blockSignals(False)

        # 4. Sincronizar Slider
        self.slider_steps.blockSignals(True)
        self.slider_steps.setValue(self.current_step_idx)
        self.slider_steps.blockSignals(False)

        # 5. Sincronizar Escenario & Audio
        self.combo_map.blockSignals(True)
        idx_m = self.combo_map.findData(step.map_id)
        if idx_m >= 0: self.combo_map.setCurrentIndex(idx_m)
        self.combo_map.blockSignals(False)

        self.combo_bgm.blockSignals(True)
        idx_b = self.combo_bgm.findData(step.bgm_id)
        if idx_b >= 0: self.combo_bgm.setCurrentIndex(idx_b)
        self.combo_bgm.blockSignals(False)

        self.combo_sfx.blockSignals(True)
        idx_s = self.combo_sfx.findData(step.sfx_id)
        if idx_s >= 0: self.combo_sfx.setCurrentIndex(idx_s)
        self.combo_sfx.blockSignals(False)

        # 6. Sincronizar Actores
        self.combo_actor_list.blockSignals(True)
        self.combo_actor_list.clear()
        for aid, act in step.actors.items():
            self.combo_actor_list.addItem(f"{act.name} ({aid})", aid)

        if self.selected_actor_id in step.actors:
            idx_act = self.combo_actor_list.findData(self.selected_actor_id)
            if idx_act >= 0: self.combo_actor_list.setCurrentIndex(idx_act)
        else:
            self.selected_actor_id = "player" if "player" in step.actors else (list(step.actors.keys())[0] if step.actors else "player")
            idx_act = self.combo_actor_list.findData(self.selected_actor_id)
            if idx_act >= 0: self.combo_actor_list.setCurrentIndex(idx_act)
        self.combo_actor_list.blockSignals(False)

        self._sync_actor_properties()

        # 7. Sincronizar Diálogo y Retrato
        dial = step.dialogue
        self.chk_dialogue_active.blockSignals(True)
        self.chk_dialogue_active.setChecked(dial.active)
        self.chk_dialogue_active.blockSignals(False)

        if dial.active and dial.portrait_pixmap and not dial.portrait_pixmap.isNull():
            sc_pix = dial.portrait_pixmap.scaled(64, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.lbl_portrait_preview.setPixmap(sc_pix)
            self.lbl_portrait_name.setText(self.asset_bank.get_portrait_name(dial.portrait_id))
        else:
            self.lbl_portrait_preview.clear()
            self.lbl_portrait_name.setText(_t("thr_no_portrait"))

        self.lbl_speaker_name.setText(_t("thr_speaker", name=dial.speaker_name or _t("thr_nobody")))
        self.txt_dialogue.blockSignals(True)
        self.txt_dialogue.setPlainText(dial.text)
        self.txt_dialogue.blockSignals(False)

    def _sync_actor_properties(self):
        step = self.current_scene
        if not step or self.selected_actor_id not in step.actors:
            return
        actor = step.actors[self.selected_actor_id]

        self.spin_x.blockSignals(True)
        self.spin_x.setValue(actor.x)
        self.spin_x.blockSignals(False)

        self.spin_y.blockSignals(True)
        self.spin_y.setValue(actor.y)
        self.spin_y.blockSignals(False)

        self.combo_facing.blockSignals(True)
        idx_f = self.combo_facing.findText(actor.facing)
        if idx_f >= 0: self.combo_facing.setCurrentIndex(idx_f)
        self.combo_facing.blockSignals(False)

        self.combo_emote.blockSignals(True)
        idx_e = self.combo_emote.findData(actor.emote)
        if idx_e >= 0: self.combo_emote.setCurrentIndex(idx_e)
        self.combo_emote.blockSignals(False)

    # ── TRANSPORTE Y PASOS ───────────────────────────────────────
    def _go_first_step(self):
        self.current_step_idx = 0
        self._sync_ui_with_current_step()

    def _go_prev_step(self):
        if self.current_step_idx > 0:
            self.current_step_idx -= 1
            self._sync_ui_with_current_step()

    def _go_next_step(self):
        if self.current_step_idx < len(self.vm.steps) - 1:
            self.current_step_idx += 1
            self._sync_ui_with_current_step()

    def _go_last_step(self):
        if self.vm.steps:
            self.current_step_idx = len(self.vm.steps) - 1
            self._sync_ui_with_current_step()

    def _on_slider_moved(self, value: int):
        self.current_step_idx = value
        self._sync_ui_with_current_step()

    def _on_ins_list_row_changed(self, row: int):
        if 0 <= row < len(self.vm.steps):
            self.current_step_idx = row
            self._sync_ui_with_current_step()

    def _toggle_playback(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.btn_play.setText(_t("thr_play"))
            self.btn_play.setStyleSheet("background-color: #238636; color: white; font-weight: bold;")
        else:
            self.play_timer.start(self.play_speed_ms)
            self.btn_play.setText(_t("thr_pause"))
            self.btn_play.setStyleSheet("background-color: #D29922; color: white; font-weight: bold;")

    def _on_play_step(self):
        if self.current_step_idx < len(self.vm.steps) - 1:
            self._go_next_step()
        else:
            self._toggle_playback()

    # ── ACCIONES DE USUARIO Y MUTACION VIRTUAL MACHINE ───────────
    def _on_actor_moved_on_stage(self, actor_id: str, x: int, y: int):
        self.vm.update_actor_position(self.current_step_idx, actor_id, x, y)
        self.spin_x.blockSignals(True)
        self.spin_x.setValue(x)
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(True)
        self.spin_y.setValue(y)
        self.spin_y.blockSignals(False)

    def _on_actor_selected_on_stage(self, actor_id: str):
        self.selected_actor_id = actor_id
        idx = self.combo_actor_list.findData(actor_id)
        if idx >= 0:
            self.combo_actor_list.blockSignals(True)
            self.combo_actor_list.setCurrentIndex(idx)
            self.combo_actor_list.blockSignals(False)
        self._sync_actor_properties()

    def _on_actor_combo_changed(self, idx: int):
        aid = self.combo_actor_list.currentData()
        if aid:
            self.selected_actor_id = aid
            self._sync_actor_properties()

    def _on_actor_spin_changed(self):
        step = self.current_scene
        if not step or self.selected_actor_id not in step.actors:
            return
        x = self.spin_x.value()
        y = self.spin_y.value()
        self.vm.update_actor_position(self.current_step_idx, self.selected_actor_id, x, y)
        item = self.canvas.actor_items.get(self.selected_actor_id)
        if item:
            item.setPos(x, y)

    def _on_facing_changed(self, idx: int):
        step = self.current_scene
        if not step or self.selected_actor_id not in step.actors:
            return
        facing = self.combo_facing.currentText()
        self.vm.update_actor_facing(self.current_step_idx, self.selected_actor_id, facing)
        item = self.canvas.actor_items.get(self.selected_actor_id)
        if item: item.update()

    def _on_emote_changed(self, idx: int):
        step = self.current_scene
        if not step or self.selected_actor_id not in step.actors:
            return
        emote = self.combo_emote.currentData()
        step.actors[self.selected_actor_id].emote = emote
        item = self.canvas.actor_items.get(self.selected_actor_id)
        if item: item.update()

    def _on_map_changed(self, idx: int):
        step = self.current_scene
        if not step: return
        mid = self.combo_map.currentData()
        step.map_id = mid
        self.canvas.load_step_state(step)

    def _on_bgm_changed(self, idx: int):
        step = self.current_scene
        if not step: return
        bid = self.combo_bgm.currentData()
        step.bgm_id = bid

    def _on_sfx_changed(self, idx: int):
        step = self.current_scene
        if not step: return
        sid = self.combo_sfx.currentData()
        step.sfx_id = sid

    def _on_dialogue_active_toggled(self, checked: bool):
        step = self.current_scene
        if not step: return
        step.dialogue.active = checked
        if hasattr(self.canvas, '_update_dialogue_hud'):
            cam_x = int(self.canvas.camera_box.rect().x())
            cam_y = int(self.canvas.camera_box.rect().y())
            self.canvas._update_dialogue_hud(step.dialogue, cam_x, cam_y)

    def _on_open_melody_editor(self):
        step = self.current_scene
        if not step: return
        dial = step.dialogue
        port_id = dial.portrait_id if dial.portrait_id is not None else 0
        from Nucleos_Positronicos.Nucleo_de_Portraits.portrait_editor import PortraitEditorDialog
        pname = self.asset_bank.get_portrait_name(port_id)
        base_name = pname.replace("_Neutral", "").replace("_Happy", "").replace("_Angry", "").split()[0]
        dlg = PortraitEditorDialog(dial.speaker_name or base_name, port_id, base_name, parent=self)
        dlg.exec()
        if port_id in self.asset_bank._portraits_cache:
            del self.asset_bank._portraits_cache[port_id]
        new_pix = self.asset_bank.get_portrait_pixmap(port_id)
        dial.portrait_pixmap = new_pix
        self._sync_step_to_ui(step)
        if hasattr(self.canvas, '_update_dialogue_hud'):
            cam_x = int(self.canvas.camera_box.rect().x())
            cam_y = int(self.canvas.camera_box.rect().y())
            self.canvas._update_dialogue_hud(step.dialogue, cam_x, cam_y)

    def _on_dialogue_text_edited(self):
        step = self.current_scene
        if not step: return
        txt = self.txt_dialogue.toPlainText()
        step.dialogue.text = txt
        if hasattr(self.canvas, '_update_dialogue_hud'):
            cam_x = int(self.canvas.camera_box.rect().x())
            cam_y = int(self.canvas.camera_box.rect().y())
            self.canvas._update_dialogue_hud(step.dialogue, cam_x, cam_y)

    def _on_event_combo_changed(self, idx: int):
        eid = self.combo_events.currentData()
        if eid:
            self.load_event(eid)

    def _on_reload_from_rom(self):
        self.load_event(self.current_event_id)

    def _on_export_script(self, show_dialog: bool = True) -> str:
        """Exporta y muestra el script C++ completo generado a partir del AST vivo."""
        code = self.vm.export_script_code()
        if show_dialog:
            dlg = QDialog(self)
            dlg.setWindowTitle(_t("thr_recompiled_title", id=f"{self.current_event_id:04d}"))
            dlg.resize(650, 520)
            lay = QVBoxLayout(dlg)
            txt = QTextEdit()
            txt.setPlainText(code)
            txt.setFont(QFont("Consolas", 10))
            lay.addWidget(txt)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            btns.accepted.connect(dlg.accept)
            lay.addWidget(btns)
            dlg.exec()
        return code
