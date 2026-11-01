import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// 30px footer: the live status line on the left, readiness on the right.
Rectangle {
    id: root

    implicitHeight: Theme.statusbarHeight
    color: Theme.surface

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
        color: Theme.borderSoft
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

        Label {
            visible: appBridge.logWarnCount > 0
            text: appBridge.logWarnCount + " warning(s)"
            color: Theme.warning
            font.pixelSize: Theme.fontSmall
        }

        Label {
            visible: appBridge.logErrorCount > 0
            text: appBridge.logErrorCount + " error(s)"
            color: Theme.error
            font.pixelSize: Theme.fontSmall
        }

        Label {
            text: "Ready " + appBridge.readinessReadyCount + "/" + appBridge.readinessRows.length
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
        }
    }
}
