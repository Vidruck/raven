#!/bin/bash
# Raven Tiling Emulator - Protected Installer
# Autor: Alejandro González Hernández (Vidruck)

TARGET_DIR="$HOME/.local/share/raven"
SOURCE_DIR=$(pwd)

echo "🐦 Iniciando despliegue de Raven en entorno protegido..."

if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    echo "[1/6] Migrando archivos a $TARGET_DIR..."
    mkdir -p "$TARGET_DIR"
    cp -r "$SOURCE_DIR"/. "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

if [ ! -d ".venv" ]; then
    echo "[2/6] Creando entorno virtual aislado..."
    python -m venv .venv
fi

source .venv/bin/activate
echo "[3/6] Instalando dependencias..."
pip install -r requirements.txt

echo "[4/6] Instalando KWin Bridge y Plasmoid..."
kpackagetool6 --type=KWin/Script --install adapters/kwin_script/ 2>/dev/null || \
kpackagetool6 --type=KWin/Script --upgrade adapters/kwin_script/

kpackagetool6 --type=Plasma/Applet --install adapters/plasmoid/ 2>/dev/null || \
kpackagetool6 --type=Plasma/Applet --upgrade adapters/plasmoid/

echo "[5/6] Configurando integración de escritorio..."
cp raven.svg ~/.local/share/icons/hicolor/scalable/apps/raven.svg

cat <<EOF > ~/.local/share/applications/raven.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Raven Control Center
GenericName=Tiling Window Manager Config
Exec=$TARGET_DIR/.venv/bin/python $TARGET_DIR/gui/preferences.py
Icon=raven
Terminal=false
Categories=Settings;
Keywords=tiling;
EOF
echo "[6/6] Registrando servicio de Systemd..."
mkdir -p ~/.config/systemd/user/
cat <<EOF > ~/.config/systemd/user/raven.service
[Unit]
Description=Raven Tiling Emulator Daemon
After=graphical-session.target

[Service]
ExecStart=$TARGET_DIR/.venv/bin/python $TARGET_DIR/main.py
WorkingDirectory=$TARGET_DIR
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable raven.service
systemctl --user restart raven.service

echo "✅ Raven ha sido desplegado exitosamente en: $TARGET_DIR .  ¡Huélum!"
echo "💡 Ya puedes borrar la carpeta de Descargas si lo deseas."