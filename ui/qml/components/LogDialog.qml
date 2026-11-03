import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The log, in a modal. Opened by the status bar's warning/error counts, by the
// Settings "View log" row and by the command palette — the three places that
// can tell something went wrong.
//
// The reference caps the text at 320px and scrolls it; an uncapped log pushed
// the dialog past the window and put the newest lines out of reach.
Item {
    id: root

    objectName: "logDialog"

    visible: false
    z: 1100

    readonly property var _overlayShadow: Theme.shadowFor(Theme.elevationOverlay)

    function open() {
        visible = true
        closeButton.forceActiveFocus()
    }

    function close() {
        visible = false
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.visible
        onActivated: root.close()
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.scrim

        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    // Level-3 rings, declared before the panel so they paint behind it.
    Rectangle {
        anchors.fill: panel
        anchors.margins: -4
        radius: Theme.dialogRadius + 4
        color: Theme.shadowColor
        opacity: root._overlayShadow.opacity * 0.5
    }

    Rectangle {
        anchors.fill: panel
        anchors.margins: -2
        radius: Theme.dialogRadius + 2
        color: Theme.shadowColor
        opacity: root._overlayShadow.opacity
    }

    Rectangle {
        id: panel
        // ``.dlg`` is top-aligned in the scrim, not centred: ``.scrim{padding-top:
        // 90px}`` plus ``#lg{margin-top:60px}`` puts its edge 150px down, so the
        // log always opens on the same reading line. The clamp keeps it on screen
        // in a short window, which the prototype never has to be.
        readonly property int referenceTop: 150
        readonly property int pad: 20
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: Math.max(Theme.xs,
                                    Math.min(referenceTop,
                                             parent.height - height - Theme.xs))
        width: Math.min(640, parent.width - 80)
        height: column.implicitHeight + 2 * panel.pad
        radius: Theme.dialogRadius
        color: Theme.surface
        border.width: 1
        border.color: Theme.borderStrong

        ColumnLayout {
            id: column
            anchors.fill: parent
            anchors.margins: panel.pad
            spacing: 12

            // ``.row{gap:8px}`` — title and count at the two ends of the line.
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    text: "Log"
                    color: Theme.text
                    font.pixelSize: Theme.fontTitle
                    // ``<h2 style="font-size:17px">`` keeps the UA's bold.
                    font.bold: true
                }

                Label {
                    objectName: "log.counts"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    horizontalAlignment: Text.AlignRight
                    text: appBridge.logWarnCount + " warnings · "
                          + appBridge.logErrorCount + " errors"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                    elide: Text.ElideRight
                }
            }

            Flickable {
                id: scroll
                objectName: "log.scroll"
                Layout.fillWidth: true
                Layout.preferredHeight: logBody.height + 24
                Layout.maximumHeight: 320
                contentHeight: logBody.height
                contentWidth: width
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar { }

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusMd
                    color: Theme.inset
                }

                Text {
                    id: logBody
                    objectName: "log.text"
                    x: 12
                    width: scroll.width - 24
                    text: appBridge.logText === "" ? "(empty)" : appBridge.logText
                    // ``pre.log`` sets no colour: the log is body ink at 12px on
                    // the recessed surface.
                    color: Theme.text
                    font.pixelSize: Theme.fontTiny
                    font.family: Theme.monoFont
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Item { Layout.fillWidth: true }

                AppButton {
                    objectName: "log.clear"
                    variant: "ghost"
                    text: "Clear"
                    onClicked: appBridge.clearLog()
                }

                AppButton {
                    objectName: "log.copy"
                    text: "Copy"
                    onClicked: appBridge.copyLog()
                }

                AppButton {
                    id: closeButton
                    objectName: "log.close"
                    variant: "primary"
                    text: "Close"
                    onClicked: root.close()
                }
            }
        }
    }
}
