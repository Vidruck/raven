/**
 * @fileoverview Raven Bridge for KDE Plasma 6 (Wayland).
 * Acts as an IPC client, capturing Wayland's composition state via KWin API
 * and forwarding it to the Raven Python Daemon.
 * @author Alejandro González Hernández (Vidruck)
 */

/**
 * Generates a unique identifier for a window's current workspace.
 * Implementa contingencia (Fallback) para ventanas recién nacidas en Wayland.
 */
function getWorkspaceId(window) {
    var output = window.output || workspace.activeOutput;
    var outName = output ? output.name : "default";
    var desktopId = "default_desk";
    
    if (window.desktops && window.desktops.length > 0) {
        desktopId = window.desktops[0].id.toString();
    } else if (workspace.currentDesktop) {
        desktopId = workspace.currentDesktop.id.toString();
    }
    return outName + "||" + desktopId;
}

/**
 * Strict heuristic filter to identify manageable top-level windows.
 * Excludes native popups, OSDs, panels, and specific KWin internal surfaces.
 * @param {object} w - The KWin window client object.
 * @returns {boolean} True if the window is a valid candidate for state tracking.
 */
function isManageable(w) {
    if (!w || w.deleted) return false;
    if (w.popupWindow || w.tooltip || w.onScreenDisplay || w.notification) return false;
    if (w.desktopWindow || w.dock || w.splash) return false;
    if (w.skipTaskbar || w.skipPager) return false;
    
    var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
    if (strClass.indexOf("spectacle") !== -1 && w.fullScreen) return false;
    if (!w.normalWindow && !w.dialog && !w.utility) return false;
    
    return true;
}

/**
 * Determines if a manageable window should bypass the tiling geometry (Float).
 * @param {object} w - The KWin window client object.
 * @returns {boolean} True if the window should float (e.g., PiP, utilities, VMs).
 */
function isFloating(w) {
    
    if (w.dialog || w.utility || w.specialWindow || w.modal || w.transientFor) return true;
    if (w.maximizeMode == 3 || w.fullScreen) return true;
    if (w.onScreenDisplay || w.tooltip || w.notification || w.splash) return true;

    var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
    var strCap = w.caption ? w.caption.toString().toLowerCase() : "";
    var isPip = strCap.indexOf("picture-in-picture") !== -1 || 
                strCap.indexOf("imagen en imagen") !== -1 || 
                strCap.indexOf("pip") !== -1 || 
                w.keepAbove;
    var isSpectacle = strClass.indexOf("spectacle") !== -1;
    var isPortal = strClass.indexOf("xdg-desktop-portal") !== -1;
    var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
    var isVirtPopup = (strClass.indexOf("qemu") !== -1 || strClass.indexOf("virt-manager") !== -1) && !w.normalWindow;

    return Boolean(isPip || isSpectacle || isPortal || isKlipper || isVirtPopup);
}

/**
 * Captures the current atomic state of all workspaces and windows.
 */
function sendFullState() {
    var windows = workspace.windowList();
    var winState = [];
    var screens = {};
    
    for (var i = 0; i < windows.length; i++) {
        var w = windows[i];
        if (!isManageable(w)) continue;
        
        var wsId = getWorkspaceId(w);
        var output = w.output || workspace.activeOutput; // Fallback forzado
        
        // Poblamos el diccionario de pantallas usando el output garantizado
        if (output && !screens[wsId]) {
            var desktop = (w.desktops && w.desktops.length > 0) ? w.desktops[0] : workspace.currentDesktop;
            var area = workspace.clientArea(0, output, desktop);
            screens[wsId] = {
                x: Math.round(area.x), y: Math.round(area.y),
                w: Math.round(area.width), h: Math.round(area.height)
            };
        }

        winState.push({
            id: w.internalId.toString(),
            ws: wsId,
            f: isFloating(w),
            m: Boolean(w.minimized)
        });
    }
    
    var payload = { windows: winState, screens: screens };
    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncState", JSON.stringify(payload));
}

/**
 * Attaches event listeners to a specific window to track state mutations.
 * Implements logic to detect the end of interactive user drags (Drop).
 * @param {object} w - The KWin window client object.
 */
function bindWindow(w) {
    if (!isManageable(w) || w.__raven_bound) return;
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

/**
 * Entry point. Binds initial window states and registers global workspace hooks.
 */
function init() {
    print("[Raven Bridge] Snapshot Engine initialized.");
    var initialWindows = workspace.windowList();
    for (var i=0; i<initialWindows.length; i++) bindWindow(initialWindows[i]);

    workspace.windowAdded.connect(function(w) {
        if (isManageable(w)) {
            bindWindow(w);
            sendFullState();
        }
    });

    workspace.windowRemoved.connect(function(w) { sendFullState(); });
    workspace.windowActivated.connect(function(w) {
        if (w && isManageable(w)) {
            callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", w.internalId.toString());
        }
    });

    listenForCommands();
}

/**
 * Parses and executes geometric or focus commands dispatched by the Python Daemon.
 */
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
                    
                    var output = windows[j].output || workspace.activeOutput;
                    var desktop = (windows[j].desktops && windows[j].desktops.length > 0) ? windows[j].desktops[0] : workspace.currentDesktop;
                    var fresh_rect = workspace.clientArea(0, output, desktop);
                    
                    fresh_rect.x = Math.round(cmd.x);
                    fresh_rect.y = Math.round(cmd.y);
                    fresh_rect.width = Math.round(cmd.width);
                    fresh_rect.height = Math.round(cmd.height);
                    
                    windows[j].frameGeometry = fresh_rect;
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

var _is_listening = false;
var _watchdog_timer = null;

/**
 * Envoltura nativa para interactuar con la clase C++ QTimer de Qt.
 * Reemplaza a setTimeout en entornos QJSEngine restrictivos.
 */
function setKWinTimeout(callback, ms) {
    var timer = new QTimer();
    timer.interval = ms;
    timer.singleShot = true;
    timer.timeout.connect(callback);
    timer.start();
    return timer;
}

/**
 * Destruye de forma segura el objeto QTimer en memoria.
 * Reemplaza a clearTimeout.
 */
function clearKWinTimeout(timer) {
    if (timer) {
        timer.stop();
    }
}

/**
 * Recursive asynchronous listener polling DBus for incoming commands.
 * Utiliza QTimer nativo para evitar cuelgues del motor KWin.
 */
function listenForCommands() {
    if (_is_listening) return;
    _is_listening = true;

    if (_watchdog_timer) clearKWinTimeout(_watchdog_timer);
    
    _watchdog_timer = setKWinTimeout(function() {
        print("[Raven Bridge] Watchdog liberando candado muerto de DBus.");
        _is_listening = false;
        listenForCommands();
    }, 8000); 

    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
        if (_watchdog_timer) clearKWinTimeout(_watchdog_timer);
        _is_listening = false;
        
        if (response) {
            try { applyCommands(response); } catch (e) { print("[Raven] Parse error: " + e); }
            setKWinTimeout(listenForCommands, 50); 
        } else {
            print("[Raven Bridge] Demonio inalcanzable. Reintentando...");
            setKWinTimeout(listenForCommands, 3000);
        }
    });
}

init();