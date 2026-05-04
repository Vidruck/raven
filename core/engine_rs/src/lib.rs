//! # Raven Core (Motor en Rust)
//!
//! Este módulo es el corazón del motor de tiling de Raven. Proporciona las herramientas
//! fundamentales para calcular la disposición de las ventanas y gestionar su orden lógico,
//! optimizado para alto rendimiento mediante Rust y expuesto a Python mediante PyO3.

use pyo3::prelude::*;
use std::collections::HashMap;
use pyo3::wrap_pyfunction;

mod geometry;
mod layout;

use geometry::{Rect, WindowNode};

/// Calcula la topología global de las ventanas delegando al algoritmo en Rust.
///
/// # Argumentos
/// * `py` - Instancia del intérprete de Python (manejada automáticamente por PyO3).
/// * `windows` - Un vector de `WindowNode` que representa las ventanas a organizar.
/// * `workspaces` - Un `HashMap` con la geometría de cada escritorio (`Rect`).
/// * `nmaster` - Número de ventanas que se ubicarán en el área principal (Master).
/// * `master_ratio` - Porcentaje de la pantalla (0.0 a 1.0) que ocupará el área Master.
/// * `default_gaps` - Espaciado (gaps) en píxeles entre ventanas.
/// * `pip_position` - Posición configurada para ventanas Picture-in-Picture.
///
/// # Retorno
/// Retorna un `HashMap` donde la llave es el ID de la ventana y el valor es su nuevo `Rect`.
#[pyfunction]
fn calculate_global_topology(
    py: Python<'_>,
    windows: Vec<WindowNode>,
    workspaces: HashMap<String, Rect>,
    nmaster: usize,
    master_ratio: f32,
    default_gaps: i32,
    pip_position: String,
) -> PyResult<HashMap<String, Rect>> {
    
    let result = py.allow_threads(move || {
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

/// Punto de entrada para el módulo binario de Python `raven_core_rs`.
///
/// Define las clases y funciones que estarán disponibles al importar el módulo en Python.
#[pymodule]
fn raven_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rect>()?;
    m.add_class::<WindowNode>()?;
    m.add_function(wrap_pyfunction!(calculate_global_topology, m)?)?;
    Ok(())
}