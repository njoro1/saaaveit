import QtQuick
import QtQuick.Window
import ".."

// The Saaaveit identity, from the C-cobalt pack in ``ui/branding``.
//
// Brand ink, not theme ink: the tile is always #2F6FEB with the glyph knocked
// out in white, so a user on the Amber swatch sees the same mark here as in the
// taskbar and in Explorer. Nothing in this file reads ``Theme.accent``.
//
//   variant "mark"   - the tile alone (96x96), for the rail and empty screens
//   variant "lockup" - tile + wordmark (572x152); the wordmark swaps between
//                      the light- and dark-background cuts, the only two
//                      variants the pack ships for in-app use
Item {
    id: root

    property string variant: "mark"
    // Height in px. The width follows the asset's own ratio, so callers size
    // one number and never fight an aspect distortion.
    property int size: 24

    readonly property real _ratio: variant === "lockup" ? 572 / 152 : 1
    readonly property string _asset: {
        if (variant === "lockup") {
            return Theme.isDark ? "../../branding/saaaveit-lockup-dark.svg"
                                : "../../branding/saaaveit-lockup-light.svg"
        }
        return "../../branding/saaaveit-mark.svg"
    }

    implicitWidth: Math.round(size * _ratio)
    implicitHeight: size

    // The mark is decoration beside the rail's navigation and the empty
    // screen's prompt, which both already speak the app's name; it must not
    // add a third stop for a screen-reader to walk.
    Accessible.ignored: true

    Image {
        anchors.fill: parent
        source: root._asset
        // Qt's SVG handler rasterises at ``sourceSize`` and leaves the item
        // alone above it. Left unset it renders the file's declared 512px and
        // downsamples that, which is soft on a HiDPI panel at these sizes.
        sourceSize: Qt.size(Math.round(width * Screen.devicePixelRatio),
                            Math.round(height * Screen.devicePixelRatio))
        fillMode: Image.PreserveAspectFit
        smooth: true
        asynchronous: true
    }
}
