import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Pre-run readiness checklist, rendered from ``appBridge.readinessRows``.
//
// The state machine lives in Python (testable, with real `na` and `unchecked`
// states) — this component is only a renderer. A row that can never fail
// teaches users to ignore the checklist, so nothing here is hardcoded green.
//
// Row status uses ``StatusMark`` so the five facts (ok / todo / na /
// unchecked / error) look different from each other. The previous version
// mapped both `n/a` and `unchecked` to a grey minus, and bolded the row label
// when the state was `ok` — bolding users read as "blocker" (UI review 2.1,
// 6.4). Both are gone.
//
// A row is laid out like a settings row: the mark beside the name, the state's
// own word under it, and a hairline between rows. Nothing here hovers or takes
// a click — it is a readout, not a control.
ColumnLayout {
    id: root

    spacing: 0

    readonly property var rows: appBridge.readinessRows

    Repeater {
        model: root.rows

        delegate: Item {
            id: row
            required property var modelData
            required property int index

            readonly property bool isNa: modelData.state === "na"
            readonly property bool isUnchecked: modelData.state === "unchecked"
            // Only real checks can be "not satisfied"; na/unchecked are facts.
            readonly property bool isBlocking: modelData.state === "todo"

            Layout.fillWidth: true
            implicitHeight: rowLayout.implicitHeight + _pad * 2

            readonly property int _pad: Theme.comfortable ? 18 : 14

            Rectangle {
                anchors.top: parent.top
                width: parent.width
                height: 1
                // A hairline above the first row would sit against the card
                // heading, which is what `.set:first-of-type` drops.
                visible: index > 0
                color: Theme.border
            }

            RowLayout {
                id: rowLayout
                anchors.fill: parent
                anchors.topMargin: row._pad
                anchors.bottomMargin: row._pad
                spacing: 10

                StatusMark {
                    Layout.alignment: Qt.AlignVCenter
                    status: row.modelData.state
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 2

                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: modelData.label
                        // No ad-hoc bolding: the StatusMark carries the state.
                        color: row.isNa || row.isUnchecked ? Theme.textMuted
                                                           : Theme.text
                        font.pixelSize: Theme.fontBody
                        wrapMode: Text.WordWrap
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        // The reference always states the finding ("Found", the
                        // folder path), not only the remedy, so a green row is
                        // not just a tick.
                        visible: modelData.detail !== ""
                        text: modelData.detail
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        font.family: modelData.id === "output" ? Theme.monoFont
                                                               : Theme.uiFont
                        elide: Text.ElideMiddle
                    }

                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: modelData.hint !== ""
                        text: modelData.hint
                        color: row.isBlocking ? Theme.warning : Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }
                }

                // The mode-dependency is spelled out rather than left as a bare
                // dash, so "n/a" always has a readable subject.
                Label {
                    visible: row.isNa
                    text: "n/a"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }
                Label {
                    visible: row.isUnchecked
                    text: "not checked"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }
            }

            Accessible.role: Accessible.StaticText
            Accessible.name: {
                var word = "needs attention"
                if (modelData.state === "ok") word = "ready"
                else if (modelData.state === "na") word = "not applicable"
                else if (modelData.state === "unchecked") word = "not checked yet"
                return modelData.label + ": " + word
            }
        }
    }
}
