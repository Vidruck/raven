"""
Motor de Mosaico (Tiling Engine) de Raven.
Implementa el Patrón Fachada con Arquitectura Zero-Copy hacia Rust.
"""
from typing import Dict
from raven_core_rs import Rect, WindowNode, Workspace
from raven_core_rs import RavenConfig
import raven_core_rs as rust_engine

class TilingEngine:
    def __init__(self, config: RavenConfig):
        self.config = config
        self.is_tiling_enabled = config.tiling_enabled_on_startup

    def toggle_tiling(self) -> bool:
        self.is_tiling_enabled = not self.is_tiling_enabled
        return self.is_tiling_enabled

    def calculate_from_payload(self, payload_json: str) -> Dict[str, Rect]:
        """Envía la cadena cruda a Rust y recibe la geometría calculada."""
        if not self.is_tiling_enabled or not payload_json:
            return {}

        rust_layout_map = rust_engine.compute_layout_from_json(
            payload_json,
            self.config.nmaster,
            self.config.master_ratio,
            self.config.default_gaps,
            self.config.pip_position
        )

        return {
            w_id: Rect(x=r.x, y=r.y, width=r.width, height=r.height) 
            for w_id, r in rust_layout_map.items()
        }