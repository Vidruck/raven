use pyo3::prelude::*;
use std::collections::HashMap;
use pyo3::wrap_pyfunction;

mod geometry;
mod layout;

use geometry::{Rect, WindowNode};

#[pyfunction]
fn calculate_layout(
    py: Python<'_>,
    windows: Vec<WindowNode>,
    screen_rect: Rect,
    nmaster: usize,
    master_ratio: f32,
    default_gaps: i32,
) -> PyResult<HashMap<String, Rect>> {
    let result = py.allow_threads(move || {
        layout::calculate_master_stack(
            windows,
            screen_rect,
            nmaster,
            master_ratio,
            default_gaps
        )
    });
    
    Ok(result)
}

#[pymodule]
fn raven_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rect>()?;
    m.add_class::<WindowNode>()?;
    m.add_function(wrap_pyfunction!(calculate_layout, m)?)?;
    Ok(())
}