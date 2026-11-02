import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The reference's ``.ban``: when a download fails, the panel says *why* in
// three lines and offers the two doors that matter - the log and a retry.
//
// It lives inside the summary card, not the status bar, because the moment a
// user notices a failure is the moment they are already looking at this panel.
Rectangle {
    id: root

    objectName: "download.failureBanner"
    visible: appBridge.failureActive

    radius: Theme.radiusMd
    // The reference paints the tint over the card and rings it with the raw
    // status colour: a 10-13% hue cannot carry 4.5:1 text on its own, the
    // border can carry the meaning.
    color: Theme.errorTint
    border.width: 1
    border.color: Theme.error

    implicitWidth: column.implicitWidth + 2 * Theme.md
    implicitHeight: column.implicitHeight + 2 * Theme.md

    ColumnLayout {
        id: column
        x: Theme.md
        y: Theme.md
        width: Math.max(0, root.width - 2 * Theme.md)
        spacing: 6

        Label {
            objectName: "download.failureTitle"
            Layout.fillWidth: true
            text: appBridge.failureTitle
            color: Theme.error
            font.pixelSize: Theme.fontBody
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
        }

        Label {
            objectName: "download.failureDetail"
            Layout.fillWidth: true
            visible: appBridge.failureDetail !== ""
            text: appBridge.failureDetail
            color: Theme.text
            font.pixelSize: Theme.fontSmall
            font.family: Theme.monoFont
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }

        Label {
            objectName: "download.failureRemedy"
            Layout.fillWidth: true
            visible: appBridge.failureRemediation !== ""
            text: appBridge.failureRemediation
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.topMargin: 2
            spacing: Theme.sm

            AppButton {
                objectName: "download.failureRetry"
                text: "Retry"
                variant: "primary"
                small: true
                enabled: !appBridge.downloadRunning && appBridge.canDownload
                onClicked: appBridge.download()
            }

            AppButton {
                objectName: "download.failureLog"
                text: "View log"
                variant: "ghost"
                small: true
                onClicked: {
                    var w = root.Window.window
                    if (w !== null && w !== undefined && w.openLog !== undefined)
                        w.openLog()
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                objectName: "download.failureDismiss"
                text: "Dismiss"
                variant: "ghost"
                small: true
                onClicked: appBridge.dismissFailure()
            }
        }
    }
}
