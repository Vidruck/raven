from dataclasses import dataclass

@dataclass
class Rect:
    """Representa un Rectángulo (Rect) con las coordenadas matemáticas en Wayland."""
    x: int
    y: int
    width: int
    height: int

@dataclass
class Workspace:
    """
    Representa un Espacio de Trabajo (Workspace) único.
    Generalmente es la combinación de Monitor + Escritorio Virtual (ej. 'HDMI-A-1_Desktop1')
    """
    id: str
    rect: Rect

@dataclass
class WindowNode:
    """Representación lógica de una Ventana (Window Node) administrada."""
    window_id: str
    workspace_id: str
    is_floating: bool = False
    is_minimized: bool = False
    is_pip: bool = False