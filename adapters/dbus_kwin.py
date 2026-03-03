import json
import asyncio
from typing import List, Callable, Awaitable, Optional, Any, Dict

from dbus_next.aio import MessageBus
from dbus_next import BusType
from dbus_next.service import ServiceInterface, method
from dbus_next.constants import NameFlag

# CORRECCIÓN 1: Importamos Workspace
from core.models import Rect, WindowNode, Workspace 
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort

class RavenEventsDBusService(ServiceInterface):
    """
    Servicio DBus hospedado en Python. 
    Actúa como un 'webhook' local para que el script JS de KWin le envíe datos.
    """
    def __init__(self, adapter: 'KWinDBusAdapter'):
        super().__init__('org.kde.raven.Events')
        self.adapter = adapter

    @method(name="windowAdded")
    def windowAdded(self, window_id: 's', workspace_id: 's', is_floating: 'b'): # type: ignore
        print(f"[DBUS] Ventana {window_id} en monitor {workspace_id}")
        self.adapter._handle_window_added(window_id, workspace_id, is_floating)
    @method(name="windowRemoved")
    def windowRemoved(self, window_id: 's'): # type: ignore
        print(f"[DBUS SERVER] Señal capturada de Wayland: Ventana cerrada {window_id}")
        self.adapter._handle_window_removed(window_id)
    
    @method(name="toggleTiling")
    def toggleTiling(self):
        print("[DBUS SERVER] Señal recibida: toggleTiling")
        self.adapter._handle_shortcut("toggle_tiling", None)

    @method(name="incrementGaps")
    def incrementGaps(self, amount: 'i'): # type: ignore
        print(f"[DBUS SERVER] Señal recibida: incrementGaps ({amount})")
        self.adapter._handle_shortcut("increment_gaps", amount)
    
    @method(name="getPendingCommands")
    async def getPendingCommands(self) -> 's': # type: ignore
        return await self.adapter.get_pending_commands_json()
    @method(name="updateScreenGeometry")
    def updateScreenGeometry(self, workspace_id: 's', x: 'i', y: 'i', w: 'i', h: 'i'): # type: ignore
        self.adapter.workspaces[workspace_id] = Workspace(id=workspace_id, rect=Rect(x, y, w, h))
    
    @method(name="windowMinimizedChanged")
    def windowMinimizedChanged(self, window_id: 's', is_minimized: 'b'): # type: ignore
        self.adapter._handle_minimized_changed(window_id, is_minimized)
    
    @method(name="incrementMaster")
    def incrementMaster(self): # type: ignore
        print("[DBUS SERVER] Señal recibida: incrementMaster")
        self.adapter._handle_shortcut("increment_master", None)

    @method(name="decrementMaster")
    def decrementMaster(self): # type: ignore
        print("[DBUS SERVER] Señal recibida: decrementMaster")
        self.adapter._handle_shortcut("decrement_master", None)

    @method(name="increaseRatio")
    def increaseRatio(self): # type: ignore
        print("[DBUS SERVER] Señal recibida: increaseRatio")
        self.adapter._handle_shortcut("increase_ratio", None)

    @method(name="decreaseRatio")
    def decreaseRatio(self): # type: ignore
        print("[DBUS SERVER] Señal recibida: decreaseRatio")
        self.adapter._handle_shortcut("decrease_ratio", None)

class KWinDBusAdapter(DisplayServerPort, EventListenerPort):
    def __init__(self):
        self.bus: Any = None
        self._on_window_created_cb: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_window_closed_cb: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_shortcut_pressed_cb: Optional[Callable[[str, Any], Awaitable[None]]] = None
        self.known_windows: Dict[str, WindowNode] = {}
        self.command_queue = asyncio.Queue()
        self.workspaces: Dict[str, Workspace] = {
            "default": Workspace(id="default", rect=Rect(0, 0, 1920, 1080))
        }
    def _handle_minimized_changed(self, window_id: str, is_minimized: bool):
        if window_id in self.known_windows:
            self.known_windows[window_id].is_minimized = is_minimized
            asyncio.create_task(self._delayed_state_change(window_id))
    async def connect(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.DO_NOT_QUEUE)
        print("[ADAPTER] Demonio Raven escuchando en DBus ('org.kde.raven.Daemon').")
        await self.command_queue.put({"action": "request_sync"})

    async def get_pending_commands_json(self) -> str:
        commands = []
        try:
            primer_comando = await asyncio.wait_for(self.command_queue.get(), timeout=20.0)
            commands.append(primer_comando)
            while not self.command_queue.empty():
                commands.append(self.command_queue.get_nowait())
        except asyncio.TimeoutError:
            pass            
        return json.dumps(commands)

    async def _delayed_state_change(self, window_id: str):
        """
        Pausa táctica de 250ms. 
        Permite que el motor de KWin finalice las animaciones nativas 
        (minimizar/cerrar) antes de forzar la nueva geometría matemática.
        """
        await asyncio.sleep(0.25)
        if self._on_window_created_cb:
            await self._on_window_created_cb(window_id)

    # --- IMPLEMENTACIÓN DE EVENT LISTENER PORT ---
    def on_window_created(self, callback: Callable[[str], Awaitable[None]]):
        self._on_window_created_cb = callback

    def on_window_closed(self, callback: Callable[[str], Awaitable[None]]):
        self._on_window_closed_cb = callback

    # CORRECCIÓN 2: Eliminamos la función duplicada on_shortcut_pressed vacía
    def on_shortcut_pressed(self, callback: Callable[[str, Any], Awaitable[None]]):
        self._on_shortcut_pressed_cb = callback

    def _handle_window_added(self, window_id: str, workspace_id: str, is_floating: bool):
        self.known_windows[window_id] = WindowNode(
            window_id=window_id, 
            workspace_id=workspace_id,
            is_floating=is_floating
        )
        asyncio.create_task(self._delayed_state_change(window_id)) 
        
    def _handle_window_removed(self, window_id: str):
        if window_id in self.known_windows:
            del self.known_windows[window_id]
        asyncio.create_task(self._delayed_state_change(window_id))

    def _handle_shortcut(self, action: str, payload: Any):
        if self._on_shortcut_pressed_cb:
            asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))

    # --- IMPLEMENTACIÓN DE DISPLAY SERVER PORT ---
    async def get_workspaces(self) -> Dict[str, Workspace]:
        return self.workspaces
    
    async def get_all_windows(self) -> List[WindowNode]:
        return list(self.known_windows.values())

    async def set_window_geometry(self, window_id: str, rect: Rect):
        command = {
            "action": "move",
            "window_id": window_id,
            "x": rect.x,
            "y": rect.y,
            "width": rect.width,
            "height": rect.height
        }
        await self.command_queue.put(command)
        print(f"[DBUS OUT] Orden para KWin -> Ventana {window_id}: {rect}")

    async def set_active_window(self, window_id: str):
        pass