import os
import psutil
import platform
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QSlider, QSpinBox, QGroupBox, QFileDialog, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from Consola_de_Comando.i18n import t as _t
from Consola_de_Comando.themes import color, style
from Nucleo_Herramientas.config_manager import ConfigManager

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("set_title"))
        self.setMinimumWidth(500)
        # El dialogo hereda el tema activo; solo los deslizadores necesitan estilo propio.
        style(self, """
            QSlider::groove:horizontal {{
                border: 1px solid {border};
                height: 8px;
                background: {surface_alt};
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {accent};
                border: 1px solid {accent};
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border: 1px solid {accent};
                height: 8px;
                border-radius: 4px;
            }}
        """)
        
        self.config = ConfigManager.load_config()
        
        # Hardware Detection
        self.total_ram_mb = int(psutil.virtual_memory().total / (1024 * 1024))
        
        # Consultar specs precisas a Windows (WMIC)
        self.processor_name = platform.processor()
        self.logical_cores = psutil.cpu_count(logical=True) or 2
        self.physical_cores = psutil.cpu_count(logical=False) or 1
        
        try:
            import subprocess
            output = subprocess.check_output('wmic cpu get Name, NumberOfCores, NumberOfLogicalProcessors /Format:List', shell=True).decode('utf-8')
            for line in output.split('\n'):
                if line.startswith('Name='):
                    self.processor_name = line.split('=')[1].strip()
                elif line.startswith('NumberOfCores='):
                    self.physical_cores = int(line.split('=')[1].strip())
                elif line.startswith('NumberOfLogicalProcessors='):
                    self.logical_cores = int(line.split('=')[1].strip())
        except Exception as e:
            print(f"WMIC fallback: {e}")

        processor_lower = self.processor_name.lower()
        self.is_amd = "amd" in processor_lower or "ryzen" in processor_lower
        self.is_intel = "intel" in processor_lower
        
        # Intel hybrid topology heuristic: P-cores = Logical - Physical
        if self.is_intel and self.logical_cores > self.physical_cores:
            self.p_cores = self.logical_cores - self.physical_cores
            self.e_cores = self.physical_cores - self.p_cores
            if self.p_cores <= 0 or self.e_cores < 0: # Fallback if math goes weird
                self.p_cores = self.physical_cores
                self.e_cores = 0
        else:
            self.p_cores = self.physical_cores
            self.e_cores = 0

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # --- RAM Group ---
        ram_group = QGroupBox(_t("set_ram_group"))
        ram_layout = QVBoxLayout()
        
        ram_info_layout = QHBoxLayout()
        ram_info_layout.addWidget(QLabel(_t("set_ram_total", mb=self.total_ram_mb)))
        ram_layout.addLayout(ram_info_layout)
        
        ram_slider_layout = QHBoxLayout()
        self.ram_slider = QSlider(Qt.Orientation.Horizontal)
        self.ram_slider.setMinimum(512)
        self.ram_slider.setMaximum(self.total_ram_mb)
        self.ram_slider.setSingleStep(256)
        
        self.ram_spin = QSpinBox()
        self.ram_spin.setMinimum(512)
        self.ram_spin.setMaximum(self.total_ram_mb)
        self.ram_spin.setSuffix(" MB")
        self.ram_spin.setFixedWidth(100)
        
        self.ram_slider.valueChanged.connect(self.ram_spin.setValue)
        self.ram_spin.valueChanged.connect(self.ram_slider.setValue)
        
        ram_slider_layout.addWidget(QLabel(_t("set_assign")))
        ram_slider_layout.addWidget(self.ram_slider)
        ram_slider_layout.addWidget(self.ram_spin)
        
        ram_layout.addLayout(ram_slider_layout)
        ram_group.setLayout(ram_layout)
        layout.addWidget(ram_group)
        
        # --- CPU Group ---
        cpu_group = QGroupBox(_t("set_cpu_group"))
        cpu_layout = QVBoxLayout()
        
        if self.is_amd or not self.is_intel:
            # AMD or unknown: just base threads
            cpu_info = QLabel(_t("set_cpu_info", cpu=self.processor_name, threads=self.logical_cores))
            cpu_layout.addWidget(cpu_info)
            
            thread_layout = QHBoxLayout()
            self.thread_slider = QSlider(Qt.Orientation.Horizontal)
            self.thread_slider.setMinimum(1)
            self.thread_slider.setMaximum(self.logical_cores)
            
            self.thread_spin = QSpinBox()
            self.thread_spin.setMinimum(1)
            self.thread_spin.setMaximum(self.logical_cores)
            self.thread_spin.setFixedWidth(60)
            
            self.thread_slider.valueChanged.connect(self.thread_spin.setValue)
            self.thread_spin.valueChanged.connect(self.thread_slider.setValue)
            
            thread_layout.addWidget(QLabel(_t("set_threads")))
            thread_layout.addWidget(self.thread_slider)
            thread_layout.addWidget(self.thread_spin)
            cpu_layout.addLayout(thread_layout)
            
        else:
            # Intel: P-Cores and E-Cores
            cpu_info = QLabel(_t("set_cpu_info_hybrid", cpu=self.processor_name, p=self.p_cores, e=self.e_cores, threads=self.logical_cores))
            cpu_layout.addWidget(cpu_info)
            
            # P-Cores
            p_layout = QHBoxLayout()
            self.p_slider = QSlider(Qt.Orientation.Horizontal)
            self.p_slider.setMinimum(1)
            self.p_slider.setMaximum(self.p_cores)
            
            self.p_spin = QSpinBox()
            self.p_spin.setMinimum(1)
            self.p_spin.setMaximum(self.p_cores)
            self.p_spin.setFixedWidth(60)
            
            self.p_slider.valueChanged.connect(self.p_spin.setValue)
            self.p_spin.valueChanged.connect(self.p_slider.setValue)
            
            p_layout.addWidget(QLabel(_t("set_pcores")))
            p_layout.addWidget(self.p_slider)
            p_layout.addWidget(self.p_spin)
            cpu_layout.addLayout(p_layout)
            
            # E-Cores
            if self.e_cores > 0:
                e_layout = QHBoxLayout()
                self.e_slider = QSlider(Qt.Orientation.Horizontal)
                self.e_slider.setMinimum(0)
                self.e_slider.setMaximum(self.e_cores)
                
                self.e_spin = QSpinBox()
                self.e_spin.setMinimum(0)
                self.e_spin.setMaximum(self.e_cores)
                self.e_spin.setFixedWidth(60)
                
                self.e_slider.valueChanged.connect(self.e_spin.setValue)
                self.e_spin.valueChanged.connect(self.e_slider.setValue)
                
                e_layout.addWidget(QLabel(_t("set_ecores")))
                e_layout.addWidget(self.e_slider)
                e_layout.addWidget(self.e_spin)
                cpu_layout.addLayout(e_layout)
                
        cpu_group.setLayout(cpu_layout)
        layout.addWidget(cpu_group)
        
        # --- Rutas Group ---
        path_group = QGroupBox(_t("set_paths_group"))
        path_layout = QVBoxLayout()
        
        dir_layout = QHBoxLayout()
        self.txt_dir = QLineEdit()
        self.txt_dir.setPlaceholderText(_t("set_dir_placeholder"))
        
        btn_browse = QPushButton(_t("set_browse"))
        btn_browse.clicked.connect(self._browse_dir)
        
        dir_layout.addWidget(self.txt_dir)
        dir_layout.addWidget(btn_browse)
        
        path_layout.addWidget(QLabel(_t("set_dir_label")))
        path_layout.addLayout(dir_layout)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton(_t("btn_cancel"))
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton(_t("set_save"))
        btn_save.setProperty("variant", "primary")
        btn_save.clicked.connect(self._save_settings)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        
        layout.addStretch()
        layout.addLayout(btn_layout)

    def _load_values(self):
        # RAM
        ram_val = self.config.get("max_ram_mb", 2048)
        self.ram_slider.setValue(min(ram_val, self.total_ram_mb))
        
        # CPU
        if self.is_amd or not self.is_intel:
            threads = self.config.get("cpu_threads", self.logical_cores)
            self.thread_slider.setValue(min(threads, self.logical_cores))
        else:
            p_val = self.config.get("cpu_p_cores", self.p_cores)
            self.p_slider.setValue(min(p_val, self.p_cores))
            if self.e_cores > 0:
                e_val = self.config.get("cpu_e_cores", self.e_cores)
                self.e_slider.setValue(min(e_val, self.e_cores))
                
        # DIR
        from Banco_de_Datos.Utilidades.rutas import get_default_workspace_dir
        current_dir = self.config.get("default_project_dir", "") or get_default_workspace_dir()
        self.txt_dir.setText(current_dir)

    def _browse_dir(self):
        from Banco_de_Datos.Utilidades.rutas import get_default_workspace_dir
        initial = self.txt_dir.text() or get_default_workspace_dir()
        directory = QFileDialog.getExistingDirectory(self, _t("set_dlg_dir"), initial)
        if directory:
            self.txt_dir.setText(directory)

    def _save_settings(self):
        self.config["max_ram_mb"] = self.ram_spin.value()
        
        if self.is_amd or not self.is_intel:
            self.config["cpu_threads"] = self.thread_spin.value()
        else:
            self.config["cpu_p_cores"] = self.p_spin.value()
            if self.e_cores > 0:
                self.config["cpu_e_cores"] = self.e_spin.value()
                
        self.config["default_project_dir"] = self.txt_dir.text()
        
        ConfigManager.save_config(self.config)
        QMessageBox.information(self, _t("set_saved_title"), _t("set_saved"))
        self.accept()
