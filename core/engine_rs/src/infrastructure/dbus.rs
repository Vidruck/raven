use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::runtime::Handle;
use tokio::sync::Mutex;
use zbus::interface;

use crate::application::controller::RavenController;
use crate::domain::action::RavenAction;
use crate::domain::error::RavenError;
use crate::domain::geometry::{Rect, WindowNode};

/// Representa las dimensiones y posición de una pantalla según KWin.
#[derive(Debug, Deserialize)]
pub struct KWinScreen {
    /// Posición en el eje X.
    pub x: i32,
    /// Posición en el eje Y.
    pub y: i32,
    /// Ancho de la pantalla.
    pub w: i32,
    /// Alto de la pantalla.
    pub h: i32,
}

/// Representa el estado de una ventana enviado por el bridge de KWin.
#[derive(Debug, Deserialize)]
pub struct KWinWindow {
    /// Identificador único de la ventana.
    pub id: String,
    /// Identificador del escritorio virtual (Workspace).
    #[serde(default)]
    pub ws: String,
    /// Identificador de monitores
    #[serde(default)]
    pub output: String,
    /// Identificador de Escritorios Virtuales
    #[serde(default)]
    pub desktops: Vec<String>,
    /// Indica si la ventana es flotante.
    #[serde(default)]
    pub f: bool,
    /// Indica si la ventana está maximizada.
    #[serde(default)]
    pub m: bool,
    /// Indica si la ventana está en modo Picture-in-Picture (PiP).
    #[serde(default)]
    pub p: bool,
    /// Posición X actual.
    pub x: i32,
    /// Posición Y actual.
    pub y: i32,
    /// Ancho actual.
    pub w: i32,
    /// Alto actual.
    pub h: i32,
    #[serde(default)]
    pub min_w:i32,
    #[serde(default)]
    pub min_h:i32,
    #[serde(default)]
    pub sb: bool,
}

#[derive(Debug, Deserialize, Clone, Default)]
pub struct KWinTopology {
    #[serde(default)]
    pub outputs: Vec<String>,
    #[serde(default)]
    pub desktops: Vec<String>,
}

/// Estructura raíz que contiene el estado completo del compositor.
#[derive(Debug, Deserialize)]
pub struct KWinPayload {
    /// Listado de ventanas activas.
    #[serde(default)]
    pub windows: Vec<KWinWindow>,
    /// Mapa de pantallas detectadas por su identificador.
    #[serde(default)]
    pub screens: HashMap<String, KWinScreen>,
    /// Topología explícita de monitores y escritorios virtuales.
    #[serde(default)]
    pub topology: KWinTopology,
}

/// Procesa la cadena JSON cruda proveniente de KWin y la convierte a objetos de dominio.
///
/// Realiza la transformación de tipos de infraestructura (`KWinPayload`) a tipos
/// de dominio puro (`Rect`, `WindowNode`) para desacoplar la lógica de negocio.
fn parse_payload(
    payload_json: &str,
) -> Result<(HashMap<String, Rect>, Vec<WindowNode>, KWinTopology), RavenError> {
    if payload_json.is_empty() || payload_json == "{}" {
        return Ok((HashMap::new(), Vec::new(), KWinTopology::default()));
    }
    let payload: KWinPayload = serde_json::from_str(payload_json)
        .map_err(|e| RavenError::ValidationError(format!("Payload KWin inválido: {}", e)))?;

    let mut workspaces = HashMap::new();
    for (ws_id, screen) in payload.screens {
        workspaces.insert(ws_id, Rect::new(screen.x, screen.y, screen.w, screen.h));
    }

    let mut windows = Vec::with_capacity(payload.windows.len());
    for win in payload.windows {
        windows.push(WindowNode::new(
            win.id,
            win.ws,
            win.output,
            win.desktops,
            win.f,
            win.m,
            win.p,
            Rect::new(win.x, win.y, win.w, win.h),
            win.min_w,
            win.min_h,
            win.sb,
        ));
    }

    Ok((workspaces, windows, payload.topology))
}

/// Objeto de Transferencia de Datos (DTO) para comandos de posicionamiento.
///
/// Esta estructura se serializa a JSON para que el adaptador de KWin (JavaScript)
/// pueda ejecutar las acciones físicas sobre las ventanas de X11/Wayland.
#[derive(Debug, Serialize, Clone)]
pub struct TilingCommand {
    /// Acción a realizar (ej. "move", "focus").
    pub action: String,
    /// Identificador de la ventana objetivo.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub window_id: Option<String>,
    /// Nueva posición X en píxeles.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x: Option<i32>,
    /// Nueva posición Y en píxeles.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub y: Option<i32>,
    /// Nuevo ancho en píxeles.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<i32>,
    /// Nuevo alto en píxeles.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<i32>,
    /// Identificador del espacio de trabajo de destino (solo para migraciones).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_ws: Option<String>,
    /// Dirección para migraciones nativas (ej. "screen_next", "desktop_prev").
    #[serde(skip_serializing_if = "Option::is_none")]
    pub direction: Option<String>,
}

