use pyo3::prelude::*;

#[pyclass(module = "raven_core_rs", get_all, set_all)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

#[pymethods]
impl Rect {
    #[new]
    pub fn new(x: i32, y: i32, width: i32, height: i32) -> Self {
        Rect { x, y, width, height }
    }
}

#[pyclass(module = "raven_core_rs", get_all, set_all)]
#[derive(Clone, Debug)]
pub struct WindowNode {
    pub window_id: String,
    pub workspace_id: String,
    pub is_floating: bool,
    pub is_minimized: bool,
    pub is_pip: bool,
}

#[pymethods]
impl WindowNode {
    #[new]
    pub fn new(window_id: String, workspace_id: String, is_floating: bool, is_minimized: bool, is_pip: bool) -> Self {
        WindowNode { window_id, workspace_id, is_floating, is_minimized, is_pip }
    }
}