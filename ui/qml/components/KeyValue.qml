import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// One ``.kv`` line of a sticky panel: a muted label, a right-aligned value that
// elides instead of pushing the row open, and a `b1` hairline on top.
//
// The row is the item; the value label is named by the caller (`valueName`) so a
// test can read the value without reaching through the row's children.
Rectangle {
    id: root

    property string key: ""
    property string value: ""
    property string valueName: ""
    property bool mono: false

    implicitHeight: row.implicitHeight + 16
    color: "transparent"

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.topMargin: 8
        anchors.bottomMargin: 8
        spacing: 12

        Label {
            text: root.key
            color: Theme.textMuted
            // `.kv span` is body text; only `:first-child` changes colour.
            font.pixelSize: Theme.fontBody
        }

        Label {
            objectName: root.valueName
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.value
            color: Theme.text
            // `.mono`/`.num` on the value span restyles it to 12.5px; an
            // unstyled value keeps the row's own 14px.
            font.pixelSize: root.mono ? Theme.fontTiny : Theme.fontBody
            font.family: root.mono ? Theme.monoFont : Theme.uiFont
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
        }
    }
}
