#!/bin/bash
# Raven Tiling Emulator - Installer
# Autor: Alejandro González Hernández (Vidruck)

echo "🐦 Iniciando despliegue de Raven..."

mkdir -p ~/.config/raven
mkdir -p ~/.local/share/icons/hicolor/scalable/apps/
mkdir -p ~/.local/share/applications/


cp icon/raven.svg ~/.local/share/icons/hicolor/scalable/apps/raven.svg
cp raven.desktop ~/.local/share/applications/


if [ ! -d ".venv" ]; then
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi


kpackagetool6 --type=KWin/Script --install adapters/kwin_script/ 2>/dev/null || \
kpackagetool6 --type=KWin/Script --upgrade adapters/kwin_script/


kpackagetool6 --type=Plasma/Applet --install adapters/plasmoid/ 2>/dev/null || \
kpackagetool6 --type=Plasma/Applet --upgrade adapters/plasmoid/


mkdir -p ~/.config/systemd/user/
cat <<EOF > ~/.config/systemd/user/raven.service
[Unit]
Description=Raven Tiling Emulator Daemon
After=graphical-session.target

[Service]
ExecStart=$(pwd)/.venv/bin/python $(pwd)/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable raven.service
systemctl --user restart raven.service

echo "✅ Raven ha sido desplegado exitosamente."
echo "💡 Recuerda habilitar 'Raven Bridge' en Preferencias del Sistema -> Guiones de KWin."