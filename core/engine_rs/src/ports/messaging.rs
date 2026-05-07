pub trait CommandDispatcher{
    fn send_move(&self, id: String, x: i32, y: i32, w: i32, h:i32);
    fn send_close(&self, id: String);
}