use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::application::engine::TilingEngine;
use crate::domain::geometry::{Rect, WindowNode};
use crate::domain::action::RavenAction;
use crate::domain::error::RavenError;

/// Realiza el seguimiento de ventanas que cambian de estado demasiado rápido.
/// Evita bucles infinitos de redibujado (flapping).
struct FlapTracker {
    /// Marca de tiempo del último cambio registrado.
    last_toggle_time: u64,
    /// Contador de cambios en un intervalo corto.
    toggle_count: u64,
    /// Indica si la ventana está actualmente penalizada.
    is_penalized: bool
}

/// Registro de la última geometría ordenada por Rust para una ventana.
struct CommandedGeometry {
    /// Dimensiones y posición enviadas.
    rect: Rect,
    /// Marca de tiempo del envío.
    timestamp: u64,
}

/// Orquestador principal de la lógica de Raven.
/// 
/// El `RavenController` actúa como puente entre la infraestructura IPC (D-Bus)
/// y el motor de cálculo matemático (`TilingEngine`). Se encarga de procesar
/// tanto los cambios de estado del sistema como las interacciones del usuario.
pub struct RavenController {
    /// Instancia del motor que realiza los cálculos de geometría.
    engine: TilingEngine,
    /// Caché del último layout aplicado para evitar comandos redundantes.
    last_known_layout: HashMap<String, Rect>,
    /// Registro para prevenir bucles infinitos de redibujado.
    flap_registry: HashMap<String, FlapTracker>,
    /// Registro de geometrías dictadas por el motor (anti-tormenta).
    commanded_geometries: HashMap<String, CommandedGeometry>,
    /// Cola de migraciones solicitadas por atajos que deben procesarse en el siguiente ciclo.
    pending_migrations: HashMap<String, String>,
}

impl RavenController {
    /// Crea un nuevo controlador vinculándolo a una instancia del motor.
    pub fn new(engine: TilingEngine) -> Self {
        RavenController { 
            engine,
            last_known_layout: HashMap::new(),
            flap_registry: HashMap::new(),
            commanded_geometries: HashMap::new(),
            pending_migrations: HashMap::new(),
        }
    }

    /// Resetea el estado interno de la caché y los registros de defensa.
    pub fn reset_state(&mut self) {
        self.last_known_layout.clear();
        self.flap_registry.clear();
        self.commanded_geometries.clear();
        self.pending_migrations.clear();
    }

    /// Indica si el motor de mosaico está habilitado actualmente.
    pub fn is_tiling_enabled(&self) -> bool {
        self.engine.is_tiling_enabled
    }

