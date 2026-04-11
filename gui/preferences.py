import sys
import json
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QSlider, QCheckBox, QPushButton, 
                             QMessageBox, QGroupBox, QSpinBox, QDoubleSpinBox, QFormLayout, QComboBox)
from PyQt6.QtCore import Qt

class RavenPreferencesWindow(QMainWindow):
    """
    Interfaz frontal (Frontend) del Centro de Control para Raven Tiling Emulator.
    Interactúa con la persistencia de datos (JSON) y orquesta 
    el ciclo de vida del proceso en segundo plano (daemon) en Arch Linux vía Systemd.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Dialog)
        
        self.config_path = Path.home() / ".config" / "raven" / "raven.json"
        self.config_data = {
            "default_gaps": 8, 
            "tiling_enabled_on_startup": True,
            "nmaster": 1,
            "master_ratio": 0.5,
            "pip_position": "bottom-right"
        }
        
        self.load_config()
        self.init_ui()
        self.center()

    def center(self):
        """Calcula el centro de la pantalla actual y mueve la ventana ahí."""
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    
    def load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data.update(json.load(f))
            except Exception as e:
                print(f"[GUI] Error al leer configuración: {e}")

    def save_config(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error de I/O Fatal", f"Fallo al escribir en disco: {e}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        group_behavior = QGroupBox("Comportamiento del Motor")
        layout_behavior = QVBoxLayout()
        self.chk_tiling = QCheckBox("Activar Mosaico (Tiling) de forma predeterminada")
        self.chk_tiling.setChecked(self.config_data.get("tiling_enabled_on_startup", True))
        layout_behavior.addWidget(self.chk_tiling)
        group_behavior.setLayout(layout_behavior)
        main_layout.addWidget(group_behavior)


        group_topology = QGroupBox("Algoritmo de Partición Maestro-Apilado (Master-Stack)")
        layout_topology = QFormLayout()
        
        self.spin_nmaster = QSpinBox()
        self.spin_nmaster.setRange(1, 10)
        self.spin_nmaster.setValue(self.config_data.get("nmaster", 1))
        
        self.spin_ratio = QDoubleSpinBox()
        self.spin_ratio.setRange(0.1, 0.9)
        self.spin_ratio.setSingleStep(0.05)
        self.spin_ratio.setValue(self.config_data.get("master_ratio", 0.5))
        
        layout_topology.addRow("Cantidad de ventanas maestras:", self.spin_nmaster)
        layout_topology.addRow("Proporción del área maestra (Ratio):", self.spin_ratio)
        group_topology.setLayout(layout_topology)
        main_layout.addWidget(group_topology)

        group_appearance = QGroupBox("Apariencia y Geometría")
        layout_appearance = QVBoxLayout()
        
        self.lbl_gaps = QLabel(f"Márgenes (Gaps): {self.config_data.get('default_gaps', 8)} px")
        self.slider_gaps = QSlider(Qt.Orientation.Horizontal)
        self.slider_gaps.setMinimum(0)
        self.slider_gaps.setMaximum(50)
        self.slider_gaps.setValue(self.config_data.get("default_gaps", 8))
        self.slider_gaps.valueChanged.connect(self.update_gap_label)
        
        layout_appearance.addWidget(self.lbl_gaps)
        layout_appearance.addWidget(self.slider_gaps)
        group_appearance.setLayout(layout_appearance)
        main_layout.addWidget(group_appearance)

        main_layout.addStretch()

        group_pip = QGroupBox("Configuración de Picture-in-Picture")
        layout_pip = QFormLayout()
        self.combo_pip = QComboBox()
        self.combo_pip.addItems(["top-right", "top-left", "bottom-right", "bottom-left"])
        current_pos = self.config_data.get("pip_position", "bottom-right")
        self.combo_pip.setCurrentText(current_pos)
        layout_pip.addRow("Ubicación en pantalla:", self.combo_pip)
        group_pip.setLayout(layout_pip)
        main_layout.addWidget(group_pip)

        layout_buttons = QHBoxLayout()
        btn_apply = QPushButton("Guardar Topología y Reiniciar Proceso (Daemon)")
        btn_apply.clicked.connect(self.apply_changes)
        
        layout_buttons.addStretch()
        layout_buttons.addWidget(btn_apply)
        main_layout.addLayout(layout_buttons)


    def update_gap_label(self, value):
        self.lbl_gaps.setText(f"Márgenes (Gaps): {value} px")

    def apply_changes(self):


        self.config_data["default_gaps"] = self.slider_gaps.value()
        self.config_data["tiling_enabled_on_startup"] = self.chk_tiling.isChecked()
        self.config_data["nmaster"] = self.spin_nmaster.value()
        self.config_data["master_ratio"] = round(self.spin_ratio.value(), 2)
        self.config_data["pip_position"] = self.combo_pip.currentText()
        self.save_config()
        
        try:
            subprocess.run(["systemctl", "--user", "restart", "raven.service"], check=True)
            QMessageBox.information(self, "Despliegue Exitoso", "La topología ha sido actualizada.\nEl proceso Raven está corriendo con los nuevos parámetros.")
        except subprocess.CalledProcessError:
            QMessageBox.critical(self, "Error de Orquestación", "No se pudo reiniciar el servicio raven.service.\nRevisa los registros (logs) de Systemd.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("RavenConfig") 
    app.setStyle("Fusion")
    window = RavenPreferencesWindow()
    window.show()
    sys.exit(app.exec())