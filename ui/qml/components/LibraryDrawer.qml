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
    implicitHeight: column.implicitHeight + 2 * Theme.lg

    radius: Theme.cardRadius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: column
        x: Theme.lg
        y: Theme.lg
        width: Math.max(0, root.width - 2 * Theme.lg)
        spacing: Theme.sm

        MediaThumb {
            objectName: "library.drawerThumb"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(width * 9 / 16)
            // `.drw .thumb{margin-bottom:12px}` — the column's own 8px plus 4.
            Layout.bottomMargin: 4
            visible: root.entry !== null
            source: root.entry && root.entry.thumbnail ? root.entry.thumbnail : ""
            duration: root.entry && root.entry.duration ? root.entry.duration : 0
            isVideo: !root.entry || root.entry.kind !== "subtitle"
        }

        Label {
            objectName: "library.drawerName"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: root.entry !== null
            text: root.entry ? root.entry.name : ""
            color: Theme.text
            // `.drw h3.mono` is 13px at weight 500 and breaks anywhere, so a
            // long filename wraps instead of deciding the drawer's width.
            font.pixelSize: Theme.fontSmall
            font.weight: Font.Medium
            font.family: Theme.monoFont
            wrapMode: Text.WrapAnywhere
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
            mono: true
        }
        KeyValue {
            Layout.fillWidth: true
            visible: root.entry !== null
            key: "Saved"
            value: root.entry ? root.entry.when : ""
            valueName: "library.drawerWhen"
            mono: true
        }

        // `.row.w` — a wrapping row of natural-width buttons, left-aligned, not
        // a stack of full-width bars. The drawer is 320 px, so five small buttons
        // flow onto two or three lines and each keeps its own weight.
        Flow {
            Layout.fillWidth: true
            Layout.topMargin: 14 - Theme.sm
            // ``.row{gap:8px}``, wrapped and left-aligned by ``.row.w``.
            spacing: 8
            visible: root.entry !== null

            AppButton {
                objectName: "library.drawerOpen"
                text: "Open"
                variant: "primary"
                small: true
                enabled: root.entry !== null && root.entry.exists
                onClicked: if (root.entry) appBridge.launchFile(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerFolder"
                text: "Show in folder"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.openDownloadedFolder(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerCopy"
                text: "Copy path"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.copyDownloadPath(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerRedownload"
                text: "Redownload"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.redownload(root.entry.index)
            }

            AppButton {
                objectName: "library.drawerRemove"
                text: "Remove from list"
                variant: "danger"
                small: true
                enabled: root.entry !== null
                onClicked: if (root.entry) appBridge.removeHistory(root.entry.index)
            }
        }

        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            visible: root.entry !== null
            text: "Removing only clears this entry. The file stays on disk."
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
            wrapMode: Text.WordWrap
        }
    }
}
