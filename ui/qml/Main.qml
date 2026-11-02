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
    // Set while the Settings page is capturing a chord: every application
    // shortcut has to stand down, or Ctrl+1 would navigate away mid-recording.
    property bool capturingShortcuts: false

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

    // A modal owns the keyboard, so the app's own chords are silent while one
    // is up — the same rule the reference applies to all three overlays.
    readonly property bool shortcutsLive: !palette.visible && !logDialog.visible
                                          && !window.capturingShortcuts

    function goTo(index) {
        window.currentPage = Math.max(0, Math.min(2, index))
    }

    function openLog() {
        logDialog.open()
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
        else if (action === "open_last")
            appBridge.openLastFile()
        else if (action === "view_log")
            window.openLog()
        else if (action === "toggle_theme")
            appBridge.toggleTheme()
        else if (action === "toggle_comfortable")
            appBridge.setComfortable(!appBridge.comfortable)
        else if (action === "toggle_reduced_motion")
            appBridge.setReducedMotion(!appBridge.reducedMotion)
        else if (action === "clear_history")
            appBridge.clearHistory()
    }

    // ``shortcutMap`` is a notified property; ``shortcutFor()`` is a slot, so
    // binding a sequence to it read the value once and never updated again —
    // a re-recorded chord kept firing the old one until restart.
    Shortcut {
        sequence: appBridge.shortcutMap.goto_download
        enabled: window.shortcutsLive
        onActivated: window.goTo(0)
    }
    Shortcut {
        sequence: appBridge.shortcutMap.goto_library
        enabled: window.shortcutsLive
        onActivated: window.goTo(1)
    }
    Shortcut {
        sequence: appBridge.shortcutMap.goto_settings
        enabled: window.shortcutsLive
        onActivated: window.goTo(2)
    }
    Shortcut {
        sequence: appBridge.shortcutMap.palette
        enabled: !logDialog.visible && !window.capturingShortcuts
        onActivated: palette.toggle()
    }
    Shortcut {
        sequence: appBridge.shortcutMap.inspect
        enabled: window.shortcutsLive
        onActivated: window.runAction("inspect")
    }
    Shortcut {
        sequence: appBridge.shortcutMap.download
        enabled: window.shortcutsLive
        onActivated: window.runAction("download")
    }
    Shortcut {
        sequence: appBridge.shortcutMap.download_subtitle
        enabled: window.shortcutsLive
        onActivated: window.runAction("download_subtitle")
    }
    Shortcut {
        sequence: appBridge.shortcutMap.cancel
        enabled: window.shortcutsLive
        onActivated: window.runAction("cancel")
    }
    Shortcut {
        sequence: appBridge.shortcutMap.open_folder
        enabled: window.shortcutsLive
        onActivated: window.runAction("open_folder")
    }
    Shortcut {
        sequence: appBridge.shortcutMap.open_last
        enabled: window.shortcutsLive
        onActivated: window.runAction("open_last")
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        CommandBar {
            Layout.fillWidth: true
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

            // The stack keeps every page alive; the wrapper only animates the
            // reveal so navigation reads as a transition, not a repaint.
            Item {
                id: pageFrame
                Layout.fillWidth: true
                Layout.fillHeight: true

                StackLayout {
                    anchors.fill: parent
                    currentIndex: window.currentPage

                    DownloadPage {}
                    LibraryPage {}
                    SettingsPage {}
                }
            }
        }

        StatusBar {
            Layout.fillWidth: true
            onLogRequested: window.openLog()
        }
    }

    CommandPalette {
        id: palette
        anchors.fill: parent
        onNavigateRequested: function (index) { window.goTo(index) }
        onActionRequested: function (action) { window.runAction(action) }
    }

    LogDialog {
        id: logDialog
        anchors.fill: parent
    }

    // The bridge asks for a page when a command has to leave the current one —
    // "Redownload" hands the URL to the Download screen, for instance.
    Connections {
        target: appBridge
        function onRequestTab(index) { window.goTo(index) }
    }

    // Page switch: the new page fades in over 160 ms. Reduced motion keeps the
    // switch instant, and navigating to the same page never animates.
    Connections {
        target: window
        function onCurrentPageChanged() {
            pageFrame.opacity = 0
            pageReveal.restart()
        }
    }

    NumberAnimation {
        id: pageReveal
        target: pageFrame
        property: "opacity"
        to: 1
        duration: Theme.reducedMotion ? 0 : 160
        easing.type: Easing.OutCubic
    }

    onClosing: appBridge.saveWindowState(x + "," + y + "," + width + "," + height)

    Component.onCompleted: {
        // A URL handed in on the command line is inspected straight away.
        if (appBridge.url !== "" && !appBridge.hasInfo)
            appBridge.inspect()
    }
}
