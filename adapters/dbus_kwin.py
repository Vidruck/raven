"""
KWin DBus Infrastructure Adapter.

Provides the implementation for the DisplayServerPort and EventListenerPort
using the DBus IPC mechanism. It bridges the pure domain logic of the 
TilingEngine with the KDE Plasma Wayland compositor.
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
    Exposes methods over the DBus session bus for the KWin Javascript Bridge 
    to trigger state syncs and query pending architectural commands.
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


class KWinDBusAdapter(DisplayServerPort, EventListenerPort):
    """
    Implements DisplayServerPort and EventListenerPort to abstract Wayland specifics.
    Handles rate-limiting (debouncing) and robust atomic state deserialization.
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
        Deserializes the atomic state snapshot received from the KWin bridge.
        Overrides internal memory to ensure absolute eventual consistency.
        
        Args:
            payload_json (str): Serialized dictionary containing screens and windows data.
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
            print(f"[ERROR] Snapshot parsing failed: {e}")

    def _trigger_recalculation(self) -> None:
        """
        Enqueues a layout calculation request. Implements throttling to prevent 
        CPU starvation during burst events from the Wayland compositor.
        """
        self._recalc_pending = True
        if self._debounce_task and not self._debounce_task.done():
            return 
        self._debounce_task = asyncio.create_task(self._debounced_state_change())
   
    async def _debounced_state_change(self) -> None:
        """Executes the calculation callback after stabilizing KWin animations."""
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

    def _handle_shortcut(self, action: str, payload: Any) -> None:
        """Asynchronously dispatches a keyboard shortcut event to the controller."""
        if self._on_shortcut_pressed_cb:
            asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))

    async def connect(self) -> None:
        """Establishes the DBus session connection and exports the service."""
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.DO_NOT_QUEUE)
        await self.command_queue.put({"action": "request_sync"})

    async def get_pending_commands_json(self) -> str:
        """Yields pending UI commands to the JS bridge using long-polling."""
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