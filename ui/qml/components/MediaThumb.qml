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

    readonly property bool hasImage: preview.status === Image.Ready
    // Before the layout assigns a width, fall back to the designed 224 px.
    readonly property bool canResize: width > 0

    implicitWidth: 224
    implicitHeight: Math.round((canResize ? width : implicitWidth) * 9 / 16)

    radius: Theme.radiusMd
    // Cached thumbnails carry transparent, pre-rounded corners, so the card
    // surface must show through them instead of the inset colour.
    color: root.hasImage ? "transparent" : Theme.inset
    clip: true

    Accessible.role: Accessible.Graphic
    Accessible.name: root.duration > 0
        ? qsTr("Video thumbnail, %1").arg(Theme.formatClock(root.duration))
        : qsTr("Video thumbnail")

    Rectangle {
        objectName: "mediaThumb.placeholder"
        anchors.fill: parent
        visible: !root.hasImage
        radius: root.radius
        color: Theme.surfaceRaised

        Icon {
            anchors.centerIn: parent
            name: "film"
            color: Theme.textMuted
            width: 28
            height: 28
            opacity: 0.9
        }
    }

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

    // The pill uses the theme's own surface and ink so it stays legible over
    // both a white and a dark thumbnail.
    Rectangle {
        id: pill
        objectName: "mediaThumb.durationPill"
        visible: root.duration > 0
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
