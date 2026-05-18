/**
 * @fileoverview Raven Bridge para KDE Plasma 6 (Wayland).
 * @author Alejandro González Hernández (Vidruck)
 */

var _debounceTimer = null;
try {
    _debounceTimer = new QTimer();
    _debounceTimer.interval = 60; 
    _debounceTimer.singleShot = true;
    _debounceTimer.timeout.connect(syncState);
} catch (e) {
    print("[Raven Bridge] Error inicializando timer global: " + e);
}

/**
 * Obtiene el identificador universal nativo de KWin para la ventana.
 * Este UUID es persistente durante todo el ciclo de vida de la superficie Wayland.
 * @param {object} w - Objeto de ventana de KWin.
 * @returns {string|null} Identificador único, o null si es inválida.
 */
function getSafeWindowId(w) {
    try {
        if (!w || !w.internalId) return null;
        return w.internalId.toString();
    } catch (e) { return null; }
}

/**
 * Construye un identificador único del espacio de trabajo combinando el monitor y el escritorio virtual.
 * @param {object} window - Objeto de ventana de KWin.
 * @returns {string} Identificador en formato "nombre_salida||id_escritorio".
 */
function getWorkspaceId(window) {
    try {
        if (!window || window.deleted) return "default||default_desk";
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
        if (!w || w.deleted || !w.managed) return false;
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
        if (!w || w.deleted) return true;
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
    try {
        if (!_debounceTimer) {
            _debounceTimer = new QTimer();
            _debounceTimer.interval = 60; 
            _debounceTimer.singleShot = true;
            _debounceTimer.timeout.connect(syncState);
        }
        if (_debounceTimer.active) _debounceTimer.stop();
        _debounceTimer.start();
    } catch (e) {
        print("[Raven] Error in requestStateSync: " + e);
        try { syncState(); } catch (err) {}
    }
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
            if (!isManageable(w) || w.__raven_quarantined) continue;
            var safeId = getSafeWindowId(w);
            if (!safeId) continue;

            var output = w.output || workspace.activeOutput;
            var outName = output ? output.name : "default";
            
            var deskIds = [];
            if (w.desktops) {
                for (var d = 0; d < w.desktops.length; d++) {
                    deskIds.push(w.desktops[d].id.toString());
                }
            }

            var wsId = getWorkspaceId(w);
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
                id: safeId, 
                ws: getWorkspaceId(w),
                desktops: deskIds,
                output: outName,
                f: isFloating(w),
                m: Boolean(w.minimized), 
                p: Boolean(w.keepAbove),
                x: Math.round(geom.x), y: Math.round(geom.y),
                w: Math.round(geom.width), h: Math.round(geom.height),
                min_w: w.minSize ? Math.round(w.minSize.width) : 0,
                min_h: w.minSize ? Math.round(w.minSize.height) : 0,
                sb: Boolean(w.__raven_strict_birth)
            });
        } catch (e) { print("[Raven] Error en syncState: " + e); }
    }
    
    var payload = { windows: winState, screens: screens };
    try {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncState", JSON.stringify(payload));
    } catch (e) { print("[Raven Bridge] D-bus Drop: " + e); }
}

/**
 * Envía un Delta: Solo la ventana que acaba de mutar.
 * Extremadamente amigable con el Recolector de Basura.
 * @param {object} w - Ventana que mutó.
 */
function syncWindowDelta(w) {
    try {
        if (!w || w.deleted || !isManageable(w) || w.__raven_quarantined) return;
        var safeId = getSafeWindowId(w);
        if (!safeId) return;

        var output = w.output || workspace.activeOutput;
        var outName = output ? output.name : "default";

        var deskIds = [];
        if (w.desktops) {
            for (var d = 0; d < w.desktops.length; d++) {
                deskIds.push(w.desktops[d].id.toString());
            }
        }

        var geom = w.frameGeometry;
        var deltaPayload = {
            id: safeId,
            ws: getWorkspaceId(w),
            output: outName,
            desktops: deskIds,
            f: isFloating(w),
            m: Boolean(w.minimized),
            p: Boolean(w.keepAbove),
            x: Math.round(geom.x), y: Math.round(geom.y),
            w: Math.round(geom.width), h: Math.round(geom.height),
            min_w: w.minSize ? Math.round(w.minSize.width) : 0,
            min_h: w.minSize ? Math.round(w.minSize.height) : 0,
            sb: Boolean(w.__raven_strict_birth)
        };

        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "syncWindowDelta", JSON.stringify(deltaPayload));
    } catch (e) { print("[Raven] Error Delta Sync: " + e); }
}

