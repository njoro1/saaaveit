import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// One shortcut row: the bound chord, a Record button that arms the window's
// key catcher, and a Reset that only lights up when the row moved off its
// default. Key presses themselves are collected by Main.qml's `keyCatcher`
// (there is exactly one grabber per window), which writes the outcome back
// through ``appBridge.setShortcut``; errors surface here as ``captureMessage``.
RowLayout {
    id: root

    property string action: ""
    property string sequence: ""
    property bool isDefault: true

    spacing: 8

    readonly property bool capturing: Window.window !== null
                                      && Window.window.capturingAction === root.action

    Label {
        objectName: "settings.shortcut.value." + root.action
        text: root.capturing ? "press keys…"
              : root.sequence === "" ? "unassigned" : root.sequence
        color: root.capturing ? Theme.textMuted : Theme.text
        font.pixelSize: Theme.fontSmall
        font.family: Theme.monoFont
        font.italic: root.capturing
    }

    Label {
        visible: root.capturing && Window.window !== null
                 && Window.window.captureMessage !== ""
        text: root.capturing && Window.window !== null ? Window.window.captureMessage : ""
        color: Theme.error
        font.pixelSize: Theme.fontTiny
    }

    AppButton {
        objectName: "settings.shortcut.record." + root.action
        text: root.capturing ? "Cancel" : "Record"
        small: true
        variant: root.capturing ? "primary" : "ghost"
        Accessible.name: (root.capturing ? "Cancel recording for " : "Record shortcut for ")
                         + root.action
        onClicked: {
            var w = Window.window
            if (!w)
                return
            if (root.capturing)
                w.finishCapturing()
            else
                w.startCapturing(root.action)
        }
    }

    AppButton {
        objectName: "settings.shortcut.reset." + root.action
        text: "Reset"
        small: true
        variant: "ghost"
        enabled: !root.isDefault && !root.capturing
        onClicked: {
            var error = appBridge.resetShortcut(root.action)
            if (error !== "" && Window.window !== null)
                Window.window.captureMessage = error
        }
    }

    Item { Layout.fillWidth: true }
}
