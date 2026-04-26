import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

MouseArea {
    id: compactRoot

    Layout.minimumWidth: row.implicitWidth
    Layout.preferredWidth: row.implicitWidth
    Layout.fillHeight: true

    hoverEnabled: true
    onClicked: function(mouse) {
        // Map local click position to global screen coordinates
        var globalPos = mapToGlobal(mouse.x, mouse.y);
        root.toggleAkiflow(globalPos.x, globalPos.y);
    }

    RowLayout {
        id: row
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        Item {
            Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
            Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
            Layout.alignment: Qt.AlignVCenter

            Image {
                id: akiflowIcon
                source: "file:///usr/share/icons/hicolor/256x256/apps/akiflow.png"
                anchors.fill: parent
                smooth: true
                mipmap: true
            }

            // Purple dot when event is ongoing
            Rectangle {
                visible: root.hasEvent && root.eventTitle.indexOf("left") !== -1
                width: 6
                height: 6
                radius: 3
                color: "#AF38F9"
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: -1
                anchors.rightMargin: -1
            }
        }

        PlasmaComponents.Label {
            id: eventLabel
            text: root.eventTitle
            visible: root.hasEvent
            Layout.alignment: Qt.AlignVCenter
            Layout.maximumWidth: Kirigami.Units.gridUnit * 16
            elide: Text.ElideRight
            font.pointSize: Kirigami.Theme.defaultFont.pointSize
            color: Kirigami.Theme.textColor
        }
    }
}
