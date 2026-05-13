/**
 * @fileoverview Raven Bridge para KDE Plasma 6 (Wayland).
 * @author Alejandro González Hernández (Vidruck)
 */

// Temporizador global para agrupar peticiones de sincronización (debouncing)
var _debounceTimer = new QTimer();
_debounceTimer.interval = 8s0; 
_debounceTimer.singleShot = true;
_debounceTimer.timeout.connect(syncState);

/**
 * Obtiene de forma segura el identificador interno de una ventana.
 * @param {object} w - Objeto de ventana de KWin.
 * @returns {string|null} Identificador de la ventana como texto, o null si es inválida.
 */
function getSafeWindowId(w) {
    try {
        return (w && w.internalId) ? w.internalId.toString() : null;
    } catch (e) { return null; }
}

/**
 * Construye un identificador único del espacio de trabajo combinando el monitor y el escritorio virtual.
 * @param {object} window - Objeto de ventana de KWin.
 * @returns {string} Identificador en formato "nombre_salida||id_escritorio".
 */
function getWorkspaceId(window) {
    try {
        var output = window.output || workspace.activeOutput;
        var outName = output ? output.name : "default";
        var desktopId = (window.desktops && window.desktops.length > 0) ? 
                        window.desktops[0].id.toString() : 
                        (workspace.currentDesktop ? workspace.currentDesktop.id.toString() : "default_desk");
        return outName + "||" + desktopId;
    } catch (e) { return "default||default_desk"; }
}

/**
 * Determina si una ventana debe ser gestionada por el motor de diseño (tiling).
 * Excluye tooltips, notificaciones, paneles y ventanas especiales.
 * @param {object} w - Objeto de ventana de KWin.
 * @returns {boolean} true si la ventana es gestionable.
 */
function isManageable(w) {
    try {
        if (!w || w.deleted || !w.managed) return false; //
        if (w.popupWindow || w.tooltip || w.onScreenDisplay || w.notification || w.specialWindow) return false;
        if (w.desktopWindow || w.dock || w.splash || w.skipTaskbar || w.skipPager) return false;

        var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
        if (strClass.indexOf("spectacle") !== -1 && w.fullScreen) return false;
        if (!w.normalWindow && !w.dialog && !w.utility) return false;

        return true;
    } catch (e) { return false; }
}

/**
 * Determina si una ventana gestionable debe tratarse como flotante (fuera del layout en mosaico).
 * Identifica modales, diálogos, utilidades, ventanas PiP y herramientas de Raven.
 * @param {object} w - Objeto de ventana de KWin.
 * @returns {boolean} true si la ventana debe ser flotante.
 */
function isFloating(w) {
    try {
        if (w.dialog || w.utility || w.specialWindow || w.modal || w.transientFor) return true;
        if (w.maximizeMode == 3 || w.fullScreen) return true;

        var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
        var strCap = w.caption ? w.caption.toString().toLowerCase() : "";
        
        var isPip = strCap.indexOf("picture-in-picture") !== -1 || strCap.indexOf("pip") !== -1 || w.keepAbove;
        if (isPip && !w.keepAbove) w.keepAbove = true;
        
        var isRaven = strClass.indexOf("raven") !== -1 || strCap.indexOf("raven control center") !== -1;
        var isSpectacle = strClass.indexOf("spectacle") !== -1;
        var isKlipper = strClass.indexOf("klipper") !== -1 || strClass.indexOf("plasma.clipboard") !== -1;
        var isVirtPopup = (strClass.indexOf("qemu") !== -1 || strClass.indexOf("virt-manager") !== -1) && !w.normalWindow;

        return Boolean(isPip || isSpectacle || isKlipper || isVirtPopup || isRaven);
    } catch (e) { return true; }
}


/**
 * Programa una sincronización de estado agrupando peticiones cercanas mediante debouncing.
 */
function requestStateSync() {
    if (_debounceTimer.active) _debounceTimer.stop();
    _debounceTimer.start(); // Iniciado mediante QTimer para mayor estabilidad
}

