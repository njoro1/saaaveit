import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Segmented control (the mockup's `.seg`): a row of mutually exclusive options
// inside one inset track.
//
//   SegmentedControl {
//       options: [{ id: "dark", label: "Dark" }, { id: "light", label: "Light" }]
//       current: appBridge.themeName
//       onActivated: (id) => appBridge.themeName = id
//   }
Item {
    id: root

    property var options: []
    property string current: ""

    // Option ids that cannot be picked right now. A disabled segment stays
    // visible (the option exists) but is muted and inert, so an impossible
    // combination reads as "not available", never as "clicked and nothing
    // happened". Callers pair this with a visible reason (see
    // `engineLocalDisabledReason` on the Run screen).
    property var disabledIds: []

    signal activated(string id)

    function isDisabled(id) {
        return root.disabledIds.indexOf(id) !== -1
    }

    // `.seg button{padding:5px 14px}` inside `.seg{padding:3px}`: one line box,
    // 10px of button padding and 6px of track. It grows with the type scale the
    // same way the reference's does.
    readonly property int _lineHeight: Math.round(Theme.fontBody * 1.45)
    implicitWidth: track.implicitWidth + 6
    implicitHeight: _lineHeight + 16
    activeFocusOnTab: true

    function _step(delta) {
        if (!root.options || root.options.length === 0)
            return
        var index = -1
        for (var i = 0; i < root.options.length; i++) {
            if (root.options[i].id === root.current) {
                index = i
                break
            }
        }
        if (index < 0)
            index = delta > 0 ? -1 : 0
        for (var step = 0; step < root.options.length; step++) {
            index = (index + delta + root.options.length) % root.options.length
            if (!root.isDisabled(root.options[index].id)) {
                root.activated(root.options[index].id)
                return
            }
        }
    }

    Keys.onLeftPressed: root._step(-1)
    Keys.onRightPressed: root._step(1)

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusMd
        // `.seg` is an inset track with no border of its own; only the keyboard
        // ring says where the control is.
        color: Theme.inset
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: Theme.radiusMd + 3
        color: "transparent"
        border.width: 2
        border.color: Theme.accentLine
        visible: root.activeFocus
    }

    RowLayout {
        id: track
        anchors.fill: parent
        anchors.margins: 3
        spacing: 3

        Repeater {
            model: root.options

            delegate: Rectangle {
                id: seg
                required property var modelData

                readonly property bool isOn: root.current === modelData.id
                readonly property bool isOff: root.isDisabled(modelData.id)

                Layout.fillHeight: true
                // `.seg button{padding:5px 14px;border-radius:8px}`
                implicitWidth: segLabel.implicitWidth + 28
                radius: Theme.radiusSm
                opacity: seg.isOff ? 0.45 : 1.0
                // The reference's pressed segment is *not* the accent: a raised
                // surface and a heavier word. The accent stays reserved for
                // shapes the eye tracks over time.
                color: seg.isOn ? Theme.surfaceRaised
                                : (segHover.hovered && !seg.isOff
                                   ? Theme.surfaceAlt : "transparent")
                // The reference's pressed segment is the fill alone: no outline,
                // no accent. Adding a border here made two things claim "on".

                Label {
                    id: segLabel
                    anchors.centerIn: parent
                    text: seg.modelData.label
                    // `.seg button` is `--mu` and only the pressed one steps up to
                    // `--tx`; a disabled segment is the same word at the row's
                    // reduced opacity.
                    color: seg.isOn ? Theme.text : Theme.textMuted
                    font.pixelSize: Theme.fontBody
                    font.weight: seg.isOn ? Font.DemiBold : Font.Normal
                }

                HoverHandler { id: segHover }

                MouseArea {
                    anchors.fill: parent
                    // A disabled segment must not look clickable, so the cursor
                    // stays an arrow and the click is swallowed.
                    enabled: !seg.isOff
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activated(seg.modelData.id)
                }

                Accessible.role: Accessible.RadioButton
                Accessible.name: seg.modelData.label
                Accessible.checked: seg.isOn
                Accessible.onPressAction: {
                    if (!seg.isOff)
                        root.activated(seg.modelData.id)
                }
            }
        }
    }
}
