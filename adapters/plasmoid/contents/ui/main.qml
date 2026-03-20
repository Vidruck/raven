import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as Plasma5Support 
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    preferredRepresentation: Plasmoid.compactRepresentation

    property bool isEngineEnabled: true
    property string queryCmd: "dbus-send --session --print-reply=literal --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.getTilingState"

    function toggleRaven() {
        executable.exec("dbus-send --session --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.toggleTiling")
        root.isEngineEnabled = !root.isEngineEnabled;
    }

    function queryState() {
        executable.exec(queryCmd)
    }

    onExpandedChanged: {
        if (expanded) {
            queryState();
        }
    }

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
        implicitWidth: 220
        implicitHeight: 120

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 15

            PlasmaComponents.Label {
                text: "Raven Tiling Engine"
                font.bold: true
                font.pixelSize: 14
                Layout.alignment: Qt.AlignHCenter
            }

            PlasmaComponents.CheckBox {
                id: tilingToggle
                text: "Mosaico Activado"
                
                checked: root.isEngineEnabled
                Layout.alignment: Qt.AlignHCenter
                
                onClicked: {
                    root.toggleRaven()
                }
            }
        }
    }
}