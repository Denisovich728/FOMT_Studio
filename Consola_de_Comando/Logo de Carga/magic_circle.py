import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush

class MagicCircleLoader(QWidget):
    animationFinished = pyqtSignal()

    def __init__(self, parent=None, size=60):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.base_s = size * 14 / 60
        
        self.font_family = "Arial"
        import os
        import sys
        from PyQt6.QtGui import QFontDatabase
        
        def get_resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, 'Consola_de_Comando', 'Logo de Carga', relative_path)
            return os.path.join(os.path.dirname(__file__), relative_path)
            
        font_path = get_resource_path("fuente.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                self.font_family = font_families[0]
        
        # Colors adjusted for loading indicator
        self.bg_color = Qt.GlobalColor.transparent
        self.primary_color = QColor(255, 215, 0, 255)
        
        self.step = 0
        self.step_progress = 0.0
        self.blink_count = 0
        self.rotation_angle = 0
        self.tick_counter = 0
        
        self.glyphs = [chr(65 + i) for i in range(24)]
        self.hex_buffer = [f"{random.randint(0, 255):02X}" for _ in range(16)]
        self.arcane_symbols = ["⏣", "⎈", "⎊", "⍟", "⌖", "⍡"]
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ritual)
        self.is_active = False
        self.is_stopping = False

    def start_animation(self):
        self.step = 0
        self.step_progress = 0.0
        self.blink_count = 0
        self.rotation_angle = 0
        self.show()
        self.is_active = True
        self.is_stopping = False
        self.timer.start(16)

    def stop_animation(self):
        self.is_stopping = True
        if not self.is_active:
            self.hide()
            self.animationFinished.emit()
            return
        if self.step < 5:
            self.step = 5
            self.step_progress = 0.0

    def mechanical_ease_out(self, t: float) -> float:
        if t <= 0: return 0.0
        if t >= 1: return 1.0
        return 1.0 - math.pow(1.0 - t, 3)

    def update_ritual(self):
        if not self.is_active: return
        self.tick_counter += 1
        
        if self.tick_counter % 4 == 0:
            self.hex_buffer = [f"{random.randint(0, 255):02X}" for _ in range(16)]

        delta = 0.15 if self.step == 1 else 0.015
        self.step_progress += delta
        
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
                if self.is_stopping:
                    self.is_active = False
                    self.timer.stop()
                    self.hide()
                    self.animationFinished.emit()
                    return
        
        if self.step >= 2: 
            self.rotation_angle += 2.0  # Speed up for smaller size
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.bg_color != Qt.GlobalColor.transparent:
            painter.fillRect(self.rect(), self.bg_color)
        
        cx, cy = self.width() / 2, self.height() / 2
        painter.translate(cx, cy)
        
        # Base size scaled down for ~56px diameter overall
        # Largest ring is s*1.90, so base_s * 1.90 = ~28 (radius) -> base_s = 14
        base_s = self.base_s
        
        if self.step >= 0:
            alpha = 0 if (self.step == 1 and self.blink_count % 2 != 0) else 1
            painter.setOpacity(alpha)
            
            raw_t = min(self.step_progress, 1.0) if self.step == 0 else 1.0
            scale = self.mechanical_ease_out(raw_t)
            s = base_s * scale
            
            painter.setPen(QPen(self.primary_color, 1))
            
            painter.drawEllipse(QPointF(0,0), s*1.25, s*1.25)
            painter.drawEllipse(QPointF(0,0), s*1.55, s*1.55)
            painter.drawEllipse(QPointF(0,0), s*1.65, s*1.65)
            painter.drawEllipse(QPointF(0,0), s*1.90, s*1.90)
            
            painter.save()
            painter.rotate(self.rotation_angle * 0.5)
            font_s = int(max(base_s * 0.15, 4))
            painter.setFont(QFont(self.font_family, font_s))
            box = base_s * 0.4
            for i in range(24):
                a = i * 15
                x, y = (s*1.40) * math.cos(math.radians(a)), (s*1.40) * math.sin(math.radians(a))
                painter.save()
                painter.translate(x, y)
                painter.rotate(a + 90)
                char = self.glyphs[i % len(self.glyphs)] if raw_t == 1.0 else random.choice(self.glyphs)
                painter.drawText(QRectF(-box/2, -box/2, box, box), int(Qt.AlignmentFlag.AlignCenter), char)
                painter.restore()
            painter.restore()

            painter.save()
            painter.rotate(-self.rotation_angle * 0.6)
            font_hex_s = int(max(base_s * 0.1, 4))
            painter.setFont(QFont("Consolas", font_hex_s, QFont.Weight.Bold))
            box_hex = base_s * 0.35
            for i in range(16):
                a = i * 22.5
                x, y = (s*1.775) * math.cos(math.radians(a)), (s*1.775) * math.sin(math.radians(a))
                painter.save()
                painter.translate(x, y)
                painter.rotate(a + 90)
                hex_val = self.hex_buffer[i] if raw_t == 1.0 else f"{random.randint(0, 255):02X}"
                painter.drawText(QRectF(-box_hex/2, -box_hex/2, box_hex, box_hex), int(Qt.AlignmentFlag.AlignCenter), hex_val)
                painter.restore()
            painter.restore()
            
            painter.setOpacity(1.0)

        if self.step >= 2:
            raw_t = min(self.step_progress, 1.0) if self.step == 2 else 1.0
            scale = self.mechanical_ease_out(raw_t)
            painter.save()
            painter.rotate(self.rotation_angle * 0.8)
            self.draw_polygon(painter, 10, base_s * scale)
            painter.restore()

        if self.step >= 3:
            raw_t = min(self.step_progress, 1.0) if self.step == 3 else 1.0
            scale = self.mechanical_ease_out(raw_t)
            painter.save()
            painter.rotate(-self.rotation_angle * 0.8)
            self.draw_hexagram(painter, base_s * scale)
            painter.restore()

        if self.step >= 4:
            painter.save()
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
                
                rad = base_s * 0.15 * circ_scale
                painter.setPen(QPen(self.primary_color, 1))
                painter.drawEllipse(QPointF(px, py), rad, rad)
                
                if self.step >= 5:
                    sq = base_s * 0.15 * quad_scale
                    painter.save()
                    painter.translate(px, py)
                    painter.rotate(self.rotation_angle * 2) 
                    painter.setBrush(QBrush(self.primary_color))
                    painter.drawRect(int(-sq), int(-sq), int(sq*2), int(sq*2))
                    
                    painter.setPen(QColor(0, 0, 0))
                    painter.setFont(QFont("Segoe UI Symbol", int(max(sq*2, 4))))
                    symb = self.arcane_symbols[i % 6] if raw_t_quad == 1.0 else random.choice(self.arcane_symbols)
                    painter.drawText(QRectF(-sq, -sq, sq*2, sq*2), int(Qt.AlignmentFlag.AlignCenter), symb)
                    painter.restore()

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
