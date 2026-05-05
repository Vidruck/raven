//! # Geometría y Estructuras de Datos
//!
//! Este submódulo define las estructuras de datos fundamentales utilizadas por el motor
//! para representar dimensiones de pantalla y propiedades de las ventanas.

use pyo3::prelude::*;

/// Representa un rectángulo en el espacio 2D de la pantalla.
///
/// Se utiliza para definir tanto el área total de la pantalla como el área
/// asignada a cada ventana después de calcular el layout.
#[pyclass(module = "raven_core_rs", get_all, set_all)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect {
    /// Posición en el eje X (horizontal).
    pub x: i32,
    /// Posición en el eje Y (vertical).
    pub y: i32,
    /// Ancho del rectángulo en píxeles.
    pub width: i32,
    /// Alto del rectángulo en píxeles.
    pub height: i32,
}

#[pymethods]
impl Rect {
    /// Crea una nueva instancia de Rect.
    #[new]
    pub fn new(x: i32, y: i32, width: i32, height: i32) -> Self {
        Rect { x, y, width, height }
    }
}

/// Representa una ventana y sus propiedades de estado dentro del motor.
#[pyclass(module = "raven_core_rs", get_all, set_all)]
#[derive(Clone, Debug)]
pub struct WindowNode {
    /// Identificador único de la ventana (usualmente el WID de X11 o KWin).
    pub window_id: String,
    /// Identificador del escritorio o actividad donde se encuentra la ventana.
    pub workspace_id: String,
    /// Indica si la ventana está en modo flotante.
    pub is_floating: bool,
    /// Indica si la ventana está minimizada.
    pub is_minimized: bool,
    /// Indica si la ventana está en modo Picture-in-Picture (PiP).
    pub is_pip: bool,
}

#[pymethods]
impl WindowNode {
    /// Crea una nueva instancia de WindowNode con sus propiedades iniciales.
    #[new]
    pub fn new(window_id: String, workspace_id: String, is_floating: bool, is_minimized: bool, is_pip: bool) -> Self {
        WindowNode { window_id, workspace_id, is_floating, is_minimized, is_pip }
    }
}

#[pyclass(module = "raven_core_rs", get_all, set_all)]
#[derive(Clone, Debug)]
pub struct Workspace {
    pub id: String,
    pub rect: Rect,
}

#[pymethods]
impl Workspace {
    /// Crea una nueva instancia de Workspace.
    #[new]
    pub fn new(id: String, rect: Rect) -> Self {
        Workspace { id, rect }
    }
}