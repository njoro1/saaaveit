import QtQuick
import QtQuick.Controls
import ".."

// Compact text field matching the mockup's `.field` (inset background, focus
// ring). Keeps the ``label`` hook used for accessibility and test lookups.
TextField {
    id: root

    property string label: ""

    font.pixelSize: Theme.fontBody
    color: Theme.text
    height: Theme.controlHeight
    selectByMouse: true
    verticalAlignment: TextInput.AlignVCenter
    placeholderTextColor: Theme.textMuted
    leftPadding: 10
    rightPadding: 10
    activeFocusOnTab: true

    Accessible.role: Accessible.EditableText
    Accessible.name: root.label !== "" ? root.label : root.placeholderText
    Accessible.description: root.placeholderText

    background: Item {
        // 1 px outer glow makes the focused field read even on a busy card.
        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: Theme.radiusSm + 1
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30)
            visible: root.activeFocus
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSm
            color: root.echoMode === TextInput.Password ? Theme.fieldSecretBackground : Theme.inset
            border.width: root.activeFocus ? 2 : 1
            border.color: root.activeFocus ? Theme.accentLine
                                            : (root.hovered ? Theme.borderStrong : Theme.border)
        }
    }
}
