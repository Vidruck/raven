import json
from pathlib import Path
from core.config import RavenConfig

class ConfigLoader:
    
    """Maneja la persistencia y lectura de las configuraciones del usuario."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "raven"
        self.config_file = self.config_dir / "raven.json"

    def load(self) -> RavenConfig:
        """Carga la configuración desde el disco o crea una por defecto."""
        if not self.config_file.exists():
            print("[CONFIG] Archivo no encontrado. Generando configuración por defecto...")
            return self._create_default()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[CONFIG] Preferencias cargadas desde {self.config_file}")
                
                return RavenConfig(
                    default_gaps=data.get("default_gaps", 8),
                    tiling_enabled_on_startup=data.get("tiling_enabled_on_startup", True),
                    nmaster=data.get("nmaster", 1),
                    master_ratio=data.get("master_ratio", 0.5)
                )
        except json.JSONDecodeError:
            print("[ERROR] JSON corrupto o mal formado. Usando memoria de respaldo.")
            return RavenConfig()
        except Exception as e:
            print(f"[ERROR CRÍTICO] Fallo de lectura IO: {e}. Usando memoria de respaldo.")
            return RavenConfig()

    def _create_default(self) -> RavenConfig:
        """Crea el directorio y el archivo JSON con los valores base."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        default_config = RavenConfig()
        
        data = {
            "default_gaps": default_config.default_gaps,
            "tiling_enabled_on_startup": default_config.tiling_enabled_on_startup,
            "nmaster": default_config.nmaster,
            "master_ratio": default_config.master_ratio
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        return default_config