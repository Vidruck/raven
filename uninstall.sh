#!/bin/bash
# Raven Tiling Emulator - Uninstaller
# Autor: Alejandro González Hernández (Vidruck)

TARGET_DIR="$HOME/.local/share/raven"
ICON_NAME="org.kde.raven.tiling"
KWIN_SCRIPT_ID="org.kde.raven.bridge"
PLASMOID_ID="org.kde.raven.toggle"

SOURCE_DIR=$(dirname "$(readlink -f "$0")")

echo "🐦 Iniciando desinstalación de Raven..."

echo "[1/7] Deteniendo y eliminando servicio nativo de Raven..."
if systemctl --user is-active --quiet raven.service; then
    systemctl --user stop raven.service
fi

if [ -f "$HOME/.config/systemd/user/raven.service" ]; then
    systemctl --user disable raven.service
    rm "$HOME/.config/systemd/user/raven.service"
    systemctl --user daemon-reload
    systemctl --user reset-failed
fi

echo "[2/7] Eliminando adaptadores de KWin y Plasma..."
kpackagetool6 --type=KWin/Script --remove "$KWIN_SCRIPT_ID" 2>/dev/null || true
kpackagetool6 --type=Plasma/Applet --remove "$PLASMOID_ID" 2>/dev/null || true

# Limpieza manual preventiva
rm -rf "$HOME/.local/share/kwin/scripts/$KWIN_SCRIPT_ID"
rm -rf "$HOME/.local/share/plasma/plasmoids/$PLASMOID_ID"

echo "[3/7] Limpiando integración gráfica e iconos..."
rm -f "$HOME/.local/share/applications/raven.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/${ICON_NAME}.svg"

echo "[4/7] Actualizando bases de datos del sistema y caché de Plasma..."
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
kbuildsycoca6 --noincremental > /dev/null 2>&1

echo "[5/7] Eliminando archivos de despliegue en entorno local..."
if [ -d "$TARGET_DIR" ]; then
    rm -rf "$TARGET_DIR"
fi

echo "[6/7] Purgando artefactos de compilación (Cargo/Rust)..."
# Limpiamos remanentes de versiones antiguas basadas en Python
rm -rf "$SOURCE_DIR/.venv"
# Limpieza de Rust
if command -v cargo >/dev/null 2>&1 && [ -f "$SOURCE_DIR/Cargo.toml" ]; then
    cargo clean --manifest-path "$SOURCE_DIR/Cargo.toml"
else
    rm -rf "$SOURCE_DIR/target"
fi

echo "[7/7] Configuración de usuario..."
read -p "❓ ¿Deseas eliminar también los archivos de configuración y logs? (~/.config/raven) (s/n): " confirm
if [[ $confirm == [sS] ]]; then
    echo "Borrando ~/.config/raven/..."
    rm -rf "$HOME/.config/raven/"
fi

echo "✅ Raven y sus componentes nativos han sido eliminados. ¡Huélum!"