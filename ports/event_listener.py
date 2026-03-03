from abc import ABC, abstractmethod
from typing import Callable, Awaitable

class EventListenerPort(ABC):
    """
    Contrato abstracto para escuchar eventos del sistema de ventanas o del teclado.
    Implementa el patrón de diseño Observer (Pub/Sub).
    """

    @abstractmethod
    def on_window_created(self, callback: Callable[[str], Awaitable[None]]):
        """Registra un callback que se ejecutará cuando nazca una nueva ventana."""
        pass

    @abstractmethod
    def on_window_closed(self, callback: Callable[[str], Awaitable[None]]):
        """Registra un callback que se ejecutará cuando una ventana sea destruida."""
        pass

    @abstractmethod
    def on_shortcut_pressed(self, shortcut_name: str, callback: Callable[[], Awaitable[None]]):
        """Registra un callback para atajos de teclado (ej. Toggle Tiling, Mover Foco)."""
        pass