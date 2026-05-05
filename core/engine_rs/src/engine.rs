use pyo3::prelude::*;
use serde::Deserialize;
use std::collections::HashMap;

use crate::config::RavenConfig;
use crate::geometry::{Rect, WindowNode};
use crate::layout::calculate_global_topology;

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
#[derive(Debug, Deserialize)]
struct KWinPayload {
    pub windows: Vec<KWinWindow>,
    pub screens: HashMap<String, KWinScreen>,
}
#[pyclass(module = "raven_core_rs", get_all, set_all)]
pub struct TilingEngine {
    pub config: RavenConfig,
    pub is_tiling_enabled: bool,
}
#[pymethods]
impl TilingEngine {
    #[new]
    pub fn new(config: RavenConfig) -> Self {
        let is_tiling_enabled = config.tiling_enabled_on_startup;
        TilingEngine {
            config,
            is_tiling_enabled,
        }
    }
    pub fn toggle_tiling(&mut self) -> bool {
        self.is_tiling_enabled = !self.is_tiling_enabled;
        self.is_tiling_enabled
    }
    pub fn calculate_from_payload(
        &self,
        py: Python<'_>,
        payload_json: String,
    ) -> PyResult<HashMap<String, Rect>> {
        if !self.is_tiling_enabled || payload_json.is_empty() {
            return Ok(HashMap::new());
        }
        let config_clone = self.config.clone();
        let result = py.allow_threads(move || {
            let payload: KWinPayload = match serde_json::from_str(&payload_json) {
                Ok(p) => p,
                Err(_e) => return HashMap::new(),
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
        });
        Ok(result)
    }
}
