import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami
import org.kde.plasma.extras as PlasmaExtras

PlasmoidItem {
    id: root

    property string eventTitle: ""
    property bool hasEvent: false

    preferredRepresentation: compactRepresentation
    compactRepresentation: CompactRepresentation {}
    fullRepresentation: FullRepresentation {}

    // DataSource for reading status JSON
    P5Support.DataSource {
        id: statusReader
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            var stdout = data["stdout"].trim();
            disconnectSource(source);

            if (stdout === "" || stdout === "{}") {
                root.hasEvent = false;
                root.eventTitle = "";
                return;
            }

            try {
                var obj = JSON.parse(stdout);
                if (obj.hasEvent && obj.title && obj.title.length > 0) {
                    root.hasEvent = true;
                    root.eventTitle = obj.title;
                } else {
                    root.hasEvent = false;
                    root.eventTitle = "";
                }
            } catch (e) {
                root.hasEvent = false;
                root.eventTitle = "";
            }
        }
    }

    // Separate DataSource for fire-and-forget commands (toggle, etc.)
    P5Support.DataSource {
        id: commander
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            disconnectSource(source);
        }
    }

    function readStatus() {
        var cmd = "cat \"$HOME/.cache/akiflow/tray-status.json\" 2>/dev/null || echo '{}'";
        statusReader.connectSource(cmd);
    }

    Timer {
        id: pollTimer
        interval: 10000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.readStatus()
    }

    function toggleAkiflow(mouseX, mouseY) {
        // Write cursor position to toggle file so Akiflow positions the window near the click
        // Append timestamp comment to make each command unique so DataSource re-executes
        var pos = JSON.stringify({x: mouseX, y: mouseY});
        commander.connectSource("echo '" + pos + "' > \"$HOME/.cache/akiflow/toggle-tray\" # " + Date.now());
    }

    toolTipMainText: root.hasEvent ? root.eventTitle : "Akiflow"
    toolTipSubText: root.hasEvent ? "Click to open Akiflow" : "No upcoming events"
}
