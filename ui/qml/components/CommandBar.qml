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
        // `.top{border-bottom:1px solid var(--b1)}` — the same hairline the
        // cards use, not the lighter header rule.
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        spacing: Theme.sm

        // The native title bar already carries the app name and icon, and each
        // page has its own H1; repeating either here would double the chrome
        // (T6.5). The bar keeps the current video as context.
        Label {
            id: headlineLabel
            objectName: "chrome.headline"
            visible: root.headline !== ""
            text: root.headline
            // `.ctx` is the muted caption colour at body size, and `flex:1` —
            // it takes every pixel the buttons leave and ellipsises on the
            // right, so no cap on its width here.
            color: Theme.textMuted
            font.pixelSize: Theme.fontBody
            elide: Text.ElideRight
            // Same class as the blocked reason: a non-filling Layout item is
            // sized to its preferred width and then simply overflows the bar,
            // so a long video title walks over the buttons on its right.
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }

        Item { Layout.fillWidth: true }

        AppButton {
            objectName: "chrome.paletteButton"
            text: "Search"
            variant: "ghost"
            iconName: "search"
            // `.top #sb` carries its chord as part of the button, so the
            // shortcut is discoverable without opening the palette.
            trailingText: appBridge.shortcutMap.palette
            onClicked: root.openPalette()
        }

        AppButton {
            objectName: "chrome.themeButton"
            text: appBridge.themeName === "dark" ? "Light" : "Dark"
            variant: "ghost"
            onClicked: appBridge.toggleTheme()
        }
    }
}
