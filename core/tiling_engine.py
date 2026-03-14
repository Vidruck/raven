"""
Core Tiling Engine.

Implements the pure domain logic for calculating window geometries based on 
a dynamic Master-Stack layout algorithm. Handles multi-monitor setups and 
geometric invariants (e.g., Pixel Loss Compensation).
"""

from typing import List, Dict
from core.models import Rect, WindowNode, Workspace
from core.config import RavenConfig
from collections import defaultdict

class TilingEngine:
    """
    Main orchestration class for geometric calculations.
    Maintains layout state decoupled from the OS infrastructure.
    """
    def __init__(self, config: RavenConfig):
        """
        Initializes the engine with user-defined preferences.
        
        Args:
            config (RavenConfig): The persistent configuration model.
        """
        self.config = config
        self.is_tiling_enabled = config.tiling_enabled_on_startup

    def toggle_tiling(self) -> bool:
        """Toggles the global tiling state."""
        self.is_tiling_enabled = not self.is_tiling_enabled
        return self.is_tiling_enabled

    def apply_gaps(self, rect: Rect, gap: int) -> Rect:
        """
        Applies aesthetic margins by shrinking the available rectangle area.
        
        Args:
            rect (Rect): The original computed geometry.
            gap (int): Pixel padding to apply on all sides.
            
        Returns:
            Rect: The adjusted geometry.
        """
        return Rect(
            x=rect.x + gap,
            y=rect.y + gap,
            width=max(1, rect.width - (2 * gap)),
            height=max(1, rect.height - (2 * gap))
        )

    def calculate_all_workspaces(self, windows: List[WindowNode], workspaces: Dict[str, Workspace]) -> Dict[str, Rect]:
        """
        Maps all manageable windows across their respective outputs (workspaces).
        
        Args:
            windows (List[WindowNode]): Flat list of atomic window states.
            workspaces (Dict[str, Workspace]): Map of active outputs and their bounding boxes.
            
        Returns:
            Dict[str, Rect]: Global map of Window IDs to their calculated geometric targets.
        """
        if not self.is_tiling_enabled or not windows or not workspaces:
            return {}

        windows_by_workspace = defaultdict(list)
        for win in windows:
            if not win.is_floating:
                windows_by_workspace[win.workspace_id].append(win)
                
        global_layout_map = {}

        for ws_id, workspace_windows in windows_by_workspace.items():
            if ws_id not in workspaces:
                continue 
            workspace_rect = workspaces[ws_id].rect
            ws_layout = self._calculate_single_workspace(workspace_windows, workspace_rect)
            global_layout_map.update(ws_layout)

        return global_layout_map

    def _calculate_single_workspace(self, windows: List[WindowNode], screen_rect: Rect) -> Dict[str, Rect]:
        """
        Performs the Master-Stack partition algorithm for a single workspace area.
        Time Complexity: O(N) where N is the number of active windows.
        
        Args:
            windows (List[WindowNode]): Windows assigned to this specific workspace.
            screen_rect (Rect): The usable bounding box of the physical monitor.
            
        Returns:
            Dict[str, Rect]: Local map of Window IDs to calculated coordinates.
        """
        layout_map = {}
        active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
        count = len(active_windows)

        if count == 0:
            return layout_map

        g = self.config.default_gaps

        if count == 1:
            layout_map[active_windows[0].window_id] = self.apply_gaps(screen_rect, g)
            return layout_map

        actual_nmaster = min(self.config.nmaster, count)
        ratio = self.config.master_ratio
        has_stack = count > actual_nmaster

        master_area_width = int(screen_rect.width * ratio) if has_stack else screen_rect.width
        stack_area_width = screen_rect.width - master_area_width

        # 1. Master Area Rendering (Y-Axis distribution)
        master_windows = active_windows[:actual_nmaster]
        base_master_height = screen_rect.height // actual_nmaster

        for i, win in enumerate(master_windows):
            current_y = screen_rect.y + (i * base_master_height)
            
            # Pixel Loss Compensation: Absorb rounding errors in the last window
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

        # 2. Stack Area Rendering (Y-Axis distribution)
        if has_stack:
            stack_windows = active_windows[actual_nmaster:]
            stack_count = len(stack_windows)
            base_stack_height = screen_rect.height // stack_count

            for i, win in enumerate(stack_windows):
                current_y = screen_rect.y + (i * base_stack_height)
                
                # Pixel Loss Compensation
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