# Raven Tiling Emulator 🐦

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![JavaScript](https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E)
![Qt](https://img.shields.io/badge/Qt-%23217346.svg?style=for-the-badge&logo=Qt&logoColor=white)
![Arch Linux](https://img.shields.io/badge/Arch%20Linux-1793D1?style=for-the-badge&logo=arch-linux&logoColor=white)
![KDE](https://img.shields.io/badge/KDE%20Plasma-21D359?style=for-the-badge&logo=kde&logoColor=white)
![Wayland](https://img.shields.io/badge/Wayland-9999ff?style=for-the-badge&logo=wayland&logoColor=white)
![GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=for-the-badge)

Raven es un gestor de ventanas híbrido diseñado para **KDE Plasma 6 (Wayland)**. Combina la potencia de un motor matemático en Python con la integración nativa de KWin mediante una arquitectura de sincronización de estado atómico (*Snapshot-based Sync*).


## 🚀 Snapshot-Based Sync
A diferencia de otros gestores como los basados en eventos diferenciales, Raven utiliza un modelo de **Consistencia Eventual Absoluta**. En cada cambio de composición, el puente de JavaScript captura una "fotografía" completa del estado de Wayland y la envía al demonio. Esto garantiza:
- **Resiliencia:** El sistema se recupera instantáneamente de desconexiones de monitores (*Hotplugging*).
- **Zero Jaloneo:** Gracias a filtros de interacción humana, las ventanas respetan el arrastre manual antes de ser absorbidas por el mosaico.
- **Inmunidad a Tormentas por Apps:** Un regulador de flujo (*Throttler*) previene el colapso del bus de datos ante ráfagas de eventos de aplicaciones pesadas.

## 🏗️ Estructura del Proyecto: Arquitectura Hexagonal
- `core/`: Motor matemático puro. Lógica de partición Master-Stack e invariantes geométricas.
- `adapters/`: 
    - **DBus Adapter:** Servidor IPC de alto rendimiento.
    - **KWin Bridge:** Script nativo de Wayland para la manipulación de la composición.
    - **Plasmoid:** Mini-widget de panel para control en tiempo real.
- `gui/`: Centro de control nativo en PyQt6.

## 🛠️ Instalación y Uso
1. Clona el repositorio.
2. Ejecuta `./install.sh`.
3. Activa "Raven Bridge" en la configuración de KWin.

## 🧹 Desinstalación
Para eliminar completamente el proyecto ejecuta en terminal 

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