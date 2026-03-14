import asyncio
import sys
import signal
from typing import Any

from core.tiling_engine import TilingEngine
from adapters.dbus_kwin import KWinDBusAdapter
from adapters.config_loader import ConfigLoader
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort
from core.config import RavenConfig

class RavenController:
    """
    Orquestador de la aplicación (Application Service).

    Actúa como el mediador entre el dominio puro (TilingEngine) y los 
    adaptadores de infraestructura (KWin/DBus). Implementa la lógica de 
    negocio de alto nivel para la gestión de ventanas.

    Attributes:
        engine: Instancia del motor lógico de mosaico.
        display: Puerto de salida para comandos al servidor de pantalla.
        events: Puerto de entrada para suscripción a eventos del sistema.
     """
    def __init__(self, engine: TilingEngine, display: DisplayServerPort, events: EventListenerPort):

        """
        Inicializa el controlador mediante Inyección de Dependencias.
        """

        self.engine = engine
        self.display = display
        self.events = events

    async def start(self):

        """
        Inicializa el ciclo de vida de la aplicación.
        Establece la conexión con el servidor de pantalla y registra los 
        manejadores de eventos (callbacks) necesarios.
        """
        if hasattr(self.display, 'connect'):
            await self.display.connect()

        self.events.on_window_created(self.handle_state_change)
        self.events.on_window_closed(self.handle_state_change)
        self.events.on_shortcut_pressed(self.handle_shortcut)

        print("[CONTROLADOR] Callbacks registrados. Ejecutando layout inicial...")

        await self.handle_state_change()

    async def handle_state_change(self, window_id: str = None):

        """
        Flujo principal de sincronización topológica.
        
        Extrae el estado actual del servidor, calcula la nueva disposición 
        matemática y aplica los cambios geométricos resultantes.

        Args:
            window_id: Identificador opcional de la ventana que disparó el evento.
        """
        
        if window_id:
            print(f"[EVENTO] Cambio detectado. Gatillo: Ventana {window_id}")

        try:

            workspaces = await self.display.get_workspaces()
            windows = await self.display.get_all_windows()

            layout_map = self.engine.calculate_all_workspaces(windows, workspaces)

            for win_id, rect in layout_map.items():
                await self.display.set_window_geometry(win_id, rect)
                
            print(f"[CONTROLADOR] Mosaico recalculado en {len(workspaces)} pantallas para {len(layout_map)} ventanas.")
            
        except Exception as e:
            print(f"[ERROR] Fallo al recalcular el layout: {e}")

    async def handle_shortcut(self, action: str, payload: Any = None):
        """
        Manejador de señales de usuario (Atajos de teclado).
        
        Modifica el estado del motor de dominio o el foco del sistema 
        basado en la entrada capturada por los adaptadores.

        Args:
            action: Nombre del comando a ejecutar.
            payload: Datos adicionales necesarios para la acción.
        """
        print(f"[EVENTO] Atajo presionado: {action} (Payload: {payload})")
        
        if action == "toggle_tiling":
            estado = self.engine.toggle_tiling()
            print(f"[CORE] Tiling activado: {estado}")
            
        elif action == "increment_gaps":
            nuevo_gap = max(0, self.engine.config.default_gaps + payload)
            self.engine.config.default_gaps = nuevo_gap
            print(f"[CORE] Gaps actualizados a: {nuevo_gap}px")
            
        elif action == "increment_master":
            self.engine.config.nmaster += 1
                
        elif action == "decrement_master":
            self.engine.config.nmaster = max(1, self.engine.config.nmaster - 1)
            
        elif action == "increase_ratio":
            self.engine.config.master_ratio = min(0.9, self.engine.config.master_ratio + 0.05)
            
        elif action == "decrease_ratio":
            self.engine.config.master_ratio = max(0.1, self.engine.config.master_ratio - 0.05)
        elif action in ["focus_next", "focus_prev"]:
            windows = await self.display.get_all_windows()

            active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
            
            if not active_windows:
                return

            current_idx = -1
            active_id = getattr(self.display, 'active_window_id', None)
            
            for i, w in enumerate(active_windows):
                if w.window_id == active_id:
                    current_idx = i
                    break
            if current_idx == -1:
                next_idx = 0
            else:
                if action == "focus_next":
                    next_idx = (current_idx + 1) % len(active_windows)
                else:
                    next_idx = (current_idx - 1) % len(active_windows)

            target_win = active_windows[next_idx]
            await self.display.set_active_window(target_win.window_id)
            return 
        await self.handle_state_change()

async def _handle_focus_rotation(self, direction: str):
        """Lógica interna para rotar el foco entre ventanas activas."""
        windows = await self.display.get_all_windows()
        active_windows = [w for w in windows if not w.is_floating and not w.is_minimized]
        
        if not active_windows:
            return

        active_id = getattr(self.display, 'active_window_id', None)
        current_idx = next((i for i, w in enumerate(active_windows) if w.window_id == active_id), -1)

        if current_idx == -1:
            next_idx = 0
        else:
            step = 1 if direction == "focus_next" else -1
            next_idx = (current_idx + step) % len(active_windows)

        await self.display.set_active_window(active_windows[next_idx].window_id)

async def main():
    print("Iniciando Raven Tiling Emulator...")
    loop = asyncio.get_running_loop()
    def sigterm_handler():
        print("\n[INFO] Señal SIGTER (Systemd) recibida. Apagando...")
        for task in asyncio.all_tasks(loop):
            task.cancel()        
    loop.add_signal_handler(signal.SIGTERM, sigterm_handler)

    loader = ConfigLoader()
    app_config = loader.load()

    engine = TilingEngine(config=app_config)
    kwin_adapter = KWinDBusAdapter()

    controller = RavenController(
        engine=engine,
        display=kwin_adapter,
        events=kwin_adapter
    )

    await controller.start()

    print("[INFO] Raven operando en segundo plano. Presiona Ctrl+C para salir.")

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        print("[INFO] Ciclo principal cancelado por Systemd. Liberando recursos...")
    finally:
        print("[INFO] Motor Raven apagado limpiamente.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Apagado seguro de Raven ejecutado por el usuario (Ctrl+C).")
        sys.exit(0)
    except asyncio.CancelledError:
        sys.exit(0)