/**
 * Recopila el estado global de las ventanas gestionables y las áreas de pantalla,
 * transmitiendo el payload resultante al demonio de Raven a través de D-Bus.
 */
function syncState() {
    var windows = workspace.windowList();
    var winState = [];
    var screens = {};
    
    for (var i = 0; i < windows.length; i++) {
        var w = windows[i];
        try {
            if (!isManageable(w)) continue;
            var safeId = getSafeWindowId(w);
            if (!safeId) continue;

            var wsId = getWorkspaceId(w);
            var output = w.output || workspace.activeOutput;

            if (output && !screens[wsId]) {
                var desktop = (w.desktops && w.desktops.length > 0) ? w.desktops[0] : workspace.currentDesktop;
                var area = workspace.clientArea(KWin.PlacementArea, output, desktop);
                screens[wsId] = {
                    x: Math.round(area.x), y: Math.round(area.y),
                    w: Math.round(area.width), h: Math.round(area.height)
                };
            }
            var geom = w.frameGeometry;
            winState.push({
                id: safeId, ws: wsId, f: isFloating(w),
                m: Boolean(w.minimized), p: Boolean(w.keepAbove),
                x: Math.round(geom.x), y: Math.round(geom.y),
                w: Math.round(geom.width), h: Math.round(geom.height)
            });
        } catch (e) { print("[Raven] Error en syncState: " + e); }
    }
    
    var payload = { windows: winState, screens: screens };
    try {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncState", JSON.stringify(payload), function() {});
    } catch (e) { print("[Raven Bridge] D-bus Drop: " + e); }
}


/**
 * Migra una ventana hacia otra pantalla o escritorio virtual, o la minimiza si no hay espacio.
 * @param {object} win - Objeto de ventana de KWin a migrar.
 * @param {string} target_ws - Espacio de trabajo destino explícito.
 */
function migrateWindow(win, target_ws) {
    if (!target_ws || !win) return;
    try {
        var parts = target_ws.split("||");
        if (parts.length < 2) return;
        var outName = parts[0];
        var deskId = parts[1];

        var outputs = workspace.outputs || [];
        for (var i = 0; i < outputs.length; i++) {
            if (outputs[i].name === outName) {
                win.output = outputs[i];
                break;
            }
        }

        var desktops = workspace.desktops || [];
        for (var j = 0; j < desktops.length; j++) {
            if (desktops[j].id.toString() === deskId) {
                win.desktops = [desktops[j]];
                break;
            }
        }
    } catch (e) { print("[Raven] Error migración: " + e); }
}

/**
 * Estrategia de respaldo para desbordar ventanas a otra pantalla, escritorio, o minimizar.
 */
function migrateWindowFallback(win, strategy) {
    try {
        var outputs = workspace.outputs || [];
        var desktops = workspace.desktops || [];
        var tryScreen = (strategy === "auto" || strategy === "screen");
        var tryDesktop = (strategy === "auto" || strategy === "desktop");

        if (tryScreen && outputs.length > 1) {
            var currentOut = win.output || workspace.activeOutput;
            var nextIdx = 0;
            for (var i = 0; i < outputs.length; i++) {
                if (outputs[i].name === currentOut.name) {
                    nextIdx = (i + 1) % outputs.length;
                    break;
                }
            }
            win.output = outputs[nextIdx];
            return;
        }

        if (tryDesktop && desktops.length > 1) {
            var currentDesks = win.desktops || [];
            var currentDesk = currentDesks.length > 0 ? currentDesks[0] : workspace.currentDesktop;
            var nextIdxD = 0;
            for (var d = 0; d < desktops.length; d++) {
                if (desktops[d].id === currentDesk.id) {
                    nextIdxD = (d + 1) % desktops.length;
                    break;
                }
            }
            win.desktops = [desktops[nextIdxD]];
            return;
        }

        if (strategy === "auto") {
            win.minimized = true; 
            callDBus("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify",
                "Raven", 0, "dialog-warning", "Límite de Espacio", "Ventana minimizada por falta de espacio.", [], {}, -1);
        }
    } catch (e) { print("[Raven] Error migración fallback: " + e); }
}


