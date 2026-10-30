import QtQuick
import QtQuick.Controls
import ".."

// The app's only scrollbar: a thin, track-less handle instead of the Basic
// style's grey trough. Attaching it as `ScrollBar.vertical` keeps the policy
// and the scroll mechanics; only the painting changes.
ScrollBar {
    id: root

    policy: ScrollBar.AsNeeded
    padding: 2

    // Qt re-evaluates AsNeeded visibility on some flickable signals but not
    // all: a list that is laid out while its page is hidden can end up stuck
    // visible at size 1.0. Re-apply the policy whenever the size changes.
    onSizeChanged: if (policy === ScrollBar.AsNeeded) visible = size < 1.0

    contentItem: Rectangle {
        implicitWidth: 8
        implicitHeight: 8
        // The handle has to stay visible in dark theme, where `surfaceRaised`
        // is *darker* than the resting `borderStrong`; hover/press therefore
        // move up the text ramp rather than to a surface token.
        radius: Math.min(root.width, root.height) / 2
        color: root.pressed ? Theme.textDim
             : root.hovered ? Theme.textMuted
             : Theme.borderStrong
        Behavior on color {
            ColorAnimation { duration: Theme.reducedMotion ? 0 : 90 }
        }
    }

    background: null
}
