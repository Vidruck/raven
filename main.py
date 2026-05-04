import asyncio
import sys
import signal
import json
from typing import Any

from core.tiling_engine import TilingEngine
from adapters.dbus_kwin import KWinDBusAdapter
from adapters.config_loader import ConfigLoader
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort

class RavenController:
    """
    Orquestador de la aplicación (Application Service).
    Actúa como el mediador entre el dominio puro (TilingEngine) y los 
    adaptadores de infraestructura (KWin/DBus).
    """
    def __init__(self, engine: TilingEngine, display: DisplayServerPort, events: EventListenerPort):
        self.engine = engine
        self.display = display
        self.events = events

    async def start(self):
        """
        Inicializa la conexión con el servidor gráfico y registra los callbacks
        para reaccionar a eventos de ventanas y atajos de teclado. Luego ejecuta
        la disposición inicial (layout).
        """
        if hasattr(self.display, 'connect'):
            await self.display.connect()

        self.events.on_window_created(self.handle_state_change)
        self.events.on_window_closed(self.handle_state_change)
        self.events.on_shortcut_pressed(self.handle_shortcut)

        print("[CONTROLADOR] Callbacks registrados. Ejecutando disposición inicial...")
        await self.handle_state_change()

    async def handle_state_change(self, *args):
        """
        Callback principal activado ante la creación o cierre de una ventana.
        Recupera el último estado emitido por KWin y solicita al motor el nuevo layout.
        """
        try:
            raw_json = self.display.last_payload_json
            layout_map = self.engine.calculate_from_payload(raw_json)

            for win_id, rect in layout_map.items():
                await self.display.set_window_geometry(win_id, rect)
                
            print(f"[CONTROLADOR] Mosaico recalculado para {len(layout_map)} ventanas (Rust Core).")
        except Exception as e:
            print(f"[ERROR] Falló al recalcular el layout: {e}")

    async def handle_shortcut(self, action: str, payload: Any = None):
        """
        Interpreta y ejecuta los atajos de teclado del usuario, delegando la acción
        correspondiente al motor de Tiling o al compositor.
        """
        print(f"[EVENTO] Atajo presionado: {action}")
        
        if action == "toggle_tiling":
            estado = self.engine.toggle_tiling()
            print(f"[CORE] Tiling activado: {estado}")
            
        elif action == "increment_gaps":
            self.engine.config.default_gaps = max(0, self.engine.config.default_gaps + payload)
            
        elif action == "increment_master":
            self.engine.config.nmaster += 1
                
        elif action == "decrement_master":
            self.engine.config.nmaster = max(1, self.engine.config.nmaster - 1)
            
        elif action == "increase_ratio":
            self.engine.config.master_ratio = min(0.9, self.engine.config.master_ratio + 0.05)
            
        elif action == "decrease_ratio":
            self.engine.config.master_ratio = max(0.1, self.engine.config.master_ratio - 0.05)

        elif action in ["focus_next", "focus_prev"]:
            try:
                raw_data = json.loads(self.display.last_payload_json)
                windows = raw_data.get("windows", [])
                active_windows = [w for w in windows if not w.get("f") and not w.get("m")]
                
                if not active_windows:
                    return

                active_id = getattr(self.display, 'active_window_id', None)
                current_idx = next((i for i, w in enumerate(active_windows) if w.get("id") == active_id), -1)

                if current_idx == -1:
                    next_idx = 0
                else:
                    step = 1 if action == "focus_next" else -1
                    next_idx = (current_idx + step) % len(active_windows)

                target_win_id = active_windows[next_idx].get("id")
                await self.display.set_active_window(target_win_id)
            except json.JSONDecodeError:
                pass
            return 
            
        await self.handle_state_change()

async def main():
    """
    Punto de entrada de la aplicación. Inicializa el loop de eventos asíncronos,
    carga la configuración, levanta el motor de dependencias (Engine, Adapter) y 
    gestiona el cierre limpio (graceful shutdown).
    """
    print("Iniciando Raven Tiling Emulator...")
    loop = asyncio.get_running_loop()
    def sigterm_handler():
        for task in asyncio.all_tasks(loop):
            task.cancel()        
    loop.add_signal_handler(signal.SIGTERM, sigterm_handler)

    loader = ConfigLoader()
    app_config = loader.load()

    engine = TilingEngine(config=app_config)
    kwin_adapter = KWinDBusAdapter()
    kwin_adapter.engine = engine

    controller = RavenController(
        engine=engine,
        display=kwin_adapter,
        events=kwin_adapter
    )

    await controller.start()
    print("[INFO] Raven operando en segundo plano. Presiona Ctrl+C para salir.")

    try:
        if kwin_adapter.bus:
            await kwin_adapter.bus.wait_for_disconnect()
            sys.exit(1)
        else:
            await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        print("[INFO] Motor apagado limpiamente.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except asyncio.CancelledError:
        sys.exit(0)