use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod dbus;
use dbus::KWinPayload;

/**
 * Procesa el JSON de estado enviado por el script de KWin y lo convierte en estructuras de Python.
 * 
 * Esta función toma una cadena JSON que contiene el estado de las ventanas y monitores,
 * lo deserializa usando Serde y mapea los datos a objetos nativos de Python (Diccionarios y Listas).
 * 
 * @param py Instancia del intérprete de Python.
 * @param payload_json Cadena de texto en formato JSON con el estado de KWin.
 * @returns Un resultado que contiene una tupla opcional con (pantallas, ventanas) o None si el JSON es inválido.
 */
#[pyfunction]
fn parse_sync_state<'py>(py: Python<'py>, payload_json: &str) -> PyResult<Option<(Bound<'py, PyDict>, Bound<'py, PyList>)>> {
    let payload: KWinPayload = match serde_json::from_str(payload_json) {
        Ok(p) => p,
        Err(_) => return Ok(None),
    };

    let py_screens = PyDict::new_bound(py);
    for (ws_id, screen) in payload.screens {
        let screen_dict = PyDict::new_bound(py);
        screen_dict.set_item("x", screen.x)?;
        screen_dict.set_item("y", screen.y)?;
        screen_dict.set_item("width", screen.w)?;
        screen_dict.set_item("height", screen.h)?;
        py_screens.set_item(ws_id, screen_dict)?;
    }

    let py_windows = PyList::empty_bound(py);
    for win in payload.windows {
        let win_dict = PyDict::new_bound(py);
        win_dict.set_item("window_id", win.id)?;
        win_dict.set_item("workspace_id", win.ws)?;
        win_dict.set_item("is_floating", win.f)?;
        win_dict.set_item("is_minimized", win.m)?;
        win_dict.set_item("is_pip", win.p)?;
        py_windows.append(win_dict)?;
    }

    Ok(Some((py_screens, py_windows)))
}

/**
 * Definición del módulo de Python `kwin_rust_adapter`.
 * Expone las funciones de procesamiento de alto rendimiento escritas en Rust a Python.
 */
#[pymodule]
fn kwin_rust_adapter(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_sync_state, m)?)?;
    Ok(())
}