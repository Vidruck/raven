#!/bin/bash
# Raven Tiling Emulator - Uninstaller
# Autor: Alejandro González Hernández (Vidruck)

TARGET_DIR="$HOME/.local/share/raven"
ICON_NAME="org.kde.raven.tiling"
KWIN_SCRIPT_ID="org.kde.raven.bridge"
PLASMOID_ID="org.kde.raven.toggle"

SOURCE_DIR=$(dirname "$(readlink -f "$0")")

echo "🐦 Iniciando desinstalación de Raven..."

echo "[1/7] Deteniendo y eliminando servicio Raven..."
if systemctl --user is-active --quiet raven.service; then
    systemctl --user stop raven.service
fi

if [ -f "$HOME/.config/systemd/user/raven.service" ]; then
    systemctl --user disable raven.service
    rm "$HOME/.config/systemd/user/raven.service"
    systemctl --user daemon-reload
    systemctl --user reset-failed
fi

echo "[2/7] Eliminando adaptadores del entorno de escritorio..."
kpackagetool6 --type=KWin/Script --remove "$KWIN_SCRIPT_ID" 2>/dev/null || true
kpackagetool6 --type=Plasma/Applet --remove "$PLASMOID_ID" 2>/dev/null || true

[ -d "$HOME/.local/share/kwin/scripts/$KWIN_SCRIPT_ID" ] && rm -rf "$HOME/.local/share/kwin/scripts/$KWIN_SCRIPT_ID"
[ -d "$HOME/.local/share/plasma/plasmoids/$PLASMOID_ID" ] && rm -rf "$HOME/.local/share/plasma/plasmoids/$PLASMOID_ID"

echo "[3/7] Limpiando integración gráfica e iconos..."
[ -f "$HOME/.local/share/applications/raven.desktop" ] && rm "$HOME/.local/share/applications/raven.desktop"
[ -f "$HOME/.local/share/icons/hicolor/scalable/apps/${ICON_NAME}.svg" ] && rm "$HOME/.local/share/icons/hicolor/scalable/apps/${ICON_NAME}.svg"

echo "[4/7] Actualizando bases de datos del sistema y caché de Plasma..."
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
kbuildsycoca6 --noincremental > /dev/null 2>&1

echo "[5/7] Eliminando archivos de despliegue en entorno aislado..."
if [ -d "$TARGET_DIR" ]; then
    rm -rf "$TARGET_DIR"
fi

echo "[6/7] Purgando artefactos de compilación en el código fuente (Limpieza de basura)..."
if [ -d "$SOURCE_DIR/core/engine_rs" ]; then
    echo "      > Eliminando entornos de Python (.venv, pycache, egg-info)..."
    rm -rf "$SOURCE_DIR/.venv"
    find "$SOURCE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find "$SOURCE_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
    
    echo "      > Eliminando binarios nativos de Rust y PyO3 (.so, target/)..."
    find "$SOURCE_DIR" -type f -name "*.so" -delete 2>/dev/null
    rm -rf "$SOURCE_DIR/target"
    rm -rf "$SOURCE_DIR/core/engine_rs/target"
    rm -rf "$SOURCE_DIR/adapters/kwin_rust_adapter/target"
fi

echo "[7/7] Configuración de usuario..."
read -p "❓ ¿Deseas eliminar también los archivos de configuración y logs? (~/.config/raven) (s/n): " confirm
if [[ $confirm == [sS] ]]; then
    echo "Borrando ~/.config/raven/..."
    rm -rf "$HOME/.config/raven/"
fi
read -p "❓ ¿Deseas reiniciar Plasma ahora para limpiar cachés visuales residuales? (Recomendado) (s/n): " restart_plasma
if [[ $restart_plasma == [sS] ]]; then
    systemctl restart --user plasma-plasmashell.service
fi

echo "✅ Raven y todos sus artefactos han sido eliminados completamente. ¡Huélum!"