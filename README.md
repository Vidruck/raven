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

Raven es un gestor de ventanas dinámico diseñado para **KDE Plasma 6 (Wayland)**. La versión 1.6 consolida la migración hacia una **Arquitectura de Dominio Puro en Rust**, delegando la totalidad de la lógica de topología al motor nativo.

## 🚀 v1.6: Topología Global Nativa (Native Global Topology)
Esta versión representa la culminación de la estrategia "Strangler Fig", donde los componentes críticos han "estrangulado" completamente las implementaciones antiguas en Python.

- **Migración 100% Rust-Native:** A diferencia de la v1.5, donde Rust solo manejaba el cálculo matemático básico, la v1.6 delega la **Topología Global** completa. Esto incluye la gestión de múltiples escritorios (workspaces), la lógica de Picture-in-Picture (PiP) y la organización jerárquica de ventanas.
  
- **Patrón Fachada (Facade Pattern):** El `TilingEngine` en Python ha sido refactorizado para actuar únicamente como una interfaz de alto nivel (Fachada). Ya no contiene lógica de cálculo; su única responsabilidad es orquestar los datos entre el sistema D-Bus y el motor `raven_core_rs`.

- **Cero Latencia en Multi-Escritorio:** Al procesar todos los workspaces en una sola llamada atómica a Rust, se eliminan los saltos de contexto (context switching) entre lenguajes para cada escritorio, resultando en una disposición instantánea incluso en configuraciones complejas de múltiples monitores.

## 🌟 Características Destacadas 
- **Global Topology Engine:** Cálculo unificado de todos los estados del escritorio en una única operación nativa.
- **Detección PiP Avanzada:** Identificación y anclaje dinámico de ventanas Picture-in-Picture gestionado directamente por el kernel de Rust.
- **Zero-Copy D-Bus IPC:** Se ha eliminado el middleware nativo intermedio (`adapters_rust`), simplificando la arquitectura. Ahora Python captura el payload de D-Bus e inyecta la cadena en bruto al motor Rust, reduciendo la latencia de serialización drásticamente y mejorando la mantenibilidad.
- **Inmunidad a Tormentas de Eventos:** El puente de integración filtra ráfagas de señales D-Bus, garantizando que el motor solo procese estados estables.
- **Raven Control Center:** Interfaz nativa en PyQt6 para la gestión de preferencias y visualización del estado del motor.

## 🏗️ Estructura: Arquitectura Hexagonal Híbrida
- `core/`: 
  - `engine_rs/`: Kernel de lógica pura en Rust. Implementa los algoritmos Master-Stack y Topología Global.
  - `tiling_engine.py`: Fachada de orquestación y puente FFI (Foreign Function Interface).
- `adapters/`: 
    - `dbus_kwin.py`: Capa de comunicación asíncrona con el compositor KWin. Operando mediante IPC D-Bus de baja latencia con un enfoque Zero-Copy, delegando el análisis del estado estructural directamente a Rust sin consumir recursos en Python.
    - `kwin_script/`: Bridge de JavaScript que interactúa con la API de composición de Plasma 6.
- `gui/`: Centro de control y configuración nativo.

## 🛠️ Instalación y Uso
El instalador gestiona automáticamente los entornos virtuales de **Python** y la compilación de los módulos nativos de **Rust**.
1. Clona el repositorio.
2. Ejecuta `./install.sh`.
3. Activa "Raven Bridge" en la configuración de KWin.

``` Bash
git clone https://github.com/Vidruck/raven
cd raven
./install.sh
```

## 🧹 Desinstalación
Para eliminar completamente el proyecto ejecuta:
`./uninstall.sh`

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

*Este proyecto se distribuye bajo la licencia GPL-3. Se permite su libre uso, estudio, modificación y redistribución, siempre que se preserve la autoría original.*

*Desarrollado por Alejandro González Hernández (Vidruck).*