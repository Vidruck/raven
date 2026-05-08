use std::collections::HashMap;

use crate::infrastructure::config::RavenConfig;
use crate::domain::geometry::{Rect, WindowNode};
use crate::domain::layout::calculate_global_topology;
use crate::domain::error::RavenError;

/// El núcleo lógico del motor de mosaico (Tiling Engine).
/// 
/// Esta estructura mantiene el estado global del motor, incluyendo su configuración
/// activa y si el modo de mosaico está habilitado.
pub struct TilingEngine {
    /// Configuración de preferencias (márgenes, proporciones, etc.).
    pub config: RavenConfig,
    /// Estado operativo del motor.
    pub is_tiling_enabled: bool,
}

impl TilingEngine {
    /// Crea una nueva instancia del motor con la configuración proporcionada.
    /// 
    /// Al inicializarse, el motor respeta la preferencia de arranque definida
    /// en la configuración del usuario.
    pub fn new(config: RavenConfig) -> Self {
        let is_tiling_enabled = config.tiling_enabled_on_startup;
        TilingEngine {
            config,
            is_tiling_enabled,
        }
    }

    /// Alterna el estado de habilitación del motor de mosaico.
    /// 
    /// # Retorno
    /// El nuevo estado del motor después de la alternancia.
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
    /// Un `Result` con un mapa de geometrías calculadas o un error de dominio.
    pub fn calculate_from_payload(
        &self,
        workspaces: HashMap<String, Rect>,
        windows: Vec<WindowNode>,
    ) -> Result<HashMap<String, Rect>, RavenError> {
        if !self.is_tiling_enabled || windows.is_empty() {
            return Ok(HashMap::new());
        }
        let config_clone = self.config.clone();
        
        let result = calculate_global_topology(
            windows,
            workspaces,
            config_clone.nmaster,
            config_clone.master_ratio,
            config_clone.default_gaps,
            &config_clone.pip_position,
        );
        Ok(result)
    }
}
