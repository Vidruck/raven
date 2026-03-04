// RAVEN BRIDGE - KDE PLASMA 6 (WAYLAND)

function sendScreenGeometry(window) {
    if (!window || !window.output) return;
    var area = workspace.clientArea(0, window.output, workspace.currentDesktop);
    var workspaceId = window.output.name; // Ej: "eDP-1", "HDMI-A-1"
    
    callDBus(
        "org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "updateScreenGeometry", 
        workspaceId, Math.round(area.x), Math.round(area.y), Math.round(area.width), Math.round(area.height)
    );
}

function init() {
    print("[Raven Bridge] Iniciando blindaje de filtrado y estados...");

    workspace.windowAdded.connect(function(window) {
        if (!window) return;
        
        // --- CAPA 1: FILTRADO DE VENTANAS ---
        if (window.skipTaskbar || window.skipPager || window.skipSwitcher || !window.moveable || !window.resizeable) {
            return; 
        }

        var strClass = window.resourceClass ? window.resourceClass.toString().toLowerCase() : "";
        var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
        var isSpectacle = strClass.indexOf("spectacle") !== -1;
        
        // Si es una ventana de sistema o alguna de nuestras excepciones, es FLOTANTE (Raven la ignora)
        var isFloating = window.dialog || window.utility || isSpectacle || isKlipper;

        var windowId = window.internalId.toString();
        var workspaceId = window.output ? window.output.name : "default";

        // --- CAPA 2: ESCUCHAR MINIMIZACIÓN ---
        window.minimizedChanged.connect(function() {
            print("[Raven Bridge] Estado de minimización cambió para: " + windowId);
            callDBus(
                "org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowMinimizedChanged", 
                windowId, window.minimized
            );
        });

        // Reportamos el nacimiento de ventanas
        callDBus(
            "org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowAdded", 
            windowId, workspaceId, isFloating
        );
        
        sendScreenGeometry(window);
    });

    workspace.windowRemoved.connect(function(window) {
        if (!window) return;
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowRemoved", window.internalId.toString());
    });
    // --- REGISTRO DE ATAJOS GLOBALES (GLOBAL SHORTCUTS) ---
    
    registerShortcut("Raven Increase Master", "Raven: Aumentar ventanas maestras", "Meta+I", function() {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "incrementMaster");
    });
    
    registerShortcut("Raven Decrease Master", "Raven: Disminuir ventanas maestras", "Meta+D", function() {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "decrementMaster");
    });
    
    registerShortcut("Raven Increase Ratio", "Raven: Expandir área maestra", "Meta+L", function() {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "increaseRatio");
    });
    
    registerShortcut("Raven Decrease Ratio", "Raven: Encoger área maestra", "Meta+H", function() {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "decreaseRatio");
    });

    workspace.windowActivated.connect(function(window) {
        if (!window) return;
        var windowId = window.internalId.toString();
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", windowId);
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
                var win = windows[j];
                if (win.internalId.toString() === cmd.window_id) {
                    win.frameGeometry = {
                        x: Math.round(cmd.x),
                        y: Math.round(cmd.y),
                        width: Math.round(cmd.width),
                        height: Math.round(cmd.height)
                    };
                    break;
                }
            }
        }
        else if (cmd.action === "request_sync") {
            print("[Raven Bridge] Petición de sincronización multi-monitor recibida.");
            
            // A. Primero actualizamos las resoluciones de todos los monitores activos
            var handledOutputs = [];
            for (var o = 0; o < windows.length; o++) {
                var outName = windows[o].output ? windows[o].output.name : null;
                if (outName && handledOutputs.indexOf(outName) === -1) {
                    sendScreenGeometry(windows[o]);
                    handledOutputs.push(outName);
                }
            }
        
            // B. Segundo enviamos el inventario de ventanas atadas a su monitor
            for (var k = 0; k < windows.length; k++) {
                var w = windows[k];
                if (!w.normalWindow && !w.dialog) continue;
                
                var workspaceId = w.output ? w.output.name : "default";
                
                var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
                var isSpectacle = strClass.indexOf("spectacle") !== -1;
                var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
                var isFloating = w.dialog || w.utility || isSpectacle || isKlipper;
                
                callDBus(
                    "org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowAdded", 
                    w.internalId.toString(), workspaceId, isFloating || false
                );
            }
            
        }
        else if (cmd.action === "focus") {
            for (var j = 0; j < windows.length; j++) {
                if (windows[j].internalId.toString() === cmd.window_id) {
                    workspace.activeWindow = windows[j];
                    break;
                }
            }
        }
    }
}

function listenForCommands() {
    callDBus(
        "org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", 
        function(response) {
            if (response) applyCommands(response);
            listenForCommands();
        }
    );
}

init();