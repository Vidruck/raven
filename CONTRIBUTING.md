# Contribuyendo a Raven 🐦

¡Gracias por el interés en mejorar Raven! Con el lanzamiento de la **v2.0**, el proyecto ha evolucionado hacia un ecosistema **100% nativo en Rust**. Estamos encantados de recibir colaboraciones que impulsen la estabilidad, el rendimiento y la eficiencia energética en KDE Plasma 6.

## 🏗️ Filosofía de Diseño v2.0
Para mantener la robustez y ligereza logradas, todas las contribuciones deben respetar estos pilares arquitectónicos:

1. **Ecosistema Nativo en Rust:**
   - **Core Asíncrono (core/engine_rs):** Toda la lógica de cálculo y la comunicación IPC reside en Rust. Utilizamos `zbus` para una integración asíncrona y de ultra-baja latencia con el bus de datos del sistema.
   - **Interfaz Nativa (raven_gui):** La UI se construye con `egui/eframe`, garantizando un consumo mínimo de recursos y una integración fluida con el compositor.

2. **Snapshot-Based Synchronization:**
   - Mantenemos el modelo de **Consistencia Eventual.** El Bridge (JS) envía el estado estructural que el daemon de Rust procesa de forma atómica para generar los comandos de posicionamiento.

3. **Debounced Sensing:**
   - El Bridge no debe reaccionar instantáneamente a eventos de geometría intermedios (como durante un redimensionado manual). Debe esperar a que la interacción finalice para sincronizar el estado, protegiendo la CPU y la estabilidad de `kwin_wayland`.

4. **Seguridad y Rendimiento Extremo:**
   - **Cero Costo:** Buscamos abstracciones de costo cero. Evita clonaciones innecesarias de datos en el motor.
   - **Rust Idiomático:** Favorecemos el uso de tipos seguros y el manejo de errores robusto (Result/Option). El uso de `unsafe` está estrictamente prohibido a menos que se justifique por interoperabilidad crítica con APIs de bajo nivel del sistema.

5. **Optimización de Peso (Binary Thinning):**
   - El minimalismo en el binario final es un requisito de diseño. Se exige a los colaboradores buscar la reducción máxima del peso en ROM, evaluando críticamente la inclusión de dependencias y sus features. El objetivo es mantener el footprint lo más bajo posible para el usuario final.

## 🚀 Cómo colaborar
1. **Reporte de Bugs:** Si encuentras un comportamiento extraño en Wayland, abre un *Issue* describiendo tu hardware, versión de Plasma y adjunta los logs del daemon si es posible (`journalctl --user -u raven`).
2. **Pull Requests:**
   - Crea una rama descriptiva (`feature/nueva-mejora` o `fix/error-especifico`).
   - Asegúrate de que tu código pase las pruebas de sanidad: `cargo check` y `cargo clippy`.
   - Documenta cualquier cambio en la interfaz DBus o en la estructura de configuración.

## 🛠️ Requisitos de Desarrollo *(Stack)*
Para compilación y pruebas necesitas:
- **Rust Toolchain:** Edición 2021 o superior.
- **Librerías de Desarrollo:** `libwayland`, `libx11`, `libxkbcommon` (requeridas por la interfaz gráfica).
- **Herramientas de KDE:** `kpackagetool6` y `kbuildsycoca6` para probar los adaptadores.

## 📝 Estándares de Código
- **Rust:** Formateo obligatorio con `cargo fmt`. Se recomienda encarecidamente seguir las sugerencias de `clippy` para un código más limpio y eficiente. Documenta las funciones públicas utilizando comentarios de documentación (`///`).
- **JavaScript (Bridge):** El código debe ser compatible con `QJSEngine` de Plasma 6.
    - **Native API First:** Prohibido el filtrado manual si existe una propiedad nativa (ej. `w.notification` vs filtrar por clase).
    - **Inmutabilidad de IDs:** El rastreo de ventanas es exclusivo mediante `w.internalId.toString()`.
    - **Atomicidad:** Los comandos desde Rust deben ser atómicos para evitar conflictos con el compositor.

---

**Tu ayuda no solo mejora a Raven, me ayuda a mí a ser un mejor ingeniero. Hagamos de Raven el Tiling Engine más rápido y elegante para KDE. ¡Huélum!**
