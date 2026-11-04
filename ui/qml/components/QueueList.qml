import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The batch the user has committed to: one row per job, in the order they run.
//
// Rows carry *states*, never live figures. ``appBridge.queueRows`` is a plain
// list, so the whole model is rebuilt whenever the queue changes — and a
// progress line arrives many times a second. The running job's numbers
// therefore come from the scalar properties (the same ones the summary panel
// reads), which notify on their own and leave the list alone.
AppCard {
    id: root

    objectName: "queue.card"
    title: "Queue"
    visible: appBridge.queueCount > 0

    // A batch can be long, and the card shares the flow column with the form:
    // past a few rows the list scrolls in its own box instead of pushing the
    // page down.
    property real maxListHeight: 240

    headerExtra: [
        Label {
            objectName: "queue.count"
            text: appBridge.pendingCount > 0
                 ? appBridge.pendingCount + " waiting"
                 : appBridge.queueCount + (appBridge.queueCount === 1 ? " job" : " jobs")
            color: Theme.textMuted
            font.pixelSize: Theme.fontTiny
            font.family: Theme.monoFont
        },

        AppButton {
            objectName: "queue.clearButton"
            text: "Clear"
            small: true
            variant: "ghost"
            onClicked: appBridge.clearQueue()
        }
    ]

    ListView {
        id: rows
        objectName: "queue.list"
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(root.maxListHeight, contentHeight)
        spacing: 0
        clip: true
        interactive: contentHeight > root.maxListHeight
        boundsBehavior: Flickable.StopAtBounds
        model: appBridge.queueRows

        // A Flickable lays its own attached bar out, so this one carries only
        // the policy: the bar shows up exactly when the list has to scroll.
        ScrollBar.vertical: AppScrollBar {
            policy: rows.interactive ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        }

        delegate: Item {
            id: row
            objectName: "queue.row"
            required property int index
            required property var modelData

            width: rows.width
            implicitHeight: line.implicitHeight + 2 * pad
            readonly property int pad: Theme.comfortable ? 11 : 9

            // What the second line is worth saying, for this job's state.
            readonly property string detail: {
                var picks = modelData.summary
                if (modelData.state === "running") {
                    var step = "Downloading " + modelData.position + " of " + modelData.total
                    return picks === "" ? step : step + " · " + picks
                }
                if (modelData.state === "queued")
                    return picks === "" ? "Waiting" : "Waiting · " + picks
                return picks === "" ? modelData.stateLabel
                                    : modelData.stateLabel + " · " + picks
            }

            // Only in-flight work can be cancelled. A job that has not started
            // is dropped before it runs, and a finished row is dismissed after.
            readonly property bool live: modelData.state === "running"
            readonly property string actionText: live ? "Cancel" : "Remove"
            readonly property string actionTip: live
                ? "Stop this job and move on to the next one"
                : (modelData.removable
                   ? "Dismiss this row; whatever it saved stays on disk"
                   : "Drop this job before it starts")

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                visible: row.index > 0
                color: Theme.border
            }

            RowLayout {
                id: line
                anchors.fill: parent
                anchors.leftMargin: 0
                anchors.rightMargin: 0
                anchors.topMargin: row.pad
                anchors.bottomMargin: row.pad
                spacing: Theme.sm

                StatusMark {
                    objectName: "queue.rowMark"
                    visible: modelData.state !== "running" && modelData.state !== "queued"
                    status: modelData.outcome === "done" ? "ok"
                          : (modelData.outcome === "failed" ? "error" : "unchecked")
                    text: ""
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 2

                    Label {
                        objectName: "queue.rowTitle"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: (modelData.index + 1) + ".  " + modelData.name
                        color: Theme.text
                        font.pixelSize: Theme.fontSmall
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }

                    Label {
                        objectName: "queue.rowDetail"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: row.detail
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontTiny
                        elide: Text.ElideRight
                    }

                    // The reason a row failed belongs on the row: a batch that
                    // carried on after it must still say what went wrong.
                    Label {
                        objectName: "queue.rowError"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: modelData.error !== ""
                        text: modelData.error
                        color: Theme.error
                        font.pixelSize: Theme.fontTiny
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        wrapMode: Text.WordWrap
                    }
                }

                AppButton {
                    objectName: "queue.rowAction"
                    small: true
                    variant: "ghost"
                    text: row.actionText
                    tooltip: row.actionTip
                    onClicked: appBridge.cancelJob(row.index)
                }
            }

            // The live figure for the one job that has it.
            Rectangle {
                objectName: "queue.rowProgress"
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 3
                radius: 1.5
                visible: modelData.state === "running"
                color: Theme.inset

                Rectangle {
                    objectName: "queue.rowProgressFill"
                    height: parent.height
                    radius: parent.radius
                    width: parent.width * Math.min(100, appBridge.downloadProgress) / 100
                    color: Theme.accent

                    Behavior on width {
                        enabled: !Theme.reducedMotion
                        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                    }
                }
            }
        }
    }
}
