/// Acciones de dominio que representan intenciones del motor sobre las ventanas.
/// Estas acciones son agnósticas a la infraestructura subyacente (DBus, X11, Wayland).
#[derive(Debug, Clone, PartialEq)]
pub enum RavenAction {
    MoveWindow { window_id: String, x: i32, y: i32, width: i32, height: i32 },
    FocusWindow { window_id: String },
    // Acciones de Resiliencia en Cascada
    MigrateToOutput { window_id: String, target_output: String },
    MigrateToDesktop { window_id: String, target_desktop: String },
    MinimizeWindow { window_id: String },
    UnminimizeWindow { window_id: String },
}
