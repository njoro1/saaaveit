import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Available formats for the inspected video, one row per codec × resolution.
// Rows are clickable and mirror the codec/resolution pickers exactly — both
// read the same `appBridge` state, so they can never disagree.
Rectangle {
    id: root

    objectName: "download.formatTable"

    signal picked(string codec, string resolution)

    implicitHeight: content.implicitHeight + 2
    color: "transparent"

    readonly property var rows: appBridge.formatRows
    readonly property real codecWidth: 112
    readonly property real resWidth: 84
    readonly property real sizeWidth: 104

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 28
            color: Theme.inset

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: Theme.sm

                Label {
                    Layout.preferredWidth: root.codecWidth
                    text: "CODEC"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontTiny
                    font.letterSpacing: 0.6
                }
                Label {
                    Layout.preferredWidth: root.resWidth
                    text: "RESOLUTION"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontTiny
                    font.letterSpacing: 0.6
                }
                Label {
                    Layout.fillWidth: true
                    text: "STREAM"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontTiny
                    font.letterSpacing: 0.6
                }
                Label {
                    Layout.preferredWidth: root.sizeWidth
                    horizontalAlignment: Text.AlignRight
                    text: "SIZE"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontTiny
                    font.letterSpacing: 0.6
                }
            }
        }

        Repeater {
            model: root.rows

            delegate: Rectangle {
                id: row
                required property var modelData

                Layout.fillWidth: true
                implicitHeight: 32
                color: row.modelData.selected
                       ? Theme.accentSoft
                       : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: Theme.sm

                    RowLayout {
                        Layout.preferredWidth: root.codecWidth
                        spacing: 5

                        Rectangle {
                            visible: row.modelData.selected
                            implicitWidth: 6
                            implicitHeight: 6
                            radius: 3
                            color: Theme.accent
                        }
                        Label {
                            text: row.modelData.codecLabel
                            color: row.modelData.selected ? Theme.accent : Theme.text
                            font.pixelSize: Theme.fontSmall
                            font.bold: row.modelData.selected
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }
                    }

                    Label {
                        Layout.preferredWidth: root.resWidth
                        text: row.modelData.resLabel
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: row.modelData.formatText
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        elide: Text.ElideRight
                    }

                    Label {
                        Layout.preferredWidth: root.sizeWidth
                        horizontalAlignment: Text.AlignRight
                        text: row.modelData.sizeText
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.borderSoft
                }

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(row.modelData.codec, row.modelData.resolution)
                }

                Accessible.role: Accessible.ListItem
                Accessible.name: row.modelData.codecLabel + " " + row.modelData.resLabel
                Accessible.description: row.modelData.formatText
                Accessible.selected: row.modelData.selected
            }
        }

        Label {
            visible: root.rows.length === 0
            Layout.fillWidth: true
            Layout.topMargin: 10
            text: "Inspect a video to see the formats it offers."
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
        }
    }
}