    /// Determina si una ventana debe ser ignorada temporalmente para evitar inestabilidad.
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
            if now - tracker.last_toggle_time > 400 {
                tracker.is_penalized = false;
                tracker.toggle_count = 0;
            } else {
                return true;
            }
        }

        if now - tracker.last_toggle_time < 400 {
            tracker.toggle_count += 1;
            if tracker.toggle_count > 8 {
                println!("[DEFENSA] Cortocircuito activado para ventana: {}. Ignorando.", window_id);
                tracker.is_penalized = true;
                tracker.last_toggle_time = now;
                return true;
            }
        } else {
            tracker.toggle_count = 1;
        }

        tracker.last_toggle_time = now;
        false
    }

    /// Maneja un cambio de estado masivo en el sistema (ventanas añadidas, movidas o cerradas).
    /// 
    /// Procesa el estado actual del compositor y genera una lista de acciones de 
    /// dominio para sincronizar KWin con la topología calculada.
    /// 
    /// # Parámetros
    /// * `workspaces` - Mapa de áreas de trabajo disponibles.
    /// * `windows` - Listado de nodos de ventana detectados.
    /// 
    /// # Retorno
    /// Un vector de `RavenAction` con las operaciones a realizar en la infraestructura.
    pub fn handle_state_change(
        &mut self, 
        workspaces: HashMap<String, Rect>,
        mut windows: Vec<WindowNode>
    ) -> Result<Vec<RavenAction>, RavenError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);

        // Guardar estado original de workspaces para detectar migraciones finales
        let original_ws: HashMap<String, String> = windows.iter()
            .map(|w| (w.window_id.clone(), w.workspace_id.clone()))
            .collect();

        // 1. Aplicar migraciones pendientes (de atajos)
        for win in &mut windows {
            if let Some(target) = self.pending_migrations.remove(&win.window_id) {
                win.workspace_id = target;
            }
        }

        for win in &windows {
            if self.is_window_flapping(&win.window_id) {
                return Ok(Vec::new());
            }

            if let Some(cmd_geom) = self.commanded_geometries.get(&win.window_id) {
                if now - cmd_geom.timestamp < 500 && win.geometry == cmd_geom.rect {
                    return Ok(Vec::new());
                }
            }
        }

        // 2. Cálculo inicial
        let mut new_layout = self.engine.calculate_from_payload(workspaces.clone(), windows.clone())?;
            
        // 3. Gestor de Topología: Detección de overflow y Recálculo Predictivo
        let mut needs_second_pass = false;
        let mut ws_ids: Vec<String> = workspaces.keys().cloned().collect();
        ws_ids.sort();

        for win in &mut windows {
            if !win.is_floating && !win.is_minimized && !win.is_pip {
                if !new_layout.contains_key(&win.window_id) {
                    if let Some(next_ws) = ws_ids.iter().find(|&id| id != &win.workspace_id) {
                        println!("[TOPOLOGY] Ventana {} overflow. Pre-migrando a {}.", win.window_id, next_ws);
                        win.workspace_id = next_ws.clone();
                        needs_second_pass = true;
                    }
                }
            }
        }

        if needs_second_pass {
            new_layout = self.engine.calculate_from_payload(workspaces, windows.clone())?;
        }

        // 4. Despacho Unificado
        let mut commands = Vec::new();
        for (wid, rect) in &new_layout {
            let current_win = windows.iter().find(|w| &w.window_id == wid).unwrap();
            let orig_ws = original_ws.get(wid).unwrap();
            
            if &current_win.workspace_id != orig_ws {
                // Comando transaccional MigrateAndMove
                commands.push(RavenAction::MigrateAndMove {
                    window_id: wid.clone(),
                    target_ws: current_win.workspace_id.clone(),
                    x: rect.x, y: rect.y, width: rect.width, height: rect.height
                });
            } else {
                let needs_move = match self.last_known_layout.get(wid) {
                    Some(old_rect) => old_rect != rect,
                    None => true,
                };

                if needs_move {
                    commands.push(RavenAction::MoveWindow {
                        window_id: wid.clone(),
                        x: rect.x, y: rect.y, width: rect.width, height: rect.height,
                    });
                }
            }

            self.commanded_geometries.insert(wid.clone(), CommandedGeometry {
                rect: *rect,
                timestamp: now,
            });
        }

        // 5. Gestión de rechazos (Overflow sin migración exitosa)
        for win in &windows {
            if !win.is_floating && !win.is_minimized && !win.is_pip {
                if !new_layout.contains_key(&win.window_id) {
                    println!("[TOPOLOGY] Ventana {} rechazada del layout. Minimizando.", win.window_id);
                    commands.push(RavenAction::MinimizeWindow {
                        window_id: win.window_id.clone(),
                    });
                }
            }
        }

        self.last_known_layout = new_layout;
        Ok(commands)
    }

    /// Procesa una acción disparada por un atajo de teclado del usuario.
    /// 
    /// Actualiza la configuración interna del motor y determina si es necesario
    /// realizar un recálculo masivo del layout.
    /// 
    /// # Parámetros
    /// * `action` - Nombre de la acción solicitada.
    /// * `payload` - Valor numérico asociado a la acción.
    /// * `windows` - Estado actual de las ventanas para contexto de navegación.
    /// * `active_window_id` - ID de la ventana con el foco actual.
    /// 
    /// # Retorno
    /// Una tupla indicando si requiere recálculo y la lista de acciones inmediatas.
    pub fn handle_shortcut(
        &mut self,
        action: String,
        payload: i32,
        windows: Vec<WindowNode>,
        _workspaces: HashMap<String, Rect>,
        active_window_id: Option<String>
    ) -> Result<(bool, Vec<RavenAction>), RavenError> {
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
                let active_windows: Vec<_> = windows.into_iter()
                    .filter(|w| !w.is_floating && !w.is_minimized && !w.is_pip)
                    .collect();

                if !active_windows.is_empty() {
                    let current_idx = active_windows.iter()
                        .position(|w| Some(&w.window_id) == active_window_id.as_ref())
                        .unwrap_or(0);

                    let step = if action == "focus_next" { 1 } else { active_windows.len() - 1 };
                    let next_idx = (current_idx + step) % active_windows.len();

                    commands.push(RavenAction::FocusWindow {
                        window_id: active_windows[next_idx].window_id.clone(),
                    });
                }
            },
            "migrate_active_to_screen" | "migrate_active_to_desktop" | "migrate_active_to_prev_screen" | "migrate_active_to_prev_desktop" => {
                if let Some(ref wid) = active_window_id {
                    let direction = match action.as_str() {
                        "migrate_active_to_screen" => "screen_next",
                        "migrate_active_to_prev_screen" => "screen_prev",
                        "migrate_active_to_desktop" => "desktop_next",
                        "migrate_active_to_prev_desktop" => "desktop_prev",
                        _ => "screen_next",
                    };
                    commands.push(RavenAction::MigrateNative {
                        window_id: wid.clone(),
                        direction: direction.to_string(),
                    });
                }
            },
            _ => {}
        }

        Ok((needs_recalc, commands))
    }
}