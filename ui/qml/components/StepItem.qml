import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// One numbered step of the download flow: a dot, a connector to the next step,
// a heading, and - as this component's content - the body.
//
//     StepItem {
//         number: 2; title: "Format"; state: appBridge.hasInfo ? "cur" : "lock"
//         FormatMatrix { }        // <- the body
//     }
//
// ``state`` is the reference's four classes: ``lock`` dims the whole step
// because the work is not reachable yet, ``cur`` fills the dot with the accent,
// ``done`` swaps the numeral for a tick, and an empty state is a step whose
// body is open but whose dot still carries its number.
Item {
    id: root

    default property alias content: body.data

    property int number: 1
    property string title: ""
    property string note: ""
    property string state: "lock"
    // The reference drops the connector on ``:last-child``; only the page knows
    // which step is last.
    property bool showConnector: true

    opacity: state === "lock" ? 0.5 : 1.0
    Behavior on opacity {
        NumberAnimation { duration: Theme.reducedMotion ? 0 : 160; easing.type: Easing.OutCubic }
    }

    implicitHeight: column.implicitHeight + Theme.stepGap

    Rectangle {
        id: dot
        // The dot is exactly the heading's line box, so the numeral always sits
        // level with the title however the title wraps.
        x: 0
        y: 0
        width: Theme.stepDotSize
        height: Theme.stepDotSize
        radius: Theme.stepDotSize / 2
        color: root.state === "done" ? Theme.success
             : (root.state === "cur" ? Theme.accent : Theme.surfaceAlt)
        border.width: 1
        border.color: root.state === "done" || root.state === "cur"
                      ? color : Theme.borderStrong

        Label {
            anchors.centerIn: parent
            text: root.state === "done" ? "✓" : String(root.number)
            // Both fills are solid colour, so both take the ink token that is
            // legible on them - never `text`, never the hue of the fill.
            color: root.state === "done" ? Theme.statusOnFill
                 : (root.state === "cur" ? Theme.accentInk : Theme.textMuted)
            font.pixelSize: Theme.fontSmall
            font.weight: Font.DemiBold
        }
    }

    Rectangle {
        visible: root.showConnector
        x: (dot.width - Theme.stepLineWidth) / 2
        y: dot.height + 2
        width: Theme.stepLineWidth
        height: Math.max(0, root.height - y - 2)
        color: Theme.border
    }

    ColumnLayout {
        id: column
        x: Theme.stepGutter
        width: Math.max(0, root.width - Theme.stepGutter)
        height: Math.max(0, root.implicitHeight - Theme.stepGap)
        // ``.body`` sits 10px under the heading; the body's own gaps are the
        // page's business.
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.stepDotSize
            spacing: Theme.sm

            Label {
                text: root.title
                color: Theme.text
                font.pixelSize: Theme.fontTitle
                font.weight: Font.DemiBold
            }

            Label {
                visible: root.note !== ""
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.note
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
                elide: Text.ElideRight
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: Theme.xs * 2
        }
    }

    Accessible.role: Accessible.Section
    Accessible.name: root.number + ". " + root.title
}
