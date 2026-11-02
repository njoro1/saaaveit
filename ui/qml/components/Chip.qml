import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Small metadata chip. tone: "" | acc | ok | warn | err | info
//
// `clickable` turns a chip into a link (the cue inspector's quality flags, which
// deep-link into the Quality issue list). It is opt-in so the many decorative
// chips in the app cannot accidentally acquire a pointer cursor and a hit area.
Rectangle {
    id: root

    property string text: ""
    property string tone: ""
    property string iconName: ""
    property bool mono: false
    property bool clickable: false

    signal clicked()

    // A toned chip's background *is* the tone at 10-14%, so its label cannot
    // also be the plain tone: accent lands at 3.57:1 there. The other tones
    // were set against their own tint and clear AA; `acc` is the one that needs
    // the derived colour.
    readonly property color _fg: tone === "" ? Theme.textMuted
                             : (tone === "acc" ? Theme.accentOnTint
                                               : Theme.toneColor(tone))

    // Reference `.chip` is `padding: 1px 10px`.
    implicitWidth: row.implicitWidth + 20
    implicitHeight: 22
    // The reference's plain chip has nothing behind it and a `b2` hairline;
    // `.chip.a` - the pressed one - adds the accent tint and a `line` border.
    radius: Theme.radiusCircle
    color: root.clickable && chipHover.hovered
           ? Theme.surfaceAlt
           : (tone === "" ? "transparent" : Theme.toneTint(tone))
    border.width: root.clickable && root.activeFocus ? 2 : 1
    border.color: root.clickable && root.activeFocus ? Theme.accentLine
                 : tone === "" ? Theme.borderStrong
                 : Theme.toneBorder(tone)
    activeFocusOnTab: root.clickable

    Keys.onReturnPressed: if (root.clickable) root.clicked()
    Keys.onSpacePressed: if (root.clickable) root.clicked()

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 5

        Icon {
            visible: root.iconName !== ""
            name: root.iconName
            color: root._fg
            Layout.preferredWidth: 11
            Layout.preferredHeight: 11
        }

        Label {
            text: root.text
            color: root._fg
            font.pixelSize: Theme.fontTiny
            font.family: root.mono ? Theme.monoFont : Theme.uiFont
        }
    }

    HoverHandler { id: chipHover; enabled: root.clickable }

    MouseArea {
        anchors.fill: parent
        enabled: root.clickable
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Accessible.role: root.clickable ? Accessible.Link : Accessible.StaticText
}
