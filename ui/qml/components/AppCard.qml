import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Card with an optional header band (uppercase title + right-hand chips) and a
// default content slot.
//
//   AppCard {
//       title: "Video"; note: "How the app renders offline"
//       headerExtra: [ Chip { text: "Saaave"; tone: "acc" } ]
//       ColumnLayout { ... }        // <- default content
//   }
Rectangle {
    id: root

    default property alias content: body.data
    property alias headerExtra: headerExtraRow.data

    property string title: ""
    property string note: ""
    property bool tight: false
    property int padding: tight ? Theme.md : 15

    // The root only reserves the layout cell; the surface and its shadow are
    // siblings so the shadow can sit behind the surface. Level-1 only (T2.1):
    // two stacked rings instead of MultiEffect, so the frozen build needs no
    // extra QML module and scrolling pays no shader cost.
    color: "transparent"
    implicitHeight: outer.implicitHeight

    readonly property var _shadow: Theme.shadowFor(Theme.elevationCard)

    Rectangle {
        anchors.fill: surface
        anchors.margins: -2
        radius: Theme.radiusLg + 2
        color: Theme.shadowColor
        opacity: root._shadow.opacity * 0.5
    }

    Rectangle {
        anchors.fill: surface
        anchors.margins: -1
        radius: Theme.radiusLg + 1
        color: Theme.shadowColor
        opacity: root._shadow.opacity * 0.9
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: Theme.radiusLg
        color: Theme.surface
    }

    ColumnLayout {
        id: outer
        anchors.fill: parent
        spacing: 0

        // --- Header ---------------------------------------------------------
        Item {
            id: header
            visible: root.title !== ""
            Layout.fillWidth: true
            Layout.preferredHeight: headerRow.implicitHeight + 26

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: 15
                anchors.rightMargin: 15
                spacing: 9

                Label {
                    text: root.title
                    color: Theme.text
                    font.pixelSize: Theme.fontSmall + 1
                    font.weight: Font.DemiBold
                }

                Label {
                    id: noteLabel
                    visible: root.note !== ""
                    Layout.fillWidth: true
                    text: root.note
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                    elide: Text.ElideRight

                    // The note is the card's only free-text slot, so it is the
                    // one thing here that can overflow. Elide, but keep the
                    // whole string on hover (UI review D4).
                    ToolTip.text: root.note
                    ToolTip.visible: noteHover.hovered && noteLabel.truncated
                    ToolTip.delay: 400
                    HoverHandler { id: noteHover }
                }

                Item {
                    visible: root.note === ""
                    Layout.fillWidth: true
                }

                RowLayout {
                    id: headerExtraRow
                    spacing: 6
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.borderSoft
            }
        }

        // --- Body -----------------------------------------------------------
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: root.padding
            spacing: 10
        }
    }
}
