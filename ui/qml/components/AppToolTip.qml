import QtQuick
import QtQuick.Controls
import ".."

// One styled tooltip for the whole app.
//
//     AppToolTip {
//         text: "Copy path"
//         hovered: someMouseArea.containsMouse
//     }
//
// Declare it inside the item it describes: it centres above that item. A plain
// `Popup` rather than a style override, so the frozen build needs no qml style
// directory and every caller gets the same surface.
Popup {
    id: root

    property string text: ""
    property int showDelay: 400
    // Drive this from a HoverHandler/MouseArea: the tooltip waits `showDelay`
    // and hides the moment the pointer leaves.
    property bool hovered: false

    readonly property var _shadow: Theme.shadowFor(Theme.elevationCard)

    padding: 8
    closePolicy: Popup.CloseOnEscape
    focus: false

    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? -height - 6 : 0

    // Level-1 elevation: a single ring, matching a card, not an overlay.
    background: Item {
        Rectangle {
            anchors.fill: card
            anchors.margins: -1
            radius: Theme.radiusSm + 1
            color: Theme.shadowColor
            opacity: root._shadow.opacity * 0.9
        }

        Rectangle {
            id: card
            anchors.fill: parent
            radius: Theme.radiusSm
            color: Theme.surfaceRaised
            border.width: 1
            border.color: Theme.borderStrong
        }
    }

    contentItem: Label {
        text: root.text
        color: Theme.text
        font.pixelSize: Theme.fontSmall
    }

    Timer {
        id: delayTimer
        interval: root.showDelay
        onTriggered: root.open()
    }

    Shortcut {
        sequences: [StandardKey.Cancel]
        enabled: root.visible
        onActivated: root.close()
    }

    onHoveredChanged: {
        if (hovered && text !== "") {
            delayTimer.restart()
        } else {
            delayTimer.stop()
            if (root.visible)
                root.close()
        }
    }

    onTextChanged: if (!hovered && root.visible) root.close()
}
