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

    implicitWidth: track.implicitWidth + 6
    implicitHeight: Theme.controlHeight
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
        radius: Theme.radiusSm
        color: Theme.inset
        border.color: root.activeFocus ? Theme.accentLine : Theme.border
        border.width: root.activeFocus ? 2 : 1
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
                implicitWidth: segLabel.implicitWidth + 24
                radius: Theme.radiusXs
                opacity: seg.isOff ? 0.45 : 1.0
                color: seg.isOn ? Theme.accent
                                : (segHover.hovered && !seg.isOff
                                   ? Theme.surfaceAlt : "transparent")

                Label {
                    id: segLabel
                    anchors.centerIn: parent
                    text: seg.modelData.label
                    color: seg.isOn ? Theme.accentInk
                         : seg.isOff ? Theme.textMuted : Theme.textDim
                    font.pixelSize: Theme.fontSmall
                    font.bold: seg.isOn
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
