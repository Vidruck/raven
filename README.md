# Raven Tiling Emulator 🐦


<p align="center">
  <img src="icon/org.kde.raven.tiling.svg" width="250" alt="Raven Logo">
</p>

![Rust](https://img.shields.io/badge/rust-%23000000.svg?style=for-the-badge&logo=rust&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![KDE](https://img.shields.io/badge/KDE%20Plasma-21D359?style=for-the-badge&logo=kde&logoColor=white)
![Wayland](https://img.shields.io/badge/Wayland-9999ff?style=for-the-badge&logo=wayland&logoColor=white)
![GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=for-the-badge)

Raven es un gestor de ventanas dinámico (Tiling Window Manager) diseñado específicamente para **KDE Plasma 6 (Wayland)**. Con la llegada de la **versión 2.6**, Raven se reestrutura y ajusta a los estándares de la **Arquitectura Hexagonal**, logrando el máximo desacoplamiento entre su lógica de negocio y la infraestructura del sistema operativo, a la vez que introduce optimizaciones agresivas de tamaño y estabilidad.

## 🚀 El Salto a la Versión 2.6: Arquitectura Hexagonal y Micro-Optimización
Esta versión se enfoca en la perfección estructural y la corrección de fallos críticos, garantizando una experiencia inquebrantable:

### 📉 Eficiencia Energética y de Almacenamiento
La optimización sigue siendo el pilar. El motor opera con recursos ridículamente bajos y el ejecutable ha sido comprimido al máximo:

| Versión | Arquitectura | Consumo de RAM (aprox.) |
|---|---|---|
| **v1.0** | Python Puro | 55.0 MB |
| **v1.6** | Híbrida (Python + Rust FFI) | ~25.9 MB |
| **v2.6** | **Optimized Rust** | **~5.8 MB** |

*Una reducción inmensa en el uso de memoria y disco gracias a LTO y la eliminación de símbolos de depuración.*

## 🌟 Nuevas Funciones y Correcciones (v2.6)
- **Refactorización a Arquitectura Hexagonal:** Desacoplamiento total del puente de comunicación (DBus/JSON) de la lógica matemática pura. Uso intensivo de DTOs y tipado estricto `RavenError` para una gestión de fallos predecible.
- **Acciones Amigables de Almacenamiento:** Compilación nivel 3 con `strip`, `lto` y `codegen-units=1`, reduciendo el peso final drásticamente. El instalador ahora ejecuta una **limpieza residual profunda (`cargo clean`)** para no saturar el almacenamiento de tu PC con artefactos intermedios.
- **Corrección de Bugs Críticos:** Resolución definitiva del *core-dump* inyectando el contexto de `tokio`, y arreglo del sistema de migración multimonitor adaptando el bridge Javascript puramente a la API de Wayland / KWin 6 (`workspace.outputs`).
- **Migración Inteligente Automatizada:** El motor detecta matemáticamente cuando una pantalla se satura. Las ventanas excedentes son propulsadas a tu monitor secundario o al siguiente escritorio virtual. *(Se requiere un escritorio virtual adicional para usarse).*
- **Control de Migración Manual:** Botones reactivos en el Plasmoid para trasladar la ventana actual entre monitores y escritorios virtuales con un clic.

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