#!/bin/bash
# Raven Tiling Emulator - Uninstaller
# Autor: Alejandro González  Hernández (Vidruck)

echo "🐦 Iniciando eliminación de Raven..."

if systemctl --user is-active --quiet raven.service; then
    echo "[1/5] Deteniendo servicio raven.service..."
    systemctl --user stop raven.service
fi

if [ -f "$HOME/.config/systemd/user/raven.service" ]; then
    echo "[1/5] Deshabilitando y borrando unidad de servicio..."
    systemctl --user disable raven.service
    rm "$HOME/.config/systemd/user/raven.service"
    systemctl --user daemon-reload
    systemctl --user reset-failed
fi

if kpackagetool6 --type=KWin/Script --list | grep -q "org.kde.raven.bridge"; then
    echo "[2/5] Desinstalando KWin Script (Raven Bridge)..."
    kpackagetool6 --type=KWin/Script --remove org.kde.raven.bridge
fi

echo "[3/5] Eliminando iconos y accesos directos..."
[ -f "$HOME/.local/share/applications/raven.desktop" ] && rm "$HOME/.local/share/applications/raven.desktop"
[ -f "$HOME/.local/share/icons/hicolor/scalable/apps/org.kde.raven.tiling.svg" ] && rm "$HOME/.local/share/icons/hicolor/scalable/apps/raven.svg"

update-desktop-database ~/.local/share/applications/

if [ -d ".venv" ]; then
    echo "[4/5] Eliminando entorno virtual de Python..."
    rm -rf .venv/
fi

read -p "❓ ¿Deseas eliminar también los archivos de configuración JSON? (s/n): " confirm
if [[ $confirm == [sS] ]]; then
    echo "[5/5] Borrando ~/.config/raven/..."
    rm -rf "$HOME/.config/raven/"
fi
echo "Eliminando carpeta protegida..."
rm -rf "$HOME/.local/share/raven"

echo "✅ Raven ha sido eliminado de tu sistema. ¡Huélum!"