/// Interfaz (Trait) para el envío de comandos físicos al compositor.
/// 
/// Define las operaciones básicas que la infraestructura debe implementar para 
/// materializar las decisiones del motor de mosaico sobre las ventanas.
pub trait CommandDispatcher {
    /// Envía una orden de movimiento y redimensionamiento.
    fn send_move(&self, id: String, x: i32, y: i32, w: i32, h: i32);
}