use pyo3::prelude::*;

mod geometry;
mod layout;
mod config;
mod engine;

use config::RavenConfig;
use geometry::{Rect, WindowNode, Workspace};
use engine::TilingEngine;

#[pymodule]
fn raven_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rect>()?;
    m.add_class::<WindowNode>()?;
    m.add_class::<Workspace>()?;
    m.add_class::<RavenConfig>()?;
    m.add_class::<TilingEngine>()?;
    Ok(())
}