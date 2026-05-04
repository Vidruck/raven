"""
Adaptador de Infraestructura DBus para KWin (Zero-Copy Edition).

Proporciona la implementación para los puertos DisplayServerPort y EventListenerPort
utilizando el mecanismo de comunicación entre procesos (IPC) de DBus. 
En esta arquitectura, el adaptador actúa como un conducto ciego (Blind Conduit),
almacenando únicamente el JSON crudo y delegando la interpretación estructural a Rust.
"""

import json
import asyncio
from typing import Callable, Optional, Any, Dict, List, Coroutine

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import BusType, NameFlag
from dbus_next.service import ServiceInterface, method

from core.models import Rect, WindowNode, Workspace 
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort

class RavenEventsDBusService(ServiceInterface):
    """
    Servicio DBus de baja latencia que expone la interfaz de comunicación para el script de KWin.
    """
    def __init__(self, adapter: 'KWinDBusAdapter'):
        super().__init__('org.kde.raven.Events')
        self.adapter = adapter

    @method(name="syncState")
    def syncState(self, payload_json: 's'): # type: ignore
        """Recibe el estado masivo del compositor en formato JSON atómico y lo delega al adaptador para su procesamiento."""
        self.adapter._handle_sync_state(payload_json)

    @method(name="getPendingCommands")
    async def getPendingCommands(self) -> 's': # type: ignore
        """Recupera la cola de comandos pendientes (acciones de ventanas) para enviarlos de regreso a KWin."""
        return await self.adapter.get_pending_commands_json()
    
    @method(name="windowActivated")
    def windowActivated(self, window_id: 's'): # type: ignore
        """Notifica al adaptador qué ventana tiene actualmente el foco."""
        self.adapter.active_window_id = window_id

    @method(name="toggleTiling")
    def toggleTiling(self):
        """Atajo D-Bus para habilitar/deshabilitar temporalmente el motor de disposición (tiling)."""
        self.adapter._handle_shortcut("toggle_tiling", None)

    @method(name="incrementGaps")
    def incrementGaps(self, amount: 'i'): # type: ignore
        self.adapter._handle_shortcut("increment_gaps", amount)

    @method(name="incrementMaster")
    def incrementMaster(self):
        self.adapter._handle_shortcut("increment_master", None)

    @method(name="decrementMaster")
    def decrementMaster(self):
        self.adapter._handle_shortcut("decrement_master", None)

    @method(name="increaseRatio")
    def increaseRatio(self):
        self.adapter._handle_shortcut("increase_ratio", None)

    @method(name="decreaseRatio")
    def decreaseRatio(self):
        self.adapter._handle_shortcut("decrease_ratio", None)

    @method(name="focusNext")
    def focusNext(self):
        self.adapter._handle_shortcut("focus_next", None)

    @method(name="focusPrev")
    def focusPrev(self):
        self.adapter._handle_shortcut("focus_prev", None)
    
    @method(name="getTilingState")
    def getTilingState(self) -> 'b': # type: ignore
        """Consulta si el motor de mosaico está actualmente activo, útil para interfaces como el plasmoide."""
        if self.adapter.engine is not None:
            return self.adapter.engine.is_tiling_enabled
        return True


class KWinDBusAdapter(DisplayServerPort, EventListenerPort):
    """
    Implementación concreta de los puertos de comunicación (Hexagonal Ports).
    Optimizada para el patrón Zero-Copy: No deserializa datos en Python.
    """
    def __init__(self):
        self.bus = None
        self._on_state_change_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None
        self._on_shortcut_pressed_cb: Optional[Callable[[str, Any], Coroutine[Any, Any, None]]] = None
        
        self.command_queue: Optional[asyncio.Queue] = None 
        self.engine = None 
        self.active_window_id: Optional[str] = None
        
        self.last_payload_json: str = "{}"
        
        self._debounce_task: Optional[asyncio.Task] = None
        self._background_task: set = set()

    def _handle_sync_state(self, payload_json: str) -> None:
        """Almacena el JSON atómico en memoria RAM y agenda un recálculo asíncrono."""
        self.last_payload_json = payload_json
        
        if self._debounce_task and not self._debounce_task.done():
            return
        self._debounce_task = asyncio.create_task(self._debounced_state_change())

    async def _debounced_state_change(self) -> None:
        """Mecanismo de Anti-Rebote (Debounce) a 10ms."""
        try:
            await asyncio.sleep(0.010)
            if self._on_state_change_cb:
                await self._on_state_change_cb()
        except asyncio.CancelledError:
            pass

    def _handle_shortcut(self, action: str, payload: Any) -> None:
        """Enruta los atajos de teclado hacia el orquestador principal."""
        if self._on_shortcut_pressed_cb:
            task = asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))
            self._background_task.add(task)
            task.add_done_callback(self._background_task.discard)

    async def connect(self) -> None:
        """Inicializa la conexión IPC y enciende el bus de eventos."""
        if self.command_queue is None:
            self.command_queue = asyncio.Queue()

        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.REPLACE_EXISTING)
        assert self.command_queue is not None
        await self.command_queue.put({"action": "request_sync"})

    async def get_pending_commands_json(self) -> str:
        """Extrae los comandos de la cola de Python y los serializa para KWin JS."""
        if self.command_queue is None:
            return "[]"
        commands = []
        try:
            primer_comando = await asyncio.wait_for(self.command_queue.get(), timeout=5.0)
            commands.append(primer_comando)
            while not self.command_queue.empty():
                commands.append(self.command_queue.get_nowait())
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            return "[]"
        except Exception as e:
            print(f"[ERROR CRITICO] Fallo en la cola de comandos: {e}")
        
        return json.dumps(commands)


    def on_window_created(self, callback: Callable[..., Coroutine[Any, Any, None]]):
        """Registra el callback de re-cálculo de layout cuando se crea una ventana."""
        self._on_state_change_cb = callback

    def on_window_closed(self, callback: Callable[..., Coroutine[Any, Any, None]]):
        """Registra el callback de re-cálculo de layout cuando se cierra una ventana."""
        self._on_state_change_cb = callback

    def on_shortcut_pressed(self, callback: Callable[[str, Any], Coroutine[Any, Any, None]]):
        """Registra el callback para reaccionar ante atajos de teclado del usuario."""
        self._on_shortcut_pressed_cb = callback
    
    async def get_workspaces(self) -> Dict[str, Workspace]:
        return {}
    
    async def get_all_windows(self) -> List[WindowNode]:
        return []


    async def set_window_geometry(self, window_id: str, rect: Rect):
        """Encola el envío de coordenadas físicas calculadas por Rust hacia KWin."""
        if self.command_queue is not None:
            command = {
                "action": "move", "window_id": window_id,
                "x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height
            }
            await self.command_queue.put(command)

    async def set_active_window(self, window_id: str):
        """Encola el envío de un comando de foco para reactivar una ventana específica en KWin."""
        if self.command_queue is not None:
            command = {"action": "focus", "window_id": window_id}
            await self.command_queue.put(command)