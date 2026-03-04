from typing import List, Dict
from core.models import Rect, WindowNode, Workspace
from core.config import RavenConfig
from collections import defaultdict

class TilingEngine:
    def __init__(self, config: RavenConfig):
        self.config = config
        self.is_tiling_enabled = config.tiling_enabled_on_startup

    def toggle_tiling(self):
        self.is_tiling_enabled = not self.is_tiling_enabled
        return self.is_tiling_enabled

    def apply_gaps(self, rect: Rect, gap: int) -> Rect:
        return Rect(
            x=rect.x + gap,
            y=rect.y + gap,
            width=rect.width - (2 * gap),
            height=rect.height - (2 * gap)
        )
    
    # ---  MÉTODO PRINCIPAL ---

    def calculate_all_workspaces(self, windows: List[WindowNode], workspaces: Dict[str, Workspace]) -> Dict[str, Rect]:
        """
        Calcula la geometría de todas las ventanas en todos los monitores simultáneamente.
        """
        if not self.is_tiling_enabled or not windows or not workspaces:
            return {}

        # 1. Agrupamieno las ventanas por Workspace (Monitor/Escritorio)
        windows_by_workspace = defaultdict(list)
        for win in windows:
            if not win.is_floating:
                windows_by_workspace[win.workspace_id].append(win)

        global_layout_map = {}

        # 2. Calculamos el layout de forma aislada para cada monitor

        for ws_id, workspace_windows in windows_by_workspace.items():
            if ws_id not in workspaces:
                continue # Si no tenemos la geometría del monitor, ignoramos sus ventanas
                
            workspace_rect = workspaces[ws_id].rect
        
            # Ejecutamos la matemática específica para este grupo

            ws_layout = self._calculate_single_workspace(workspace_windows, workspace_rect)
            global_layout_map.update(ws_layout)

        return global_layout_map

# --- EL MOTOR  ---

    def _calculate_single_workspace(self, windows: List[WindowNode], screen_rect: Rect) -> Dict[str, Rect]:
        """
        Algoritmo Dinámico: Master-Stack con Ratio y N-Masters variables.
        Complejidad algorítmica: O(N)
        """
        layout_map = {}
        active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
        count = len(active_windows)

        if count == 0:
            return layout_map

        g = self.config.default_gaps

        # Caso Base Absoluto

        if count == 1:
            layout_map[active_windows[0].window_id] = self.apply_gaps(screen_rect, g)
            return layout_map

        # --- PREPARACIÓN DE CONSTANTES MATEMÁTICAS ---
        # Aseguramos que nmaster no sea mayor que las ventanas actuales

        actual_nmaster = min(self.config.nmaster, count)
        ratio = self.config.master_ratio
        
        # Caso : Tenemos ventanas suficientes para formar una pila a la derecha

        has_stack = count > actual_nmaster

        # --- CÁLCULO DE ÁREAS (EJE X) ---
        # Si hay pila, aplicamos el porcentaje. Si no, el maestro toma toda la pantalla.

        master_area_width = int(screen_rect.width * ratio) if has_stack else screen_rect.width
        stack_area_width = screen_rect.width - master_area_width

        # --- RENDERIZADO DEL ÁREA MAESTRA (EJE Y) ---

        master_windows = active_windows[:actual_nmaster]
        base_master_height = screen_rect.height // actual_nmaster

        for i, win in enumerate(master_windows):
            current_y = screen_rect.y + (i * base_master_height)
            
            # Sellado de pérdida de píxeles (Pixel Loss Compensation)

            if i == actual_nmaster - 1:
                current_height = screen_rect.height - (i * base_master_height)
            else:
                current_height = base_master_height

            rect_master = Rect(
                x=screen_rect.x,
                y=current_y,
                width=master_area_width,
                height=current_height
            )
            layout_map[win.window_id] = self.apply_gaps(rect_master, g)

        # --- RENDERIZADO DE LA PILA (EJE Y) ---

        if has_stack:
            stack_windows = active_windows[actual_nmaster:]
            stack_count = len(stack_windows)
            base_stack_height = screen_rect.height // stack_count

            for i, win in enumerate(stack_windows):
                current_y = screen_rect.y + (i * base_stack_height)
                
                # Sellado de pérdida de píxeles
                
                if i == stack_count - 1:
                    current_height = screen_rect.height - (i * base_stack_height)
                else:
                    current_height = base_stack_height

                rect_stack = Rect(
                    x=screen_rect.x + master_area_width,
                    y=current_y,
                    width=stack_area_width,
                    height=current_height
                )
                layout_map[win.window_id] = self.apply_gaps(rect_stack, g)

        return layout_map