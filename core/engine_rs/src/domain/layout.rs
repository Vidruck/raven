//! # Algoritmos de Layout
//!
//! Este submódulo contiene la lógica principal para el cálculo de la disposición
//! de las ventanas (tiling). Actualmente implementa el algoritmo Master-Stack.

use std::collections::HashMap;
use crate::domain::geometry::{Rect, WindowNode};

/// Porcentaje mínimo del área de la pantalla que puede ocupar una ventana.
/// Si el cálculo resulta en un área menor, la ventana será rechazada del layout
/// para que el controlador la migre.
const MIN_AREA_PERCENTAGE: f32 = 0.08;

/// Aplica un espaciado (gap) interno a un rectángulo.
///
/// Reduce el tamaño del rectángulo y ajusta su posición para crear un margen
/// visual alrededor del contenido.
#[inline(always)]
fn apply_gaps(rect: &Rect, gap: i32) -> Rect {
    Rect {
        x: rect.x + gap,
        y: rect.y + gap,
        width: std::cmp::max(1, rect.width - (2 * gap)),
        height: std::cmp::max(1, rect.height - (2 * gap)),
    }
}

/// Calcula la disposición Master-Stack para una lista de ventanas.
///
/// Divide el área de la pantalla en dos secciones principales:
/// 1. **Área Master**: Contiene las ventanas principales (definidas por `nmaster`).
/// 2. **Área Stack**: Contiene el resto de las ventanas apiladas verticalmente.
///
/// # Argumentos
/// * `windows` - Vector de ventanas a organizar.
/// * `screen_rect` - El área total de la pantalla disponible.
/// * `nmaster` - Número de ventanas deseadas en el área Master.
/// * `master_ratio` - Proporción del ancho de la pantalla para el área Master (0.0 a 1.0).
/// * `default_gaps` - Espaciado total entre ventanas.
///
/// # Retorno
/// Un `HashMap` mapeando IDs de ventana a sus geometrías calculadas.
pub fn calculate_master_stack(
    windows: Vec<WindowNode>,
    screen_rect: Rect,
    nmaster: usize,
    master_ratio: f32,
    default_gaps: i32,
) -> (HashMap<String, Rect>, Vec<String>) {
    
    // Filtrar solo las ventanas que deben ser organizadas (no flotantes ni minimizadas)
    let active_windows: Vec<&WindowNode> = windows.iter()
        .filter(|w| !w.is_floating && !w.is_minimized)
        .collect();

    let count = active_windows.len();
    let mut layout_map = HashMap::with_capacity(count);
    let mut evicted_windows = Vec::new();

    if count == 0 { return (layout_map, evicted_windows); }

    let g = default_gaps;
    let half_g = g / 2;

    // Área útil considerando la mitad de los gaps en los bordes externos
    let usable_rect = Rect {
        x: screen_rect.x + half_g,
        y: screen_rect.y + half_g,
        width: screen_rect.width - g,
        height: screen_rect.height - g,
    };

    // Si solo hay una ventana, ocupa toda la pantalla (con gaps)
    if count == 1 {
        let final_rect = apply_gaps(&screen_rect, g);
        let min_allowed_area = (screen_rect.width as f32 * screen_rect.height as f32 * MIN_AREA_PERCENTAGE) as i32;
        if final_rect.width * final_rect.height >= min_allowed_area {
            layout_map.insert(active_windows[0].window_id.clone(), final_rect);
        } else {
            evicted_windows.push(active_windows[0].window_id.clone());
        }
        return (layout_map, evicted_windows);
    }

    // Umbral mínimo de área permitido
    let min_allowed_area = (screen_rect.width as f32 * screen_rect.height as f32 * MIN_AREA_PERCENTAGE) as i32;

    // Suposición inicial
    let mut has_stack = count > nmaster;

    // Calcular el ancho de las áreas master y stack teóricas
    let master_area_width = if has_stack {
        // Sanitizar proporción para evitar geometrías corruptas o invisibles
        let safe_ratio = master_ratio.clamp(0.1, 0.9);
        (screen_rect.width as f32 * safe_ratio) as i32
    } else {
        screen_rect.width
    };
    
    let stack_area_width = usable_rect.width - master_area_width;

    // Calcular capacidad predictiva (Pila Dinámica)
    let min_height_master = std::cmp::max(1, min_allowed_area / std::cmp::max(1, master_area_width));
    let max_masters_capacity = std::cmp::max(1, (usable_rect.height / min_height_master) as usize);
    
    let safe_nmaster = std::cmp::min(nmaster, max_masters_capacity);
    let actual_nmaster = std::cmp::max(1, std::cmp::min(count, safe_nmaster));
    
    has_stack = count > actual_nmaster;

    let max_stack_capacity = if has_stack {
        let min_height_stack = std::cmp::max(1, min_allowed_area / std::cmp::max(1, stack_area_width));
        (usable_rect.height / min_height_stack) as usize
    } else {
        0
    };

    let total_safe_capacity = actual_nmaster + max_stack_capacity;
    let windows_to_place = std::cmp::min(count, total_safe_capacity);

    // Las ventanas que queden fuera del total_safe_capacity se consideran desalojadas automáticamente
    if count > total_safe_capacity {
        for win in active_windows.iter().skip(total_safe_capacity) {
            evicted_windows.push(win.window_id.clone());
        }
    }

    // Posicionar ventanas en el área Master
    let base_master_height = usable_rect.height / actual_nmaster as i32;
    for (i, win) in active_windows.iter().take(actual_nmaster).enumerate() {
        let current_y = usable_rect.y + (i as i32 * base_master_height);
        let current_height = if i == actual_nmaster - 1 {
            usable_rect.height - (i as i32 * base_master_height)
        } else {
            base_master_height
        };

        let rect_master = Rect { x: usable_rect.x, y: current_y, width: master_area_width, height: current_height };
        let final_rect = apply_gaps(&rect_master, half_g);
        
        // Verificar límite de desbordamiento por seguridad
        if final_rect.width * final_rect.height >= min_allowed_area {
            layout_map.insert(win.window_id.clone(), final_rect);
        } else {
            evicted_windows.push(win.window_id.clone());
        }
    }

    // Posicionar el resto de las ventanas permitidas en el área Stack
    if has_stack && max_stack_capacity > 0 {
        let stack_windows = &active_windows[actual_nmaster..windows_to_place];
        let stack_count = stack_windows.len() as i32;
        
        if stack_count > 0 {
            let base_stack_height = usable_rect.height / stack_count;

            for (i, win) in stack_windows.iter().enumerate() {
                let current_y = usable_rect.y + (i as i32 * base_stack_height);
                let current_height = if i as i32 == stack_count - 1 {
                    usable_rect.height - (i as i32 * base_stack_height)
                } else {
                    base_stack_height
                };

                let rect_stack = Rect {
                    x: usable_rect.x + master_area_width,
                    y: current_y,
                    width: stack_area_width,
                    height: current_height,
                };
                let final_rect = apply_gaps(&rect_stack, half_g);
                
                if final_rect.width * final_rect.height >= min_allowed_area {
                    layout_map.insert(win.window_id.clone(), final_rect);
                } else {
                    evicted_windows.push(win.window_id.clone());
                }
            }
        }
    }

    (layout_map, evicted_windows)
}

