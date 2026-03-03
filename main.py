import asyncio
import sys
from typing import Any

from core.tiling_engine import TilingEngine
from adapters.dbus_kwin import KWinDBusAdapter
from adapters.config_loader import ConfigLoader
from ports.display_server import DisplayServerPort
from ports.event_listener import EventListenerPort
from core.config import RavenConfig

class RavenController:
    """
    Servicio de Aplicación que orquesta el flujo de información.
    Actúa como el 'pegamento' entre el dominio puro y los adaptadores impuros.
    """
    def __init__(self, engine: TilingEngine, display: DisplayServerPort, events: EventListenerPort):
        # Inyección de Dependencias: El controlador recibe los objetos ya creados.
        self.engine = engine
        self.display = display
        self.events = events

    async def start(self):
        """Inicializa las conexiones y registra los callbacks."""
        if hasattr(self.display, 'connect'):
            await self.display.connect()

        # Suscripción a eventos mediante el patrón Observer
        self.events.on_window_created(self.handle_state_change)
        self.events.on_window_closed(self.handle_state_change)
        self.events.on_shortcut_pressed(self.handle_shortcut)

        print("[CONTROLADOR] Callbacks registrados. Ejecutando layout inicial...")
        
        # Forzamos un acomodo inicial para las ventanas que ya estaban abiertas
        await self.handle_state_change()

    async def handle_state_change(self, window_id: str = None):
        """
        El flujo principal de Raven. Se ejecuta cada vez que el estado del mundo cambia.
        """
        if window_id:
            print(f"[EVENTO] Cambio detectado. Gatillo: Ventana {window_id}")

        try:
            # 1. Leer el estado del mundo real (Ahora topológico)
            workspaces = await self.display.get_workspaces()
            windows = await self.display.get_all_windows()

            # 2. Procesar el estado en el dominio matemático (Motor Multi-Monitor)
            layout_map = self.engine.calculate_all_workspaces(windows, workspaces)

            # 3. Modificar el mundo real con los resultados
            for win_id, rect in layout_map.items():
                await self.display.set_window_geometry(win_id, rect)
                
            print(f"[CONTROLADOR] Mosaico recalculado en {len(workspaces)} pantallas para {len(layout_map)} ventanas.")
            
        except Exception as e:
            print(f"[ERROR] Fallo al recalcular el layout: {e}")

    async def handle_shortcut(self, action: str, payload: Any = None):
        """
        Procesa las órdenes del teclado y muta el estado del motor matemático.
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

        # Al cambiar reglas matemáticas, forzamos un redibujado
        await self.handle_state_change()

async def main():
    print("Iniciando Raven Tiling Emulator...")

    # 1. Cargamos la configuración del sistema de archivos
    loader = ConfigLoader()
    app_config = loader.load()

    # 2. Instanciamos el Dominio (Core) inyectándole la configuración
    engine = TilingEngine(config=app_config)
    kwin_adapter = KWinDBusAdapter()

    # 3. Ensamblamos la aplicación inyectando las dependencias
    controller = RavenController(
        engine=engine,
        display=kwin_adapter,
        events=kwin_adapter
    )

    # 4. Arrancamos el ciclo de vida
    await controller.start()

    print("[INFO] Raven operando en segundo plano. Presiona Ctrl+C para salir.")
    
    # Mantiene el bucle de eventos asíncrono vivo
    await asyncio.Future()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Apagado seguro de Raven ejecutado por el usuario.")
        sys.exit(0)