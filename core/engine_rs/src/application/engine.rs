
use serde::Deserialize;
use std::collections::HashMap;

use crate::infrastructure::config::RavenConfig;
use crate::domain::geometry::{Rect, WindowNode};
use crate::domain::layout::calculate_global_topology;

/// Estructuras internas para la deserialización de datos provenientes de KWin.
#[derive(Debug, Deserialize)]
struct KWinScreen {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

#[derive(Debug, Deserialize)]
struct KWinWindow {
    pub id: String,
    pub ws: String,
    pub f: bool,
    pub m: bool,
    pub p: bool,
}

/// Representa la carga útil (payload) completa enviada por el script de KWin.
#[derive(Debug, Deserialize)]
struct KWinPayload {
    pub windows: Vec<KWinWindow>,
    pub screens: HashMap<String, KWinScreen>,
}

/// El núcleo lógico del motor de mosaico (Tiling Engine).
/// 
/// Esta estructura mantiene el estado global del motor, incluyendo su configuración
/// activa y si el modo de mosaico está habilitado para el usuario actual.
pub struct TilingEngine {
    /// Configuración de preferencias (gaps, ratios, etc.).
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

    /// Procesa un payload JSON de KWin y calcula la nueva disposición de ventanas.
    /// 
    /// Este método deserializa la información del sistema (ventanas y pantallas),
    /// la convierte a estructuras internas de Raven y ejecuta el algoritmo de 
    /// topología global para determinar las nuevas posiciones.
    /// 
    /// # Parámetros
    /// * `payload_json` - Cadena JSON cruda enviada por el adaptador de KWin.
    /// 
    /// # Retorno
    /// Un `Result` que contiene un mapa de geometrías calculadas o un mensaje de error.
    pub fn calculate_from_payload(
        &self,
        payload_json: String,
    ) -> Result<HashMap<String, Rect>, String> {
        if !self.is_tiling_enabled || payload_json.is_empty() {
            return Ok(HashMap::new());
        }
        let config_clone = self.config.clone();
        let result = {
            let payload: KWinPayload = match serde_json::from_str(&payload_json) {
                Ok(p) => p,
                Err(_e) => return Ok(HashMap::new()),
            };
            let mut workspaces = HashMap::new();
            for (ws_id, screen) in payload.screens {
                workspaces.insert(ws_id, Rect::new(screen.x, screen.y, screen.w, screen.h));
            }
            let mut windows = Vec::with_capacity(payload.windows.len());
            for win in payload.windows {
                windows.push(WindowNode::new(win.id, win.ws, win.f, win.m, win.p));
            }

            calculate_global_topology(
                windows,
                workspaces,
                config_clone.nmaster,
                config_clone.master_ratio,
                config_clone.default_gaps,
                &config_clone.pip_position,
            )
        };
        Ok(result)
    }
}
