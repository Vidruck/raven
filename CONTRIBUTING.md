# Contribuyendo a Raven 🐦

¡Gracias por el interés en mejorar Raven! Este proyecto ha evolucionado hacia un modelo híbrido **Python-Rust**. Estamos encantados de recibir colaboraciones que impulsen la estabilidad, el rendimiento y la eficiencia energética en KDE Plasma 6.

## 🏗️ Filosofía de Diseño v1.5
Para mantener la robustez lograda, todas las contribuciones deben respetar estos pilares arquitectónicos:

1. **Arquitectura Hexagonal Híbrida:**

- **Core Puro (core/engine_rs):** La lógica matemática pesada reside en Rust. El motor debe permanecer determinista y libre de efectos secundarios.

- **Adaptadores Nativos (adapters/kwin_rust_adapter):** Las tareas de infraestructura crítica (DBus, Serialización masiva) deben implementarse en Rust para garantizar latencia sub-milisegundo.

- **Orquestación en Python:** Python actúa como el "Pegamento" (Glue Code) asíncrono para la lógica de alto nivel y la interfaz de usuario.

2. **Snapshot-Based Synchronization (Rust Accelerated):**

- Mantenemos el modelo de **Consistencia Eventual Absoluta.**

- Cualquier Snapshot enviado desde el Bridge (JS) debe ser procesado por el adaptador de Rust mediante serde antes de llegar al dominio de Python.

3. **Seguridad y Rendimiento:**

- Se debe evitar el uso de unsafe en Rust a menos que sea estrictamente necesario para la interoperabilidad con la C-API de Python (PyO3).

- Cualquier nueva función nativa debe incluir un archivo de tipado Stub (.pyi) para mantener la integridad del análisis estático en Python.

## 🚀 Cómo colaborar
1. **Reporte de Bugs:** Si encuentras un "jaloneo" o un comportamiento extraño en Wayland, abre un *Issue* describiendo tu hardware y versión de Plasma.
2. **Pull Requests:** - Crea una rama descriptiva (`feature/nueva-mejora` o `fix/error-especifico`).
   - Asegúrate de que tu código pase un linter de Python (flake8 o black).
   - Documenta cualquier cambio en la firma de los métodos DBus.
## 🛠️ Requisitos de Desarrollo *(Stack)*
Para compilación y pruebas necesitas:
- **Rust Toolchain:** Edicion 2021.
- **Python 3.10+**: Recomiendo 3.14
- **Maturin:** Para gestionar los bindings nativos.
### Para enviar un PR:**
1. Crea una rama descriptiva (`feature/` ó `fix/`).
2. Si modificas el **core** o **adapter**, asegura funcionamiento  y verifica que no haya regresiones de rendimiento.
3. Documenta cualquier cambio en la interfaz de los modulos nativos en los archivos `.pyi`correspondientes.

## 📝 Estándares de Código
- **Rust:** Fromateo estricto con `cargo fmt`. Los módulos deben compilarse con àbi3`para garantizar compatibilidad con Python.
- **Python:** Seguimos PEP 8 y tipos estrictos *(Strict Type Hinting)*. Es obligatorio el uso de `Coroutine` en firmas de métodos asíncronos.
- **JavaScript (KWin):** El código debe ser compatible con el motor QJSEngine de Plasma 6 y evitar el uso de APIs obsoletas de X11.

---

**Tu ayuda no solo mejora a Raven, me ayuda a mí a ser un mejor ingeniero. Hagamos de Raven el Tiling Engine más rápido y elegante para KDE. ¡Huélum!**
