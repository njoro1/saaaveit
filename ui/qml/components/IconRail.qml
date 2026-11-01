import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Left icon rail: the app's three destinations plus the palette shortcut.
Rectangle {
    id: root

    property int currentIndex: 0

    signal navigate(int index)
    signal openPalette()

    implicitWidth: Theme.railWidth
    color: Theme.surface

    readonly property var items: [
        { label: "Download", icon: "download" },
        { label: "Library", icon: "history" },
        { label: "Settings", icon: "settings" }
    ]

    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.borderSoft
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: Theme.md
        anchors.bottomMargin: Theme.md
        spacing: Theme.xs

        Repeater {
            model: root.items

            delegate: Item {
                id: stop
                required property var modelData
                required property int index

                objectName: "rail.destination." + index
                Layout.preferredWidth: 52
                Layout.preferredHeight: 52
                Layout.alignment: Qt.AlignHCenter
                // The rail is the app's primary navigation, so it has to be
                // walkable: a plain Item is invisible to Tab otherwise.
                activeFocusOnTab: true

                readonly property bool isOn: root.currentIndex === index

                Keys.onReturnPressed: root.navigate(index)
                Keys.onSpacePressed: root.navigate(index)

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusMd
                    color: parent.isOn ? Theme.accentSoft
                                       : (railMouse.containsMouse ? Theme.surfaceAlt : "transparent")
                    border.width: stop.activeFocus ? 2 : 0
                    border.color: Theme.accentLine
                }

                Icon {
                    anchors.centerIn: parent
                    name: parent.modelData.icon
                    color: parent.isOn ? Theme.accent : Theme.textMuted
                    strokeWidth: 1.9
                    width: 22
                    height: 22
                }

                MouseArea {
                    id: railMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.navigate(index)
                }

                AppToolTip {
                    text: modelData.label
                    hovered: railMouse.containsMouse
                    showDelay: 400
                }

                Accessible.role: Accessible.PageTab
                Accessible.name: modelData.label
                Accessible.selected: isOn
            }
        }

        Item { Layout.fillHeight: true }

        Item {
            id: paletteStop
            objectName: "rail.palette"
            Layout.preferredWidth: 52
            Layout.preferredHeight: 52
            Layout.alignment: Qt.AlignHCenter
            activeFocusOnTab: true

            Keys.onReturnPressed: root.openPalette()
            Keys.onSpacePressed: root.openPalette()

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusMd
                color: paletteMouse.containsMouse ? Theme.surfaceAlt : "transparent"
                border.width: paletteStop.activeFocus ? 2 : 0
                border.color: Theme.accentLine
            }

            Icon {
                anchors.centerIn: parent
                name: "keyboard"
                color: Theme.textMuted
                width: 22
                height: 22
            }

            MouseArea {
                id: paletteMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.openPalette()
            }

            AppToolTip {
                text: "Command palette · Ctrl K"
                hovered: paletteMouse.containsMouse
                showDelay: 400
            }

            Accessible.role: Accessible.Button
            Accessible.name: "Open the command palette"
        }
    }
}
