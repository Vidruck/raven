import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kquickcontrolsaddons
import org.kde.plasma.components as PlasmaComponents

PlasmoidItem {
    id: root
    
    // Conexión con el bus de sesión para llamar a toggleTiling
    function toggleRaven() {
        executable.exec("dbus-send --session --type=method_call --dest=org.kde.raven.Daemon /Events org.kde.raven.Events.toggleTiling")
    }

    PlasmaCore.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            disconnectSource(sourceName)
        }
        function exec(cmd) {
            connectSource(cmd)
        }
    }

    fullRepresentation: PlasmaComponents.Button {
        id: toggleButton
        icon.name: "raven"
        display: PlasmaComponents.AbstractButton.IconOnly
        ToolTip.text: "Alternar Raven Tiling"
        onClicked: root.toggleRaven()
        
        // Efecto visual: Brillo sutil cuando está activo
        background: Rectangle {
            color: "transparent"
            border.color: "cyan"
            border.width: 2
            radius: 4
            opacity: 0.5
        }
    }
}