impl From<RavenAction> for TilingCommand {
    fn from(action: RavenAction) -> Self {
        match action {
            RavenAction::MoveWindow { window_id, x, y, width, height } => TilingCommand {
                action: "move".to_string(), window_id: Some(window_id), x: Some(x), y: Some(y), width: Some(width), height: Some(height), target_ws: None, direction: None,
            },
            RavenAction::FocusWindow { window_id } => TilingCommand {
                action: "focus".to_string(), window_id: Some(window_id), x: None, y: None, width: None, height: None, target_ws: None, direction: None,
            },
            RavenAction::MigrateToOutput { window_id, target_output } => TilingCommand {
                action: "migrate_to_output".to_string(), window_id: Some(window_id), target_ws: Some(target_output), x: None, y: None, width: None, height: None, direction: None,
            },
            RavenAction::MigrateToDesktop { window_id, target_desktop } => TilingCommand {
                action: "migrate_to_desktop".to_string(), window_id: Some(window_id), target_ws: Some(target_desktop), x: None, y: None, width: None, height: None, direction: None,
            },
            RavenAction::MinimizeWindow { window_id } => TilingCommand {
                action: "minimize".to_string(), window_id: Some(window_id), x: None, y: None, width: None, height: None, target_ws: None, direction: None,
            },
            RavenAction::UnminimizeWindow { window_id } => TilingCommand {
                action: "unminimize".to_string(), window_id: Some(window_id), x: None, y: None, width: None, height: None, target_ws: None, direction: None,
            },
            RavenAction::RequestFeedback { window_id } => TilingCommand {
                action: "request_feedback".to_string(), window_id: Some(window_id), x: None, y: None, width: None, height: None, target_ws: None, direction: None,
            },
        }
    }
}

/// Punto de entrada para las señales y métodos de D-Bus.
///
/// Expone la interfaz `org.kde.raven.Events` que es consumida por KWin.
/// Utiliza un modelo de concurrencia basado en `Arc<Mutex<T>>` para permitir
/// el procesamiento asíncrono y seguro de eventos del compositor.
pub struct RavenDBusService {
    /// El controlador de dominio protegido para acceso concurrente.
    pub controller: Arc<Mutex<RavenController>>,
    /// Cola de comandos pendientes de ser recogidos por el adaptador.
    pub pending_commands: Arc<Mutex<Vec<TilingCommand>>>,
    /// ID de la ventana que tiene el foco actualmente en el sistema.
    pub active_window_id: Arc<Mutex<Option<String>>>,
    /// Último estado completo recibido (cacheado para recálculos rápidos).
    pub last_payload_json: Arc<Mutex<String>>,
    /// Topología explícita del sistema.
    pub current_topology: Arc<Mutex<KWinTopology>>,
    /// Manejador inyectado del runtime de Tokio para delegar tareas.
    pub tokio_handle: Handle,
}

#[interface(name = "org.kde.raven.Events")]
impl RavenDBusService {
    /// Sincroniza el estado masivo del compositor.
    ///
    /// Este método es llamado por KWin cada vez que ocurre un cambio estructural
    /// en las ventanas. Realiza un throttling para evitar saturar el motor.
    #[zbus(name = "syncState")]
    async fn sync_state(&self, payload_json: String) {
        if payload_json.len() > 5 * 1024 * 1024 {
            eprintln!("[DBUS ERROR] Payload descartado: excede el límite de 5MB.");
            return;
        }

        static LAST_SYNC: AtomicU64 = AtomicU64::new(0);
        static CIRCUIT_BREAKER: AtomicU64 = AtomicU64::new(0);

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);

        if now < CIRCUIT_BREAKER.load(Ordering::Relaxed) {
            if let Ok(mut last_payload) = self.last_payload_json.try_lock() {
                *last_payload = payload_json;
            }
            return;
        }

        if now - LAST_SYNC.load(Ordering::Relaxed) < 32 {
            if let Ok(mut last_payload) = self.last_payload_json.try_lock() {
                *last_payload = payload_json;
            }
            return;
        }

        LAST_SYNC.store(now, Ordering::Relaxed);

        let controller_clone = Arc::clone(&self.controller);
        let pending_clone = Arc::clone(&self.pending_commands);
        let payload_clone = Arc::clone(&self.last_payload_json);
        let topology_clone = Arc::clone(&self.current_topology);

