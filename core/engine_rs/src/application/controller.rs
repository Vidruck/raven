use serde::Deserialize;
use crate::application::engine::TilingEngine;
use crate::infrastructure::dbus::TilingCommand; 

#[derive(Debug, Deserialize)]
struct KWinWindow { pub id: String, pub f: bool, pub m: bool }

#[derive(Debug, Deserialize)]
struct KWinPayload { pub windows: Vec<KWinWindow> }

/// Orquestador principal de la lógica de Raven.
/// 
/// El `RavenController` actúa como puente entre la infraestructura IPC (DBus)
/// y el motor de cálculo matemático (`TilingEngine`). Se encarga de procesar
/// tanto los cambios de estado del sistema como las interacciones del usuario
/// (atajos de teclado).
pub struct RavenController {
    /// Instancia del motor que realiza los cálculos de geometría.
    engine: TilingEngine,
}

impl RavenController {
    /// Crea un nuevo controlador vinculándolo a una instancia del motor.
    pub fn new(engine: TilingEngine) -> Self {
        RavenController { engine }
    }

    /// Indica si el motor de mosaico está actualmente activo.
    pub fn is_tiling_enabled(&self) -> bool {
        self.engine.is_tiling_enabled
    }

    /// Maneja un cambio de estado masivo en el sistema (ventanas añadidas/movidas/cerradas).
    /// 
    /// Procesa el estado actual del compositor y genera una lista de comandos de 
    /// posicionamiento nativos para sincronizar KWin con la topología calculada.
    /// 
    /// # Parámetros
    /// * `payload_json` - Estado del sistema en formato JSON.
    /// 
    /// # Retorno
    /// Lista de comandos `TilingCommand` a ser ejecutados por el adaptador.
    pub fn handle_state_change(&mut self, payload_json: String) -> Result<Vec<TilingCommand>, String> {
        let layout = self.engine.calculate_from_payload(payload_json)
            .map_err(|e| e.to_string())?;
            
        let mut commands = Vec::new();

        for (wid, rect) in layout {
            commands.push(TilingCommand {
                action: "move".to_string(),
                window_id: Some(wid),
                x: Some(rect.x),
                y: Some(rect.y),
                width: Some(rect.width),
                height: Some(rect.height),
            });
        }
        Ok(commands)
    }

    /// Procesa una acción disparada por un atajo de teclado del usuario.
    /// 
    /// Actualiza la configuración interna del motor (ej. cambiar gaps o ratio)
    /// y determina si es necesario realizar un recálculo masivo del layout.
    /// 
    /// # Parámetros
    /// * `action` - Nombre de la acción ("toggle_tiling", "focus_next", etc.).
    /// * `payload` - Valor numérico asociado a la acción (ej. cantidad de cambio en gaps).
    /// * `payload_json` - Estado actual para cálculos que requieren contexto de ventanas.
    /// * `active_window_id` - ID de la ventana que tiene el foco actualmente.
    /// 
    /// # Retorno
    /// Una tupla conteniendo un booleano (si requiere recálculo) y una lista de comandos inmediatos.
    pub fn handle_shortcut(
        &mut self,
        action: String,
        payload: i32,
        payload_json: String,
        active_window_id: Option<String>
    ) -> Result<(bool, Vec<TilingCommand>), String> {
        let mut needs_recalc = false;
        let mut commands = Vec::new();

        match action.as_str() {
            "toggle_tiling" => { self.engine.toggle_tiling(); needs_recalc = true; },
            "increment_gaps" => {
                self.engine.config.default_gaps = std::cmp::max(0, self.engine.config.default_gaps + payload);
                needs_recalc = true;
            },
            "increment_master" => { self.engine.config.nmaster += 1; needs_recalc = true; },
            "decrement_master" => {
                self.engine.config.nmaster = std::cmp::max(1, self.engine.config.nmaster.saturating_sub(1));
                needs_recalc = true;
            },
            "increase_ratio" => {
                self.engine.config.master_ratio = f32::min(0.9, self.engine.config.master_ratio + 0.05);
                needs_recalc = true;
            },
            "decrease_ratio" => {
                self.engine.config.master_ratio = f32::max(0.1, self.engine.config.master_ratio - 0.05);
                needs_recalc = true;
            },
            "focus_next" | "focus_prev" => {
                if let Ok(kwin_payload) = serde_json::from_str::<KWinPayload>(&payload_json) {
                    let active_windows: Vec<_> = kwin_payload.windows.into_iter()
                        .filter(|w| !w.f && !w.m)
                        .collect();

                    if !active_windows.is_empty() {
                        let current_idx = active_windows.iter()
                            .position(|w| Some(&w.id) == active_window_id.as_ref())
                            .unwrap_or(0);

                        let step = if action == "focus_next" { 1 } else { active_windows.len() - 1 };
                        let next_idx = (current_idx + step) % active_windows.len();

                        commands.push(TilingCommand {
                            action: "focus".to_string(),
                            window_id: Some(active_windows[next_idx].id.clone()),
                            x: None, y: None, width: None, height: None,
                        });
                    }
                }
            },
            _ => {}
        }

        Ok((needs_recalc, commands))
    }
}