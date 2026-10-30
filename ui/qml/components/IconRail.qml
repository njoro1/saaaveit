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
                required property var modelData
                required property int index

                Layout.preferredWidth: 52
                Layout.preferredHeight: 52
                Layout.alignment: Qt.AlignHCenter

                readonly property bool isOn: root.currentIndex === index

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusMd
                    color: parent.isOn ? Theme.accentSoft
                                       : (railMouse.containsMouse ? Theme.surfaceAlt : "transparent")
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
            Layout.preferredWidth: 52
            Layout.preferredHeight: 52
            Layout.alignment: Qt.AlignHCenter

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusMd
                color: paletteMouse.containsMouse ? Theme.surfaceAlt : "transparent"
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
