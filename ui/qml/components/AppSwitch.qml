import QtQuick
import QtQuick.Controls
import ".."

// Labelled switch. Emits ``toggled(checked)`` so the caller can push the value
// into the bridge; ``checked`` is normally bound to a bridge property.
Item {
    id: root

    property string text: ""
    property bool checked: false
    property string accessibleName: text

    signal toggled(bool checked)

    implicitWidth: track.width + (text !== "" ? 9 + label.implicitWidth : 0)
    implicitHeight: Math.max(18, label.implicitHeight)
    opacity: enabled ? 1.0 : 0.45
    activeFocusOnTab: true
    scale: switchMouse.pressed ? 0.97 : 1.0
    Behavior on scale {
        NumberAnimation {
            duration: Theme.reducedMotion ? 0 : 90
            easing.type: Easing.OutCubic
        }
    }

    function _toggle() {
        root.checked = !root.checked
        root.toggled(root.checked)
    }

    Rectangle {
        id: track
        objectName: "appSwitch.track"
        // ``.tg`` in the reference: 40x22 with a 16 px knob at a 3 px inset.
        width: 40
        height: 22
        radius: 11
        anchors.verticalCenter: parent.verticalCenter
        color: root.checked ? Theme.accent : Theme.borderStrong
        Behavior on color { ColorAnimation { duration: Theme.reducedMotion ? 0 : 140 } }

        Rectangle {
            width: 16
            height: 16
            radius: 8
            y: 3
            x: root.checked ? parent.width - width - 3 : 3
            // The knob takes the ink token of whatever sits under it: accent in
            // dark theme is light, so a white knob would vanish into it — and
            // the reference's fixed white would vanish into a dark *off* track.
            color: root.checked ? Theme.statusOnFill : Theme.text
            Behavior on x { NumberAnimation { duration: Theme.reducedMotion ? 0 : 140 } }
        }
    }

    Label {
        id: label
        anchors.left: track.right
        anchors.leftMargin: 9
        anchors.verticalCenter: parent.verticalCenter
        visible: root.text !== ""
        text: root.text
        color: Theme.textDim
        font.pixelSize: Theme.fontBody
    }

    Rectangle {
        id: focusRing
        objectName: "appSwitch.ring"
        anchors.fill: track
        anchors.margins: -3
        // The ring is the track's radius plus its 3 px offset; hard-coding 12
        // here is how it drifts the first time the switch grows.
        radius: track.radius + 3
        color: "transparent"
        border.width: 2
        border.color: Theme.accentLine
        visible: root.activeFocus
    }

    MouseArea {
        id: switchMouse
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root._toggle()
    }

    Keys.onSpacePressed: root._toggle()
    Keys.onReturnPressed: root._toggle()

    Accessible.role: Accessible.CheckBox
    Accessible.name: root.accessibleName
    Accessible.checked: root.checked
    Accessible.focusable: true
}
