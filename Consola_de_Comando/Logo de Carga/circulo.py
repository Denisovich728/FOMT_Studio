import sys
import math
import random
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QFontDatabase

class MagicCircleEngine(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FOMT Studio - SlipSpace Loader")
        self.resize(700, 700)
        
        # Carga tipográfica nativa
        font_id = QFontDatabase.addApplicationFont("fuente.ttf")
        self.font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"
        
        # Hardware Palette
        self.bg_color = QColor(20, 20, 25, 255)
        self.primary_color = QColor(255, 215, 0, 255)
        
        # FSM Core
        self.step = 0
        self.step_progress = 0.0
        self.blink_count = 0
        self.rotation_angle = 0
        self.tick_counter = 0
        
        # Buffers de datos
        self.glyphs = [chr(65 + i) for i in range(24)] # ASCII A-X
        self.hex_buffer = [f"{random.randint(0, 255):02X}" for _ in range(16)]
        self.arcane_symbols = ["⏣", "⎈", "⎊", "⍟", "⌖", "⍡"]
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ritual)
        self.timer.start(16)

    def mechanical_ease_out(self, t: float) -> float:
        # Curva cúbica: Desaceleración mecánica y estricta (cero rebote)
        if t <= 0: return 0.0
        if t >= 1: return 1.0
        return 1.0 - math.pow(1.0 - t, 3)

    def update_ritual(self):
        self.tick_counter += 1
        
        # Hardware Tickrate (Telemetría)
        if self.tick_counter % 4 == 0:
            self.hex_buffer = [f"{random.randint(0, 255):02X}" for _ in range(16)]

        delta = 0.15 if self.step == 1 else 0.015
        self.step_progress += delta
        
        # Secuenciador FSM
        if self.step_progress >= 1.0:
            if self.step == 1:
                self.blink_count += 1
                self.step_progress = 0.0
                if self.blink_count >= 4: 
                    self.step = 2
            elif self.step < 6:
                self.step += 1
                self.step_progress = 0.0
            else:
                self.step_progress = 1.0 
        
        if self.step >= 2: 
            self.rotation_angle += 0.5
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.bg_color)
        
        cx, cy = self.width() / 2, self.height() / 2
        painter.translate(cx, cy)
        
        base_s = 100 
        
        # --- 0 y 1. Círculos base, Telemetría y Parpadeo ---
        if self.step >= 0:
            alpha = 0 if (self.step == 1 and self.blink_count % 2 != 0) else 1
            painter.setOpacity(alpha)
            
            raw_t = min(self.step_progress, 1.0) if self.step == 0 else 1.0
            scale = self.mechanical_ease_out(raw_t)
            s = base_s * scale
            
            painter.setPen(QPen(self.primary_color, 2))
            
            # Anillos perimetrales
            painter.drawEllipse(QPointF(0,0), s*1.25, s*1.25)
            painter.drawEllipse(QPointF(0,0), s*1.55, s*1.55)
            painter.drawEllipse(QPointF(0,0), s*1.65, s*1.65)
            painter.drawEllipse(QPointF(0,0), s*1.90, s*1.90)
            
            # Banda de Glifos (Rotación Positiva / Derecha)
            painter.save()
            painter.rotate(self.rotation_angle * 0.5)
            font_s = int(max(base_s * 0.15, 1))
            painter.setFont(QFont(self.font_family, font_s))
            box = base_s * 0.3
            for i in range(24):
                a = i * 15
                x, y = (s*1.40) * math.cos(math.radians(a)), (s*1.40) * math.sin(math.radians(a))
                painter.save()
                painter.translate(x, y)
                painter.rotate(a + 90)
                # Lock Criptográfico
                char = self.glyphs[i % len(self.glyphs)] if raw_t == 1.0 else random.choice(self.glyphs)
                painter.drawText(QRectF(-box/2, -box/2, box, box), int(Qt.AlignmentFlag.AlignCenter), char)
                painter.restore()
            painter.restore()

            # Banda Hexadecimal (Rotación Negativa / Izquierda)
            painter.save()
            painter.rotate(-self.rotation_angle * 0.6)
            font_hex_s = int(max(base_s * 0.1, 1))
            painter.setFont(QFont("Consolas", font_hex_s, QFont.Weight.Bold))
            box_hex = base_s * 0.25
            for i in range(16):
                a = i * 22.5
                x, y = (s*1.775) * math.cos(math.radians(a)), (s*1.775) * math.sin(math.radians(a))
                painter.save()
                painter.translate(x, y)
                painter.rotate(a + 90)
                # Lock Criptográfico Hex
                hex_val = self.hex_buffer[i] if raw_t == 1.0 else f"{random.randint(0, 255):02X}"
                painter.drawText(QRectF(-box_hex/2, -box_hex/2, box_hex, box_hex), int(Qt.AlignmentFlag.AlignCenter), hex_val)
                painter.restore()
            painter.restore()
            
            painter.setOpacity(1.0)

        # --- 2. Decágono (Rotación Positiva / Derecha) ---
        if self.step >= 2:
            raw_t = min(self.step_progress, 1.0) if self.step == 2 else 1.0
            scale = self.mechanical_ease_out(raw_t)
            painter.save()
            painter.rotate(self.rotation_angle * 0.8)
            self.draw_polygon(painter, 10, base_s * scale)
            painter.restore()

        # --- 3. Estrella Hexagrama (Rotación Negativa / Izquierda) ---
        if self.step >= 3:
            raw_t = min(self.step_progress, 1.0) if self.step == 3 else 1.0
            scale = self.mechanical_ease_out(raw_t)
            painter.save()
            painter.rotate(-self.rotation_angle * 0.8)
            self.draw_hexagram(painter, base_s * scale)
            painter.restore()

        # --- 4, 5 y 6. Hardware de inyección en puntas ---
        if self.step >= 4:
            painter.save()
            # Orbitan acoplados al hexagrama (Izquierda)
            painter.rotate(-self.rotation_angle * 0.8)
            
            raw_t_circ = min(self.step_progress, 1.0) if self.step == 4 else 1.0
            circ_scale = self.mechanical_ease_out(raw_t_circ)
            
            raw_t_quad = min(self.step_progress, 1.0) if self.step == 5 else (1.0 if self.step > 5 else 0.0)
            quad_scale = self.mechanical_ease_out(raw_t_quad) if raw_t_quad > 0 else 0
            
            points_for_constellation = []
            
            for i in range(6):
                a = i * 60 - 90
                px, py = base_s * math.cos(math.radians(a)), base_s * math.sin(math.radians(a))
                points_for_constellation.append(QPointF(px, py))
                
                # Círculos Periféricos
                rad = base_s * 0.15 * circ_scale
                painter.setPen(QPen(self.primary_color, 2))
                painter.drawEllipse(QPointF(px, py), rad, rad)
                
                # Nodos Cuadrados
                if self.step >= 5:
                    sq = base_s * 0.08 * quad_scale
                    painter.save()
                    painter.translate(px, py)
                    # Rotación local sobre su eje (Derecha)
                    painter.rotate(self.rotation_angle * 2) 
                    painter.setBrush(QBrush(self.primary_color))
                    painter.drawRect(int(-sq), int(-sq), int(sq*2), int(sq*2))
                    
                    # Decodificación Símbolos Arcanos
                    painter.setPen(QColor(0, 0, 0))
                    painter.setFont(QFont("Segoe UI Symbol", int(max(sq*1.2, 1))))
                    symb = self.arcane_symbols[i % 6] if raw_t_quad == 1.0 else random.choice(self.arcane_symbols)
                    painter.drawText(QRectF(-sq, -sq, sq*2, sq*2), int(Qt.AlignmentFlag.AlignCenter), symb)
                    painter.restore()

            # --- 6. Binding: Cierre de Circuito Constelación ---
            if self.step >= 6:
                raw_t_const = min(self.step_progress, 1.0)
                alpha_const = int(100 * raw_t_const)
                pen_const = QPen(QColor(255, 215, 0, alpha_const), 1, Qt.PenStyle.DashLine)
                painter.setPen(pen_const)
                for i in range(6):
                    painter.drawLine(points_for_constellation[i], points_for_constellation[(i+1)%6])

            painter.restore()

    def draw_polygon(self, p, sides, r):
        for i in range(sides):
            a1, a2 = math.radians(i*(360/sides)-90), math.radians((i+1)*(360/sides)-90)
            p.drawLine(int(r*math.cos(a1)), int(r*math.sin(a1)), int(r*math.cos(a2)), int(r*math.sin(a2)))

    def draw_hexagram(self, p, r):
        for s in [0, 180]:
            pts = [QPointF(r*math.cos(math.radians(i*120-90+s)), r*math.sin(math.radians(i*120-90+s))) for i in range(3)]
            p.drawPolyline(*pts, pts[0])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MagicCircleEngine()
    window.show()
    sys.exit(app.exec())