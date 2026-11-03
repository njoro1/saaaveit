import QtQuick
import ".."

// Placeholder geometry for content that is still loading.
//
// ``.sk`` is a *sliding* gradient, not a blink: `linear-gradient(90deg,s2,s3,s2)`
// at ``background-size:200%`` walked left one full cycle every 1100 ms. A block
// twice the bar's width, moved the same distance, is the same picture without a
// shader, and the bar is purely decorative: callers put the accessible
// description on their container.
Rectangle {
    id: root

    implicitHeight: Theme.fontBody
    radius: Theme.radiusXs
    color: Theme.surfaceAlt
    clip: true

    Rectangle {
        id: sweep
        // Parked off the left edge: with reduced motion the bar is simply the
        // flat `s2` track, never a half-lit gradient.
        x: -width
        y: 0
        width: root.width * 2
        height: root.height
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Theme.surfaceAlt }
            GradientStop { position: 0.5; color: Theme.surfaceRaised }
            GradientStop { position: 1.0; color: Theme.surfaceAlt }
        }

        SequentialAnimation on x {
            running: !Theme.reducedMotion && root.width > 0
            loops: Animation.Infinite
            NumberAnimation {
                from: -sweep.width
                to: 0
                duration: 1100
                easing.type: Easing.Linear
            }
        }
    }
}
