"""
Motor de Mosaico (Tiling Engine) de Raven.
Implementa el Patrón Fachada delegando el 100% de la carga de topología a Rust.
"""

from typing import List, Dict
from core.models import Rect, WindowNode, Workspace
from core.config import RavenConfig

try:
    import raven_core_rs as rust_engine
    RUST_ENGINE_AVAILABLE = True
    print("[CORE] Motor de Rust (raven_core_rs) cargado. Topología Global Nativa Activada.")
except ImportError:
    RUST_ENGINE_AVAILABLE = False
    print("[WARNING] Motor de Rust no encontrado. El sistema requiere Rust en la v1.5.")

class TilingEngine:
    """
    Motor de Mosaico (Tiling Engine) principal del sistema.
    
    Actúa como una Fachada (Facade) que recibe las solicitudes de organización
    de ventanas desde Python y delega el 100% del cálculo topológico al motor
    nativo en Rust (`raven_core_rs`) para garantizar el máximo rendimiento.
    """
    def __init__(self, config: RavenConfig):
        self.config = config
        self.is_tiling_enabled = config.tiling_enabled_on_startup

    def toggle_tiling(self) -> bool:
        """Alterna el estado del tiling (activado/desactivado)."""
        self.is_tiling_enabled = not self.is_tiling_enabled
        return self.is_tiling_enabled

    def calculate_all_workspaces(self, windows: List[WindowNode], workspaces: Dict[str, Workspace]) -> Dict[str, Rect]:
        """
        Calcula la disposición de todas las ventanas en todos los escritorios virtuales activos.

        Delega el procesamiento matemático completamente a Rust (`calculate_global_topology`),
        traduciendo las estructuras de datos de Python a Rust y viceversa.

        Args:
            windows (List[WindowNode]): Lista de objetos con el estado actual de las ventanas.
            workspaces (Dict[str, Workspace]): Diccionario de escritorios activos indexados por su ID.

        Returns:
            Dict[str, Rect]: Mapa que asocia cada ID de ventana con su nueva geometría calculada (Rect).
        """
        if not self.is_tiling_enabled or not windows or not workspaces or not RUST_ENGINE_AVAILABLE:
            return {}

        rust_windows = [
            rust_engine.WindowNode(
                window_id=w.window_id,
                workspace_id=w.workspace_id,
                is_floating=w.is_floating,
                is_minimized=w.is_minimized,
                is_pip=w.is_pip
            ) for w in windows
        ]

        rust_workspaces = {
            ws_id: rust_engine.Rect(x=ws.rect.x, y=ws.rect.y, width=ws.rect.width, height=ws.rect.height)
            for ws_id, ws in workspaces.items()
        }

        rust_layout_map = rust_engine.calculate_global_topology(
            rust_windows,
            rust_workspaces,
            self.config.nmaster,
            self.config.master_ratio,
            self.config.default_gaps,
            self.config.pip_position
        )

        return {
            w_id: Rect(x=r.x, y=r.y, width=r.width, height=r.height) 
            for w_id, r in rust_layout_map.items()
        }