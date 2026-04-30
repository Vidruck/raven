use serde::Deserialize;
use std::collections::HashMap;

/// Representa la geometría y dimensiones de un monitor u salida (output) detectada por KWin.
#[derive(Debug, Deserialize)]
pub struct KWinScreen {
    /// Posición en el eje X del monitor en el canvas global de Wayland.
    pub x: i32,
    /// Posición en el eje Y del monitor en el canvas global de Wayland.
    pub y: i32,
    /// Ancho efectivo del área de trabajo (excluyendo paneles de sistema).
    pub w: i32,
    /// Alto efectivo del área de trabajo (excluyendo paneles de sistema).
    pub h: i32,
}

/// Representa el estado atómico de una ventana gestionada por el compositor.
#[derive(Debug, Deserialize)]
pub struct KWinWindow {
    /// Identificador único interno de la ventana en KWin.
    pub id: String,
    /// Identificador del espacio de trabajo (combinación de monitor y escritorio virtual).
    pub ws: String,
    /// Indica si la ventana está en modo flotante (bypass del tiling).
    pub f: bool,
    /// Indica si la ventana se encuentra minimizada.
    pub m: bool,
    /// Indica si la ventana está marcada como "Picture-in-Picture" o "Keep Above".
    pub p: bool, 
}

/// Estructura principal que contiene el snapshot completo del estado de composición de KWin.
/// Es el objetivo de deserialización del JSON enviado por el script de KWin.
#[derive(Debug, Deserialize)]
pub struct KWinPayload {
    /// Lista de todas las ventanas rastreadas y su estado actual.
    pub windows: Vec<KWinWindow>,
    /// Mapeo de identificadores de espacio de trabajo a su geometría de pantalla correspondiente.
    pub screens: HashMap<String, KWinScreen>,
}