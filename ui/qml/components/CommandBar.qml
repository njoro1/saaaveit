import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Top command bar: app name, current screen, and the two global affordances
// (command palette / theme).
Rectangle {
    id: root

    property int page: 0
    property string headline: ""

    signal openPalette()

    implicitHeight: Theme.topbarHeight
    color: Theme.surface

    readonly property var pageNames: ["Download", "Library", "Settings"]

    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.borderSoft
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.lg
        anchors.rightMargin: Theme.lg
        spacing: Theme.md

        RowLayout {
            spacing: 10

            Rectangle {
                implicitWidth: 26
                implicitHeight: 26
                radius: Theme.radiusSm
                color: Theme.accentSoft

                Icon {
                    anchors.centerIn: parent
                    name: "download"
                    width: 16
                    height: 16
                    color: Theme.accent
                }
            }

            Label {
                text: "Saaaveit"
                color: Theme.text
                font.pixelSize: Theme.fontTitle
                font.bold: true
            }
        }

        Rectangle {
            implicitWidth: 1
            implicitHeight: 18
            color: Theme.border
        }

        Label {
            text: root.pageNames[Math.max(0, Math.min(root.pageNames.length - 1, root.page))] || ""
            color: Theme.textMuted
            font.pixelSize: Theme.fontBody
        }

        Item { Layout.fillWidth: true }

        Label {
            visible: root.headline !== ""
            Layout.maximumWidth: 520
            text: root.headline
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideMiddle
        }

        AppButton {
            objectName: "chrome.paletteButton"
            text: "Search"
            small: true
            variant: "ghost"
            iconName: "search"
            onClicked: root.openPalette()
        }

        AppButton {
            objectName: "chrome.themeButton"
            text: appBridge.themeName === "dark" ? "Light" : "Dark"
            small: true
            variant: "ghost"
            iconName: appBridge.themeName === "dark" ? "sun" : "moon"
            onClicked: appBridge.toggleTheme()
        }
    }
}
