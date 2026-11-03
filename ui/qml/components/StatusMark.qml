import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The app's single status vocabulary (UI review 2.1).
//
// Shape leads, colour assists: every status carries a glyph AND a word, so it
// survives greyscale and colour-blindness. Adopting the model-table STATE
// column as the universal language is deliberate — it was the only consistent
// status system in the app, so it is the one that gets exported everywhere
// instead of each screen inventing its own.
//
// Five facts, five distinct treatments:
//
//   ok        check    success   "Verified", "Ready"
//   todo      alert    warning   "Missing", "Not created"
//   error     x        error     "Failed", "Run blocked"
//   na        minus in a muted ring   "n/a — not used in Saaave mode"
//   unchecked open ring, no glyph     "Not checked"
//
// `na` and `unchecked` MUST look different. They are different facts: `na`
// means "this mode never uses it", `unchecked` means "not evaluated yet".
// Collapsing them into one grey dash is what made the readiness score's
// denominator disagree with the visible rows.
//
// Usage:
//     StatusMark { status: "todo"; text: "Missing" }
Item {
    id: root

    property string status: "ok"
    property string text: ""

    // `.m` is one size: an 18px disc with an 11px mark knocked out of it.
    readonly property int glyph: 12
    readonly property int ring: Theme.statusMarkSize
    readonly property string iconName: {
        if (status === "ok") return "check"
        if (status === "todo") return "alert"
        if (status === "error") return "x"
        if (status === "na") return "minus"
        return ""          // unchecked: an open ring, no glyph inside
    }
    readonly property color tone: {
        if (status === "ok") return Theme.success
        if (status === "todo") return Theme.warning
        if (status === "error") return Theme.error
        return Theme.textMuted          // na + unchecked share the muted hue,
                                        // but not the shape
    }
    // Reference `.m`: a decided state is a solid disc with the glyph knocked out
    // of it. Only the two "no verdict" shapes are outlines.
    readonly property bool filled: status === "ok" || status === "todo"
                                   || status === "error"

    implicitWidth: row.implicitWidth
    implicitHeight: Math.max(root.ring, label.implicitHeight)

    RowLayout {
        id: row
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        // `.leg{gap:8px}` between the mark and its word.
        spacing: Theme.sm

        // The ring: filled for a decided state, an open outline for
        // `unchecked`, a closed muted outline for `na`, so "we don't know yet"
        // reads differently from "not applicable" at a glance. The geometry
        // comes from `Theme.statusRing*` so no page can invent a third grey.
        Rectangle {
            Layout.preferredWidth: root.ring
            Layout.preferredHeight: root.ring
            Layout.alignment: Qt.AlignVCenter
            radius: root.ring / 2
            color: root.filled ? root.tone : "transparent"
            border.width: Theme.statusRingWidth(root.status)
            border.color: Theme.statusRing(root.status)

            Icon {
                anchors.centerIn: parent
                visible: root.iconName !== ""
                name: root.iconName
                // Both the fill and the ink come from the status system, so the
                // glyph is legible on all four discs in both themes.
                color: root.filled ? Theme.statusOnFill : root.tone
                strokeWidth: 2.4
                width: root.glyph
                height: root.glyph
            }
        }

        Label {
            id: label
            visible: root.text !== ""
            text: root.text
            // `.leg` carries its word in the reading colour at normal weight:
            // the mark is the only thing that states the verdict, so the word
            // beside it must not repeat the emphasis.
            color: root.status === "na" || root.status === "unchecked"
                   ? Theme.textMuted : Theme.text
            font.pixelSize: root.small ? Theme.fontTiny : Theme.fontSmall
            verticalAlignment: Text.AlignVCenter
        }
    }

    Accessible.role: Accessible.StaticText
    Accessible.name: {
        const word = status === "ok" ? "ready"
                   : status === "todo" ? "needs attention"
                   : status === "error" ? "failed"
                   : status === "na" ? "not applicable"
                   : "not checked"
        return root.text !== "" ? root.text + ": " + word : word
    }
}
