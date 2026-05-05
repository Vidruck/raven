/// Motor principal (Core Engine) nativo en Rust para el cálculo de topologías de ventanas.
/// Este módulo se compila como una librería dinámica (extensión de Python) a través de PyO3.
use pyo3::prelude::*;
use std::collections::HashMap;
use serde::Deserialize;

mod geometry;
mod layout;
mod config;

use config::RavenConfig;

use geometry::{Rect, WindowNode, Workspace};

/// Representa una pantalla o monitor de KWin con sus dimensiones y coordenadas físicas.
#[derive(Debug, Deserialize)]
pub struct KWinScreen { pub x: i32, pub y: i32, pub w: i32, pub h: i32 }

/// Representa el estado y metadatos de una ventana gestionada por KWin.
/// Contiene su identificador (`id`), el espacio de trabajo asociado (`ws`), 
/// y los flags de estado: flotante (`f`), minimizada (`m`) y picture-in-picture (`p`).
#[derive(Debug, Deserialize)]
pub struct KWinWindow { pub id: String, pub ws: String, pub f: bool, pub m: bool, pub p: bool }

/// Estructura de carga útil (payload) que representa el estado completo emitido por KWin.
/// Contiene una lista de ventanas y un mapa de las pantallas disponibles.
#[derive(Debug, Deserialize)]
pub struct KWinPayload {
    pub windows: Vec<KWinWindow>,
    pub screens: HashMap<String, KWinScreen>,
}

/// Calcula la disposición espacial (layout) de todas las ventanas a partir de un JSON atómico.
/// Transforma el estado crudo (payload_json) de KWin y devuelve un mapa asociando cada 
/// `window_id` con sus nuevas coordenadas calculadas (`Rect`).
#[pyfunction]
fn compute_layout_from_json(
    py: Python<'_>,
    payload_json: String,
    nmaster: usize,
    master_ratio: f32,
    default_gaps: i32,
    pip_position: String,
) -> PyResult<HashMap<String, Rect>> {
    
    let result = py.allow_threads(move || {
        let payload: KWinPayload = match serde_json::from_str(&payload_json) {
            Ok(p) => p,
            Err(_) => return HashMap::new(),
        };

        let mut workspaces = HashMap::new();
        for (ws_id, screen) in payload.screens {
            workspaces.insert(ws_id, Rect::new(screen.x, screen.y, screen.w, screen.h));
        }

        let mut windows = Vec::with_capacity(payload.windows.len());
        for win in payload.windows {
            windows.push(geometry::WindowNode::new(win.id, win.ws, win.f, win.m, win.p));
        }

        layout::calculate_global_topology(
            windows,
            workspaces,
            nmaster,
            master_ratio,
            default_gaps,
            &pip_position
        )
    });
    
    Ok(result)
}

/// Inicialización del módulo de extensión para Python llamado `raven_core_rs`.
/// Expone las clases de geometría (`Rect`) y las funciones de cálculo espacial.
#[pymodule]
fn raven_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rect>()?;
    m.add_class::<WindowNode>()?;
    m.add_class::<Workspace>()?;
    m.add_class::<RavenConfig>()?;
    m.add_function(wrap_pyfunction!(compute_layout_from_json,m)?)?;
    Ok(())
}