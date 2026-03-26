"""
Adaptador de Infraestructura DBus para KWin.

Proporciona la implementación para los puertos DisplayServerPort y EventListenerPort
utilizando el mecanismo de comunicación entre procesos (IPC) de DBus. Sirve de puente 
entre la lógica de dominio puro del TilingEngine y el compositor Wayland de KDE Plasma.
"""

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
    """
    Expone métodos sobre el bus de sesión de DBus para que el puente de Javascript (Javascript Bridge) 
    de KWin dispare sincronizaciones de estado y consulte comandos arquitectónicos pendientes.
    """
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
        """
        Punto de acceso RPC (RPC Endpoint) para que la interfaz de usuario (UI) consulte el estado actual del motor.
        Retorna True si el mosaico (tiling) está activo, False si está pausado.
        """
        if hasattr(self.adapter, 'engine'):
            return self.adapter.engine.is_tiling_enabled
        return True


class KWinDBusAdapter(DisplayServerPort, EventListenerPort):
    """
    Implementa DisplayServerPort y EventListenerPort para abstraer los específicos de Wayland.
    Maneja la limitación de frecuencia (debouncing) y la deserialización robusta del estado atómico.
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

    def _handle_sync_state(self, payload_json: str) -> None:
        """
        Deserializa la captura del estado atómico (atomic state snapshot) recibida desde el puente de KWin.
        Sobrescribe la memoria interna para asegurar una consistencia eventual absoluta.
        
        Args:
            payload_json (str): Diccionario serializado que contiene datos de pantallas y ventanas.
        """
        try:
            data = json.loads(payload_json)

            for ws_id, rect_data in data.get("screens", {}).items():
                self.workspaces[ws_id] = Workspace(
                    id=ws_id, 
                    rect=Rect(rect_data["x"], rect_data["y"], rect_data["w"], rect_data["h"])
                )

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
            print(f"[ERROR] Falló el procesamiento de la captura (snapshot parsing): {e}")

    def _trigger_recalculation(self) -> None:
        """
        Encola una solicitud de cálculo de disposición (layout). Implementa una regulación de flujo (throttling) 
        para prevenir la saturación del CPU durante ráfagas de eventos del compositor Wayland.
        """
        self._recalc_pending = True
        if self._debounce_task and not self._debounce_task.done():
            return 
        self._debounce_task = asyncio.create_task(self._debounced_state_change())
   
    async def _debounced_state_change(self) -> None:
        """Ejecuta la función de respuesta (callback) de cálculo tras estabilizar las animaciones de KWin."""
        try:
            while self._recalc_pending:
                self._recalc_pending = False
                await asyncio.sleep(0.05)
                if self._on_window_created_cb:
                    await self._on_window_created_cb("sync")
        except asyncio.CancelledError:
            pass

    def _handle_shortcut(self, action: str, payload: Any) -> None:
        """Despacha de forma asíncrona un evento de atajo de teclado al controlador."""
        if self._on_shortcut_pressed_cb:
            asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))

    async def connect(self) -> None:
        """Establece la conexión de sesión de DBus y exporta el servicio."""
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.REPLACE_EXISTING)
        await self.command_queue.put({"action": "request_sync"})

    async def get_pending_commands_json(self) -> str:
        """Entrega comandos de UI pendientes al puente de JS utilizando espera larga (long-polling)."""
        commands = []
        try:
            primer_comando = await asyncio.wait_for(self.command_queue.get(), timeout=5.0)
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