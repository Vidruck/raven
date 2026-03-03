from abc import ABC, abstractmethod
from typing import List, Dict
from core.models import Rect, WindowNode, Workspace

class DisplayServerPort(ABC):
    """
    Contrato abstracto. Define las operaciones que el núcleo de Raven 
    necesita ejecutar sobre el Gestor de Ventanas del sistema.
    """

    @abstractmethod
    async def get_workspaces(self) -> Dict[str, Workspace]:
        """Obtiene el diccionario de todos los monitores/escritorios activos."""
        pass

    @abstractmethod
    async def get_all_windows(self) -> List[WindowNode]:
        """Obtiene la lista de todas las ventanas actualmente manejadas por el compositor."""
        pass

    @abstractmethod
    async def set_window_geometry(self, window_id: str, rect: Rect):
        """Envía la orden al compositor para mover/redimensionar una ventana específica."""
        pass

    @abstractmethod
    async def set_active_window(self, window_id: str):
        pass