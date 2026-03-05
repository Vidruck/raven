// ==========================================
// RAVEN BRIDGE - KDE PLASMA 6 (WAYLAND)
// ==========================================

function getWorkspaceId(window) {
    var outName = window.output ? window.output.name : "default";
    var desktopId = "default_desk";
    
    if (window.desktops && window.desktops.length > 0) {
        desktopId = window.desktops[0].id.toString();
    } else if (workspace.currentDesktop) {
        desktopId = workspace.currentDesktop.id.toString();
    }
    return outName + "||" + desktopId;
}

// --- FOTOGRAFÍA DE ESTADO (SNAPSHOT) ---

function sendFullState() {
    var windows = workspace.windowList();
    var winState = [];
    var screens = {};
    
    for (var i = 0; i < windows.length; i++) {
        var w = windows[i];
        if (!w.normalWindow && !w.dialog) continue;
        
        var wsId = getWorkspaceId(w);
        
        // Empaquetamos la geometría del monitor si es la primera vez que lo vemos:
        
        if (w.output && !screens[wsId]) {
            var desktop = (w.desktops && w.desktops.length > 0) ? w.desktops[0] : workspace.currentDesktop;
            var area = workspace.clientArea(0, w.output, desktop);
            screens[wsId] = {
                x: Math.round(area.x), y: Math.round(area.y),
                w: Math.round(area.width), h: Math.round(area.height)
            };
        }

        var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
        var strCap = w.caption ? w.caption.toString().toLowerCase() : "";
        
        var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
        var isSpectacle = strClass.indexOf("spectacle") !== -1;
        var isPip = strCap.indexOf("picture-in-picture") !== -1 || strCap.indexOf("imagen en imagen") !== -1;
        var isSystemApp = w.utility || w.fullScreen || w.specialWindow;
        
        var isFloat = Boolean(w.dialog || isSystemApp || isSpectacle || isKlipper || isPip);
        var isMin = Boolean(w.minimized);
        
        winState.push({
            id: w.internalId.toString(),
            ws: wsId,
            f: isFloat,
            m: isMin
        });
    }
    
    var payload = { windows: winState, screens: screens };
    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncState", JSON.stringify(payload));
}

// --- VIGILANTE DE EVENTOS ---

function bindWindow(w) {
    if (w.__raven_bound) return;
    w.__raven_bound = true;
    
    // Cualquier cambio reporta el estado completo

    w.minimizedChanged.connect(sendFullState);
    w.outputChanged.connect(sendFullState);
    w.desktopsChanged.connect(sendFullState);
    
    // ALGORITMO ANTI-JALONEO: Detecta el final exacto de un arrastre de ventana
    w.frameGeometryChanged.connect(function() {
        if (w.__was_moving && !w.interactiveMove) {

            // Drop detectado: El usuario soltó el clic

            w.__was_moving = false;
            sendFullState(); 
        } else if (w.interactiveMove) {
            // Drag en curso: El usuario tiene el clic presionado

            w.__was_moving = true;
        }
    });
}

function init() {
    print("[Raven Bridge] Iniciando Snapshot Engine...");

    var initialWindows = workspace.windowList();
    for (var i=0; i<initialWindows.length; i++) {
        bindWindow(initialWindows[i]);
    }

    workspace.windowAdded.connect(function(w) {
        if (w) {
            bindWindow(w);
            sendFullState();
        }
    });

    workspace.windowRemoved.connect(function(w) {
        sendFullState();
    });

    workspace.windowActivated.connect(function(w) {
        if (w) callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", w.internalId.toString());
    });

    listenForCommands();
}

function applyCommands(commandsJson) {
    if (!commandsJson) return;
    var cmds = JSON.parse(commandsJson);
    var windows = workspace.windowList();
    
    for (var i = 0; i < cmds.length; i++) {
        var cmd = cmds[i];
        
        if (cmd.action === "move") {
            for (var j = 0; j < windows.length; j++) {
                if (windows[j].internalId.toString() === cmd.window_id) {
                    
                    if (windows[j].maximizeMode === 3) break; 
                    if (windows[j].interactiveMove || windows[j].interactiveResize) break; 
                    
                    windows[j].frameGeometry = {
                        x: Math.round(cmd.x), y: Math.round(cmd.y),
                        width: Math.round(cmd.width), height: Math.round(cmd.height)
                    };
                    break;
                }
            }
        }
        else if (cmd.action === "focus") {
            for (var f = 0; f < windows.length; f++) {
                if (windows[f].internalId.toString() === cmd.window_id) {
                    workspace.activeWindow = windows[f];
                    break;
                }
            }
        }
        else if (cmd.action === "request_sync") {
            sendFullState();
        }
    }
}

function listenForCommands() {
    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
        if (response) {
            try { applyCommands(response); } catch (e) { print("[Raven] Error: " + e); }
        }
        listenForCommands(); 
    });
}

init();