/**
 * Parsea y ejecuta las órdenes de diseño (movimiento, enfoque, migración) enviadas desde Rust.
 * @param {string} commandsJson - Array de comandos en formato JSON.
 */
function applyCommands(commandsJson) {
    if (!commandsJson) return;
    try {
        var cmds = JSON.parse(commandsJson);
        var windows = workspace.windowList();

        for (var i = 0; i < cmds.length; i++) {
            var cmd = cmds[i];
            if (cmd.action === "request_sync") { requestStateSync(); continue; }

            for (var j = 0; j < windows.length; j++) {
                var w = windows[j];
                if (getSafeWindowId(w) === cmd.window_id) {
                    if (cmd.action === "move") {
                        try {
                            if (w.maximizeMode === 3 || w.interactiveMove || w.interactiveResize) break;
                            w.__raven_mutating = true;
                            w.frameGeometry = { x: Math.round(cmd.x), y: Math.round(cmd.y), width: Math.round(cmd.width), height: Math.round(cmd.height) };
                            setKWinTimeout(function() { try { if (w) w.__raven_mutating = false; } catch(e){} }, 100);
                        } catch(e) { print("[Raven] Error apply move: " + e); }
                    } else if (cmd.action === "focus") {
                        try { workspace.activeWindow = w; } catch(e){}
                    } else if (cmd.action === "migrate_and_move") {
                        try {
                            w.__raven_mutating = true;
                            migrateWindow(w, cmd.target_ws);
                            w.frameGeometry = { x: Math.round(cmd.x), y: Math.round(cmd.y), width: Math.round(cmd.width), height: Math.round(cmd.height) };
                            setKWinTimeout(function() { try { if (w) w.__raven_mutating = false; } catch(e){} }, 100);
                        } catch(e) { print("[Raven] Error apply migrate: " + e); }
                    } else if (cmd.action === "minimize") {
                        try { w.minimized = true; } catch(e) { print("[Raven] Error apply minimize: " + e); }
                    } else if (cmd.action === "migrate_native") {
                        try {
                            w.__raven_mutating = true;
                            var dir = cmd.direction || "auto";
                            if (dir.indexOf("screen") !== -1) {
                                var outs = workspace.outputs || [];
                                if (outs.length > 1) {
                                    var currOut = w.output || workspace.activeOutput;
                                    var currName = currOut ? currOut.name : "";
                                    var idx = 0;
                                    for (var k = 0; k < outs.length; k++) { if (outs[k].name === currName) { idx = k; break; } }
                                    var step = dir === "screen_prev" ? outs.length - 1 : 1;
                                    var nextIdx = (idx + step) % outs.length;
                                    w.output = outs[nextIdx];
                                }
                            } else if (dir.indexOf("desktop") !== -1) {
                                var desks = workspace.desktops || [];
                                if (desks.length > 1) {
                                    var currDesk = (w.desktops && w.desktops.length > 0) ? w.desktops[0] : workspace.currentDesktop;
                                    var currId = currDesk ? currDesk.id.toString() : "";
                                    var idx = 0;
                                    for (var k = 0; k < desks.length; k++) { if (desks[k].id.toString() === currId) { idx = k; break; } }
                                    var step = dir === "desktop_prev" ? desks.length - 1 : 1;
                                    var nextIdx = (idx + step) % desks.length;
                                    w.desktops = [desks[nextIdx]];
                                }
                            } else if (dir === "auto") {
                                migrateWindowFallback(w, "auto");
                            }
                            setKWinTimeout(function() { try { if (w) w.__raven_mutating = false; } catch(e){} }, 100);
                        } catch(e) { print("[Raven] Error apply migrate_native: " + e); }
                    } else if (cmd.action.indexOf("migrate") !== -1 && cmd.action !== "migrate_and_move") {
                        try {
                            w.__raven_mutating = true;
                            var strategy = (cmd.action === "migrate_to_next_screen") ? "screen" : 
                                           ((cmd.action === "migrate_to_next_workspace") ? "desktop" : "auto");
                            migrateWindowFallback(w, strategy);
                            setKWinTimeout(function() { try { if (w) w.__raven_mutating = false; } catch(e){} }, 100);
                        } catch(e) { print("[Raven] Error apply fallback migrate: " + e); }
                    }
                    break;
                }
            }
        }
    } catch (e) { print("[Raven Bridge] Error applyCommands: " + e); }
}