/**
 * Migra una ventana hacia otra pantalla o escritorio virtual, o la minimiza si no hay espacio.
 * @param {object} win - Objeto de ventana de KWin a migrar.
 * @param {string} target_ws - Espacio de trabajo destino explícito.
 */
function migrateWindow(win, target_ws) {
    if (!target_ws || !win) return;
    try {
        if (win.deleted) return;
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
        if (!win || win.deleted) return;
        var outputs = workspace.outputs || [];
        var desktops = workspace.desktops || [];
        var tryScreen = (strategy === "auto" || strategy === "screen");
        var tryDesktop = (strategy === "auto" || strategy === "desktop");

        if (tryScreen && outputs.length > 1) {
            var currentOut = win.output || workspace.activeOutput;
            if (!currentOut && outputs.length > 0) currentOut = outputs[0];
            var nextIdx = 0;
            for (var i = 0; i < outputs.length; i++) {
                if (currentOut && outputs[i].name === currentOut.name) {
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
                if (currentDesk && desktops[d].id === currentDesk.id) {
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
            
            // Si Rust nos pide sincronizar (ej. tras un atajo de teclado complejo)
            if (cmd.action === "request_sync") { 
                requestStateSync(); 
                continue; 
            }

            // Buscamos la ventana objetivo
            for (var j = 0; j < windows.length; j++) {
                var w = windows[j];
                
                // Utilizamos la nueva identidad nativa de Wayland
                if (getSafeWindowId(w) === cmd.window_id) {
                    if (!w || w.deleted) {
                        print("[Raven] Mutacion abortada: La superficie Wayland " + cmd.window_id + " fue destruida en transito.");
                        break;
                    }
                    
                    if (cmd.action === "move") {
                        try {
                            if (w.maximizeMode === 3 || w.interactiveMove || w.interactiveResize) break;
                            
                            var expectedGeom = {
                                x: Math.round(cmd.x), y: Math.round(cmd.y), 
                                width: Math.round(cmd.width), height: Math.round(cmd.height) 
                            };

                            w.__raven_mutating = true;
                            w.__raven_expected_geometry = expectedGeom;
                            w.frameGeometry = expectedGeom;
                            
                            (function(capturedWindow) {
                                setKWinTimeout(function() { 
                                    try { 
                                        if (capturedWindow && !capturedWindow.deleted && capturedWindow.__raven_mutating) {
                                            capturedWindow.__raven_mutating = false; 
                                            capturedWindow.__raven_expected_geometry = null;
                                        } 
                                    } catch(e){} 
                                }, 500);
                            })(w);
                        } catch(e) { print("[Raven] Error apply move: " + e); }
                        
                    } else if (cmd.action === "focus") {
                        try { workspace.activeWindow = w; } catch(e){}
                        
                    } else if (cmd.action === "request_feedback") {
                        try {
                            if (w.__raven_strict_birth) {
                                w.__raven_strict_birth = false; // Limpiar para que suceda solo 1 vez
                                syncWindowDelta(w);
                            }
                        } catch(e) { print("[Raven] Error apply request_feedback: " + e); }
                        
                    } else if (cmd.action === "minimize") {
                        try {
                            w.__raven_mutating = true;
                            w.minimized = true;
                            (function(capturedWindow) {
                                setKWinTimeout(function() { 
                                    try { 
                                        if (capturedWindow && !capturedWindow.deleted) {
                                            capturedWindow.__raven_mutating = false; 
                                            requestStateSync(); 
                                        }
                                    } catch(e){} 
                                }, 100);
                            })(w);
                        } catch(e) { print("[Raven] Error apply minimize: " + e); }

                    } else if (cmd.action === "unminimize") {
                        try {
                            w.__raven_mutating = true;
                            w.minimized = false;
                            (function(capturedWindow) {
                                setKWinTimeout(function() { 
                                    try { 
                                        if (capturedWindow && !capturedWindow.deleted) {
                                            capturedWindow.__raven_mutating = false; 
                                            requestStateSync(); 
                                        }
                                    } catch(e){} 
                                }, 100);
                            })(w);
                        } catch(e) { print("[Raven] Error apply unminimize: " + e); }
                        
                    } else if (cmd.action === "migrate_to_output") {
                        try {
                            w.__raven_mutating = true;
                            var outs = workspace.outputs || [];
                            var targetFound = false;
                            for (var k = 0; k < outs.length; k++) {
                                if (outs[k].name === cmd.target_ws) {
                                    // [NUEVO]: Reflexión dinámica para API de monitores
                                    if (typeof workspace.sendClientToScreen === "function") {
                                        try {
                                            workspace.sendClientToScreen(w, outs[k]); // Invocación nativa Wayland
                                        } catch (e) {
                                            w.output = outs[k]; // Fallback si sendClientToScreen falla internamente
                                        }
                                    } else {
                                        w.output = outs[k]; // Fallback clásico si la API no está expuesta
                                    }
                                    targetFound = true;
                                    break;
                                }
                            }
                            if (!targetFound) {
                                w.__raven_mutating = false;
                                requestStateSync();
                            } else {
                                (function(capturedWindow) {
                                    setKWinTimeout(function() { 
                                        try { 
                                            if (capturedWindow && !capturedWindow.deleted) {
                                                capturedWindow.__raven_mutating = false; 
                                                requestStateSync(); 
                                            }
                                        } catch(e){} 
                                    }, 100);
                                })(w);
                            }
                        } catch(e) { print("[Raven] Error apply migrate_to_output: " + e); }

                    } else if (cmd.action === "migrate_to_desktop") {
                        try {
                            w.__raven_mutating = true;
                            var desks = workspace.desktops || [];
                            var targetFound = false;
                            for (var k = 0; k < desks.length; k++) {
                                if (desks[k].id.toString() === cmd.target_ws) {
                                    w.desktops = [desks[k]];
                                    targetFound = true;
                                    break;
                                }
                            }
                            if (!targetFound) {
                                w.__raven_mutating = false;
                                requestStateSync();
                            } else {
                                (function(capturedWindow) {
                                    setKWinTimeout(function() { 
                                        try { 
                                            if (capturedWindow && !capturedWindow.deleted) {
                                                capturedWindow.__raven_mutating = false; 
                                                requestStateSync(); 
                                            }
                                        } catch(e){} 
                                    }, 100);
                                })(w);
                            }
                        } catch(e) { print("[Raven] Error apply migrate_to_desktop: " + e); }
                    }
                    
                    break; // Salimos del for interior una vez encontrada y procesada la ventana
                }
            }
        }
    } catch (e) { print("[Raven Bridge] Error applyCommands: " + e); }
}

// Estado y temporizador de supervisión para el bucle de escucha de comandos
var _is_listening = false;
var _watchdog_timer = null;
var _active_timers = [];

/**
 * Crea un temporizador de disparo único (similar a setTimeout) nativo para KWin.
 * Mantiene la referencia viva en una colección global para evitar recolección de basura prematura.
 * @param {function} callback - Función a ejecutar tras el tiempo de espera.
 * @param {number} ms - Milisegundos a esperar.
 * @returns {object} Instancia del QTimer iniciado.
 */
function setKWinTimeout(callback, ms) {
    try {
        var timer = new QTimer();
        timer.interval = ms;
        timer.singleShot = true;
        
        _active_timers.push(timer);
        
        timer.timeout.connect(function() {
            try {
                callback();
            } catch (e) {
                print("[Raven] Error in timer callback: " + e);
            } finally {
                if (timer) {
                    try { timer.stop(); } catch(e) {}
                }
                var idx = _active_timers.indexOf(timer);
                if (idx !== -1) {
                    _active_timers.splice(idx, 1);
                }
            }
        });
        timer.start();
        return timer;
    } catch (e) {
        print("[Raven] Error setKWinTimeout: " + e);
        try { callback(); } catch(err) {}
        return null;
    }
}

/**
 * Inicia el bucle de consulta (long-polling) para recibir comandos pendientes desde D-Bus.
 * Utiliza un temporizador de supervisión (watchdog) para autorecuperarse ante bloqueos.
 */
function listenForCommands() {
    if (_is_listening) return;
    _is_listening = true;
    if (_watchdog_timer) {
        try { _watchdog_timer.stop(); } catch(e) {}
    }
    _watchdog_timer = setKWinTimeout(function() { _is_listening = false; listenForCommands(); }, 8000);

    try {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "getPendingCommands", function(response) {
            try {
                if (_watchdog_timer) {
                    try { _watchdog_timer.stop(); } catch(e) {}
                }
                _is_listening = false;
                if (response) { 
                    applyCommands(response); 
                    setKWinTimeout(listenForCommands, 50); 
                } 
                else { 
                    setKWinTimeout(listenForCommands, 3000); 
                }
            } catch (errInner) {
                print("[Raven Bridge] Error inside D-Bus response callback: " + errInner);
                _is_listening = false;
                setKWinTimeout(listenForCommands, 3000);
            }
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
        if (!isManageable(w) || w.__raven_bound || w.__raven_quarantined) return;
        w.__raven_bound = true;
        
        try {
            w.minimizedChanged.connect(function() {
                try {
                    if (w && !w.deleted && !w.__raven_mutating) {
                        var hasMove = ("interactiveMove" in w);
                        var hasResize = ("interactiveResize" in w);
                        var isInteracting = (hasMove && w.interactiveMove) || (hasResize && w.interactiveResize);
                        if (!isInteracting) {
                            requestStateSync();
                        }
                    }
                } catch(e) {}
            });
        } catch(e) { print("[Raven] Error connecting minimizedChanged: " + e); }
        
        try {
            w.outputChanged.connect(function() {
                try {
                    if (w && !w.deleted && !w.__raven_mutating) {
                        var hasMove = ("interactiveMove" in w);
                        var hasResize = ("interactiveResize" in w);
                        var isInteracting = (hasMove && w.interactiveMove) || (hasResize && w.interactiveResize);
                        if (!isInteracting) {
                            requestStateSync();
                        }
                    }
                } catch(e) {}
            });
        } catch(e) { print("[Raven] Error connecting outputChanged: " + e); }
        
        try {
            w.desktopsChanged.connect(function() {
                try {
                    if (w && !w.deleted && !w.__raven_mutating) {
                        var hasMove = ("interactiveMove" in w);
                        var hasResize = ("interactiveResize" in w);
                        var isInteracting = (hasMove && w.interactiveMove) || (hasResize && w.interactiveResize);
                        if (!isInteracting) {
                            requestStateSync();
                        }
                    }
                } catch(e) {}
            });
        } catch(e) { print("[Raven] Error connecting desktopsChanged: " + e); }
        
        try {
            w.frameGeometryChanged.connect(function() {
                try {
                    if (!w || w.deleted) return;

                    // [NUEVO]: Verificación segura de propiedades dinámicas
                    var hasMove = ("interactiveMove" in w);
                    var hasResize = ("interactiveResize" in w);
                    var isInteracting = (hasMove && w.interactiveMove) || (hasResize && w.interactiveResize);

                    if (isInteracting) { 
                        w.__was_interacting = true; 
                        return; // Bloqueamos el reporte mientras el usuario arrastra
                    }
                    if (w.__was_interacting && !isInteracting) {
                        w.__was_interacting = false; 
                        requestStateSync(); 
                        return;
                    }

                    if (w.__raven_mutating) {
                        if (w.__raven_expected_geometry) {
                            var currentGeom = w.frameGeometry;
                            var matchX = Math.abs(Math.round(currentGeom.x) - w.__raven_expected_geometry.x) <= 1;
                            var matchY = Math.abs(Math.round(currentGeom.y) - w.__raven_expected_geometry.y) <= 1;
                            var matchW = Math.abs(Math.round(currentGeom.width) - w.__raven_expected_geometry.width) <= 1;
                            var matchH = Math.abs(Math.round(currentGeom.height) - w.__raven_expected_geometry.height) <= 1;
                            
                            if (matchX && matchY && matchW && matchH) {
                                w.__raven_mutating = false;
                                w.__raven_expected_geometry = null;
                            }
                        }
                        return; 
                    }

                    syncWindowDelta(w);
                } catch(e) { print("[Raven] Error frameGeometryChanged callback: " + e); }
            });
        } catch(e) { print("[Raven] Error connecting frameGeometryChanged: " + e); }

        // [NUEVO]: Vinculación segura de señales experimentales
        try {
            if (w.interactiveMoveResizeFinished !== undefined) {
                w.interactiveMoveResizeFinished.connect(function() {
                    try {
                        if (!w || w.deleted) return;
                        w.__was_interacting = false;
                        requestStateSync(); // Disparamos la recalculación de mosaico
                    } catch(e) {}
                });
            }
        } catch(e) { print("[Raven] Señal interactiveMoveResizeFinished no disponible: " + e); }
        
    } catch(e) { print("[Raven] Error bindWindow: " + e); }
}

/**
 * Inicializa el puente conectando las señales globales del espacio de trabajo (workspace),
 * registrando las ventanas existentes e iniciando la escucha de comandos.
 */
function init() {
    print("[Raven Bridge] Inicializando v2.8 (Debounce 60ms)...");
    
    try {
        var initialWindows = workspace.windowList();
        for (var i=0; i<initialWindows.length; i++) {
            try {
                bindWindow(initialWindows[i]);
            } catch (e) {
                print("[Raven] Error en binding inicial de ventana: " + e);
            }
        }
    } catch (e) {
        print("[Raven] Error obteniendo lista inicial de ventanas: " + e);
    }

    try {
        var _quarantine_classes = ["firefox", "electron", "zen-browser", "code", "spotify"];

        workspace.windowAdded.connect(function(w) { 
            try {
                if (!isManageable(w)) return;

                var strClass = w.resourceClass ? w.resourceClass.toString().toLowerCase() : "";
                var needsQuarantine = false;
                
                for (var i = 0; i < _quarantine_classes.length; i++) {
                    if (strClass.indexOf(_quarantine_classes[i]) !== -1) {
                        needsQuarantine = true;
                        break;
                    }
                }

                if (needsQuarantine) {
                    w.__raven_quarantined = true;
                    setKWinTimeout(function() {
                        try {
                            if (w && !w.deleted) {
                                w.__raven_quarantined = false;
                                w.__raven_strict_birth = true;
                                bindWindow(w); 
                                requestStateSync(); 
                            }
                        } catch(errTimeout) {
                            print("[Raven] Error en timeout de cuarentena: " + errTimeout);
                        }
                    }, 250);
                } else {
                    bindWindow(w); 
                    requestStateSync(); 
                }
            } catch (errAdded) {
                print("[Raven] Error en manejador de windowAdded: " + errAdded);
            }
        });
    } catch (e) {
        print("[Raven] Error conectando windowAdded: " + e);
    }

    try {
        workspace.windowRemoved.connect(function() {
            try {
                requestStateSync();
            } catch(e) {}
        });
    } catch (e) {
        print("[Raven] Error conectando windowRemoved: " + e);
    }

    try {
        workspace.windowActivated.connect(function(w) {
            try {
                if (w && isManageable(w)) {
                    var id = getSafeWindowId(w);
                    if (id) {
                        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "windowActivated", id, function(){});
                    }
                }
            } catch (errActivated) {
                print("[Raven] Error en manejador de windowActivated: " + errActivated);
            }
        });
    } catch (e) {
        print("[Raven] Error conectando windowActivated: " + e);
    }

    try {
        callDBus("org.kde.raven.Daemon", "/Events", "org.kde.raven.Events", "bridgeReady", function() {});
    } catch (e) { 
        print("[Raven] Error bridgeReady D-Bus: " + e); 
    }

    try {
        listenForCommands();
    } catch (e) {
        print("[Raven] Error iniciando escucha de comandos: " + e);
    }
}

try {
    init();
} catch (e) {
    print("[Raven Bridge] Error crítico en inicialización global: " + e);
}