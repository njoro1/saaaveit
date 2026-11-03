import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// One settings row — the reference's `.set`: a label with its hint lines
// beneath it on the left, the control hugged to the right edge, and a hairline
// above. The card that hosts the rows contributes the 18px of side padding, so
// the hairline runs the full width of the card's content box.
//
//   SettingsRow {
//       label: "Filename template"
//       hint: "Fields: %(title)s, %(id)s, %(ext)s"
//       CompactTextField { Layout.preferredWidth: 300 }
//   }
Item {
    id: root

    property string label: ""
    property string hint: ""
    // The mono value of an information row (a path, a version): right-aligned so
    // the column of values reads as one block.
    property string value: ""
    property bool valueMono: false
    // Every row draws the hairline above it; the first row in a card hides it,
    // which is what `border-top` + `:first-of-type` do in the reference.
    property bool topBorder: true

    default property alias content: slot.data
    // A row may stack more than one hint under its label (the reference's
    // `.set small` repeats). Items here join the label column, so they stay on
    // the left with the label instead of becoming controls.
    property alias hintContent: labels.data

    implicitWidth: 200
    implicitHeight: row.implicitHeight + root._pad * 2

    readonly property int _pad: Theme.comfortable ? 18 : 14

    Layout.fillWidth: true

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        visible: root.topBorder
        color: Theme.border
    }

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.topMargin: root._pad
        anchors.bottomMargin: root._pad
        spacing: 16

        ColumnLayout {
            id: labels
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 2

            Label {
                visible: root.label !== ""
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.label
                color: Theme.text
                font.pixelSize: Theme.fontBody
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Label {
                visible: root.hint !== ""
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.hint
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
                wrapMode: Text.WordWrap
            }
        }

        Label {
            visible: root.value !== ""
            Layout.maximumWidth: 420
            text: root.value
            horizontalAlignment: Text.AlignRight
            // The reference's `.mono`/`.num` spans change only family and size,
            // so a value is the same colour as its label and reads as data
            // because it is monospaced.
            color: Theme.text
            font.pixelSize: Theme.fontTiny
            font.family: root.valueMono ? Theme.monoFont : Theme.uiFont
            elide: Text.ElideMiddle
        }

        RowLayout {
            id: slot
            spacing: 8
        }
    }
}
