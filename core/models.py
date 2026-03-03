from dataclasses import dataclass

@dataclass
class Rect:
    """Representa las coordenadas matemáticas en Wayland."""
    x: int
    y: int
    width: int
    height: int

@dataclass
class Workspace:
    """
    Representa un espacio de trabajo único.
    Generalmente es la combinación de Monitor + Escritorio Virtual (ej. 'HDMI-A-1_Desktop1')
    """
    id: str
    rect: Rect

@dataclass
class WindowNode:
    """Representación lógica de una ventana administrada."""
    def __init__(self, window_id: str, workspace_id: str, is_floating: bool = False, is_minimized: bool = False):
        self.window_id = window_id
        self.workspace_id = workspace_id 
        self.is_floating = is_floating
        self.is_minimized = is_minimized