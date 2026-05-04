/**
 * @fileoverview Raven Bridge para KDE Plasma 6 (Wayland).
 * Actúa como un cliente IPC, capturando el estado de composición de Wayland mediante la API de KWin
 * y enviándolo al demonio Python de Raven.
 * @author Alejandro González Hernández (Vidruck)
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

function isFloating(w) {
    if (w.dialog || w.utility || w.specialWindow || w.modal || w.transientFor) return true;
    if (w.maximizeMode == 3 || w.fullScreen) return true;
    if (w.onScreenDisplay || w.tooltip || w.notification || w.splash) return true;

    var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
    var strCap = w.caption ? w.caption.toString().toLowerCase() : "";
    var isRaven = strClass.indexOf("raven") !== -1 || strCap.indexOf("raven control center") !== -1;
    var isPip = strCap.indexOf("picture-in-picture") !== -1 ||
        strCap.indexOf("imagen en imagen") !== -1 ||
        strCap.indexOf("pip") !== -1 ||
        w.keepAbove;
    
    if (isPip && !w.keepAbove) {
        w.keepAbove = true;
    }
    
    var isSpectacle = strClass.indexOf("spectacle") !== -1;
    var isPortal = strClass.indexOf("xdg-desktop-portal") !== -1;
    var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
    var isVirtPopup = (strClass.indexOf("qemu") !== -1 || strClass.indexOf("virt-manager") !== -1) && !w.normalWindow;

    return Boolean(isPip || isSpectacle || isPortal || isKlipper || isVirtPopup || isRaven);
}

var _sync_timer = null;
function bindWindow(w) {
    if (!isManageable(w) || w.__raven_bound) return;
    w.__raven_bound = true;
    
    w.minimizedChanged.connect(sendFullState);
    w.outputChanged.connect(sendFullState);
    w.desktopsChanged.connect(sendFullState);
    w.captionChanged.connect(sendFullState);
    w.windowClassChanged.connect(sendFullState);
    
    w.frameGeometryChanged.connect(function() {
        if (w.__raven_mutating) return;
        if (w.interactiveMove || w.interactiveResize) {
            w.__was_interacting = true;
            return;
        }

        if (w.__was_interacting && !w.interactiveMove && !w.interactiveResize) {
            w.__was_interacting = false;
            
            var cx = w.frameGeometry.x + Math.round(w.frameGeometry.width / 2);
            var cy = w.frameGeometry.y + Math.round(w.frameGeometry.height / 2);
            var targetId = null;
            var windows = workspace.windowList();
            
            for (var i = 0; i < windows.length; i++) {
                var cand = windows[i];
                if (cand.internalId === w.internalId || !isManageable(cand) || isFloating(cand) || cand.minimized) continue;
                
                var r = cand.frameGeometry;
                if (cx >= r.x && cx <= r.x + r.width && cy >= r.y && cy <= r.y + r.height) {
                    targetId = cand.internalId.toString();
                    break;
                }
            }

            if (targetId) {
                print("[Raven Bridge] Drag-to-Swap detectado: " + w.internalId.toString() + " <-> " + targetId);
                try {
                    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "swapWindows", w.internalId.toString(), targetId);
                } catch(e) {}
            } else {
                sendFullState();
            }
            return;
        }

        sendFullState();
    });
}


function sendFullState() {
    if (_sync_timer) {
        return;
    }
    _sync_timer = setKWinTimeout(function () {
        _sync_timer = null;
        var windows = workspace.windowList();
        var winState = [];
        var screens = {};
        
        for (var i = 0; i < windows.length; i++) {
            var w = windows[i];

            if (!isManageable(w)) continue;
            var wsId = getWorkspaceId(w);
            var output = w.output || workspace.activeOutput;

            if (output && !screens[wsId]) {
                var desktop = (w.desktops && w.desktops.length > 0) ? w.desktops[0] : workspace.currentDesktop;
                var area = workspace.clientArea(0, output, desktop);
                screens[wsId] = {
                    x: Math.round(area.x),
                    y: Math.round(area.y),
                    w: Math.round(area.width),
                    h: Math.round(area.height),
                };
            }
            winState.push({
                id: w.internalId.toString(),
                ws: wsId,
                f: isFloating(w),
                m: Boolean(w.minimized),
                p: Boolean((w.caption && String(w.caption).toLowerCase().indexOf("picture-in-picture") !== -1) || w.keepAbove)
            });
        }
        
        var payload = { windows: winState, screens: screens };
        try {
            callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncState", JSON.stringify(payload));
        } catch (e) {
            print("[Raven Bridge] D-bus Drop (Filtro de Seguridad Activo)" + e);
        }
    }, 16); 
}


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

                    var fresh_rect = {
                        x: Math.round(cmd.x),
                        y: Math.round(cmd.y),
                        width: Math.round(cmd.width),
                        height: Math.round(cmd.height)
                    };

                    windows[j].__raven_mutating = true;
                    windows[j].frameGeometry = fresh_rect;
                    setKWinTimeout((function(win) {
                        return function() {
                            if (win) win.__raven_mutating = false;
                        };
                    })(windows[j]), 50);

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

function setKWinTimeout(callback, ms) {
    var timer = new QTimer();
    timer.interval = ms;
    timer.singleShot = true;
    timer.timeout.connect(callback);
    timer.start();
    return timer;
}

function clearKWinTimeout(timer) {
    if (timer) {
        timer.stop();
    }
}

function listenForCommands() {
    if (_is_listening) return;
    _is_listening = true;

    if (_watchdog_timer) clearKWinTimeout(_watchdog_timer);

    _watchdog_timer = setKWinTimeout(function () {
        print("[Raven Bridge] Watchdog liberando candado muerto de DBus.");
        _is_listening = false;
        listenForCommands();
    }, 8000);

    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function (response) {
        if (_watchdog_timer) clearKWinTimeout(_watchdog_timer);
        _is_listening = false;

        if (response) {
            try { applyCommands(response); } catch (e) { print("[Raven] Parse error: " + e); }
            setKWinTimeout(listenForCommands, 50);
        } else {
            setKWinTimeout(listenForCommands, 3000);
        }
    });
}

init();