        self.tokio_handle.spawn(async move {
            *(payload_clone.lock().await) = payload_json.clone();

            let (workspaces, windows, topology) = match parse_payload(&payload_json) {
                Ok(p) => p,
                Err(_) => return,
            };

            *(topology_clone.lock().await) = topology;

            let mut ctrl = controller_clone.lock().await;
            match ctrl.handle_state_change(workspaces, windows) {
                Ok(commands) => {
                    let mut queue = pending_clone.lock().await;

                    if queue.len() > 150 {
                        eprintln!(
                            "[CIRCUIT BREAKER] Tormenta detectada. Abriendo circuito por 1000ms."
                        );
                        queue.clear();
                        let future_time = SystemTime::now()
                            .duration_since(UNIX_EPOCH)
                            .map(|d| d.as_millis() as u64)
                            .unwrap_or(0)
                            + 1000;
                        CIRCUIT_BREAKER.store(future_time, Ordering::Relaxed);
                        return;
                    }

                    let dbus_commands: Vec<TilingCommand> =
                        commands.into_iter().map(Into::into).collect();
                    queue.extend(dbus_commands);
                }
                Err(e) => {
                    eprintln!("[ENGINE ERROR] Fallo al procesar cambio de estado: {}", e);
                }
            }
        });
    }

    /// Sincronización Diferencial: Actualiza solo una ventana específica
    #[zbus(name = "syncWindowDelta")]
    async fn sync_window_delta(&self, delta_json: String) {
        let controller_clone = Arc::clone(&self.controller);
        let pending_clone = Arc::clone(&self.pending_commands);

        self.tokio_handle.spawn(async move {
            if let Ok(win) = serde_json::from_str::<KWinWindow>(&delta_json) {
                let win_node = WindowNode::new(
                    win.id,
                    win.ws,
                    win.output,
                    win.desktops,
                    win.f,
                    win.m,
                    win.p,
                    Rect::new(win.x, win.y, win.w, win.h),
                    win.min_w,
                    win.min_h,
                    win.sb,
                );

                let mut ctrl = controller_clone.lock().await;
                match ctrl.handle_delta_change(win_node) {
                    Ok(commands) => {
                        let mut queue = pending_clone.lock().await;
                        let dbus_commands: Vec<TilingCommand> =
                            commands.into_iter().map(Into::into).collect();
                        queue.extend(dbus_commands);
                    }
                    Err(e) => {
                        eprintln!("[ENGINE ERROR] Fallo al procesar delta change: {}", e);
                    }
                }
            }
        });
    }

    /// Notifica que el bridge está listo para operar (handshake inicial).
    /// Limpia comandos pendientes y resetea el estado del controlador.
    #[zbus(name = "bridgeReady")]
    async fn bridge_ready(&self) {
        self.pending_commands.lock().await.clear();
        self.last_payload_json.lock().await.clear();
        let mut ctrl = self.controller.lock().await;
        ctrl.reset_state();
    }

    /// Retorna y limpia la cola de comandos pendientes.
    ///
    /// KWin llama a este método periódicamente para aplicar los cambios de
    /// geometría calculados por el motor de Raven.
    #[zbus(name = "getPendingCommands")]
    async fn get_pending_commands(&self) -> String {
        let mut queue = self.pending_commands.lock().await;
        if queue.is_empty() {
            return String::from("[]");
        }

        let cmds = queue.drain(..).collect::<Vec<_>>();
        serde_json::to_string(&cmds).unwrap_or_else(|e| {
            eprintln!(
                "[DBUS ERROR] Fallo al serializar comandos pendientes: {}",
                e
            );
            String::from("[]")
        })
    }

    /// Actualiza el registro de la ventana activa en el motor.
    #[zbus(name = "windowActivated")]
    async fn window_activated(&self, window_id: String) {
        if window_id.trim().is_empty() {
            return;
        }
        *self.active_window_id.lock().await = Some(window_id);
    }

    /// Habilita o deshabilita globalmente el motor de mosaico.
    #[zbus(name = "toggleTiling")]
    async fn toggle_tiling(&self) {
        self.dispatch_shortcut("toggle_tiling", 0).await;
    }

    /// Incrementa o decrementa los márgenes (gaps) entre ventanas.
    #[zbus(name = "incrementGaps")]
    async fn increment_gaps(&self, amount: i32) {
        self.dispatch_shortcut("increment_gaps", amount).await;
    }

    /// Incrementa el número de ventanas maestras.
    #[zbus(name = "incrementMaster")]
    async fn increment_master(&self) {
        self.dispatch_shortcut("increment_master", 0).await;
    }

    /// Decrementa el número de ventanas maestras.
    #[zbus(name = "decrementMaster")]
    async fn decrement_master(&self) {
        self.dispatch_shortcut("decrement_master", 0).await;
    }

    /// Aumenta la proporción del área maestra.
    #[zbus(name = "increaseRatio")]
    async fn increase_ratio(&self) {
        self.dispatch_shortcut("increase_ratio", 0).await;
    }

    /// Disminuye la proporción del área maestra.
    #[zbus(name = "decreaseRatio")]
    async fn decrease_ratio(&self) {
        self.dispatch_shortcut("decrease_ratio", 0).await;
    }

    /// Mueve el foco a la siguiente ventana en el stack.
    #[zbus(name = "focusNext")]
    async fn focus_next(&self) {
        self.dispatch_shortcut("focus_next", 0).await;
    }

    /// Mueve el foco a la ventana anterior en el stack.
    #[zbus(name = "focusPrev")]
    async fn focus_prev(&self) {
        self.dispatch_shortcut("focus_prev", 0).await;
    }

    /// Envía manualmente la ventana activa al siguiente monitor.
    #[zbus(name = "migrateActiveToScreen")]
    async fn migrate_active_to_screen(&self) {
        self.dispatch_shortcut("migrate_active_to_screen", 0).await;
    }

    /// Envía manualmente la ventana activa al monitor anterior.
    #[zbus(name = "migrateActiveToPrevScreen")]
    async fn migrate_active_to_prev_screen(&self) {
        self.dispatch_shortcut("migrate_active_to_prev_screen", 0)
            .await;
    }

    /// Envía manualmente la ventana activa al siguiente escritorio virtual.
    #[zbus(name = "migrateActiveToDesktop")]
    async fn migrate_active_to_desktop(&self) {
        self.dispatch_shortcut("migrate_active_to_desktop", 0).await;
    }

    /// Envía manualmente la ventana activa al escritorio virtual anterior.
    #[zbus(name = "migrateActiveToPrevDesktop")]
    async fn migrate_active_to_prev_desktop(&self) {
        self.dispatch_shortcut("migrate_active_to_prev_desktop", 0)
            .await;
    }

    /// Consulta el estado actual del motor.
    #[zbus(name = "getTilingState")]
    async fn get_tiling_state(&self) -> bool {
        let ctrl = self.controller.lock().await;
        ctrl.is_tiling_enabled()
    }

    /// Cuenta la cantidad de monitores (pantallas) conectados en la topología.
    #[zbus(name = "getMonitorCount")]
    async fn get_monitor_count(&self) -> i32 {
        let topo = self.current_topology.lock().await;
        if !topo.outputs.is_empty() {
            topo.outputs.len() as i32
        } else {
            1
        }
    }

    /// Cuenta la cantidad de escritorios virtuales activos en la topología.
    #[zbus(name = "getDesktopCount")]
    async fn get_desktop_count(&self) -> i32 {
        let topo = self.current_topology.lock().await;
        if !topo.desktops.is_empty() {
            topo.desktops.len() as i32
        } else {
            1
        }
    }
}

