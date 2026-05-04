import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as Plasma5Support 
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    preferredRepresentation: Plasmoid.compactRepresentation

    // Estado local para reflejar si el motor de Tiling está activo o pausado.
    property bool isEngineEnabled: true
    // Comando para consultar por D-Bus el estado actual del motor de Tiling.
    property string queryCmd: "dbus-send --session --print-reply=literal --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.getTilingState"

    // Función auxiliar para ejecutar llamadas D-Bus de manera asíncrona hacia el demonio de Raven.
    function execDbus(method) {
        executable.exec("dbus-send --session --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events." + method)
    }

    // Activa o desactiva la disposición automática de ventanas e invierte el estado local.
    function toggleRaven() {
        execDbus("toggleTiling")
        root.isEngineEnabled = !root.isEngineEnabled;
    }

    // Dispara la consulta al daemon para obtener el estado real del motor.
    function queryState() {
        executable.exec(queryCmd)
    }

    onExpandedChanged: {
        if (expanded) {
            queryState();
        }
    }

    // Integración con Plasma5Support para la ejecución de comandos del sistema operativo (DataSource).
    Plasma5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            if (sourceName === root.queryCmd && data["stdout"] !== undefined) {
                var output = data["stdout"].trim();
                if (output.indexOf("true") !== -1) {
                    root.isEngineEnabled = true;
                } else if (output.indexOf("false") !== -1) {
                    root.isEngineEnabled = false;
                }
            }
            disconnectSource(sourceName)
        }
        function exec(cmd) { connectSource(cmd) }
    }

    fullRepresentation: Item {
        implicitWidth: 420
        implicitHeight: 380

        ColumnLayout {
            anchors.centerIn: parent
            anchors.margins: 10
            spacing: 12

            PlasmaComponents.Label {
                text: "Raven Control Center"
                font.bold: true
                font.pixelSize: 15
                Layout.alignment: Qt.AlignHCenter
            }

            PlasmaComponents.CheckBox {
                id: tilingToggle
                text: "Mosaico Dinámico Activo"
                checked: root.isEngineEnabled
                Layout.alignment: Qt.AlignHCenter
                onClicked: {
                    root.toggleRaven()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: PlasmaComponents.Theme.textColor
                opacity: 0.15
            }

            GridLayout {
                columns: 2
                rowSpacing: 10
                columnSpacing: 10
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true

                PlasmaComponents.Button {
                    text: "Foco Anterior"
                    icon.name: "go-previous"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("focusPrev")
                }
                PlasmaComponents.Button {
                    text: "Foco Siguiente"
                    icon.name: "go-next"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("focusNext")
                }
                PlasmaComponents.Button {
                    text: "Ventana Maestra"
                    icon.name: "list-add"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("incrementMaster")
                }
                PlasmaComponents.Button {
                    text: "Ventana Maestra"
                    icon.name: "list-remove"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("decrementMaster")
                }
                PlasmaComponents.Button {
                    text: " + Ratio Maestro"
                    icon.name: "view-split-left-right"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("increaseRatio")
                }
                PlasmaComponents.Button {
                    text: " - Ratio Maestro"
                    icon.name: "view-split-left-right"
                    Layout.fillWidth: true
                    onClicked: root.execDbus("decreaseRatio")
                }
                PlasmaComponents.Button {
                    text: "Márgenes"
                    icon.name: "zoom-in"
                    Layout.fillWidth: true
                    onClicked: executable.exec("dbus-send --session --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.incrementGaps int32:2")
                }
                PlasmaComponents.Button {
                    text: "Márgenes"
                    icon.name: "zoom-out"
                    Layout.fillWidth: true
                    onClicked: executable.exec("dbus-send --session --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.incrementGaps int32:-2")
                }
            }
        }
    }
}