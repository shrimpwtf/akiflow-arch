import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami

Item {
    Layout.preferredWidth: Kirigami.Units.gridUnit * 20
    Layout.preferredHeight: content.implicitHeight + 2 * Kirigami.Units.largeSpacing

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.mediumSpacing

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Image {
                source: "file:///usr/share/icons/hicolor/256x256/apps/akiflow.png"
                smooth: true
                mipmap: true
                Layout.preferredWidth: Kirigami.Units.iconSizes.small
                Layout.preferredHeight: Kirigami.Units.iconSizes.small
            }

            PlasmaExtras.Heading {
                level: 4
                text: "Akiflow"
                Layout.fillWidth: true
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        // Event status section
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            visible: root.hasEvent

            // Status badge
            RowLayout {
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: root.eventTitle.indexOf("left") !== -1 ? "#AF38F9" : "#3B82F6"
                }

                PlasmaComponents.Label {
                    text: root.eventTitle.indexOf("left") !== -1 ? "Now" : "Up next"
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize - 1
                    font.bold: true
                    color: root.eventTitle.indexOf("left") !== -1 ? "#AF38F9" : "#3B82F6"
                }
            }

            // Event title and timing
            PlasmaComponents.Label {
                text: root.eventTitle
                Layout.fillWidth: true
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
                font.bold: true
                wrapMode: Text.Wrap
                color: Kirigami.Theme.textColor
            }
        }

        // No events state
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            visible: !root.hasEvent

            PlasmaComponents.Label {
                text: "No upcoming events"
                Layout.fillWidth: true
                font.pointSize: Kirigami.Theme.defaultFont.pointSize
                color: Kirigami.Theme.disabledTextColor
            }

            PlasmaComponents.Label {
                text: "You're all clear!"
                Layout.fillWidth: true
                font.pointSize: Kirigami.Theme.defaultFont.pointSize - 1
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        // Action button
        PlasmaComponents.Button {
            text: root.hasEvent ? "Open in Akiflow" : "Open Akiflow"
            icon.name: "window-new"
            Layout.alignment: Qt.AlignRight
            onClicked: root.toggleAkiflow(0, 0)
        }
    }
}
