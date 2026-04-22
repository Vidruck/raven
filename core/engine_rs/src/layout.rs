use std::collections::HashMap;
use crate::geometry::{Rect, WindowNode};

#[inline(always)]
fn apply_gaps(rect: &Rect, gap: i32) -> Rect {
    Rect {
        x: rect.x + gap,
        y: rect.y + gap,
        width: std::cmp::max(1, rect.width - (2 * gap)),
        height: std::cmp::max(1, rect.height - (2 * gap)),
    }
}

pub fn calculate_master_stack(
    windows: Vec<WindowNode>,
    screen_rect: Rect,
    nmaster: usize,
    master_ratio: f32,
    default_gaps: i32,
) -> HashMap<String, Rect> {
    
    let active_windows: Vec<&WindowNode> = windows.iter()
        .filter(|w| !w.is_floating && !w.is_minimized)
        .collect();

    let count = active_windows.len();
    let mut layout_map = HashMap::with_capacity(count);

    if count == 0 { return layout_map; }

    let g = default_gaps;
    let half_g = g / 2;

    let usable_rect = Rect {
        x: screen_rect.x + half_g,
        y: screen_rect.y + half_g,
        width: screen_rect.width - g,
        height: screen_rect.height - g,
    };

    if count == 1 {
        layout_map.insert(active_windows[0].window_id.clone(), apply_gaps(&screen_rect, g));
        return layout_map;
    }

    let actual_nmaster = std::cmp::min(nmaster, count);
    let has_stack = count > actual_nmaster;

    let master_area_width = if has_stack {
        (screen_rect.width as f32 * master_ratio) as i32
    } else {
        screen_rect.width
    };
    
    let stack_area_width = usable_rect.width - master_area_width;
    let base_master_height = usable_rect.height / actual_nmaster as i32;

    for (i, win) in active_windows.iter().take(actual_nmaster).enumerate() {
        let current_y = usable_rect.y + (i as i32 * base_master_height);
        let current_height = if i == actual_nmaster - 1 {
            usable_rect.height - (i as i32 * base_master_height)
        } else {
            base_master_height
        };

        let rect_master = Rect { x: usable_rect.x, y: current_y, width: master_area_width, height: current_height };
        layout_map.insert(win.window_id.clone(), apply_gaps(&rect_master, half_g));
    }

    if has_stack {
        let stack_windows = &active_windows[actual_nmaster..];
        let stack_count = stack_windows.len() as i32;
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
            layout_map.insert(win.window_id.clone(), apply_gaps(&rect_stack, half_g));
        }
    }

    layout_map
}