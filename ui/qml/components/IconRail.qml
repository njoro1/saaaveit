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
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 6

        Repeater {
            model: root.items

            delegate: Item {
                id: stop
                required property var modelData
                required property int index

                objectName: "rail.destination." + index
                Layout.preferredWidth: Theme.railItemSize
                Layout.preferredHeight: Theme.railItemSize
                Layout.alignment: Qt.AlignHCenter
                // The rail is the app's primary navigation, so it has to be
                // walkable: a plain Item is invisible to Tab otherwise.
                activeFocusOnTab: true

                readonly property bool isOn: root.currentIndex === index

                Keys.onReturnPressed: root.navigate(index)
                Keys.onSpacePressed: root.navigate(index)

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusLg
                    color: parent.isOn ? Theme.accentSoft
                                       : (railMouse.containsMouse ? Theme.surfaceAlt : "transparent")
                    border.width: stop.activeFocus ? 2 : 0
                    border.color: Theme.accentLine
                }

                Icon {
                    anchors.centerIn: parent
                    name: parent.modelData.icon
                    // The active icon is a *shape* in accent, which is legal;
                    // a word in raw accent on this tint would not be.
                    color: parent.isOn ? Theme.accent : Theme.textMuted
                    strokeWidth: 1.8
                    width: 20
                    height: 20
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
            Layout.preferredWidth: Theme.railItemSize
            Layout.preferredHeight: Theme.railItemSize
            Layout.alignment: Qt.AlignHCenter
            activeFocusOnTab: true

            Keys.onReturnPressed: root.openPalette()
            Keys.onSpacePressed: root.openPalette()

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusLg
                color: paletteMouse.containsMouse ? Theme.surfaceAlt : "transparent"
                border.width: paletteStop.activeFocus ? 2 : 0
                border.color: Theme.accentLine
            }

            Icon {
                anchors.centerIn: parent
                name: "keyboard"
                color: Theme.textMuted
                width: 20
                height: 20
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
