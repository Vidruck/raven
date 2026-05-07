use serde::Deserialize;
use serde_json;
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::application::engine::TilingEngine;
use crate::infrastructure::dbus::TilingCommand; 
use crate::domain::geometry::Rect;

#[derive(Debug, Deserialize)]
struct KWinWindow { 
    pub id: String,
    #[serde(default)]
    pub f: bool, // floating
    #[serde(default)]
    pub m: bool, // maximized
    #[serde(default)]
    pub p: bool  // picture-in-picture
}

#[derive(Debug, Deserialize)]
struct KWinPayload { 
    #[serde(default)]
    pub windows: Vec<KWinWindow> 
}

struct FlapTracker {
    last_toggle_time: u64,
    toggle_count: u64,
    is_penalized: bool
}


/// Orquestador principal de la lógica de Raven.
/// 
/// El `RavenController` actúa como puente entre la infraestructura IPC (DBus)
/// y el motor de cálculo matemático (`TilingEngine`). Se encarga de procesar
/// tanto los cambios de estado del sistema como las interacciones del usuario
/// (atajos de teclado).
pub struct RavenController {
    /// Instancia del motor que realiza los cálculos de geometría.
    engine: TilingEngine,
    /// Caché del último layout aplicado para evitar comandos redundantes.
    last_known_layout: HashMap<String, Rect>,
    /// Registro para prevenir bucles infinitos de redibujado (flapping).
    flap_registry: HashMap<String, FlapTracker>,
}

impl RavenController {
    /// Crea un nuevo controlador vinculándolo a una instancia del motor.
    pub fn new(engine: TilingEngine) -> Self {
        RavenController { 
            engine,
            last_known_layout: HashMap::new(),
            flap_registry: HashMap::new(),
        }
    }

    /// Indica si el motor de tiling está habilitado actualmente.
    pub fn is_tiling_enabled(&self) -> bool {
        self.engine.is_tiling_enabled
    }

    fn is_window_flapping(&mut self, window_id: &str) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        
        let tracker = self.flap_registry.entry(window_id.to_string()).or_insert(FlapTracker {
            last_toggle_time: now,
            toggle_count: 0,
            is_penalized: false,
        });

        if tracker.is_penalized {
            if now - tracker.last_toggle_time > 2000 {
                tracker.is_penalized = false;
                tracker.toggle_count = 0;
            } else {
                return true;
            }
        }

        if now - tracker.last_toggle_time < 300 {
            tracker.toggle_count += 1;
            if tracker.toggle_count > 4 {
                println!("[DEFENSA] Cortocircuito activado para ventana: {}. Ignorando.", window_id);
                tracker.is_penalized = true;
                tracker.last_toggle_time = now;
                return true;
            }
        } else {
            tracker.toggle_count = 0;
        }

        tracker.last_toggle_time = now;
        false
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
        let payload: KWinPayload = match serde_json::from_str(&payload_json) {
            Ok(p) => p,
            Err(_) => return Ok(Vec::new()), 
        };

        for win in &payload.windows {
            if self.is_window_flapping(&win.id) {
                return Ok(Vec::new());
            }
        }

        let new_layout = self.engine.calculate_from_payload(payload_json)
            .map_err(|e| e.to_string())?;
            
        let mut commands = Vec::new();

        // [MIGRACIÓN] 1. Detectar ventanas huérfanas (desechadas por límite de área)
        for win in &payload.windows {
            // Solo evaluamos ventanas que teóricamente deberían haber entrado en el layout (no flotantes/min/pip)
            if !win.f && !win.m && !win.p {
                if !new_layout.contains_key(&win.id) {
                    println!("[CONTROLLER] Ventana {} desbordada. Solicitando migración automática.", win.id);
                    commands.push(TilingCommand {
                        action: "migrate_window_auto".to_string(),
                        window_id: Some(win.id.clone()),
                        x: None, y: None, width: None, height: None,
                    });
                }
            }
        }

        // 2. Comandos normales de movimiento para las ventanas que sí cupieron
        for (wid, rect) in &new_layout {
            let needs_move = match self.last_known_layout.get(wid) {
                Some(old_rect) => old_rect != rect,
                None => true,
            };

            if needs_move {
                commands.push(TilingCommand {
                    action: "move".to_string(),
                    window_id: Some(wid.clone()),
                    x: Some(rect.x),
                    y: Some(rect.y),
                    width: Some(rect.width),
                    height: Some(rect.height),
                });
            }
        }

        // Actualizamos nuestra caché maestra
        self.last_known_layout = new_layout;

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
                self.engine.config.nmaster = std::cmp::max(1usize, self.engine.config.nmaster.saturating_sub(1));
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
                        .filter(|w| !w.f && !w.m && !w.p)
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
            "migrate_active_to_screen" => {
                if let Some(ref wid) = active_window_id {
                    commands.push(TilingCommand {
                        action: "migrate_to_next_screen".to_string(),
                        window_id: Some(wid.clone()),
                        x: None, y: None, width: None, height: None,
                    });
                }
            },
            "migrate_active_to_desktop" => {
                if let Some(ref wid) = active_window_id {
                    commands.push(TilingCommand {
                        action: "migrate_to_next_workspace".to_string(),
                        window_id: Some(wid.clone()),
                        x: None, y: None, width: None, height: None,
                    });
                }
            },
            _ => {}
        }

        Ok((needs_recalc, commands))
    }
}