import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The single button used everywhere.
// variants: default | primary | danger | ghost | link
Button {
    id: root

    property string variant: "default"
    property bool small: false
    property string iconName: ""
    // `.btn svg{width:16px;height:16px}` — one size for every button, small
    // included, so an icon keeps its weight when the label shrinks.
    property int iconSize: 16
    // Hover text; primarily for icon-only buttons whose label is empty.
    property string tooltip: ""
    // A status-coloured label — the status bar's "2 errors". Only the four
    // status tones: "acc" would paint raw accent on a word, which is below AA
    // on any surface it could land on.
    property string tone: ""
    // ``[aria-pressed=true]`` on a ``.btn``: the accent tint, a `line` border
    // and a heavier word. The label stays `text` — accent on its own tint is a
    // shape's contrast ratio, not a word's.
    property bool selected: false
    // Reference buttons are flex boxes with ``justify-content: center``, so a
    // button that a Layout *stretches* still keeps its label in the middle
    // instead of hugging the left edge.
    property bool centered: false
    // A mono kicker after the label — the top bar's ``Search  Ctrl K``. It is
    // part of the button, not a sibling, so it scales and dims with it.
    property string trailingText: ""

    readonly property bool _primary: variant === "primary"
    readonly property bool _danger: variant === "danger"
    readonly property bool _ghost: variant === "ghost"
    readonly property bool _link: variant === "link"
    readonly property bool _bordered: !(_primary || _danger || _ghost || _link)

    readonly property color labelColor: {
        if (!enabled) return Theme.textMuted
        if (tone !== "") return Theme.toneColor(tone)
        if (_primary) return Theme.accentInk
        if (_danger) return Theme.error
        if (_link) return Theme.accent
        // `.btn g{color:var(--mu)}` and `.btn g:hover{color:var(--tx)}`.
        if (_ghost) return hovered ? Theme.text : Theme.textMuted
        return Theme.text
    }

    implicitHeight: small ? Theme.controlHeightSmall : Theme.controlHeight
    implicitWidth: Math.max(contentItem.implicitWidth + (small ? 20 : 28),
                            small ? Theme.controlHeightSmall : Theme.controlHeight)
    padding: 0
    opacity: enabled ? 1.0 : 0.45
    activeFocusOnTab: true

    // Press feedback is a transform, never a size change, so rows never shift.
    scale: pressed ? 0.98 : 1.0
    Behavior on scale {
        NumberAnimation {
            duration: Theme.reducedMotion ? 0 : 90
            easing.type: Easing.OutCubic
        }
    }

    Keys.onReturnPressed: if (root.enabled) root.clicked()
    Keys.onEnterPressed: if (root.enabled) root.clicked()

    background: Rectangle {
        radius: Theme.buttonRadius
        color: {
            if (root._primary) return root.hovered ? Theme.accentHover : Theme.accent
            // `.btn.d` is an outline, not a tint: transparent fill, status
            // border, status label. Hovering gives it the same fill a plain
            // button gets.
            if (root._danger) return root.hovered ? Theme.surfaceRaised : "transparent"
            if (root._ghost || root._link) return root.hovered ? Theme.surfaceAlt : "transparent"
            if (root.selected) return Theme.accentSoft
            return root.hovered ? Theme.surfaceRaised : Theme.surfaceAlt
        }
        // The keyboard focus ring is a 2 px accent border; it has to win over
        // the resting border so tabbing is always visible.
        border.width: root.activeFocus || root.selected ? 2 : (root._bordered || root._danger ? 1 : 0)
        border.color: root.activeFocus || root.selected ? Theme.accentLine
                      : root._danger ? Theme.error
                      : Theme.borderStrong
        Behavior on color { ColorAnimation { duration: Theme.reducedMotion ? 0 : 120 } }
    }

    contentItem: RowLayout {
        spacing: 8

        Item {
            visible: root.centered
            Layout.fillWidth: true
        }

        Icon {
            visible: root.iconName !== ""
            name: root.iconName
            color: root.labelColor
            strokeWidth: 1.8
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize
        }

        Label {
            text: root.text
            color: root.labelColor
            font.pixelSize: root.small ? Theme.fontSmall : Theme.fontBody
            // The reference sets buttons at 500, its primary at 600, its
            // pressed ones at 700, and the status bar's counts at 600.
            font.weight: root.selected ? Font.Bold
                     : (root._primary || root.tone !== "" ? Font.DemiBold : Font.Medium)
            verticalAlignment: Text.AlignVCenter
        }

        Label {
            visible: root.trailingText !== ""
            text: root.trailingText
            color: root.labelColor
            font.pixelSize: Theme.fontTiny
            font.family: Theme.monoFont
            verticalAlignment: Text.AlignVCenter
        }

        Item {
            visible: root.centered
            Layout.fillWidth: true
        }
    }

    AppToolTip {
        text: root.tooltip
        hovered: root.hovered && root.tooltip !== ""
        showDelay: 400
    }

    Accessible.role: Accessible.Button
    Accessible.name: root.text
}
