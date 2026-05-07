use std::sync::Arc;
use tokio::sync::Mutex;
use zbus::ConnectionBuilder;
use std::error::Error;

use raven_core::infrastructure::config::RavenConfig;
use raven_core::application::engine::TilingEngine;
use raven_core::application::controller::RavenController;
use raven_core::infrastructure::dbus::RavenDBusService;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    println!("🐦 Iniciando Raven Tiling Emulator (Motor Nativo Rust v2.0)...");

    // 1. Instanciación del Dominio (Single Source of Truth)
    let app_config = RavenConfig::load();
    let engine = TilingEngine::new(app_config);
    
    // 2. Orquestador envuelto en concurrencia segura
    // Arc (Atomic Reference Counting) y Mutex garantizan que múltiples señales 
    // de Wayland puedan ser procesadas en hilos paralelos sin Data Races.
    let controller = Arc::new(Mutex::new(RavenController::new(engine)));
    
    // 3. Inicialización de la Infraestructura IPC (zbus)
    let dbus_service = RavenDBusService {
        controller,
        pending_commands: Arc::new(Mutex::new(Vec::new())),
        active_window_id: Arc::new(Mutex::new(None)),
        last_payload_json: Arc::new(Mutex::new(String::from("{}"))),
    };

    println!("[DBUS] Solicitando registro en el bus de sesión de Arch Linux...");
    
    // 4. Conexión Zero-Copy al compositor KWin
    let _connection = ConnectionBuilder::session()?
        .name("org.kde.raven.Daemon")?
        .serve_at("/Events", dbus_service)?
        .build()
        .await?;

    println!("✅ Raven está ejecutándose. Topología y callbacks IPC registrados.");

    // 5. Suspensión infinita y eficiente del hilo principal (Event Loop)
    std::future::pending::<()>().await;

    Ok(())
}