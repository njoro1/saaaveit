import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// One settings row: a fixed-width key on the left, the control on the right.
//
//   SettingsRow {
//       label: "Batch size"
//       CompactTextField { Layout.preferredWidth: 90 }
//   }
RowLayout {
    id: root

    property string label: ""
    property string hint: ""

    default property alias content: slot.data

    Layout.fillWidth: true
    spacing: 12

    Label {
        text: root.label
        Layout.preferredWidth: 186
        color: Theme.textDim
        font.pixelSize: Theme.fontBody
        elide: Text.ElideRight
        wrapMode: Text.WordWrap
        maximumLineCount: 2
    }

    RowLayout {
        id: slot
        Layout.fillWidth: true
        spacing: 8
    }

    HoverHandler { id: hintHover }

    AppToolTip {
        text: root.hint
        hovered: root.hint !== "" && hintHover.hovered
        showDelay: 500
    }
}
