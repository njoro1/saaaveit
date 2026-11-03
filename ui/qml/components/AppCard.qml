import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Card with an optional header (15px/600 title + right-hand chips) and a
// default content slot.
//
//   AppCard {
//       title: "Video"; note: "How the app renders offline"
//       headerExtra: [ Chip { text: "Saaave"; tone: "acc" } ]
//       ColumnLayout { ... }        // <- default content
//   }
Rectangle {
    id: root

    default property alias content: body.data
    property alias headerExtra: headerExtraRow.data

    property string title: ""
    property string note: ""
    // The reference's `.card` insets its content 6px vertically and 18px
    // horizontally: the rows themselves supply the air between them, so the
    // card only supplies the frame. A card of loose widgets (the summary panel)
    // overrides both.
    property int paddingV: 6
    property int paddingH: 18
    // The reference card stacks its rows with no extra gap - each row brings
    // its own 14px of air and a hairline - while a card of loose widgets
    // (the summary panel aside) keeps the 10px rhythm.
    property int bodySpacing: 10

    // `.card` carries no shadow at all — its fill and a `b1` hairline separate
    // it from the page. Only `.panel` (the sticky summary) casts one, so a card
    // asks for elevation rather than assuming it.
    property int elevation: Theme.elevationNone

    // The root only reserves the layout cell; the surface and its shadow are
    // siblings so the shadow can sit behind the surface. Level-1 only (T2.1):
    // two stacked rings instead of MultiEffect, so the frozen build needs no
    // extra QML module and scrolling pays no shader cost.
    color: "transparent"
    implicitHeight: outer.implicitHeight

    readonly property var _shadow: Theme.shadowFor(root.elevation)

    Rectangle {
        visible: root.elevation > Theme.elevationNone
        anchors.fill: surface
        anchors.margins: -2
        radius: Theme.cardRadius + 2
        color: Theme.shadowColor
        opacity: root._shadow.opacity * 0.5
    }

    Rectangle {
        visible: root.elevation > Theme.elevationNone
        anchors.fill: surface
        anchors.margins: -1
        radius: Theme.cardRadius + 1
        color: Theme.shadowColor
        opacity: root._shadow.opacity * 0.9
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: Theme.cardRadius
        color: Theme.surface
        // `.card{border:1px solid var(--b1)}` is the whole separation: the page
        // is one step darker than the card.
        border.width: 1
        border.color: Theme.border
    }

    ColumnLayout {
        id: outer
        anchors.fill: parent
        spacing: 0

        // --- Header ---------------------------------------------------------
        Item {
            id: header
            visible: root.title !== ""
            Layout.fillWidth: true
            // ``.card{padding:6px 18px}`` is spent *before* the heading, so the
            // title sits 6+14=20px below the top border.
            Layout.topMargin: root.paddingV
            Layout.preferredHeight: headerRow.implicitHeight + 18

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: root.paddingH
                anchors.rightMargin: root.paddingH
                anchors.topMargin: 14
                anchors.bottomMargin: 4
                spacing: 9

                Label {
                    text: root.title
                    color: Theme.text
                    font.pixelSize: Theme.fontLabel
                    font.weight: Font.DemiBold
                }

                Label {
                    id: noteLabel
                    visible: root.note !== ""
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: root.note
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                    elide: Text.ElideRight

                    // The note is the card's only free-text slot, so it is the
                    // one thing here that can overflow. Elide, but keep the
                    // whole string on hover (UI review D4).
                    HoverHandler { id: noteHover }
                }

                Item {
                    visible: root.note === ""
                    Layout.fillWidth: true
                }

                RowLayout {
                    id: headerExtraRow
                    spacing: 6
                }
            }
        }

        // --- Body -----------------------------------------------------------
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: root.paddingH
            Layout.rightMargin: root.paddingH
            // A titled card has already spent the frame's vertical padding above
            // the heading: ``.card>h2{padding:14px 0 4px}`` is the only air before
            // the first row, which brings its own 14px.
            Layout.topMargin: root.title === "" ? root.paddingV : 0
            Layout.bottomMargin: root.paddingV
            spacing: root.bodySpacing
        }
    }

    AppToolTip {
        text: root.note
        hovered: noteHover.hovered && noteLabel.truncated
        showDelay: 400
    }
}
