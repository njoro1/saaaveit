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
        // `.ban b{margin-bottom:2px}`; the detail and the remedy are one block of
        // text broken by `<br>`, so they do not get a gap of their own.
        spacing: 2

        Label {
            objectName: "download.failureTitle"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            // `.ban b` is bold text in the reading colour, not a red headline:
            // the border and the tint already say "error", so the words can
            // stay neutral and legible.
            text: appBridge.failureTitle
            color: Theme.text
            font.pixelSize: Theme.fontSmall
            font.weight: Font.Bold
            wrapMode: Text.WordWrap
        }

        Label {
            objectName: "download.failureDetail"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: appBridge.failureDetail !== ""
            text: appBridge.failureDetail
            color: Theme.text
            font.pixelSize: Theme.fontSmall
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }

        Label {
            objectName: "download.failureRemedy"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: appBridge.failureRemediation !== ""
            text: appBridge.failureRemediation
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
            wrapMode: Text.WordWrap
        }

        RowLayout {
            // `.ban .row{margin-top:10px}` less the column's own 2px.
            Layout.topMargin: 8
            spacing: Theme.sm

            AppButton {
                objectName: "download.failureRetry"
                text: "Retry"
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

            AppButton {
                objectName: "download.failureDismiss"
                text: "Dismiss"
                variant: "ghost"
                small: true
                onClicked: appBridge.dismissFailure()
            }

            Item { Layout.fillWidth: true }
        }
    }
}
