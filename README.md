# Raven Tiling Emulator 🐦

<p align="center">
  <img src="icon/org.kde.raven.tiling.svg" width="250" alt="Raven Logo">
</p>

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Rust](https://img.shields.io/badge/rust-%23000000.svg?style=for-the-badge&logo=rust&logoColor=white)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Qt](https://img.shields.io/badge/Qt-%23217346.svg?style=for-the-badge&logo=Qt&logoColor=white)
![KDE](https://img.shields.io/badge/KDE%20Plasma-21D359?style=for-the-badge&logo=kde&logoColor=white)
![Wayland](https://img.shields.io/badge/Wayland-9999ff?style=for-the-badge&logo=wayland&logoColor=white)
![GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=for-the-badge)

Raven es un gestor de ventanas dinámico diseñado para **KDE Plasma 6 (Wayland)**. La versión 1.5 marca la transición hacia una Arquitectura Híbrida de Alto Rendimiento, utilizando **Rust** para el procesamiento crítico de datos y **Python** para la orquestación de alto nivel.

## 🚀 v1.5 Rust Hybrid Edition
A partir de esta versión, Raven implementa una estrategia de "Strangler Fig" (Migración por Estrangulamiento) para mover componentes críticos de Python a Rust, buscando estándares de grado empresarial en eficiencia y estabilidad.

- **Ultra-Performance Core (raven_core_rs):** El motor matemático de cálculo de geometría ha sido migrado a Rust. Ahora los algoritmos de partición Master-Stack se ejecutan de forma nativa, reduciendo la latencia de respuesta tras eventos de composición.

- **Zero-Stutter IPC Bridge (kwin_rust_adapter):** Se ha implementado un adaptador de infraestructura en Rust que utiliza Serde para la deserialización masiva del estado de KWin. Esto elimina el cuello de botella del Garbage Collector de Python al procesar JSONs masivos, garantizando una fluidez absoluta en el escritorio.

- **Memoria y Energía:** Reducción drástica en el uso de recursos. El procesamiento de señales D-Bus ahora consume menos ciclos de CPU, optimizando la autonomía en dispositivos portátiles.

## 🌟 Características Destacadas 
- **Snapshot-Based Sync (Optimizado):** Captura atómica del estado de Wayland con procesamiento nativo en Rust.
  - **Inmunidad a Tormentas:** El adaptador nativo filtra y procesa ráfagas de eventos de aplicaciones pesadas antes de que lleguen al motor lógico.
- **Gestión Inteligente de PiP (Picture-in-Picture):** - Detección Proactiva: Identificación nativa de ventanas flotantes.
  - **Anclaje Dinámico:** Ubicación configurable con un margen de aislamiento de **$8px$** para jerarquía visual.
- **Raven Control Center:** Interfaz nativa en PyQt6 para la gestión de preferencias en tiempo real.

## 🏗️ Estructura: Arquitectura Hexagonal Híbrida
- `core/`: 
  - `rust_engine/`: Motor matemático puro en Rust (Cálculo de invariantes).
  - `tiling_engine.py/`: Orquestador de lógica de dominio y puente FFI.
- `adapters/`: 
    - `kwin_rust_adapter/`: Adaptador de infrastructura nativo para comunicación D-Bus de alta velocidad.
    - `dbus_kwin.py`: Fachada asíncrona que implementa los puertos de comunicación.
    - `kwin_script/`: Puente de JavaScript para la manipulación de la composición en KWin.
- `gui/`: Centro de control nativo.
## 🛠️ Instalación y Uso
El instalador cuenta con un mecanismo de gestión de entornos virtuales aislados de **Python** y compilación de los modulos nativos de **Rust**, además de contar con un actualizado de dependencias inteligente compatible para distribuciones **Rolling Release.**
1. Clona el repositorio.
2. Ejecuta `./install.sh`.
3. Activa "Raven Bridge" en la configuración de KWin.

``` Bash
git clone https://github.com/Vidruck/raven
cd raven
./install.sh
```

## 🧹 Desinstalación
Para eliminar completamente el proyecto ejecuta en terminal:

`./uninstall.sh`. 


### Atajos Predeterminados
| Tecla | Acción |
|---|---|
| `Meta + I / D` | Incrementar/Disminuir ventanas maestras |
| `Meta + L / H` | Ajustar ratio del área maestra |
| `Meta + J / K` | Cambiar foco entre ventanas |

## ⚠️ Descargo de Responsabilidad (Disclaimer)

**Este software se proporciona "tal cual" (AS IS), sin garantía de ningún tipo.** Dado que Raven interactúa directamente con el compositor de ventanas (KWin) y el bus de datos del sistema (DBus), el usuario asume toda la responsabilidad derivada de su uso. El autor no se hace responsable de:
- Inestabilidad del entorno de escritorio o fallos en la sesión gráfica.
- Conflictos con otros scripts de KWin o configuraciones del sistema.
- Cualquier daño indirecto, pérdida de datos o comportamiento imprevisto del hardware.

Este es un proyecto de investigación académica y desarrollo personal. Al ser software experimental, se recomienda su uso bajo supervisión y conocimiento de las herramientas de recuperación de KWin/Wayland.

---
**Si te gusta este proyecto, te pido que me ayudes a mejorarlo; así me ayudas a ser un mejor programador.**

*Este proyecto se distribuye bajo la licencia GPL-3. Se permite su libre uso, estudio, modificación y redistribución, siempre que se preserve la autoría original y cualquier obra derivada se libere bajo estos mismos términos de código abierto.*


*Desarrollado por Alejandro González Hernández (Vidruck).*