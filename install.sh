#!/bin/bash
# Raven Tiling Emulator - Smart Installer & Updater Rust FFI Edition
# Autor: Alejandro González Hernández (Vidruck)

TARGET_DIR="$HOME/.local/share/raven"
SOURCE_DIR=$(pwd)
ICON_NAME="org.kde.raven.tiling"

echo "🦅 Iniciando orquestación profesional de Raven..."

# [0/8] Verificación de Dependencias Críticas
command -v cargo >/dev/null 2>&1 || { echo >&2 "❌ Error: Rust/Cargo no detectado. Requerido para módulos nativos."; exit 1; }
command -v kpackagetool6 >/dev/null 2>&1 || { echo >&2 "❌ Error: kpackagetool6 no detectado. ¿Estás en Plasma 6?"; exit 1; }

if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    echo "[1/8] Desplegando en entorno protegido ($TARGET_DIR)..."
    mkdir -p "$TARGET_DIR"
    rsync -a --exclude='.venv' --exclude='target' --exclude='core/engine_rs/target' --exclude='adapters/kwin_rust_adapter/target' "$SOURCE_DIR/" "$TARGET_DIR/"
    cd "$TARGET_DIR" || exit
else
    echo "[1/8] Ejecutando desde entorno protegido. Verificando actualizaciones..."
    if [ -d ".git" ]; then
        git pull origin main || echo "⚠️ Sincronización fallida. Manteniendo versión local."
    fi
fi

echo "[2/8] Preparando entorno virtual aislado..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
fi
source .venv/bin/activate

echo "[3/8] Instalando dependencias y herramientas de compilación..."
python -m pip install --upgrade pip
pip install maturin
pip install -r requirements.txt --upgrade

echo "[4/8] Compilando componentes Rust/PyO3..."
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1

echo "  > Compilando Motor Geométrico (core/engine_rs)..."
maturin develop --release -m core/engine_rs/Cargo.toml

echo "  > Compilando Adaptador DBus (adapters/kwin_rust_adapter)..."
maturin develop --release -m adapters/kwin_rust_adapter/Cargo.toml

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

echo "[6/8] Regenerando caché de servicios de KDE..."
kbuildsycoca6 --noincremental > /dev/null 2>&1

echo "[7/8] Instalando adaptadores de KWin y Plasmoids..."
kpackagetool6 --type=KWin/Script -i adapters/kwin_script/ 2>/dev/null || kpackagetool6 --type=KWin/Script -u adapters/kwin_script/
kpackagetool6 --type=Plasma/Applet -i adapters/plasmoid/ 2>/dev/null || kpackagetool6 --type=Plasma/Applet -u adapters/plasmoid/

echo "[8/8] Configurando persistencia del Daemon (Systemd)..."
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
# Optimizaciones de rendimiento de grado empresarial
CPUSchedulingPolicy=rr
CPUSchedulingPriority=50
OOMScoreAdjust=-200

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now raven.service

echo "✅ Raven v1.5 instalado y operando. ¡Huélum!"