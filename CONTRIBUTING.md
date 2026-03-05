# Contribuyendo a Raven 🐦

¡Gracias por el interés en mejorar Raven! Este proyecto nació como una iniciativa personal para potenciar el flujo de trabajo en KDE Plasma 6 y estoy encantado de recibir colaboraciones que impulsen su estabilidad y potencia.

## 🏗️ Filosofía de Diseño
Para mantener la robustez que hemos logrado, todas las contribuciones deben respetar los siguientes pilares arquitectónicos:

1. **Arquitectura Hexagonal (Puertos y Adaptadores):**
   - El motor lógico (`core/`) debe permanecer puro, sin dependencias de librerías externas o del sistema operativo.
   - Cualquier interacción con el sistema (KWin, DBus, Sistema de archivos) debe realizarse a través de un adaptador que implemente los puertos definidos.

2. **Snapshot-Based Synchronization:**
   - No implementamos lógica basada en eventos diferenciales aislados.
   - Cualquier cambio en el estado de las ventanas debe disparar un "Snapshot" completo desde el Bridge (JS) hacia el Daemon (Python) para garantizar la consistencia eventual.

3. **Invariantes Geométricas:**
   - El motor matemático debe ser determinista y manejar correctamente el *Pixel Loss Compensation* para evitar huecos en pantallas de alta resolución.

## 🛠️ Cómo colaborar
1. **Reporte de Bugs:** Si encuentras un "jaloneo" o un comportamiento extraño en Wayland, abre un *Issue* describiendo tu hardware y versión de Plasma.
2. **Pull Requests:** - Crea una rama descriptiva (`feature/nueva-mejora` o `fix/error-especifico`).
   - Asegúrate de que tu código pase un linter de Python (flake8 o black).
   - Documenta cualquier cambio en la firma de los métodos DBus.

## 📝 Estándares de Código
- **Python:** Seguimos PEP 8 y usamos `asyncio` para todas las tareas de I/O.
- **JavaScript (KWin):** El código debe ser compatible con el motor QJSEngine de Plasma 6 y evitar el uso de APIs obsoletas de X11.

---
**Tu ayuda no solo mejora a Raven, me ayuda a mí a ser un mejor ingeniero. ¡Hagamos de Raven un mejor Tiling Engine para KDE!**