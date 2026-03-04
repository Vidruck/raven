// ==========================================
// RAVEN BRIDGE - KDE PLASMA 6 (WAYLAND)
// ==========================================

// --- Generador de Matriz Espacial (Monitor + Virtual Desktop) ---

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

function sendScreenGeometry(window) {
    if (!window || !window.output) return;
    var desktop = (window.desktops && window.desktops.length > 0) ? window.desktops[0] : workspace.currentDesktop;
    var area = workspace.clientArea(0, window.output, desktop);
    var workspaceId = getWorkspaceId(window);
    
    callDBus(
        "org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "updateScreenGeometry", 
        workspaceId, Math.round(area.x), Math.round(area.y), Math.round(area.width), Math.round(area.height)
    );
}

function init() {
    print("[Raven Bridge] Iniciando motor topológico avanzado...");

    workspace.windowAdded.connect(function(window) {
        if (!window) return;
        
        if (window.skipTaskbar || window.skipPager || window.skipSwitcher || !window.moveable || !window.resizeable) {
            return; 
        }

        var strClass = window.resourceClass ? window.resourceClass.toString().toLowerCase() : "";
        var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
        var isSpectacle = strClass.indexOf("spectacle") !== -1;
        var isSystemApp = window.utility || window.fullScreen || window.specialWindow;
        var isFloating = window.dialog || isSystemApp || isSpectacle || isKlipper;
        
        var windowId = window.internalId.toString();
        var workspaceId = getWorkspaceId(window);

        // --- RASTREADOR DE MIGRACIONES ---

        window.desktopsChanged.connect(function() {
            var newWorkspaceId = getWorkspaceId(window);
            callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowWorkspaceChanged", windowId, newWorkspaceId);
            sendScreenGeometry(window);
        });

        window.outputChanged.connect(function() {
            var newWorkspaceId = getWorkspaceId(window);
            callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowWorkspaceChanged", windowId, newWorkspaceId);
            sendScreenGeometry(window);
        });

        window.minimizedChanged.connect(function() {
            callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowMinimizedChanged", windowId, window.minimized);
        });

        // ÚNICA LLAMADA DBUS (Inyectando el estado de minimización desde el nacimiento)
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowAdded", windowId, workspaceId, isFloating, window.minimized || false);
        sendScreenGeometry(window);
    });

    workspace.windowRemoved.connect(function(window) {
        if (!window) return;
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowRemoved", window.internalId.toString());
    });

    workspace.windowActivated.connect(function(window) {
        if (!window) return;
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", window.internalId.toString());
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
                    
                    // FILTRO DE MAXIMIZACIÓN
                    // 3 equivale a Full Maximized en la API de KDE. Si está maximizada, KWin la controla.
                    
                    if (windows[j].maximizeMode === 3) {
                        break; 
                    }
                    
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
            var handledOutputs = [];
            for (var o = 0; o < windows.length; o++) {
                var compId = getWorkspaceId(windows[o]);
                if (compId && handledOutputs.indexOf(compId) === -1) {
                    sendScreenGeometry(windows[o]);
                    handledOutputs.push(compId);
                }
            }

            for (var k = 0; k < windows.length; k++) {
                var w = windows[k];
                if (!w.normalWindow && !w.dialog) continue;
                
                var wsId = getWorkspaceId(w);
                var isFloat = w.dialog || w.utility || w.fullScreen;
                var isMin = w.minimized || false; // Sincronización del estado de minimización
                
                callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowAdded", w.internalId.toString(), wsId, isFloat || false, isMin);
            }
        }
    }
}

function listenForCommands() {
    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
        if (response) applyCommands(response);
        listenForCommands();
    });
}

init();