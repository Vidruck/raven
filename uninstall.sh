#!/bin/bash
# Raven Tiling Emulator - Professional Uninstaller
# Autor: Alejandro González Hernández (Vidruck)

TARGET_DIR="$HOME/.local/share/raven"
ICON_NAME="org.kde.raven.tiling"
KWIN_SCRIPT_ID="org.kde.raven.bridge"
PLASMOID_ID="org.kde.raven.toggle"

echo "🐦 Iniciando desinstalación profesional de Raven..."

echo "[1/6] Deteniendo y eliminando servicio Raven..."
if systemctl --user is-active --quiet raven.service; then
    systemctl --user stop raven.service
fi

if [ -f "$HOME/.config/systemd/user/raven.service" ]; then
    systemctl --user disable raven.service
    rm "$HOME/.config/systemd/user/raven.service"
    systemctl --user daemon-reload
    systemctl --user reset-failed
fi


echo "[2/6] Eliminando adaptadores del entorno de escritorio..."
if kpackagetool6 --type=KWin/Script --list | grep -q "$KWIN_SCRIPT_ID"; then
    kpackagetool6 --type=KWin/Script --remove "$KWIN_SCRIPT_ID"
fi

if kpackagetool6 --type=Plasma/Applet --list | grep -q "$PLASMOID_ID"; then
    kpackagetool6 --type=Plasma/Applet --remove "$PLASMOID_ID"
fi

echo "[3/6] Limpiando integración gráfica e iconos..."
[ -f "$HOME/.local/share/applications/raven.desktop" ] && rm "$HOME/.local/share/applications/raven.desktop"
[ -f "$HOME/.local/share/icons/hicolor/scalable/apps/${ICON_NAME}.svg" ] && rm "$HOME/.local/share/icons/hicolor/scalable/apps/${ICON_NAME}.svg"

echo "[4/6] Actualizando bases de datos del sistema..."
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
kbuildsycoca6 --noincremental > /dev/null 2>&1

echo "[5/6] Eliminando archivos de despliegue y entornos..."
if [ -d "$TARGET_DIR" ]; then
    rm -rf "$TARGET_DIR"
fi

read -p "❓ ¿Deseas eliminar también los archivos de configuración y logs? (~/.config/raven) (s/n): " confirm
if [[ $confirm == [sS] ]]; then
    echo "Borrando ~/.config/raven/..."
    rm -rf "$HOME/.config/raven/"
fi

echo "✅ Raven ha sido eliminado completamente del sistema. ¡Huélum!"