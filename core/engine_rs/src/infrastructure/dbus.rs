use std::sync::Arc;
use tokio::sync::Mutex;
use zbus::interface;
use serde::Serialize;

use crate::application::controller::RavenController;

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
}

/// Punto de entrada para las señales y métodos de DBus.
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
}

#[interface(name = "org.kde.raven.Events")]
impl RavenDBusService {
    /// Sincroniza el estado masivo del compositor.
    /// 
    /// Este método es llamado por KWin cada vez que ocurre un cambio estructural
    /// en las ventanas (creación, cierre, movimiento manual).
    #[zbus(name = "syncState")]
    async fn sync_state(&self, payload_json: String) {
        *self.last_payload_json.lock().await = payload_json.clone();
        
        let mut ctrl = self.controller.lock().await;
        if let Ok(commands) = ctrl.handle_state_change(payload_json) {
            let mut queue = self.pending_commands.lock().await;
            queue.extend(commands);
        }
    }

    /// Retorna y limpia la cola de comandos pendientes.
    /// 
    /// KWin llama a este método periódicamente (polling) o tras señales para
    /// aplicar los cambios de geometría calculados por el motor Rust.
    #[zbus(name = "getPendingCommands")]
    async fn get_pending_commands(&self) -> String {
        let mut queue = self.pending_commands.lock().await;
        if queue.is_empty() {
            return String::from("[]");
        }
        
        let cmds = queue.drain(..).collect::<Vec<_>>();
        serde_json::to_string(&cmds).unwrap_or_else(|_| String::from("[]"))
    }

    /// Actualiza el registro de la ventana activa en el motor.
    #[zbus(name = "windowActivated")]
    async fn window_activated(&self, window_id: String) {
        *self.active_window_id.lock().await = Some(window_id);
    }

    /// Habilita o deshabilita globalmente el motor de mosaico.
    #[zbus(name = "toggleTiling")]
    async fn toggle_tiling(&self) { self.dispatch_shortcut("toggle_tiling", 0).await; }

    /// Incrementa o decrementa los márgenes (gaps) entre ventanas.
    #[zbus(name = "incrementGaps")]
    async fn increment_gaps(&self, amount: i32) { self.dispatch_shortcut("increment_gaps", amount).await; }

    /// Incrementa el número de ventanas maestras.
    #[zbus(name = "incrementMaster")]
    async fn increment_master(&self) { self.dispatch_shortcut("increment_master", 0).await; }

    /// Decrementa el número de ventanas maestras.
    #[zbus(name = "decrementMaster")]
    async fn decrement_master(&self) { self.dispatch_shortcut("decrement_master", 0).await; }

    /// Aumenta la proporción del área maestra.
    #[zbus(name = "increaseRatio")]
    async fn increase_ratio(&self) { self.dispatch_shortcut("increase_ratio", 0).await; }

    /// Disminuye la proporción del área maestra.
    #[zbus(name = "decreaseRatio")]
    async fn decrease_ratio(&self) { self.dispatch_shortcut("decrease_ratio", 0).await; }

    /// Mueve el foco a la siguiente ventana en el stack.
    #[zbus(name = "focusNext")]
    async fn focus_next(&self) { self.dispatch_shortcut("focus_next", 0).await; }

    /// Mueve el foco a la ventana anterior en el stack.
    #[zbus(name = "focusPrev")]
    async fn focus_prev(&self) { self.dispatch_shortcut("focus_prev", 0).await; }

    /// Consulta el estado actual del motor.
    #[zbus(name = "getTilingState")]
    async fn get_tiling_state(&self) -> bool {
        let ctrl = self.controller.lock().await;
        ctrl.is_tiling_enabled() 
    }
}

impl RavenDBusService {
    /// Enruta atajos de teclado hacia el controlador y gestiona recálculos necesarios.
    async fn dispatch_shortcut(&self, action: &str, payload: i32) {
        let payload_json = self.last_payload_json.lock().await.clone();
        let active_id = self.active_window_id.lock().await.clone();
        
        let mut ctrl = self.controller.lock().await;
        if let Ok((needs_recalc, cmds)) = ctrl.handle_shortcut(action.to_string(), payload, payload_json.clone(), active_id) {
            let mut queue = self.pending_commands.lock().await;
            queue.extend(cmds);
            
            if needs_recalc {
                if let Ok(recalc_cmds) = ctrl.handle_state_change(payload_json) {
                    queue.extend(recalc_cmds);
                }
            }
        }
    }
}