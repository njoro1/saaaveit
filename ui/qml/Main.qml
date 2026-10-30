import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."
import "components"
import "pages"

// Application shell: 56px command bar, 64px icon rail, the page stack, and a
// 30px status bar. Pages are instantiated once and kept alive, so switching
// screens never loses state.
ApplicationWindow {
    id: window

    property int currentPage: 0

    x: appBridge.windowX
    y: appBridge.windowY
    width: appBridge.windowWidth
    height: appBridge.windowHeight
    minimumWidth: 1080
    minimumHeight: 680
    visible: true
    title: "Saaaveit"
    color: Theme.background

    Binding { target: Theme; property: "themeName"; value: appBridge.themeName }
    Binding { target: Theme; property: "comfortable"; value: appBridge.comfortable }
    Binding { target: Theme; property: "reducedMotion"; value: appBridge.reducedMotion }
    Binding { target: Theme; property: "accentName"; value: appBridge.accentName }

    function goTo(index) {
        window.currentPage = Math.max(0, Math.min(2, index))
    }

    function runAction(action) {
        if (action === "inspect")
            appBridge.inspect()
        else if (action === "download")
            appBridge.download()
        else if (action === "download_subtitle")
            appBridge.downloadSubtitleOnly()
        else if (action === "cancel")
            appBridge.cancelDownload()
        else if (action === "open_folder")
            appBridge.openDownloadFolder()
        else if (action === "toggle_theme")
            appBridge.toggleTheme()
        else if (action === "toggle_comfortable")
            appBridge.setComfortable(!appBridge.comfortable)
        else if (action === "toggle_reduced_motion")
            appBridge.setReducedMotion(!appBridge.reducedMotion)
        else if (action === "clear_history")
            appBridge.clearHistory()
    }

    Shortcut {
        sequence: appBridge.shortcutFor("goto_download")
        onActivated: window.goTo(0)
    }
    Shortcut {
        sequence: appBridge.shortcutFor("goto_library")
        onActivated: window.goTo(1)
    }
    Shortcut {
        sequence: appBridge.shortcutFor("goto_settings")
        onActivated: window.goTo(2)
    }
    Shortcut {
        sequence: appBridge.shortcutFor("palette")
        onActivated: palette.toggle()
    }
    Shortcut {
        sequence: appBridge.shortcutFor("inspect")
        enabled: !palette.visible
        onActivated: window.runAction("inspect")
    }
    Shortcut {
        sequence: appBridge.shortcutFor("download")
        enabled: !palette.visible
        onActivated: window.runAction("download")
    }
    Shortcut {
        sequence: appBridge.shortcutFor("download_subtitle")
        enabled: !palette.visible
        onActivated: window.runAction("download_subtitle")
    }
    Shortcut {
        sequence: appBridge.shortcutFor("cancel")
        enabled: !palette.visible
        onActivated: window.runAction("cancel")
    }
    Shortcut {
        sequence: appBridge.shortcutFor("open_folder")
        enabled: !palette.visible
        onActivated: window.runAction("open_folder")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        CommandBar {
            Layout.fillWidth: true
            page: window.currentPage
            headline: appBridge.hasInfo ? appBridge.videoTitle : ""
            onOpenPalette: palette.open()
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            IconRail {
                Layout.fillHeight: true
                currentIndex: window.currentPage
                onNavigate: function (index) { window.goTo(index) }
                onOpenPalette: palette.open()
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: window.currentPage

                DownloadPage {}
                LibraryPage {}
                SettingsPage {}
            }
        }

        StatusBar { Layout.fillWidth: true }
    }

    CommandPalette {
        id: palette
        anchors.fill: parent
        onNavigateRequested: function (index) { window.goTo(index) }
        onActionRequested: function (action) { window.runAction(action) }
    }

    onClosing: appBridge.saveWindowState(x + "," + y + "," + width + "," + height)

    Component.onCompleted: {
        // A URL handed in on the command line is inspected straight away.
        if (appBridge.url !== "" && !appBridge.hasInfo)
            appBridge.inspect()
    }
}
