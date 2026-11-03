import QtQuick
import QtQuick.Controls
import ".."

// 16:9 preview of a video. The source is always a local ``file:///`` URL:
// the inspection worker caches the thumbnail first (see app/thumbnail.py),
// because the frozen build ships no QtNetwork/TLS QML plugin.
//
// The aspect ratio is enforced by this item, not by the image, so the layout
// never jumps between empty → loading → ready.
Rectangle {
    id: root

    property url source: ""
    property int duration: 0
    // `.lib .thumb` swaps its glyph by kind: a frame and play triangle for the
    // video, a folded page for the subtitle.
    property bool isVideo: true
    // ``.thumb svg{26px}`` and ``.lib .thumb svg{16px}``: the reference names the
    // two sizes instead of scaling one, so a 64px slot keeps a readable glyph.
    property int glyphSize: 26

    readonly property bool hasImage: preview.status === Image.Ready
    // Before the layout assigns a width, fall back to the designed 224 px.
    readonly property bool canResize: width > 0

    implicitWidth: 224
    implicitHeight: Math.round((canResize ? width : implicitWidth) * 9 / 16)

    // `.thumb{border-radius:8px}`; a list slot tightens it to 5px at the call
    // site, exactly as `.lib .thumb` does.
    radius: Theme.radiusSm
    clip: true
    // ``.thumb{background:linear-gradient(135deg,var(--s3),var(--inset))}``: the
    // recessed end of the ramp, so an empty preview reads as a hole in the card.
    // A thumbnail that lands paints straight over it.
    //
    // ``Rectangle.gradient`` only runs Horizontal or Vertical (Qt 6.12 has no
    // diagonal orientation, and assigning one fails silently), so the ramp goes
    // along the axis a 16:9 box actually spends its width on: the 135° line's
    // larger component.
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0.0; color: Theme.surfaceRaised }
        GradientStop { position: 1.0; color: Theme.inset }
    }

    Accessible.role: Accessible.Graphic
    Accessible.name: root.duration > 0
        ? qsTr("Video thumbnail, %1").arg(Theme.formatClock(root.duration))
        : qsTr("Video thumbnail")

    Image {
        id: preview
        objectName: "mediaThumb.image"
        anchors.fill: parent
        source: root.source
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true
        visible: status === Image.Ready
    }

    Icon {
        objectName: "mediaThumb.placeholder"
        anchors.centerIn: parent
        visible: !root.hasImage
        name: root.isVideo ? "video" : "file"
        color: Theme.textMuted
        width: root.glyphSize
        height: root.glyphSize
        strokeWidth: 1.6
    }

    // The pill uses the theme's own surface and ink so it stays legible over
    // both a white and a dark thumbnail.
    Rectangle {
        id: pill
        objectName: "mediaThumb.durationPill"
        // Library slots are 64 px wide; a clock there would cover the image.
        visible: root.duration > 0 && root.width >= 120
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 6
        width: pillLabel.implicitWidth + 12
        height: pillLabel.implicitHeight + 6
        radius: Theme.radiusXs
        color: Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.85)

        Label {
            id: pillLabel
            objectName: "mediaThumb.durationLabel"
            anchors.centerIn: parent
            text: Theme.formatClock(root.duration)
            color: Theme.text
            font.family: Theme.monoFont
            font.pixelSize: Theme.fontTiny
            font.weight: Font.DemiBold
        }
    }
}