// Estado y temporizador de supervisión para el bucle de escucha de comandos
var _is_listening = false;
var _watchdog_timer = null;

/**
 * Crea un temporizador de disparo único (similar a setTimeout) nativo para KWin.
 * @param {function} callback - Función a ejecutar tras el tiempo de espera.
 * @param {number} ms - Milisegundos a esperar.
 * @returns {object} Instancia del QTimer iniciado.
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
 * Inicia el bucle de consulta (long-polling) para recibir comandos pendientes desde D-Bus.
 * Utiliza un temporizador de supervisión (watchdog) para autorecuperarse ante bloqueos.
 */
function listenForCommands() {
    if (_is_listening) return;
    _is_listening = true;
    if (_watchdog_timer) _watchdog_timer.stop();
    _watchdog_timer = setKWinTimeout(function() { _is_listening = false; listenForCommands(); }, 8000);

    try {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
            if (_watchdog_timer) _watchdog_timer.stop();
            _is_listening = false;
            if (response) { applyCommands(response); setKWinTimeout(listenForCommands, 50); } 
            else { setKWinTimeout(listenForCommands, 3000); }
        });
    } catch (e) {
        print("[Raven Bridge] Error getPendingCommands D-Bus: " + e);
        _is_listening = false;
        setKWinTimeout(listenForCommands, 3000);
    }
}

/**
 * Conecta las señales de una ventana para sincronizar su estado ante cambios de geometría,
 * monitor, escritorio o minimización, respetando interacciones del usuario.
 * @param {object} w - Objeto de ventana de KWin.
 */
function bindWindow(w) {
    try {
        if (!isManageable(w) || w.__raven_bound) return;
        w.__raven_bound = true;
        w.minimizedChanged.connect(requestStateSync);
        w.outputChanged.connect(requestStateSync);
        w.desktopsChanged.connect(requestStateSync);
        
        w.frameGeometryChanged.connect(function() {
            try {
                if (w.__raven_mutating) return;
                if (w.interactiveMove || w.interactiveResize) { w.__was_interacting = true; return; }
                if (w.__was_interacting && !w.interactiveMove && !w.interactiveResize) {
                    w.__was_interacting = false; requestStateSync(); return;
                }
                requestStateSync();
            } catch(e) { print("[Raven] Error frameGeometryChanged: " + e); }
        });
    } catch(e) { print("[Raven] Error bindWindow: " + e); }
}

/**
 * Inicializa el puente conectando las señales globales del espacio de trabajo (workspace),
 * registrando las ventanas existentes e iniciando la escucha de comandos.
 */
function init() {
    print("[Raven Bridge] Inicializando v2.8 (Debounce 60ms)...");
    var initialWindows = workspace.windowList();
    for (var i=0; i<initialWindows.length; i++) bindWindow(initialWindows[i]);

    workspace.windowAdded.connect(function(w) { if (isManageable(w)) { bindWindow(w); requestStateSync(); } });
    workspace.windowRemoved.connect(requestStateSync);
    workspace.windowActivated.connect(function(w) {
        if (w && isManageable(w)) {
            var id = getSafeWindowId(w);
            try {
                if (id) callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", id, function(){});
            } catch (e) { print("[Raven] Error windowActivated D-Bus: " + e); }
        }
    });

    try {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "bridgeReady", function() {});
    } catch (e) { print("[Raven] Error bridgeReady D-Bus: " + e); }
    listenForCommands();
}

init();