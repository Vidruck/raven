/**
 * @fileoverview Raven Bridge para KDE Plasma 6 (Wayland).
 * @author Alejandro González Hernández (Vidruck)
 */

// Temporizador global para agrupar peticiones de sincronización (debouncing)
var _debounceTimer = new QTimer();
_debounceTimer.interval = 32; 
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
    if (!w || w.deleted || !w.managed) return false; //
    if (w.popupWindow || w.tooltip || w.onScreenDisplay || w.notification || w.specialWindow) return false;
    if (w.desktopWindow || w.dock || w.splash || w.skipTaskbar || w.skipPager) return false;

    var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
    if (strClass.indexOf("spectacle") !== -1 && w.fullScreen) return false;
    if (!w.normalWindow && !w.dialog && !w.utility) return false;

    return true;
}

/**
 * Determina si una ventana gestionable debe tratarse como flotante (fuera del layout en mosaico).
 * Identifica modales, diálogos, utilidades, ventanas PiP y herramientas de Raven.
 * @param {object} w - Objeto de ventana de KWin.
 * @returns {boolean} true si la ventana debe ser flotante.
 */
function isFloating(w) {
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
            winState.push({
                id: safeId, ws: wsId, f: isFloating(w),
                m: Boolean(w.minimized), p: Boolean(w.keepAbove)
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
 * @param {string} strategy - Estrategia de migración ("screen", "desktop" o "auto").
 */
function migrateWindow(win, strategy) {
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
    } catch (e) { print("[Raven] Error migración: " + e); }
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
                        if (w.maximizeMode === 3 || w.interactiveMove || w.interactiveResize) break;
                        w.__raven_mutating = true;
                        w.frameGeometry = { x: Math.round(cmd.x), y: Math.round(cmd.y), width: Math.round(cmd.width), height: Math.round(cmd.height) };
                        setKWinTimeout(function() { try { if (w) w.__raven_mutating = false; } catch(e){} }, 32);
                    } else if (cmd.action === "focus") {
                        workspace.activeWindow = w;
                    } else if (cmd.action.indexOf("migrate") !== -1) {
                        var strategy = (cmd.action === "migrate_to_next_screen") ? "screen" : 
                                       ((cmd.action === "migrate_to_next_workspace") ? "desktop" : "auto");
                        migrateWindow(w, strategy);
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

    callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
        if (_watchdog_timer) _watchdog_timer.stop();
        _is_listening = false;
        if (response) { applyCommands(response); setKWinTimeout(listenForCommands, 50); } 
        else { setKWinTimeout(listenForCommands, 3000); }
    });
}

/**
 * Conecta las señales de una ventana para sincronizar su estado ante cambios de geometría,
 * monitor, escritorio o minimización, respetando interacciones del usuario.
 * @param {object} w - Objeto de ventana de KWin.
 */
function bindWindow(w) {
    if (!isManageable(w) || w.__raven_bound) return;
    w.__raven_bound = true;
    w.minimizedChanged.connect(requestStateSync);
    w.outputChanged.connect(requestStateSync);
    w.desktopsChanged.connect(requestStateSync);
    
    w.frameGeometryChanged.connect(function() {
        if (w.__raven_mutating) return;
        if (w.interactiveMove || w.interactiveResize) { w.__was_interacting = true; return; }
        if (w.__was_interacting && !w.interactiveMove && !w.interactiveResize) {
            w.__was_interacting = false; requestStateSync(); return;
        }
        requestStateSync();
    });
}

/**
 * Inicializa el puente conectando las señales globales del espacio de trabajo (workspace),
 * registrando las ventanas existentes e iniciando la escucha de comandos.
 */
function init() {
    print("[Raven Bridge] Inicializando v2.7 (Latencia 16ms + PlacementArea)...");
    var initialWindows = workspace.windowList();
    for (var i=0; i<initialWindows.length; i++) bindWindow(initialWindows[i]);

    workspace.windowAdded.connect(function(w) { if (isManageable(w)) { bindWindow(w); requestStateSync(); } });
    workspace.windowRemoved.connect(requestStateSync);
    workspace.windowActivated.connect(function(w) {
        if (w && isManageable(w)) {
            var id = getSafeWindowId(w);
            if (id) callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", id, function(){});
        }
    });

    listenForCommands();
}

init();