/// Calcula la topología global de todas las ventanas en todos los escritorios.
/// 
/// Organiza las ventanas de cada escritorio de forma independiente utilizando el 
/// algoritmo Master-Stack, y luego aplica una capa adicional para las ventanas 
/// en modo Picture-in-Picture (PiP).
///
/// # Argumentos
/// * `windows` - Vector de todas las ventanas gestionadas.
/// * `workspaces` - Mapa de geometrías de los escritorios disponibles.
/// * `nmaster` - Número de ventanas en el área Master por escritorio.
/// * `master_ratio` - Proporción del área Master.
/// * `default_gaps` - Espaciado base entre ventanas.
/// * `pip_position` - Posición deseada para las ventanas PiP ("top-left", "top-right", etc.).
///
/// # Retorno
/// Una tupla: (Geometrías Calculadas, IDs de Ventanas Desalojadas)
pub fn calculate_global_topology(
    windows: Vec<WindowNode>,
    workspaces: HashMap<String, Rect>,
    nmaster: usize,
    master_ratio: f32,
    default_gaps: i32,
    pip_position: &str,
) -> (HashMap<String, Rect>, Vec<String>) {
    let mut global_layout = HashMap::new();
    let mut global_evicted = Vec::new();
    let mut windows_by_ws: HashMap<String, Vec<WindowNode>> = HashMap::new();
    
    // Agrupar ventanas por su escritorio (workspace) correspondiente
    for win in windows {
        if !win.is_floating || win.is_pip {
            windows_by_ws
                .entry(win.workspace_id.clone())
                .or_insert_with(Vec::new)
                .push(win);
        }
    } 

    // Procesar cada escritorio para calcular su disposición
    for (ws_id, ws_windows) in windows_by_ws {
        if let Some(screen_rect) = workspaces.get(&ws_id) {
            // Primero calculamos el layout base (Master-Stack)
            let (ws_layout, ws_evicted) = calculate_master_stack(
                ws_windows.clone(),
                *screen_rect,
                nmaster,
                master_ratio,
                default_gaps,
            );
            global_layout.extend(ws_layout);
            global_evicted.extend(ws_evicted);

            // Dimensiones para ventanas PiP (aproximadamente 22% del ancho de pantalla)
            let pip_w = (screen_rect.width as f32 * 0.22) as i32;
            let pip_h = (pip_w as f32 * 0.56) as i32;
            let pip_gap = default_gaps + 10;

            // Sobreponer ventanas PiP en su posición configurada
            for win in ws_windows {
                if win.is_pip && !win.is_minimized {   
                    let mut x = screen_rect.x + pip_gap;
                    let mut y = screen_rect.y + pip_gap;

                    match pip_position {
                        "top-right" => {
                            x = screen_rect.x + screen_rect.width - pip_w - pip_gap;
                        }
                        "bottom-left" => {
                            y = screen_rect.y + screen_rect.height - pip_h - pip_gap;
                        }
                        "bottom-right" => {
                            x = screen_rect.x + screen_rect.width - pip_w - pip_gap;
                            y = screen_rect.y + screen_rect.height - pip_h - pip_gap;
                        }
                        _ => {} // Por defecto: top-left
                    }
                    
                    let pip_rect = Rect::new(x, y, pip_w, pip_h);
                    global_layout.insert(win.window_id.clone(), pip_rect);
                }
            }
        }
    }   
    (global_layout, global_evicted)
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::geometry::{Rect, WindowNode};

    fn mock_window(id: &str) -> WindowNode {
        WindowNode::new(
            id.to_string(),
            "workspace_1".to_string(),
            "DP-1".to_string(),
            vec!["desktop_1".to_string()],
            false,
            false,
            false,
            Rect::new(0, 0, 0, 0),
        )
    }

    #[test]
    fn test_calculo_vacio_retorna_limpio() {
        // [Escenario]: El puente envía un arreglo vacío (escritorio sin ventanas)
        let (layout, evicted) = calculate_master_stack(
            vec![], 
            Rect::new(0, 0, 1920, 1080), 
            1, 
            0.5, 
            10
        );
        
        // [Validación]: El motor no debe crashear, debe devolver colecciones vacías
        assert!(layout.is_empty(), "El layout debería estar vacío");
        assert!(evicted.is_empty(), "No debería haber ventanas desalojadas");
    }

    #[test]
    fn test_ventana_unica_respeta_gaps() {
        // [Escenario]: Una sola ventana en una pantalla 1080p con gaps de 20px
        let windows = vec![mock_window("win_1")];
        let screen = Rect::new(0, 0, 1920, 1080);
        let gaps = 20;

        let (layout, evicted) = calculate_master_stack(windows, screen, 1, 0.5, gaps);

        // [Validación]: La ventana no debe ser desalojada y debe aplicar el gap perimetral
        assert!(evicted.is_empty());
        let rect = layout.get("win_1").expect("La ventana 1 debería estar en el layout");
        
        // Si el gap es 20, la ventana debe estar en (20, 20) y su tamaño reducirse en 2 * gap (40px)
        assert_eq!(rect.x, 20);
        assert_eq!(rect.y, 20);
        assert_eq!(rect.width, 1880); // 1920 - 40
        assert_eq!(rect.height, 1040); // 1080 - 40
    }

    #[test]
    fn test_resiliencia_desbordamiento_fifo() {
        // [Escenario Estrés]: Intentamos meter 20 ventanas en 1080p.
        // Dado que MIN_AREA_PERCENTAGE es 0.08 (8%), matemáticamente solo caben
        // un máximo de 12 ventanas (100% / 8% = 12.5). El resto DEBE ser desalojado.
        let mut windows = Vec::new();
        for i in 0..20 {
            windows.push(mock_window(&format!("win_{}", i)));
        }

        let screen = Rect::new(0, 0, 1920, 1080);
        let (layout, evicted) = calculate_master_stack(windows, screen, 1, 0.5, 10);

        // [Validación]: Comprobamos que el motor protege la legibilidad de la pantalla
        assert!(layout.len() <= 12, "El layout aceptó más ventanas de las matemáticamente posibles");
        assert!(evicted.len() >= 8, "El motor no desalojó las ventanas sobrantes");
        
        // Verificamos que no haya superposición lógica entre admitidas y desalojadas
        for id in evicted {
            assert!(!layout.contains_key(&id), "Una ventana desalojada apareció en el layout");
        }
    }
}