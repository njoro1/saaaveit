import QtQuick
import ".."

// Placeholder geometry for content that is still loading. The 1200 ms pulse is
// disabled under reduced motion, and the bar is purely decorative: callers put
// the accessible description on their container.
Rectangle {
    id: root

    implicitHeight: Theme.fontBody
    radius: Theme.radiusXs
    color: Theme.surfaceRaised

    SequentialAnimation {
        id: pulse
        running: !Theme.reducedMotion
        loops: Animation.Infinite
        // Stopping the loop mid-cycle would leave the bar dimmed.
        onRunningChanged: if (!running) root.opacity = 1.0

        NumberAnimation {
            target: root
            property: "opacity"
            from: 1.0
            to: 0.55
            duration: 600
            easing.type: Easing.InOutQuad
        }
        NumberAnimation {
            target: root
            property: "opacity"
            from: 0.55
            to: 1.0
            duration: 600
            easing.type: Easing.InOutQuad
        }
    }
}
