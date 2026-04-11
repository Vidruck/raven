"""
Motor de Mosaico (Tiling Engine) de Raven.

Implementa la lógica de dominio puro para calcular la geometría de las ventanas 
basándose en un algoritmo de disposición dinámica de Maestro-Apilado (Master-Stack). 
Maneja configuraciones de múltiples monitores e invariantes geométricas (ej. Compensación de pérdida de píxeles).
"""

from typing import List, Dict
from core.models import Rect, WindowNode, Workspace
from core.config import RavenConfig
from collections import defaultdict

class TilingEngine:
    """
    Clase de orquestación principal para cálculos geométricos.
    Mantiene el estado de la disposición (layout) desacoplado de la infraestructura del sistema operativo.
    """
    def __init__(self, config: RavenConfig):
        """
        Inicializa el motor con las preferencias definidas por el usuario.
        
        Args:
            config (RavenConfig): El modelo de configuración persistente.
        """
        self.config = config
        self.is_tiling_enabled = config.tiling_enabled_on_startup

    def toggle_tiling(self) -> bool:
        """Alterna el estado global del mosaico (tiling)."""
        self.is_tiling_enabled = not self.is_tiling_enabled
        return self.is_tiling_enabled

    def apply_gaps(self, rect: Rect, gap: int) -> Rect:
        """
        Aplica márgenes estéticos reduciendo el área del rectángulo disponible.
        
        Args:
            rect (Rect): La geometría calculada originalmente.
            gap (int): Relleno de píxeles (padding) a aplicar en todos los lados.
            
        Returns:
            Rect: La geometría ajustada.
        """
        return Rect(
            x=rect.x + gap,
            y=rect.y + gap,
            width=max(1, rect.width - (2 * gap)),
            height=max(1, rect.height - (2 * gap))
        )

    def calculate_all_workspaces(self, windows: List[WindowNode], workspaces: Dict[str, Workspace]) -> Dict[str, Rect]:
        """
        Mapea todas las ventanas administrables en sus respectivas salidas (espacios de trabajo/workspaces).
        
        Args:
            windows (List[WindowNode]): Lista plana de estados atómicos de las ventanas.
            workspaces (Dict[str, Workspace]): Mapa de salidas activas y sus áreas delimitadoras (bounding boxes).
            
        Returns:
            Dict[str, Rect]: Mapa global de IDs de ventana hacia sus objetivos geométricos calculados.
        """
        if not self.is_tiling_enabled or not windows or not workspaces:
            return {}

        windows_by_workspace = defaultdict(list)
        for win in windows:
            if not win.is_floating or win.is_pip:
                windows_by_workspace[win.workspace_id].append(win)
                
        global_layout_map = {}

        for ws_id, workspace_windows in windows_by_workspace.items():
            if ws_id not in workspaces:
                continue 
            screen = workspaces[ws_id].rect
            ws_layout = self._calculate_single_workspace(workspace_windows, screen)
            global_layout_map.update(ws_layout)

            pips = [w for w in workspace_windows if w.is_pip and not w.is_minimized]
            pip_w = int (screen.width * 0.22)
            pip_h = int (pip_w * 0.56)
            gap = self.config.default_gaps

            for win in pips:
                pos = self.config.pip_position
                x , y = screen.x + gap, screen.y + gap
                if pos == "top-right":
                    x = screen.x + screen.width - pip_w - gap
                elif pos == "bottom-left":
                    y = screen.y + screen.height - pip_h - gap
                elif pos == "bottom-right":
                    x = screen.x + screen.width - pip_w - gap
                    y = screen.y + screen.height - pip_h - gap

                global_layout_map[win.window_id] = Rect(x, y, pip_w, pip_h)

        return global_layout_map

    def _calculate_single_workspace(self, windows: List[WindowNode], screen_rect: Rect) -> Dict[str, Rect]:
        """
        Realiza el algoritmo de partición Maestro-Apilado (Master-Stack) para un área de espacio de trabajo única.
        Complejidad Temporal: O(N) donde N es el número de ventanas activas.
        
        Args:
            windows (List[WindowNode]): Ventanas asignadas a este espacio de trabajo específico.
            screen_rect (Rect): El área delimitadora utilizable del monitor físico.
            
        Returns:
            Dict[str, Rect]: Mapa local de IDs de ventana hacia las coordenadas calculadas.
        """
        layout_map = {}
        active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
        count = len(active_windows)

        if count == 0:
            return layout_map

        g = self.config.default_gaps
        half_g = g // 2

        usable_rect = Rect(
            x=screen_rect.x + half_g,
            y=screen_rect.y + half_g,
            width=screen_rect.width - g,
            height=screen_rect.height - g
        )
        
        if count == 1:
            layout_map[active_windows[0].window_id] = self.apply_gaps(screen_rect, g)
            return layout_map

        actual_nmaster = min(self.config.nmaster, count)
        ratio = self.config.master_ratio
        has_stack = count > actual_nmaster

        master_area_width = int(screen_rect.width * ratio) if has_stack else screen_rect.width
        stack_area_width = usable_rect.width - master_area_width

        master_windows = active_windows[:actual_nmaster]
        base_master_height = usable_rect.height // actual_nmaster

        for i, win in enumerate(master_windows):
            current_y = usable_rect.y + (i * base_master_height)
            current_height = usable_rect.height - (i * base_master_height) if i == actual_nmaster - 1 else base_master_height
            
            rect_master = Rect(usable_rect.x, current_y, master_area_width, current_height)
            layout_map[win.window_id] = self.apply_gaps(rect_master, half_g)

        if has_stack:
            stack_windows = active_windows[actual_nmaster:]
            stack_count = len(stack_windows)
            base_stack_height = usable_rect.height // stack_count

            for i, win in enumerate(stack_windows):
                current_y = usable_rect.y + (i * base_stack_height)
                
                if i == stack_count - 1:
                    current_height =  usable_rect.height - (i * base_stack_height)
                else:
                    current_height = base_stack_height

                rect_stack = Rect(
                    x=usable_rect.x + master_area_width,
                    y=current_y,
                    width=stack_area_width,
                    height=current_height
                )
                layout_map[win.window_id] = self.apply_gaps(rect_stack, half_g)

        return layout_map