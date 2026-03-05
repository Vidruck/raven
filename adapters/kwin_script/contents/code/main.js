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

function isManageable(w) {
    if (!w || w.deleted) return false;
    
    if (w.popupWindow || w.tooltip || w.onScreenDisplay || w.notification) return false;
    
    if (w.desktopWindow || w.dock || w.splash) return false;
    
    if (w.skipTaskbar || w.skipPager) return false;
    
    if (!w.normalWindow && !w.dialog) return false;
    
    return true;
}

// --- FOTOGRAFÍA DE ESTADO (SNAPSHOT) ---

function sendFullState() {
    var windows = workspace.windowList();
    var winState = [];
    var screens = {};
    
    for (var i = 0; i < windows.length; i++) {
        var w = windows[i];
        
        if (!isManageable(w)) continue;
        
        var wsId = getWorkspaceId(w);
        
        if (w.output && !screens[wsId]) {
            var desktop = (w.desktops && w.desktops.length > 0) ? w.desktops[0] : workspace.currentDesktop;
            var area = workspace.clientArea(0, w.output, desktop);
            screens[wsId] = {
                x: Math.round(area.x), y: Math.round(area.y),
                w: Math.round(area.width), h: Math.round(area.height)
            };
        }

        var strCap = w.caption ? w.caption.toString().toLowerCase() : "";
        var isPip = strCap.indexOf("picture-in-picture") !== -1 || strCap.indexOf("imagen en imagen") !== -1;
        var isFloat = Boolean(w.dialog || isPip);
        
        winState.push({
            id: w.internalId.toString(),
            ws: wsId,
            f: isFloat,
            m: Boolean(w.minimized)
        });
    }
    
    var payload = { windows: winState, screens: screens };
    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncState", JSON.stringify(payload));
}

// --- VIGILANTE DE EVENTOS ---

function bindWindow(w) {
    if (!isManageable(w)) return;
    if (w.__raven_bound) return;
    w.__raven_bound = true;
    
    w.minimizedChanged.connect(sendFullState);
    w.outputChanged.connect(sendFullState);
    w.desktopsChanged.connect(sendFullState);
    
    w.frameGeometryChanged.connect(function() {
        if (w.__was_moving && !w.interactiveMove) {
            w.__was_moving = false;
            sendFullState(); 
        } else if (w.interactiveMove) {
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
        if (isManageable(w)) {
            bindWindow(w);
            sendFullState();
        }
    });

    workspace.windowRemoved.connect(function(w) {
        sendFullState();
    });

    workspace.windowActivated.connect(function(w) {
        if (w && isManageable(w)) {
            callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", w.internalId.toString());
        }
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

// --- ALGORITMO WATCHDOG (Tolerancia a la Interfaz Gráfica) ---
var _is_listening = false;

function listenForCommands() {
    if (_is_listening) return;
    _is_listening = true;

    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
        _is_listening = false;
        
        if (response) {
            try { applyCommands(response); } catch (e) { print("[Raven] Error de parseo: " + e); }
            
            listenForCommands(); 
        } else {
            print("[Raven Bridge] Demonio no responde. Activando Watchdog de reconexión (3s)...");
            
            var retryTimer = new QTimer();
            retryTimer.interval = 3000;
            retryTimer.singleShot = true;
            retryTimer.triggered.connect(listenForCommands);
            retryTimer.start();
        }
    });
}

init();