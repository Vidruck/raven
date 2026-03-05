from dataclasses import dataclass

@dataclass
class RavenConfig:
    """Modelo de dominio que almacena las preferencias del usuario."""
    default_gaps: int = 8
    tiling_enabled_on_startup: bool = True
    nmaster: int = 1                
    master_ratio: float = 0.5       