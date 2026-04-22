#!/bin/bash
# Raven Tiling Emulator - Smart Installer & Updater Rust FFI Edition
# Autor: Alejandro González Hernández (Vidruck)

TARGET_DIR="$HOME/.local/share/raven"
SOURCE_DIR=$(pwd)
ICON_NAME="org.kde.raven.tiling"

echo "🐦 Iniciando orquestación de Raven..."


if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    echo "[1/8] Desplegando en entorno protegido ($TARGET_DIR)..."
    mkdir -p "$TARGET_DIR"
    rsync -a --exclude='.venv' --exclude='core/engine_rs/target' "$SOURCE_DIR/" "$TARGET_DIR/"
    cd "$TARGET_DIR" || exit
else
    echo "[1/8] Ejecutando desde entorno protegido. Verificando actualizaciones..."
    if [ -d ".git" ]; then
        git pull origin main || echo "⚠️ No se pudo sincronizar con el repositorio local. Manteniendo versión actual."
    fi
fi

echo "[2/8] Preparando entorno virtual aislado..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi
source .venv/bin/activate

echo "[3/8] Actualizando dependencias a estándares recientes..."
python -m pip install --upgrade pip
pip install -r requirements.txt --upgrade

echo "[4/8] Compilando motor geométrico nativo (Rust/PyO3)..."
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
cd core/engine_rs || exit
maturin develop --release
cd ../..

echo "[5/8] Configurando integración gráfica (Iconos y Desktop Entry)..."
mkdir -p ~/.local/share/icons/hicolor/scalable/apps/
cp icon/${ICON_NAME}.svg ~/.local/share/icons/hicolor/scalable/apps/${ICON_NAME}.svg

cat <<EOF > ~/.local/share/applications/raven.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Raven Control Center
GenericName=Tiling Window Manager Config
Exec=$TARGET_DIR/.venv/bin/python $TARGET_DIR/gui/preferences.py
Icon=${ICON_NAME}
Terminal=false
Categories=Settings;DesktopSettings;
Keywords=tiling;raven;kde;plasma;
StartupNotify=true
EOF

echo "[6/8] Regenerando caché de iconos del sistema (kbuildsycoca6)..."
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor 2>/dev/null || true
kbuildsycoca6 --noincremental > /dev/null 2>&1

echo "[7/8] Instalando/Actualizando adaptadores de KWin..."
kpackagetool6 --type=KWin/Script --install adapters/kwin_script/ 2>/dev/null || \
kpackagetool6 --type=KWin/Script --upgrade adapters/kwin_script/

kpackagetool6 --type=Plasma/Applet --install adapters/plasmoid/ 2>/dev/null || \
kpackagetool6 --type=Plasma/Applet --upgrade adapters/plasmoid/

echo "[8/8] Registrando y reiniciando Daemon (Systemd)..."
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
# Resiliencia contra inanición por TLP y ahorro de energía
CPUSchedulingPolicy=rr
CPUSchedulingPriority=50
OOMScoreAdjust=-200
Slice=session.slice

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable raven.service
systemctl --user restart raven.service

echo "✅ Orquestación finalizada con éxito. ¡Huélum!"