impl RavenDBusService {
    /// Enruta atajos de teclado hacia el controlador y gestiona recálculos necesarios.
    async fn dispatch_shortcut(&self, action: &str, payload: i32) {
        let payload_json = self.last_payload_json.lock().await.clone();

        if payload_json.is_empty() && action != "toggle_tiling" {
            eprintln!(
                "[DBUS WARN] Ignorando atajo '{}' por falta de estado del compositor.",
                action
            );
            return;
        }

        let active_id = self.active_window_id.lock().await.clone();
        let (workspaces, parsed_windows, _topology) =
            parse_payload(&payload_json).unwrap_or_else(|_| (HashMap::new(), Vec::new(), KWinTopology::default()));

        let mut ctrl = self.controller.lock().await;
        match ctrl.handle_shortcut(
            action.to_string(),
            payload,
            parsed_windows,
            workspaces,
            active_id,
        ) {
            Ok((needs_recalc, cmds)) => {
                let mut queue = self.pending_commands.lock().await;
                if queue.len() > 200 {
                    queue.clear();
                }
                let dbus_commands: Vec<TilingCommand> = cmds.into_iter().map(Into::into).collect();
                queue.extend(dbus_commands);

                if needs_recalc {
                    if let Ok((workspaces, windows, _topology)) = parse_payload(&payload_json) {
                        match ctrl.handle_state_change(workspaces, windows) {
                            Ok(recalc_cmds) => {
                                let recalc_dbus_cmds: Vec<TilingCommand> =
                                    recalc_cmds.into_iter().map(Into::into).collect();
                                queue.extend(recalc_dbus_cmds);
                            }
                            Err(e) => eprintln!(
                                "[ENGINE ERROR] Fallo al recalcular estado tras atajo: {}",
                                e
                            ),
                        }
                    }
                }
            }
            Err(e) => {
                eprintln!("[ENGINE ERROR] Error al procesar atajo {}: {}", action, e);
            }
        }
    }
}
