use std::collections::{HashMap, VecDeque};

use crate::infrastructure::config::RavenConfig;
use crate::domain::geometry::{Rect, WindowNode};
use crate::domain::layout::calculate_global_topology;
use crate::domain::error::RavenError;

/// El núcleo lógico del motor de mosaico (Tiling Engine).
/// 
/// Mantiene la configuración activa, el estado global de habilitación y
/// el historial cronológico de ventanas utilizado en la evicción FIFO.
pub struct TilingEngine {
    pub config: RavenConfig,
    pub is_tiling_enabled: bool,
    pub window_history: VecDeque<String>, 
    pub current_workspaces: HashMap<String, Rect>,
    pub current_windows: HashMap<String, WindowNode>,
}

impl TilingEngine {
    pub fn new(config: RavenConfig) -> Self {
        TilingEngine {
            is_tiling_enabled: config.tiling_enabled_on_startup,
            config,
            window_history: VecDeque::new(),
            current_workspaces: HashMap::new(),
            current_windows: HashMap::new(),
        }
    }

    /// Alterna el estado operativo del motor de mosaico.
    /// 
    /// # Retorno
    /// El nuevo estado del motor tras la alternancia.
    pub fn toggle_tiling(&mut self) -> bool {
        self.is_tiling_enabled = !self.is_tiling_enabled;
        self.is_tiling_enabled
    }

    /// Calcula la nueva disposición de ventanas basándose en el estado del dominio.
    /// 
    /// Ejecuta el algoritmo de topología global para determinar las nuevas 
    /// posiciones y dimensiones de cada ventana según la configuración actual.
    /// 
    /// # Parámetros
    /// * `workspaces` - Mapa de áreas de trabajo disponibles.
    /// * `windows` - Listado de nodos de ventana a organizar.
    /// 
    /// # Retorno
    /// Un `Result` con una tupla que contiene el mapa de geometrías calculadas y la lista de ventanas desalojadas, o un error de dominio.
    pub fn calculate_from_payload(
        &self,
        workspaces: HashMap<String, Rect>,
        windows: Vec<WindowNode>,
    ) -> Result<(HashMap<String, Rect>, Vec<String>), RavenError> {
        if !self.is_tiling_enabled || windows.is_empty() {
            return Ok((HashMap::new(), Vec::new()));
        }
        let config_clone = self.config.clone();
        
        let (layout_map, evicted_windows) = calculate_global_topology(
            windows,
            workspaces,
            config_clone.nmaster,
            config_clone.master_ratio,
            config_clone.default_gaps,
            &config_clone.pip_position,
        );
        Ok((layout_map, evicted_windows))
    }

    /// Sincroniza el historial cronológico interno con el estado del compositor.
    /// 
    /// Elimina de la memoria aquellas ventanas destruidas o cerradas en el compositor
    /// y registra las nuevas ventanas visibles (no flotantes) al final de la cola FIFO.
    /// 
    /// # Parámetros
    /// * `current_windows` - Estado actual de ventanas activas reportadas por el compositor.
    pub fn update_history(&mut self, current_windows: &[WindowNode]) {
        self.window_history.retain(|id| current_windows.iter().any(|w| &w.window_id == id));

        for win in current_windows {
            if !self.window_history.contains(&win.window_id) && !win.is_floating {
                self.window_history.push_back(win.window_id.clone());
            }
        }
    }
}
