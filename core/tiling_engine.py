"""
Motor de Mosaico (Tiling Engine) de Raven.
Refactorizado para soportar FFI con motor nativo de Rust.
"""

from typing import List, Dict
from core.models import Rect, WindowNode, Workspace
from core.config import RavenConfig
from collections import defaultdict

try:
    import raven_core_rs as rust_engine
    RUST_ENGINE_AVAILABLE = True
    print("[CORE] Motor de Rust (raven_core_rs) cargado correctamente. Modo Ultra-Performance activado.")
except ImportError:
    RUST_ENGINE_AVAILABLE = False
    print("[WARNING] Motor de Rust no encontrado. Revirtiendo al cálculo en Python.")

class TilingEngine:
    def __init__(self, config: RavenConfig):
        self.config = config
        self.is_tiling_enabled = config.tiling_enabled_on_startup

    def toggle_tiling(self) -> bool:
        self.is_tiling_enabled = not self.is_tiling_enabled
        return self.is_tiling_enabled

    def apply_gaps(self, rect: Rect, gap: int) -> Rect:
        return Rect(
            x=rect.x + gap,
            y=rect.y + gap,
            width=max(1, rect.width - (2 * gap)),
            height=max(1, rect.height - (2 * gap))
        )

    def calculate_all_workspaces(self, windows: List[WindowNode], workspaces: Dict[str, Workspace]) -> Dict[str, Rect]:
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
            pip_w = int(screen.width * 0.22)
            pip_h = int(pip_w * 0.56)
            pip_gap = self.config.default_gaps + 10
            for win in pips:
                pos = self.config.pip_position
                x, y = screen.x + pip_gap, screen.y + pip_gap
                if pos == "top-right":
                    x = screen.x + screen.width - pip_w - pip_gap
                elif pos == "bottom-left":
                    y = screen.y + screen.height - pip_h - pip_gap
                elif pos == "bottom-right":
                    x = screen.x + screen.width - pip_w - pip_gap
                    y = screen.y + screen.height - pip_h - pip_gap

                global_layout_map[win.window_id] = Rect(x, y, pip_w, pip_h)

        return global_layout_map
    def _calculate_single_workspace(self, windows: List[WindowNode], screen_rect: Rect) -> Dict[str, Rect]:
        """Orquesta la ejecución matemática, delegando a Rust si está disponible."""
        
        if RUST_ENGINE_AVAILABLE:
            rust_windows = [
                rust_engine.WindowNode(
                    window_id=w.window_id,
                    workspace_id=w.workspace_id,
                    is_floating=w.is_floating,
                    is_minimized=w.is_minimized,
                    is_pip=w.is_pip
                ) for w in windows
            ]

            rust_screen = rust_engine.Rect(
                x=screen_rect.x, y=screen_rect.y, 
                width=screen_rect.width, height=screen_rect.height
            )

            rust_layout_map = rust_engine.calculate_layout(
                rust_windows,
                rust_screen,
                self.config.nmaster,
                self.config.master_ratio,
                self.config.default_gaps
            )
            return {
                w_id: Rect(x=r.x, y=r.y, width=r.width, height=r.height) 
                for w_id, r in rust_layout_map.items()
            }
        
        #FALLBACK

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
                current_height =  usable_rect.height - (i * base_stack_height) if i == stack_count - 1 else base_stack_height

                rect_stack = Rect(
                    x=usable_rect.x + master_area_width,
                    y=current_y,
                    width=stack_area_width,
                    height=current_height
                )
                layout_map[win.window_id] = self.apply_gaps(rect_stack, half_g)

        return layout_map