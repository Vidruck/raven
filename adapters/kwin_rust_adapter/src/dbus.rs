use serde::Deserialize;
use std::collections::HashMap;

#[derive(Debug, Deserialize)]
pub struct KWinScreen {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
}

#[derive(Debug, Deserialize)]
pub struct KWinWindow {
    pub id: String,
    pub ws: String,
    pub f: bool,
    pub m: bool,
    pub p: bool, 
}
#[derive(Debug, Deserialize)]
pub struct KWinPayload {
    pub windows: Vec<KWinWindow>,
    pub screens: HashMap<String, KWinScreen>,
}