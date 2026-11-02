import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The reference's ``.drw``: the one file the list points at, opened beside it.
//
// The row keeps its identity (thumb, name) and gains the facts the 6-column
// grid had to abbreviate - what kind it is, what was used to fetch it, when it
// landed - plus every action the row menu and inline buttons used to split
// between. It is a sibling of the list, not a row overlay: clicking a row
// selects, and the drawer *follows the selection*.
Rectangle {
    id: root

    objectName: "library.drawer"
    visible: entry !== null

    property var entry: null

    implicitWidth: Theme.drawerWidth
    implicitHeight: column.implicitHeight + 2 * Theme.md

    radius: Theme.cardRadius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: column
        x: Theme.md
        y: Theme.md
        width: Math.max(0, root.width - 2 * Theme.md)
        spacing: Theme.sm

        MediaThumb {
            objectName: "library.drawerThumb"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(width * 9 / 16)
            visible: root.entry !== null
            source: root.entry && root.entry.thumbnail ? root.entry.thumbnail : ""
            duration: root.entry && root.entry.duration ? root.entry.duration : 0
        }

        Label {
            objectName: "library.drawerName"
            Layout.fillWidth: true
            visible: root.entry !== null
            text: root.entry ? root.entry.name : ""
            color: Theme.text
            font.pixelSize: Theme.fontBody
            font.weight: Font.DemiBold
            font.family: Theme.monoFont
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }

        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: root.entry !== null && root.entry.exists === false
            text: "Missing from disk — the entry stays so you can remove it."
            color: Theme.warning
            font.pixelSize: Theme.fontSmall
            wrapMode: Text.WordWrap
        }

        KeyValue {
            Layout.fillWidth: true
            visible: root.entry !== null
            key: "Kind"
            value: root.entry ? root.entry.kindLabel : ""
            valueName: "library.drawerKind"
        }
        KeyValue {
            Layout.fillWidth: true
            visible: root.entry !== null
            key: "Used"
            value: root.entry && root.entry.detail ? root.entry.detail : "—"
            valueName: "library.drawerUsed"
        }
        KeyValue {
            Layout.fillWidth: true
            visible: root.entry !== null
            key: "Size"
            value: root.entry ? root.entry.sizeText : ""
            valueName: "library.drawerSize"
        }
        KeyValue {
            Layout.fillWidth: true
            visible: root.entry !== null
            key: "Saved"
            value: root.entry ? root.entry.when : ""
            valueName: "library.drawerWhen"
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.topMargin: Theme.xs
            spacing: Theme.xs

            AppButton {
                objectName: "library.drawerOpen"
                Layout.fillWidth: true
                centered: true
                text: "Open file"
                variant: "primary"
                small: true
                enabled: root.entry !== null && root.entry.exists
                onClicked: if (root.entry) appBridge.launchFile(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerFolder"
                Layout.fillWidth: true
                centered: true
                text: "Show in folder"
                small: true
                enabled: root.entry !== null && root.entry.exists
                onClicked: if (root.entry) appBridge.openDownloadedFolder(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerCopy"
                Layout.fillWidth: true
                centered: true
                text: "Copy path"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.copyDownloadPath(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerRedownload"
                Layout.fillWidth: true
                centered: true
                text: "Redownload"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.redownload(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerRemove"
                Layout.fillWidth: true
                centered: true
                text: "Remove from list"
                variant: "danger"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.removeHistory(root.entry.index)
            }
        }

        Label {
            Layout.fillWidth: true
            Layout.topMargin: Theme.xs
            visible: root.entry !== null
            text: "Removing edits the list only. The file stays on disk."
            color: Theme.textMuted
            font.pixelSize: Theme.fontTiny
            wrapMode: Text.WordWrap
        }
    }
}
