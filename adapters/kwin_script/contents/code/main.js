/**
 * @fileoverview Raven Bridge para KDE Plasma 6 (Wayland).
 * 
 * Este script actúa como un puente (bridge) entre el gestor de composición KWin y el daemon 
 * de Raven. Su función principal es capturar eventos de ventanas y cambios en la composición,
 * sincronizando el estado mediante D-Bus para permitir el manejo del tiling (mosaico) desde 
 * el motor externo en Python/Rust.
 * 
 * @author Alejandro González Hernández (Vidruck)
 */

/**
 * Genera un identificador único para el espacio de trabajo actual basado en el monitor y el escritorio virtual.
 * 
 * @param {KWin.Window} window La ventana de la cual se desea obtener el ID del workspace.
 * @returns {string} Un string con el formato "NombreMonitor||IDEscritorio".
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
 * Determina si una ventana es candidata para ser gestionada por el motor de tiling de Raven.
 * Filtra ventanas especiales como paneles, tooltips, notificaciones y diálogos de sistema específicos.
 * 
 * @param {KWin.Window} w La ventana a evaluar.
 * @returns {boolean} True si la ventana es gestionable, False en caso contrario.
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
 * Evalúa si una ventana debe ser tratada como flotante (floating) o si debe entrar al layout de mosaico.
 * Considera tipos de ventana, estados de maximización y clases de recursos específicas (ej. Picture-in-Picture).
 * 
 * @param {KWin.Window} w La ventana a evaluar.
 * @returns {boolean} True si la ventana es flotante, False si es apta para tiling.
 */


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

/**
 * Conecta los eventos de cambio de una ventana a la lógica de sincronización de Raven.
 * Gestiona cambios de estado (minimizado, geometría, clase) y detecta interacciones de intercambio (drag-to-swap).
 * 
 * @param {KWin.Window} w La ventana a vincular.
 */

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
            sendFullState();
            return;
        }

        sendFullState();
    });
}

/**
 * Envía el estado completo de todas las ventanas gestionables y las geometrías de pantalla a Raven.
 * Implementa un mecanismo de debouncing (32ms) para evitar saturar el bus de D-Bus durante cambios rápidos.
 */
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
    }, 32); 
}


/**
 * Inicializa el motor de captura de Raven Bridge.
 * Configura los escuchas globales de workspace y vincula las ventanas existentes.
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
 * Ejecuta la lógica de migración de una ventana a otro monitor o escritorio.
 * Sigue la prioridad establecida: 1° Monitor Secundario, 2° Escritorio Virtual.
 * 
 * @param {KWin.Window} win La ventana a migrar.
 * @param {string} strategy Estrategia: 'auto', 'screen', 'desktop'.
 */
function migrateWindow(win, strategy) {
    var screens = workspace.screens || [];
    var desktops = workspace.desktops || [];
    
    var tryScreen = (strategy === "auto" || strategy === "screen");
    var tryDesktop = (strategy === "auto" || strategy === "desktop");

    // 1. Intentar mover a siguiente pantalla
    if (tryScreen && screens.length > 1) {
        var currentOut = win.output || workspace.activeOutput;
        var idx = screens.indexOf(currentOut);
        if (idx === -1) idx = 0;
        var nextIdx = (idx + 1) % screens.length;
        win.output = screens[nextIdx];
        return;
    }

    // 2. Intentar mover a siguiente escritorio virtual
    if (tryDesktop && desktops.length > 1) {
        var currentDesks = win.desktops || [];
        var currentDesk = currentDesks.length > 0 ? currentDesks[0] : workspace.currentDesktop;
        var idx = desktops.indexOf(currentDesk);
        if (idx === -1) idx = 0;
        var nextIdx = (idx + 1) % desktops.length;
        win.desktops = [desktops[nextIdx]];
        return;
    }

    // 3. Fallo: No hay escape posible
    if (strategy === "auto") {
        print("[Raven] Fallo migración: solo hay 1 monitor y 1 escritorio.");
        try {
            callDBus("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify",
                "Raven", 0, "dialog-warning", "Límite de Espacio Alcanzado", "Crea un escritorio virtual adicional para alojar las ventanas desbordadas.", [], {}, -1);
        } catch(e) {}
    }
}

/**
 * Procesa y aplica una lista de comandos recibidos desde el daemon de Raven.
 * Soporta acciones de movimiento (move), enfoque (focus) y peticiones de sincronización forzada.
 * 
 * @param {string} commandsJson String JSON que contiene el arreglo de comandos a ejecutar.
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
                    })(windows[j]), 32);

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
        else if (cmd.action === "migrate_window_auto" || cmd.action === "migrate_to_next_screen" || cmd.action === "migrate_to_next_workspace") {
            var strategy = "auto";
            if (cmd.action === "migrate_to_next_screen") strategy = "screen";
            if (cmd.action === "migrate_to_next_workspace") strategy = "desktop";
            
            for (var m = 0; m < windows.length; m++) {
                if (windows[m].internalId.toString() === cmd.window_id) {
                    migrateWindow(windows[m], strategy);
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
 * Crea un temporizador único (SingleShot) utilizando la API de QTimer de Qt.
 * Esencial para operaciones asíncronas dentro del contexto de KWin.
 * 
 * @param {function} callback Función a ejecutar cuando el tiempo expire.
 * @param {number} ms Tiempo de espera en milisegundos.
 * @returns {QTimer} Instancia del temporizador creado.
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
 * Detiene un temporizador activo de forma segura.
 * 
 * @param {QTimer} timer La instancia del temporizador a detener.
 */
function clearKWinTimeout(timer) {
    if (timer) {
        timer.stop();
    }
}

/**
 * Mantiene un bucle persistente de comunicación con Raven vía D-Bus.
 * Solicita comandos pendientes y gestiona un Watchdog para evitar bloqueos en la comunicación IPC.
 */
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