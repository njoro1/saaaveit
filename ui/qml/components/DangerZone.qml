import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The reference's `.card.danger`: the destructive card keeps the same shape as
// every other card — a quiet heading and one row — and only its border and tint
// say "careful". `Clear stored settings` used to sit at equal visual weight, on
// the same row, beside the benign `Open debug.log` — a footgun next to a safe
// action. It is now spatially separated, styled as destructive, and gated behind
// a typed confirmation that names what will be erased.
Rectangle {
    id: root

    property string title: "Danger zone"
    // The row's own word, set beside the input — the reference puts the
    // description there and lets the placeholder carry the confirmation.
    property string rowLabel: ""
    property string description: ""
    property string actionLabel: "Clear stored settings"
    // The word the user must type. Deliberately a word they cannot type by
    // accident while clicking around.
    property string confirmWord: "RESET"

    signal confirmed()

    Layout.fillWidth: true
    implicitHeight: body.implicitHeight
    radius: Theme.cardRadius
    color: Theme.errorTint
    border.width: 1
    border.color: Theme.error

    readonly property bool armed: confirmField.text.trim().toUpperCase() === root.confirmWord

    ColumnLayout {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 0

        Label {
            visible: root.title !== ""
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.topMargin: 20
            Layout.bottomMargin: 4
            text: root.title
            color: Theme.text
            font.pixelSize: Theme.fontLabel
            font.weight: Font.DemiBold
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.topMargin: Theme.comfortable ? 18 : 14
            // The row's own padding plus the card's 6px of bottom padding
            // (`:root.cmf .set{padding:18px 0}`).
            Layout.bottomMargin: Theme.comfortable ? 24 : 20
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2

                Label {
                    visible: root.rowLabel !== ""
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: root.rowLabel
                    color: Theme.text
                    font.pixelSize: Theme.fontBody
                    wrapMode: Text.WordWrap
                }

                Label {
                    visible: root.description !== ""
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: root.description
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                    wrapMode: Text.WordWrap
                }
            }

            CompactTextField {
                id: confirmField
                Layout.preferredWidth: 120
                Layout.minimumWidth: 0
                fieldHeight: Theme.rowInputHeight
                placeholderText: "Type " + root.confirmWord
                label: "Type " + root.confirmWord + " to confirm"
                font.family: Theme.monoFont
                onAccepted: if (root.armed) root.fire()
            }

            AppButton {
                text: root.actionLabel
                // `#rbtn` is a plain `.btn d`, not a `.sm`: the one irreversible
                // action in the app gets the full-height control.
                variant: "danger"
                enabled: root.armed
                onClicked: root.fire()
                Accessible.name: root.actionLabel
            }
        }
    }

    function fire() {
        if (!root.armed)
            return
        root.confirmed()
        confirmField.text = ""
    }
}
