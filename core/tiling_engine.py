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

# --- EL MOTOR ORIGINAL (Renombrado y protegido) ---
    def _calculate_single_workspace(self, windows: List[WindowNode], screen_rect: Rect) -> Dict[str, Rect]:
        layout_map = {}
        active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
        count = len(active_windows)
        g = self.config.default_gaps

        if count == 1:
            layout_map[windows[0].window_id] = self.apply_gaps(screen_rect, g)

        elif count == 2:
            half_width = screen_rect.width // 2
            
            rect_left = Rect(screen_rect.x, screen_rect.y, half_width, screen_rect.height)
            layout_map[windows[0].window_id] = self.apply_gaps(rect_left, g)
            
            rect_right = Rect(screen_rect.x + half_width, screen_rect.y, half_width, screen_rect.height)
            layout_map[windows[1].window_id] = self.apply_gaps(rect_right, g)

        elif count == 3:
            half_width = screen_rect.width // 2
            half_height = screen_rect.height // 2
            
            rect_master = Rect(screen_rect.x, screen_rect.y, half_width, screen_rect.height)
            layout_map[windows[0].window_id] = self.apply_gaps(rect_master, g)
            
            rect_top_right = Rect(screen_rect.x + half_width, screen_rect.y, half_width, half_height)
            layout_map[windows[1].window_id] = self.apply_gaps(rect_top_right, g)
            
            rect_bot_right = Rect(screen_rect.x + half_width, screen_rect.y + half_height, half_width, half_height)
            layout_map[windows[2].window_id] = self.apply_gaps(rect_bot_right, g)

        elif count == 4:
            half_width = screen_rect.width // 2
            half_height = screen_rect.height // 2
            coords = [(0, 0), (half_width, 0), (0, half_height), (half_width, half_height)]
            for i in range(4):
                base_rect = Rect(screen_rect.x + coords[i][0], screen_rect.y + coords[i][1], half_width, half_height)
                layout_map[windows[i].window_id] = self.apply_gaps(base_rect, g)

        else:
            offset = 30 
            cascade_w = int(screen_rect.width * 0.6)
            cascade_h = int(screen_rect.height * 0.6)
            for i, win in enumerate(windows):
                cx = screen_rect.x + (i * offset)
                cy = screen_rect.y + (i * offset)
                if cx + cascade_w > screen_rect.width: cx = screen_rect.width - cascade_w
                if cy + cascade_h > screen_rect.height: cy = screen_rect.height - cascade_h
                base_rect = Rect(cx, cy, cascade_w, cascade_h)
                layout_map[win.window_id] = self.apply_gaps(base_rect, g)

        return layout_map