# Raven Tiling Emulator 🐦

Raven es un demonio híbrido (Python + JavaScript) diseñado para proveer capacidades de Tiling Window Management (Mosaico dinámico) de forma nativa sobre **KDE Plasma 6 (Wayland)**.

A diferencia de los scripts tradicionales de KWin, Raven extrae la complejidad matemática de la interfaz de usuario utilizando una **Arquitectura Hexagonal**. El motor lógico (Python) opera en segundo plano como un servicio de Systemd, comunicándose en tiempo real con KWin mediante el bus de mensajes IPC (DBus).

## Características
- **Zero-Polling:** Utiliza un patrón de *Long-Polling* asíncrono sobre DBus para un consumo mínimo de CPU (menos de 15MB de RAM).
- **Multi-Monitor Dinámico:** Respeta resoluciones mixtas y Fractional Scaling nativo de Wayland.
- **Smart Filtering:** Ignora paneles, docks, utilidades del sistema (como Spectacle) y herramientas de portapapeles (Klipper).
- **Gestión de Estados:** Soporte nativo para ventanas minimizadas sin romper el layout geométrico.

## Estructura del Proyecto (Arquitectura Hexagonal)
- `core/`: Entidades de dominio puro y motor matemático (`TilingEngine`). Cero dependencias externas.
- `ports/`: Interfaces abstractas de entrada y salida.
- `adapters/`: Implementaciones de tecnología específica (Servidor DBus en Python, Bridge JS para KWin, Loader de Configuración).
- `gui/`: Interfaz gráfica nativa en PyQt6 para la configuración en tiempo real.

## Requisitos
* dbus-next==0.2.3
* PyQt6==6.10.2
* PyQt6-Qt6==6.10.2
* PyQt6_sip==13.11.0
