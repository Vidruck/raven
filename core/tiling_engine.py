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
    # --- NUEVO MÉTODO PRINCIPAL ---
    def calculate_all_workspaces(self, windows: List[WindowNode], workspaces: Dict[str, Workspace]) -> Dict[str, Rect]:
        """
        Calcula la geometría de todas las ventanas en todos los monitores simultáneamente.
        """
        if not self.is_tiling_enabled or not windows or not workspaces:
            return {}

        # 1. Agrupamos las ventanas por Workspace (Monitor/Escritorio)
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
        Algoritmo de Partición Espacial: Master-Stack Layout.
        Escalable a N ventanas sin superposición (0(N)) de complejidad).
        """
        layout_map = {}
        # Filtramos las ventanas inválidas (flotantes o minimizadas)
        active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
        count = len(active_windows)
        
        if count == 0:
            return layout_map
        
        g = self.config.default_gaps

        #Caso base: una sola ventana abarca todo el lienzo
        if count == 1:
            layout_map[active_windows[0].window_id] = self.apply_gaps(screen_rect, g)
            return layout_map
        #--- Area Maestra (izquierda) ---
        master_win = active_windows[0]
        #Usamos divisiones enteras para no entregar flotantes a Wayland
        master_width = screen_rect.width // 2

        rect_master = Rect(screen_rect.x, screen_rect.y, master_width, screen_rect.height)
        layout_map[master_win.window_id] = self.apply_gaps(rect_master, g)

        # --- Pila / stack (derecha) ---
        stack_windows = active_windows[1:]
        stack_count = len(stack_windows)

        # El ancho de la pila absorbe el resto exacto del ancho total
        stack_width = screen_rect.width - master_width
        #Altura teórica de cada celda
        base_stack_height = screen_rect.height // stack_count

        for i, win in enumerate(stack_windows):
            current_y = screen_rect.y + (i * base_stack_height)

            """
            Compensación de la Pérdida de Pixeles (Pixel Loss Compensation)

            Se implementa porque inevitablemente habra casos donde las operaciones generan decimales
            al no compensarse, aparecen huecos negros. El compensamiento se realizará  haciendo que
            la ultima  ventana de la pila absorba los sobrantes. 
            
            """
            if i == stack_count -1:
                current_height = screen_rect.height - (i * base_stack_height)
            else:
                current_height = base_stack_height

            rect_stack = Rect(
                x=screen_rect.x + master_width,
                y=current_y,
                width=stack_width,
                height=current_height
            )
            layout_map[win.window_id] = self.apply_gaps(rect_stack, g)

        return layout_map
