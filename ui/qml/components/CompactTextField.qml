import QtQuick
import QtQuick.Controls
import ".."

// Text field matching the reference's `.in`: 44px tall, inset fill, `b2`
// border, 10px radius, 14px side padding, accent outline on focus. Keeps the
// ``label`` hook used for accessibility and test lookups.
TextField {
    id: root

    property string label: ""

    font.pixelSize: Theme.fontBody
    color: Theme.text
    height: Theme.inputHeight
    selectByMouse: true
    verticalAlignment: TextInput.AlignVCenter
    placeholderTextColor: Theme.textMuted
    leftPadding: 14
    rightPadding: 14
    activeFocusOnTab: true

    Accessible.role: Accessible.EditableText
    Accessible.name: root.label !== "" ? root.label : root.placeholderText
    Accessible.description: root.placeholderText

    background: Item {
        // The reference focuses with a 2px `line` outline *offset* 2px, keeping
        // the field's own border. A sibling ring is how that offset is drawn
        // here, since a Rectangle border cannot sit outside its own fill.
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: Theme.radiusMd + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.accentLine
            visible: root.activeFocus
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusMd
            color: root.echoMode === TextInput.Password ? Theme.fieldSecretBackground : Theme.inset
            border.width: 1
            border.color: root.activeFocus ? "transparent" : Theme.borderStrong
        }
    }
}
