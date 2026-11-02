import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// 30px footer: the live status line on the left, the log's counts in the
// middle, readiness on the right. The counts are buttons — the only way to read
// what actually went wrong is the log itself.
Rectangle {
    id: root

    implicitHeight: Theme.statusbarHeight
    color: Theme.surface

    signal logRequested()

    readonly property color stateColor: {
        if (appBridge.statusState === "failed") return Theme.error
        if (appBridge.statusState === "running") return Theme.info
        if (appBridge.statusState === "done") return Theme.success
        if (appBridge.statusState === "cancelled") return Theme.warning
        return Theme.textMuted
    }

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.lg
        anchors.rightMargin: Theme.lg
        spacing: Theme.sm

        Rectangle {
            implicitWidth: 7
            implicitHeight: 7
            radius: 999
            color: root.stateColor
        }

        Label {
            objectName: "chrome.statusMessage"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: appBridge.statusMessage
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideRight
        }

        AppButton {
            objectName: "chrome.logErrors"
            visible: appBridge.logErrorCount > 0
            variant: "ghost"
            small: true
            tone: "err"
            text: appBridge.logErrorCount + (appBridge.logErrorCount === 1 ? " error" : " errors")
            onClicked: root.logRequested()
        }

        AppButton {
            objectName: "chrome.logWarnings"
            visible: appBridge.logWarnCount > 0
            variant: "ghost"
            small: true
            tone: "warn"
            text: appBridge.logWarnCount + (appBridge.logWarnCount === 1 ? " warning" : " warnings")
            onClicked: root.logRequested()
        }

        Label {
            text: "Ready " + appBridge.readinessReadyCount + "/" + appBridge.readinessRows.length
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
        }
    }
}
