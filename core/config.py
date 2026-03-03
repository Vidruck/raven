from dataclasses import dataclass

@dataclass
class RavenConfig:
    """Modelo de dominio que almacena las preferencias del usuario."""
    default_gaps: int = 8
    tiling_enabled_on_startup: bool = True
    nmaster: int = 1                #Cantidad de ventanas en el área principal 
    master_ratio: float = 0.5       #Porcentage de pantalla para el área principal (0.1 a 0.9)