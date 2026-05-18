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
#[allow(dead_code)]
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
    /// Historial de prioridad de ventanas visibles (para Pila LIFO estable).
    visible_windows_order: Vec<String>,
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
            visible_windows_order: Vec::new(),
        }
    }

    /// Resetea el estado interno de la caché y los registros de defensa.
    pub fn reset_state(&mut self) {
        self.last_known_layout.clear();
        self.flap_registry.clear();
        self.commanded_geometries.clear();
        self.pending_migrations.clear();
        self.visible_windows_order.clear();
        self.engine.current_workspaces.clear();
        self.engine.current_windows.clear();
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

    /// Procesa los cambios de estado reportados por el compositor para calcular
    /// y aplicar el layout correspondiente a las ventanas del sistema.
    /// 
    /// Filtra ventanas inestables mediante el registro de rebotes, organiza las
    /// ventanas de acuerdo con el historial cronológico y ejecuta la lógica de
    /// resiliencia en cascada para cualquier ventana desalojada.
    /// 
    /// # Parámetros
    /// * `workspaces` - Colección de áreas de trabajo físicas y virtuales.
    /// * `windows` - Listado de nodos de ventana a diagramar.
    /// 
    /// # Retornos
    /// Lista de acciones de dominio a ejecutar por la infraestructura de KWin.
    pub fn handle_state_change(
        &mut self, 
        workspaces: HashMap<String, Rect>,
        windows: Vec<WindowNode>
    ) -> Result<Vec<RavenAction>, RavenError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);

        self.engine.current_workspaces = workspaces.clone();
        self.engine.current_windows = windows.iter().map(|w| (w.window_id.clone(), w.clone())).collect();

        self.engine.update_history(&windows);

        let mut healthy_windows = Vec::new();
        for win in windows {
            if !self.is_window_flapping(&win.window_id) {
                healthy_windows.push(win);
            }
        }
        let mut windows = healthy_windows;

        windows.sort_by_key(|w| {
            let is_strict = w.min_w > 0 || w.min_h > 0;
            let pos = self.engine.window_history.iter().position(|id| id == &w.window_id).unwrap_or(usize::MAX);
            (!is_strict, std::cmp::Reverse(pos))
        });

        let (new_layout, evicted_windows) = self.engine.calculate_from_payload(workspaces.clone(), windows.clone())?;

        let mut commands = Vec::new();
        for (wid, rect) in &new_layout {
            let needs_move = match self.last_known_layout.get(wid) {
                Some(old_rect) => old_rect != rect,
                None => true,
            };

            if needs_move {
                commands.push(RavenAction::MoveWindow {
                    window_id: wid.clone(),
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                });
                
                // Si la ventana es estricta y recién nacida, solicitamos rectificación
                if let Some(win_node) = windows.iter().find(|w| &w.window_id == wid) {
                    if win_node.strict_birth {
                        commands.push(RavenAction::RequestFeedback {
                            window_id: wid.clone(),
                        });
                    }
                }
            }

            self.commanded_geometries.insert(wid.clone(), CommandedGeometry {
                rect: *rect,
                timestamp: now,
            });
        }

        for evicted_id in &evicted_windows {
            if let Some(win_node) = windows.iter().find(|w| &w.window_id == evicted_id) {
                let mut outputs = Vec::new();
                for key in workspaces.keys() {
                    if let Some(out) = key.split("||").next() {
                        let out_str = out.to_string();
                        if !outputs.contains(&out_str) {
                            outputs.push(out_str);
                        }
                    }
                }

                if outputs.len() > 1 && outputs.iter().any(|o| o != &win_node.output) {
                    if let Some(target_out) = outputs.iter().find(|&o| o != &win_node.output) {
                        println!("[TOPOLOGY] Ventana {} desalojada. Migrando a monitor secundario: {}.", evicted_id, target_out);
                        commands.push(RavenAction::MigrateToOutput {
                            window_id: evicted_id.clone(),
                            target_output: target_out.clone(),
                        });
                        continue;
                    }
                }

                let mut desktops = Vec::new();
                for key in workspaces.keys() {
                    let mut parts = key.split("||");
                    if let (Some(out), Some(desk)) = (parts.next(), parts.next()) {
                        if out == win_node.output {
                            let desk_str = desk.to_string();
                            if !desktops.contains(&desk_str) {
                                desktops.push(desk_str);
                            }
                        }
                    }
                }

                let current_desk = win_node.desktops.first().cloned().unwrap_or_default();
                if desktops.len() > 1 && desktops.iter().any(|d| d != &current_desk) {
                    if let Some(target_desk) = desktops.iter().find(|&d| d != &current_desk) {
                        println!("[TOPOLOGY] Ventana {} desalojada. Migrando a escritorio virtual secundario: {}.", evicted_id, target_desk);
                        commands.push(RavenAction::MigrateToDesktop {
                            window_id: evicted_id.clone(),
                            target_desktop: target_desk.clone(),
                        });
                        continue;
                    }
                }

                println!("[TOPOLOGY] Ventana {} desalojada sin escape. Minimizando en pila local.", evicted_id);
                commands.push(RavenAction::MinimizeWindow {
                    window_id: evicted_id.clone(),
                });
            }
        }


        self.last_known_layout = new_layout;
        Ok(commands)
    }

    /// Procesa una actualizacion diferencial de una ventana especifica (Delta Sync).
    pub fn handle_delta_change(&mut self, win: WindowNode) -> Result<Vec<RavenAction>, RavenError> {
        self.engine.current_windows.insert(win.window_id.clone(), win);

        let workspaces = self.engine.current_workspaces.clone();
        let windows: Vec<WindowNode> = self.engine.current_windows.values().cloned().collect();

        self.handle_state_change(workspaces, windows)
    }

    /// Procesa una acción disparada por un atajo de teclado del usuario.
    /// 
    /// Actualiza la configuración interna del motor y determina si es necesario
    /// realizar un recálculo masivo del layout.
    /// 
    /// # Parámetros
    /// * `action` - Nombre de la acción de atajo solicitada.
    /// * `payload` - Modificador de la acción.
    /// * `windows` - Lista de ventanas actuales del dominio.
    /// * `_workspaces` - Mapa de espacios de trabajo del sistema.
    /// * `active_window_id` - ID de la ventana activa enfocada.
    /// 
    /// # Retornos
    /// Tupla con indicador de recálculo necesario y listado de acciones a disparar.
    pub fn handle_shortcut(
        &mut self,
        action: String,
        payload: i32,
        windows: Vec<WindowNode>,
        _workspaces: HashMap<String, Rect>,
        active_window_id: Option<String>
    ) -> Result<(bool, Vec<RavenAction>), RavenError> {
        self.engine.update_history(&windows);

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
                    if let Some(win_node) = windows.iter().find(|w| &w.window_id == wid) {
                        let is_desktop = action.contains("desktop");
                        if is_desktop {
                            let mut desktops = Vec::new();
                            for key in _workspaces.keys() {
                                let mut parts = key.split("||");
                                if let (Some(out), Some(desk)) = (parts.next(), parts.next()) {
                                    if out == win_node.output {
                                        let desk_str = desk.to_string();
                                        if !desktops.contains(&desk_str) {
                                            desktops.push(desk_str);
                                        }
                                    }
                                }
                            }
                            let current_desk = win_node.desktops.first().cloned().unwrap_or_default();
                            if let Some(target_desk) = desktops.iter().find(|&d| d != &current_desk) {
                                commands.push(RavenAction::MigrateToDesktop {
                                    window_id: wid.clone(),
                                    target_desktop: target_desk.clone(),
                                });
                            }
                        } else {
                            let mut outputs = Vec::new();
                            for key in _workspaces.keys() {
                                if let Some(out) = key.split("||").next() {
                                    let out_str = out.to_string();
                                    if !outputs.contains(&out_str) {
                                        outputs.push(out_str);
                                    }
                                }
                            }
                            if let Some(target_out) = outputs.iter().find(|&o| o != &win_node.output) {
                                commands.push(RavenAction::MigrateToOutput {
                                    window_id: wid.clone(),
                                    target_output: target_out.clone(),
                                });
                            }
                        }
                    }
                }
            },
            _ => {}
        }

        Ok((needs_recalc, commands))
    }
}