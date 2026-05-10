//! # Raven Core - Motor de Tiling Nativo
//! 
//! Esta librería implementa la lógica central del gestor de mosaico Raven.
//! Sigue una arquitectura hexagonal para garantizar el desacoplamiento entre
//! la lógica de negocio y los detalles de infraestructura.

pub mod application;
pub mod domain;
pub mod infrastructure;
pub mod ports;