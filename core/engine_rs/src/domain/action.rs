/// Acciones de dominio que representan intenciones del motor sobre las ventanas.
/// Estas acciones son agnósticas a la infraestructura subyacente (DBus, X11, Wayland).
#[derive(Debug, Clone, PartialEq)]
pub enum RavenAction {
    /// Mueve y redimensiona una ventana a las coordenadas especificadas.
    MoveWindow { window_id: String, x: i32, y: i32, width: i32, height: i32 },
    /// Da el foco a una ventana específica.
    FocusWindow { window_id: String },
    /// Mueve una ventana a otro espacio de trabajo y le asigna una geometría en una sola operación.
    MigrateAndMove { 
        window_id: String, 
        target_ws: String, 
        x: i32, 
        y: i32, 
        width: i32, 
        height: i32 
    },
    /// Minimiza una ventana que no tiene espacio en el área de layout actual.
    MinimizeWindow { window_id: String },
    /// Envía una orden de migración manual para que el compositor la resuelva nativamente.
    MigrateNative { window_id: String, direction: String },
}
