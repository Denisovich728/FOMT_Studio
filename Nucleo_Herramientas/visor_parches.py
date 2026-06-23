from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QMessageBox, QGroupBox, QHBoxLayout)
from PyQt6.QtCore import Qt

class VisorParches(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Título y descripción
        lbl_titulo = QLabel("💉 Parches de la Comunidad")
        lbl_titulo.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl_titulo)
        
        lbl_desc = QLabel(
            "Estos parches aplican modificaciones directamente a la ROM en memoria.\n"
            "Utilizan el Gestor de Memoria para repuntear el código automáticamente\n"
            "hacia espacios vacíos seguros (FF)."
        )
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)
        
        # Grupo: Escaleras
        group_escaleras = QGroupBox("Mina: Escaleras Anti-Softlock")
        l_escaleras = QVBoxLayout()
        lbl_esc_desc = QLabel("Corrige la generación de escaleras para que nunca aparezcan de forma adyacente y te bloqueen el paso.")
        lbl_esc_desc.setWordWrap(True)
        btn_escaleras = QPushButton("Instalar Parche de Escaleras")
        btn_escaleras.clicked.connect(self._aplicar_escaleras)
        l_escaleras.addWidget(lbl_esc_desc)
        l_escaleras.addWidget(btn_escaleras)
        group_escaleras.setLayout(l_escaleras)
        layout.addWidget(group_escaleras)
        
        # Grupo: Cultivos
        group_cultivos = QGroupBox("Granja: Cultivos Traspasables")
        l_cultivos = QVBoxLayout()
        lbl_cul_desc = QLabel("Permite caminar a través de los cultivos plantados, similar a juegos modernos.")
        lbl_cul_desc.setWordWrap(True)
        btn_cultivos = QPushButton("Instalar Parche de Cultivos")
        btn_cultivos.clicked.connect(self._aplicar_cultivos)
        l_cultivos.addWidget(lbl_cul_desc)
        l_cultivos.addWidget(btn_cultivos)
        group_cultivos.setLayout(l_cultivos)
        layout.addWidget(group_cultivos)
        
        # Grupo: TP Stone
        group_tp = QGroupBox("Ítems: Teleport Stone (Año 1)")
        l_tp = QVBoxLayout()
        lbl_tp_desc = QLabel("Elimina la restricción que impide conseguir la Piedra de Teletransporte antes del Año 3.")
        lbl_tp_desc.setWordWrap(True)
        btn_tp = QPushButton("Instalar Parche TP Stone")
        btn_tp.clicked.connect(self._aplicar_tp_stone)
        l_tp.addWidget(lbl_tp_desc)
        l_tp.addWidget(btn_tp)
        group_tp.setLayout(l_tp)
        layout.addWidget(group_tp)
        
        layout.addStretch()

    def _aplicar_escaleras(self):
        from Consola_de_Comando.parches_comunidad import aplicar_parche_escaleras
        success, msg = aplicar_parche_escaleras(self.project)
        if success:
            QMessageBox.information(self, "Éxito", msg)
        else:
            QMessageBox.warning(self, "Aviso", msg)

    def _aplicar_cultivos(self):
        from Consola_de_Comando.parches_comunidad import aplicar_parche_cultivos
        success, msg = aplicar_parche_cultivos(self.project)
        if success:
            QMessageBox.information(self, "Éxito", msg)
        else:
            QMessageBox.warning(self, "Aviso", msg)

    def _aplicar_tp_stone(self):
        from Consola_de_Comando.parches_comunidad import aplicar_parche_tp_stone
        success, msg = aplicar_parche_tp_stone(self.project)
        if success:
            QMessageBox.information(self, "Éxito", msg)
        else:
            QMessageBox.warning(self, "Aviso", msg)
