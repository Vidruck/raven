/// Acciones de dominio que representan intenciones del motor sobre las ventanas.
/// Estas acciones son agnósticas a la infraestructura subyacente (DBus, X11, Wayland).
#[derive(Debug, Clone, PartialEq)]
pub enum RavenAction {
    /// Mueve y redimensiona una ventana a las coordenadas especificadas.
    MoveWindow { window_id: String, x: i32, y: i32, width: i32, height: i32 },
    /// Da el foco a una ventana específica.
    FocusWindow { window_id: String },
    /// Solicita que una ventana huérfana sea migrada automáticamente de forma inteligente.
    MigrateAuto { window_id: String },
    /// Mueve la ventana al siguiente monitor.
    MigrateToNextScreen { window_id: String },
    /// Mueve la ventana al siguiente escritorio virtual.
    MigrateToNextWorkspace { window_id: String },
}
