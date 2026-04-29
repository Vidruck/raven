"""
Adaptador de Infraestructura DBus para KWin.
Proporciona la implementación para los puertos DisplayServerPort y EventListenerPort
utilizando el mecanismo de comunicación entre procesos (IPC) de DBus.
"""

import json
import asyncio
import kwin_rust_adapter 
from typing import List, Callable, Optional, Any, Dict, Coroutine

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import BusType, NameFlag
from dbus_next.service import ServiceInterface, method

from core.models import Rect, WindowNode, Workspace 
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort

class RavenEventsDBusService(ServiceInterface):
    """Servicio DBus para la comunicación con el script de KWin."""
    def __init__(self, adapter: 'KWinDBusAdapter'):
        super().__init__('org.kde.raven.Events')
        self.adapter = adapter

    @method(name="syncState")
    def syncState(self, payload_json: 's'): # type: ignore
        self.adapter._handle_sync_state(payload_json)

    @method(name="getPendingCommands")
    async def getPendingCommands(self) -> 's': # type: ignore
        return await self.adapter.get_pending_commands_json()
    
    @method(name="windowActivated")
    def windowActivated(self, window_id: 's'): # type: ignore
        self.adapter.active_window_id = window_id

    @method(name="toggleTiling")
    def toggleTiling(self):
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
        if self.adapter.engine is not None:
            return self.adapter.engine.is_tiling_enabled
        return True


class KWinDBusAdapter(DisplayServerPort, EventListenerPort):
    """
    Adaptador optimizado con Lazy Initialization y Tipado Estricto (Strict Type Hinting).
    """
    def __init__(self):
        self.bus: Any = None
        self._on_window_created_cb: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None
        self._on_window_closed_cb: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None
        self._on_shortcut_pressed_cb: Optional[Callable[[str, Any], Coroutine[Any, Any, None]]] = None
        
        self.known_windows: Dict[str, WindowNode] = {}
        self.command_queue: Optional[asyncio.Queue] = None 
        self.engine: Any = None 
        
        self.active_window_id: Optional[str] = None
        self.workspaces: Dict[str, Workspace] = {}
        
        self._debounce_task: Optional[asyncio.Task] = None

    def _handle_sync_state(self, payload_json: str) -> None:
        try:
            screens_data, windows_data = kwin_rust_adapter.parse_sync_state(payload_json)

            self.workspaces = {
                ws_id: Workspace(id=ws_id, rect=Rect(**r_data))
                for ws_id, r_data in screens_data.items()
            }

            self.known_windows = {
                w_data["window_id"]: WindowNode(**w_data)
                for w_data in windows_data
            }

            self._trigger_recalculation()
        except Exception as e:
            print(f"[ERROR] Falló el procesamiento de la captura nativa: {e}")

    def _trigger_recalculation(self) -> None:
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounced_state_change())

    async def _debounced_state_change(self) -> None:
        try:
            await asyncio.sleep(0.15)
            if self._on_window_created_cb:
                await self._on_window_created_cb("sync")
        except asyncio.CancelledError:
            pass

    def _handle_shortcut(self, action: str, payload: Any) -> None:
        if self._on_shortcut_pressed_cb:
            asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))

    async def connect(self) -> None:
        if self.command_queue is None:
            self.command_queue = asyncio.Queue()

        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.REPLACE_EXISTING)
        assert self.command_queue is not None
        await self.command_queue.put({"action": "request_sync"})

    async def get_pending_commands_json(self) -> str:
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
        return json.dumps(commands)

    def on_window_created(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        self._on_window_created_cb = callback

    def on_window_closed(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        self._on_window_closed_cb = callback

    def on_shortcut_pressed(self, callback: Callable[[str, Any], Coroutine[Any, Any, None]]):
        self._on_shortcut_pressed_cb = callback
    
    async def get_workspaces(self) -> Dict[str, Workspace]:
        return self.workspaces
    
    async def get_all_windows(self) -> List[WindowNode]:
        return list(self.known_windows.values())

    async def set_window_geometry(self, window_id: str, rect: Rect):
        if self.command_queue is not None:
            command = {
                "action": "move", "window_id": window_id,
                "x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height
            }
            await self.command_queue.put(command)

    async def set_active_window(self, window_id: str):
        if self.command_queue is not None:
            command = {"action": "focus", "window_id": window_id}
            await self.command_queue.put(command)