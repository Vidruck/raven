#!/bin/bash
# Raven Tiling Emulator - Installer
# Autor: Alejandro González Hernández (Vidruck)

echo "🐦 Iniciando despliegue de Raven..."

# 1. Preparar directorios de configuración
mkdir -p ~/.config/raven
mkdir -p ~/.local/share/icons/hicolor/scalable/apps/
mkdir -p ~/.local/share/applications/

# 2. Copiar Activos Visuales
cp raven.svg ~/.local/share/icons/hicolor/scalable/apps/raven.svg
cp raven.desktop ~/.local/share/applications/

# 3. Configurar Entorno de Python (Backend)
if [ ! -d ".venv" ]; then
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

# 4. Instalar Componentes de KDE (Frontend)
# Instala el script de KWin
kpackagetool6 --type=KWin/Script --install adapters/kwin_script/ 2>/dev/null || \
kpackagetool6 --type=KWin/Script --upgrade adapters/kwin_script/

# Instalar el Widget del Panel
kpackagetool6 --type=Plasma/Applet --install adapters/plasmoid/ 2>/dev/null || \
kpackagetool6 --type=Plasma/Applet --upgrade adapters/plasmoid/

# 5. Configurar Systemd
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