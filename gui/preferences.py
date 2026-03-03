import sys
import json
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QSlider, QCheckBox, QPushButton, 
                             QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt

class RavenPreferencesWindow(QMainWindow):
    """
    Frontend Gráfico (GUI) para la configuración del Tiling Manager.
    Actúa independientemente del demonio, comunicándose a través del sistema de archivos
    y comandos de Systemd.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuración de Raven")
        self.setFixedSize(400, 250)
        
        # Resolvemos la ruta a tu archivo JSON exacto
        self.config_path = Path.home() / ".config" / "raven" / "raven.json"
        self.config_data = {"default_gaps": 8, "tiling_enabled_on_startup": True}
        
        self.load_config()
        self.init_ui()

    def load_config(self):
        """Lee el estado actual de las configuraciones desde el disco."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config_data.update(json.load(f))
            except Exception as e:
                print(f"[GUI] Error al leer configuración: {e}")

    def save_config(self):
        """Escribe las mutaciones del usuario de vuelta al disco."""
        try:
            # Aseguramos que la carpeta exista por si el usuario borró todo
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error Fatal", f"No se pudo guardar: {e}")

    def init_ui(self):
        """Ensambla los widgets de Qt en la pantalla."""
        # Widget y Layout Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- SECCIÓN: COMPORTAMIENTO ---
        group_behavior = QGroupBox("Comportamiento del Mosaico")
        layout_behavior = QVBoxLayout()
        
        self.chk_tiling = QCheckBox("Activar Tiling al iniciar el sistema")
        self.chk_tiling.setChecked(self.config_data.get("tiling_enabled_on_startup", True))
        
        layout_behavior.addWidget(self.chk_tiling)
        group_behavior.setLayout(layout_behavior)
        main_layout.addWidget(group_behavior)

        # --- SECCIÓN: APARIENCIA (GAPS) ---
        group_appearance = QGroupBox("Apariencia (Márgenes / Gaps)")
        layout_appearance = QVBoxLayout()
        
        # Etiqueta dinámica para ver los píxeles
        self.lbl_gaps = QLabel(f"Tamaño del margen: {self.config_data.get('default_gaps', 8)} px")
        
        # Slider interactivo
        self.slider_gaps = QSlider(Qt.Orientation.Horizontal)
        self.slider_gaps.setMinimum(0)
        self.slider_gaps.setMaximum(50)
        self.slider_gaps.setValue(self.config_data.get("default_gaps", 8))
        self.slider_gaps.valueChanged.connect(self.update_gap_label)
        
        layout_appearance.addWidget(self.lbl_gaps)
        layout_appearance.addWidget(self.slider_gaps)
        group_appearance.setLayout(layout_appearance)
        main_layout.addWidget(group_appearance)

        main_layout.addStretch() # Empuja los botones hacia abajo

        # --- SECCIÓN: BOTONES DE ACCIÓN ---
        layout_buttons = QHBoxLayout()
        
        btn_apply = QPushButton("Aplicar y Reiniciar Demonio")
        btn_apply.clicked.connect(self.apply_changes)
        
        layout_buttons.addStretch()
        layout_buttons.addWidget(btn_apply)
        main_layout.addLayout(layout_buttons)

    def update_gap_label(self, value):
        """Callback interactivo para el Slider."""
        self.lbl_gaps.setText(f"Tamaño del margen: {value} px")

    def apply_changes(self):
        """Flujo de actualización: 1. Extraer datos -> 2. Guardar JSON -> 3. Ordenar a Systemd."""
        # Extraemos valores de la UI
        self.config_data["default_gaps"] = self.slider_gaps.value()
        self.config_data["tiling_enabled_on_startup"] = self.chk_tiling.isChecked()
        
        # Persistencia
        self.save_config()

        # Interacción con el Sistema Operativo (El pilar de Arch Linux)
        try:
            # Mandamos un reinicio grácil al demonio para que lea el nuevo JSON
            subprocess.run(["systemctl", "--user", "restart", "raven.service"], check=True)
            QMessageBox.information(self, "Configuración Aplicada", "Las nuevas preferencias están en efecto y Raven ha sido reiniciado.")
        except subprocess.CalledProcessError:
            QMessageBox.critical(self, "Error de Sistema", "No se pudo reiniciar el servicio raven.service de Systemd.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RavenPreferencesWindow()
    window.show()
    sys.exit(app.exec())