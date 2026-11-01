import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Top command bar: the current video as context plus the two global
// affordances (command palette / theme). The screen name lives in each page's
// H1; the app name lives in the native title bar.
Rectangle {
    id: root

    property string headline: ""

    signal openPalette()

    implicitHeight: Theme.topbarHeight
    color: Theme.surface

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

        // The native title bar already carries the app name and icon, and each
        // page has its own H1; repeating either here would double the chrome
        // (T6.5). The bar keeps the current video as context.
        Label {
            id: headlineLabel
            objectName: "chrome.headline"
            visible: root.headline !== ""
            text: root.headline
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideMiddle
            // Same class as the blocked reason: a non-filling Layout item is
            // sized to its preferred width and then simply overflows the bar,
            // so a long video title walks over the buttons on its right.
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.maximumWidth: 520
        }

        Item { Layout.fillWidth: true }

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
