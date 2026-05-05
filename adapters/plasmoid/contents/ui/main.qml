import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.plasma.plasmoid
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support 
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    
    property bool isEngineEnabled: true
    property string queryCmd: "dbus-send --session --print-reply=literal --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.getTilingState"

    // --- Lógica de Comunicación ---
    function execDbus(method, args) {
        let cmd = "dbus-send --session --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events." + method;
        if (args) { cmd += " " + args; }
        executable.exec(cmd);
    }

    function toggleRaven() {
        execDbus("toggleTiling", "");
        root.isEngineEnabled = !root.isEngineEnabled;
    }

    function queryState() { executable.exec(queryCmd); }

    onExpandedChanged: {
        if (expanded) { queryState(); }
    }

    Plasma5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            if (sourceName === root.queryCmd && data["stdout"] !== undefined) {
                let output = data["stdout"].trim().toLowerCase();
                root.isEngineEnabled = output.includes("true");
            }
            disconnectSource(sourceName);
        }
        function exec(cmd) { connectSource(cmd); }
    }

    // --- Representación Compacta (Icono en el panel) ---
    compactRepresentation: MouseArea {
        id: compactRoot
        activeFocusOnTab: true
        onClicked: root.expanded = !root.expanded
        
        Kirigami.Icon {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            source: "org.kde.raven.tiling"
            active: root.isEngineEnabled
            opacity: root.isEngineEnabled ? 1.0 : 0.4
            
            Behavior on opacity { OpacityAnimator { duration: Kirigami.Units.longDuration } }
        }
        
        PlasmaComponents.ToolTip {
            text: "Raven Tiling: " + (root.isEngineEnabled ? "Activo" : "Inactivo")
        }
    }

    // --- Representación Extendida (Popup) ---
    fullRepresentation: Kirigami.Page {
        implicitWidth: Kirigami.Units.gridUnit * 18
        implicitHeight: Kirigami.Units.gridUnit * 20
        
        background: null // Usar fondo transparente del tema de Plasma

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            // Encabezado Premium
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.mediumSpacing

                Kirigami.Icon {
                    source: "org.kde.raven.tiling"
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: Kirigami.Units.iconSizes.medium
                }

                ColumnLayout {
                    spacing: 0
                    PlasmaComponents.Label {
                        text: "Raven Engine"
                        font.bold: true
                        font.pixelSize: Kirigami.Units.gridUnit * 0.9
                    }
                    PlasmaComponents.Label {
                        text: "v2.0 Native Rust"
                        opacity: 0.6
                        font.pixelSize: Kirigami.Units.gridUnit * 0.7
                    }
                }

                Item { Layout.fillWidth: true }

                PlasmaComponents.Switch {
                    checked: root.isEngineEnabled
                    onClicked: root.toggleRaven()
                }
            }

            Kirigami.Separator { Layout.fillWidth: true }

            // Sección de Control de Foco y Layout
            Kirigami.Heading {
                text: "Gestión de Ventanas"
                level: 4
                opacity: 0.8
            }

            GridLayout {
                columns: 2
                Layout.fillWidth: true
                rowSpacing: Kirigami.Units.smallSpacing
                columnSpacing: Kirigami.Units.smallSpacing

                PlasmaComponents.Button {
                    text: "Foco Anterior"
                    icon.name: "go-previous"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("focusPrev", "")
                }
                PlasmaComponents.Button {
                    text: "Foco Siguiente"
                    icon.name: "go-next"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("focusNext", "")
                }
                PlasmaComponents.Button {
                    text: "Añadir Maestra"
                    icon.name: "list-add"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("incrementMaster", "")
                }
                PlasmaComponents.Button {
                    text: "Quitar Maestra"
                    icon.name: "list-remove"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("decrementMaster", "")
                }
            }

            // Sección de Dimensiones
            Kirigami.Heading {
                text: "Ajustes de Espacio"
                level: 4
                opacity: 0.8
            }

            GridLayout {
                columns: 2
                Layout.fillWidth: true
                rowSpacing: Kirigami.Units.smallSpacing
                columnSpacing: Kirigami.Units.smallSpacing

                PlasmaComponents.Button {
                    text: "Expandir Ratio"
                    icon.name: "view-split-left-right"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("increaseRatio", "")
                }
                PlasmaComponents.Button {
                    text: "Reducir Ratio"
                    icon.name: "view-split-left-right"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("decreaseRatio", "")
                }
                PlasmaComponents.Button {
                    text: "Más Gaps"
                    icon.name: "zoom-in"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("incrementGaps", "int32:2")
                }
                PlasmaComponents.Button {
                    text: "Menos Gaps"
                    icon.name: "zoom-out"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("incrementGaps", "int32:-2")
                }
            }

            Item { Layout.fillHeight: true } // Espaciador final
            
            PlasmaComponents.Label {
                text: "© 2026 Vidruck"
                Layout.alignment: Qt.AlignHCenter
                opacity: 0.4
                font.pixelSize: Kirigami.Units.gridUnit * 0.6
            }
        }
    }
}