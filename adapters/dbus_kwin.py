import json
import asyncio
from typing import List, Callable, Awaitable, Optional, Any, Dict

from dbus_next.aio import MessageBus
from dbus_next import BusType
from dbus_next.service import ServiceInterface, method
from dbus_next.constants import NameFlag

from core.models import Rect, WindowNode, Workspace 
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort

class RavenEventsDBusService(ServiceInterface):
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
    def incrementMaster(self): # type: ignore
        self.adapter._handle_shortcut("increment_master", None)

    @method(name="decrementMaster")
    def decrementMaster(self): # type: ignore
        self.adapter._handle_shortcut("decrement_master", None)

    @method(name="increaseRatio")
    def increaseRatio(self): # type: ignore
        self.adapter._handle_shortcut("increase_ratio", None)

    @method(name="decreaseRatio")
    def decreaseRatio(self): # type: ignore
        self.adapter._handle_shortcut("decrease_ratio", None)

    @method(name="focusNext")
    def focusNext(self): # type: ignore
        self.adapter._handle_shortcut("focus_next", None)

    @method(name="focusPrev")
    def focusPrev(self): # type: ignore
        self.adapter._handle_shortcut("focus_prev", None)


class KWinDBusAdapter(DisplayServerPort, EventListenerPort):

    """
    Adaptador de infraestructura que implementa la comunicación asíncrona entre 
    el motor de Raven y el compositor KWin (KDE) a través de DBus.
    
    Implementa el patrón Bridge para desacoplar la lógica matemática del protocolo 
    de mensajería de Wayland.
    """
    def __init__(self):
        self.bus: Any = None
        self._on_window_created_cb: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_window_closed_cb: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_shortcut_pressed_cb: Optional[Callable[[str, Any], Awaitable[None]]] = None
        
        self.known_windows: Dict[str, WindowNode] = {}
        self.command_queue = asyncio.Queue()
        self.active_window_id: Optional[str] = None
        self.workspaces: Dict[str, Workspace] = {}
        
        self._debounce_task: Optional[asyncio.Task] = None
        self._recalc_pending: bool = False

    def _handle_sync_state(self, payload_json: str):
        """
        Reconstruye el estado atómico del mundo desde un snapshot JSON.
        Garantiza consistencia eventual eliminando el desfasamiento de eventos individuales.
        """
        try:
            # Deserialización del estado global enviado por el Bridge de KWin

            data = json.loads(payload_json)

            # Sincronización de Topología de Monitores:
            # Mapeamos los rectángulos físicos de cada salida de video activa.

            for ws_id, rect_data in data.get("screens", {}).items():
                self.workspaces[ws_id] = Workspace(
                    id=ws_id, 
                    rect=Rect(rect_data["x"], rect_data["y"], rect_data["w"], rect_data["h"])
                )

            # Sincronización de Nodos de Ventana:
            # Realizamos una reconstrucción limpia (Clean Slate) para evitar estados zombis
            # de ventanas ya cerradas o minimizadas en el monitor.
            
            new_windows = {}
            for w in data.get("windows", []):
                win_id = w["id"]
                new_windows[win_id] = WindowNode(
                    window_id=win_id,
                    workspace_id=w["ws"],
                    is_floating=w["f"],
                    is_minimized=w["m"] 
                )
            self.known_windows = new_windows

            self._trigger_recalculation()
        except Exception as e:
            print(f"[ERROR] Parseo de Snapshot fallido: {e}")

    def _trigger_recalculation(self):

        # Implementamos un Throttler/Debouncer para evitar la 'inanición' del CPU.
        # Si ya existe una tarea de cálculo en curso, marcamos la bandera de 'pendiente'
        # y permitimos que la tarea actual procese los nuevos datos al finalizar.

        self._recalc_pending = True
        if self._debounce_task and not self._debounce_task.done():
            return 
        self._debounce_task = asyncio.create_task(self._debounced_state_change())
   
    async def _debounced_state_change(self):
        try:
            while self._recalc_pending:
                self._recalc_pending = False
                await asyncio.sleep(0.15)
                if self._on_window_created_cb:
                    await self._on_window_created_cb("sync")
                await asyncio.sleep(0.35)
                if self._on_window_created_cb:
                    await self._on_window_created_cb("sync")
        except asyncio.CancelledError:
            pass

                # Los Delays (0.15s y 0.35s) están calibrados para permitir que KWin finalice 
                # las animaciones de renderizado antes de que Raven imponga la nueva geometría.
                # Esto previene el parpadeo (flickering) en el servidor gráfico.

    def _handle_shortcut(self, action: str, payload: Any):
        if self._on_shortcut_pressed_cb:
            asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))

    async def connect(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.DO_NOT_QUEUE)
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

    def on_window_created(self, callback: Callable[[str], Awaitable[None]]):
        self._on_window_created_cb = callback

    def on_window_closed(self, callback: Callable[[str], Awaitable[None]]):
        self._on_window_closed_cb = callback

    def on_shortcut_pressed(self, callback: Callable[[str, Any], Awaitable[None]]):
        self._on_shortcut_pressed_cb = callback
    
    async def get_workspaces(self) -> Dict[str, Workspace]:
        return self.workspaces
    
    async def get_all_windows(self) -> List[WindowNode]:
        return list(self.known_windows.values())

    async def set_window_geometry(self, window_id: str, rect: Rect):
        command = {
            "action": "move", "window_id": window_id,
            "x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height
        }
        await self.command_queue.put(command)

    async def set_active_window(self, window_id: str):
        command = {"action": "focus", "window_id": window_id}
        await self.command_queue.put(command)