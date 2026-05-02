"""
Adaptador de Infraestructura DBus para KWin.

Proporciona la implementación para los puertos DisplayServerPort y EventListenerPort
utilizando el mecanismo de comunicación entre procesos (IPC) de DBus. Integra una
extensión nativa en Rust para maximizar el rendimiento en la deserialización de
estados masivos provenientes del compositor.
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
    """
    Servicio DBus de baja latencia que expone la interfaz de comunicación para el script de KWin.
    Implementa los métodos necesarios para recibir estados, eventos y gestionar atajos de teclado.
    """
    def __init__(self, adapter: 'KWinDBusAdapter'):
        super().__init__('org.kde.raven.Events')
        self.adapter = adapter

    @method(name="syncState")
    def syncState(self, payload_json: 's'): # type: ignore
        """Recibe el estado atómico de ventanas y monitores en formato JSON."""
        self.adapter._handle_sync_state(payload_json)

    @method(name="getPendingCommands")
    async def getPendingCommands(self) -> 's': # type: ignore
        """Devuelve una lista de comandos pendientes (movimientos, enfoques) para que KWin los ejecute."""
        return await self.adapter.get_pending_commands_json()
    
    @method(name="windowActivated")
    def windowActivated(self, window_id: 's'): # type: ignore
        """Notifica cuando una ventana ha ganado el enfoque en el compositor."""
        self.adapter.active_window_id = window_id

    @method(name="toggleTiling")
    def toggleTiling(self):
        """Alterna el estado del motor de mosaico (Tiling)."""
        self.adapter._handle_shortcut("toggle_tiling", None)

    @method(name="incrementGaps")
    def incrementGaps(self, amount: 'i'): # type: ignore
        """Incrementa el espaciado (gaps) entre ventanas."""
        self.adapter._handle_shortcut("increment_gaps", amount)

    @method(name="incrementMaster")
    def incrementMaster(self):
        """Aumenta el número de ventanas en el área maestra."""
        self.adapter._handle_shortcut("increment_master", None)

    @method(name="decrementMaster")
    def decrementMaster(self):
        """Disminuye el número de ventanas en el área maestra."""
        self.adapter._handle_shortcut("decrement_master", None)

    @method(name="increaseRatio")
    def increaseRatio(self):
        """Aumenta la proporción del área maestra respecto al área de stack."""
        self.adapter._handle_shortcut("increase_ratio", None)

    @method(name="decreaseRatio")
    def decreaseRatio(self):
        """Disminuye la proporción del área maestra respecto al área de stack."""
        self.adapter._handle_shortcut("decrease_ratio", None)

    @method(name="focusNext")
    def focusNext(self):
        """Mueve el enfoque a la siguiente ventana según la disposición actual."""
        self.adapter._handle_shortcut("focus_next", None)

    @method(name="focusPrev")
    def focusPrev(self):
        """Mueve el enfoque a la ventana anterior según la disposición actual."""
        self.adapter._handle_shortcut("focus_prev", None)
    
    @method(name="getTilingState")
    def getTilingState(self) -> 'b': # type: ignore
        """Consulta si el motor de mosaico está activo actualmente."""
        if self.adapter.engine is not None:
            return self.adapter.engine.is_tiling_enabled
        return True


class KWinDBusAdapter(DisplayServerPort, EventListenerPort):
    """
    Implementación concreta de los puertos de servidor de pantalla y escucha de eventos para KWin.
    
    Utiliza una arquitectura asíncrona basada en `asyncio` y delega el procesamiento pesado
    al adaptador Rust (`kwin_rust_adapter`) para evitar bloqueos en el bucle de eventos principal.
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
        self._background_task: set= set()

    def _handle_sync_state(self, payload_json: str) -> None:
        """
        Procesa la actualización de estado enviada por KWin.
        
        Utiliza el adaptador Rust para transformar el JSON masivo en objetos de dominio.
        Implementa un mecanismo de seguridad que aborta el procesamiento si los datos son corruptos.
        """
        try:
            parse_data = kwin_rust_adapter.parse_sync_state(payload_json)
            if parse_data is None:
                print(f"[ERROR IPC] Rust rechazó el JSON por violación de esquema (Schema Breach). Payload: {payload_json[:150]}...")
                return
            screens_data, windows_data = parse_data
            
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
        """
        Dispara una solicitud de recalculo de layout con anti-rebote (debouncing).
        Si ya existe una tarea en curso, se ignora la nueva solicitud para permitir que la actual finalice.
        """
        if self._debounce_task and not self._debounce_task.done():
            return
        self._debounce_task = asyncio.create_task(self._debounced_state_change())
    async def _debounced_state_change(self) -> None:
        """
        Aplica un retardo ultra-bajo (100ms) antes de notificar el cambio de estado.
        Este mecanismo suaviza ráfagas de eventos sin introducir latencia perceptible para el usuario.
        """
        try:
            await asyncio.sleep(0.1)
            if self._on_window_created_cb:
                await self._on_window_created_cb("sync")
        except asyncio.CancelledError:
            pass

    def _handle_shortcut(self, action: str, payload: Any) -> None:
        """Enruta los atajos de teclado recibidos por DBus hacia el motor lógico."""
        if self._on_shortcut_pressed_cb:
            task = asyncio.create_task(self._on_shortcut_pressed_cb(action, payload))
            self._background_task.add(task)
            task.add_done_callback(self._background_task.discard)

    async def connect(self) -> None:
        """Inicializa la conexión con el bus de sesión y registra el servicio org.kde.raven.Daemon."""
        if self.command_queue is None:
            self.command_queue = asyncio.Queue()

        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export('/Events', RavenEventsDBusService(self))
        await self.bus.request_name('org.kde.raven.Daemon', NameFlag.REPLACE_EXISTING)
        assert self.command_queue is not None
        await self.command_queue.put({"action": "request_sync"})

    async def get_pending_commands_json(self) -> str:
        """
        Obtiene y limpia la cola de comandos pendientes para enviarlos al script de KWin.
        Implementa un sondeo (polling) asíncrono para mantener la reactividad.
        """
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
            print("[WARNING] Sondeo D-Bus cancelado (Desconexión de kwin o reinio).")
            return "[]"
        except Exception as e:
            print("[ERROR CRITICO] Fallo en la cola de comandos: {e}")
        
        return json.dumps(commands)

    def on_window_created(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        """Registra el callback para la creación o sincronización de ventanas."""
        self._on_window_created_cb = callback

    def on_window_closed(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        """Registra el callback para el cierre de ventanas."""
        self._on_window_closed_cb = callback

    def on_shortcut_pressed(self, callback: Callable[[str, Any], Coroutine[Any, Any, None]]):
        """Registra el callback para la pulsación de atajos de teclado globales."""
        self._on_shortcut_pressed_cb = callback
    
    async def get_workspaces(self) -> Dict[str, Workspace]:
        """Devuelve el estado actual de todos los espacios de trabajo detectados."""
        return self.workspaces
    
    async def get_all_windows(self) -> List[WindowNode]:
        """Devuelve la lista de todas las ventanas conocidas por el adaptador."""
        return list(self.known_windows.values())

    async def set_window_geometry(self, window_id: str, rect: Rect):
        """Encola un comando de movimiento/redimensionamiento para una ventana específica."""
        if self.command_queue is not None:
            command = {
                "action": "move", "window_id": window_id,
                "x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height
            }
            await self.command_queue.put(command)

    async def set_active_window(self, window_id: str):
        """Encola un comando para cambiar el enfoque a una ventana específica."""
        if self.command_queue is not None:
            command = {"action": "focus", "window_id": window_id}
            await self.command_queue.put(command)