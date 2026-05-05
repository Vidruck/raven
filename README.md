# Raven Tiling Emulator 🐦


<p align="center">
  <img src="icon/org.kde.raven.tiling.svg" width="250" alt="Raven Logo">
</p>

![Rust](https://img.shields.io/badge/rust-%23000000.svg?style=for-the-badge&logo=rust&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![KDE](https://img.shields.io/badge/KDE%20Plasma-21D359?style=for-the-badge&logo=kde&logoColor=white)
![Wayland](https://img.shields.io/badge/Wayland-9999ff?style=for-the-badge&logo=wayland&logoColor=white)
![GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=for-the-badge)

Raven es un gestor de ventanas dinámico (Tiling Window Manager) diseñado específicamente para **KDE Plasma 6 (Wayland)**. Con la llegada de la **versión 2.0**, Raven alcanza su madurez tecnológica al convertirse en una solución **100% nativa en Rust**, eliminando por completo la capa de dependencia de Python tanto en el motor como en la interfaz de usuario.

## 🚀 El Salto a la Versión 2.0: Cambio de Paradigma
Esta versión culmina el ciclo de transición de arquitectura híbrida (Python + Rust FFI) a un ecosistema puramente binario y nativo. El resultado es un gestor extremadamente rápido, ligero y estable que se integra de forma invisible en el sistema.

### 📉 Eficiencia Energética y de Memoria
La optimización ha sido el pilar de esta actualización. Al eliminar el intérprete de Python y las envolturas FFI, hemos reducido el consumo de recursos de manera drástica:

| Versión | Arquitectura | Consumo de RAM (aprox.) |
|---|---|---|
| **v1.0** | Python Puro | 55.0 MB |
| **v1.6** | Híbrida (Python + Rust FFI) | ~25.9 MB |
| **v2.0** | **Native All-Rust Edition** | **~6.0 MB** |

*Una reducción del **89%** en el uso de memoria comparado con la primera versión.*

## 🌟 Nuevas Funciones y Mejoras
- **Motor de Topología Global Nativo:** El daemon (`raven_core`) procesa ahora todos los eventos del bus D-Bus de forma directa y asíncrona mediante `zbus`, eliminando cualquier cuello de botella.
- **Raven Control Center (Renovado):** Una nueva interfaz de configuración moderna y minimalista construida íntegramente en Rust con **egui/eframe**. Sigue automáticamente el esquema de colores (Oscuro/Claro) del sistema y consume una fracción de los recursos que su predecesora.
- **Compilación sobre Metal:** El motor se compila optimizando específicamente para la arquitectura de tu procesador local durante la instalación, garantizando latencias sub-milisegundo en los cálculos de geometría.
- **Gestión PiP Avanzada:** La lógica de Picture-in-Picture ha sido refinada para ser más intuitiva y configurable desde la nueva interfaz.

## 🏗️ Nueva Estructura del Proyecto
- `core/engine_rs/`: El corazón del proyecto. Un daemon nativo asíncrono que escucha al compositor KWin.
- `raven_gui/`: Aplicación de preferencias nativa basada en egui para una configuración visual fluida.
- `adapters/`: 
    - `kwin_script/`: Bridge liviano en JavaScript para la API de Plasma 6.
    - `plasmoid/`: Widget de Plasma para el control rápido del estado del motor.
- `bin/`: Directorio de destino para los binarios optimizados una vez instalados.

## 🛠️ Instalación y Uso
El nuevo instalador gestiona la descarga de crates de Rust y la compilación optimizada de los componentes nativos.

1. Clona el repositorio.
2. Ejecuta `./install.sh`.
3. Activa "Raven Bridge" en la configuración de KWin (Scripts de KWin).

```bash
git clone https://github.com/Vidruck/raven
cd raven
./install.sh
```

## 🧹 Desinstalación
Si deseas eliminar Raven y todos sus binarios, ejecuta:
`./uninstall.sh`

### Atajos Predeterminados
| Tecla | Acción |
|---|---|
| `Meta + I / D` | Incrementar/Disminuir ventanas maestras |
| `Meta + L / H` | Ajustar ratio del área maestra (Ancho) |
| `Meta + J / K` | Cambiar foco entre ventanas del stack |
| `Meta + G` | Alternar (Toggle) el motor de mosaico globalmente |

## ⚠️ Descargo de Responsabilidad (Disclaimer)
**Este software se proporciona "tal cual" (AS IS), sin garantía de ningún tipo.** Raven interactúa directamente con el compositor de ventanas (KWin) y el bus de datos del sistema (DBus). El usuario asume toda la responsabilidad derivada de su uso. El autor no se hace responsable de inestabilidades en la sesión gráfica o conflictos con otros scripts del sistema.

---
**Si este proyecto te es útil, considera ayudarme a mejorarlo con feedback o contribuciones. ¡Huélum!**

*Desarrollado por Alejandro González Hernández (Vidruck). Licencia GPL-3.*