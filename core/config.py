from dataclasses import dataclass

@dataclass
class RavenConfig:
    """Modelo de dominio que almacena las preferencias del usuario."""
    default_gaps: int = 8
    tiling_enabled_on_startup: bool = True
    
    # Aquí en el futuro podremos agregar colores de bordes, 
    # reglas de ventanas específicas, etc.