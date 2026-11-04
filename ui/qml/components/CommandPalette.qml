import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Modal command palette (Ctrl K).
//
// Entries are rebuilt on every open so the list always matches what the app can
// actually do right now: a busy download offers "Cancel" and not "Download".
Item {
    id: root

    objectName: "commandPalette"

    visible: false
    z: 1000

    signal navigateRequested(int page)
    signal actionRequested(string action)

    property string query: ""
    property int activeIndex: 0
    property var entries: []
    readonly property var _overlayShadow: Theme.shadowFor(Theme.elevationOverlay)

    function entry(name, detail, shortcut, action, page) {
        return {
            name: name,
            detail: detail || "",
            shortcut: shortcut || "",
            action: action || "",
            page: page === undefined ? -1 : page
        }
    }

    // The one commit command means three things, and the bridge decides which,
    // so the palette can never offer a word the panel is not showing.
    function primaryCommand() {
        var kind = appBridge.primaryAction
        if (kind === "queue")
            return ["Add to queue", "Join the batch that is already running"]
        if (kind === "start")
            return ["Start queue", "Run the jobs that are waiting"]
        return ["Download", "Video and the selected subtitle"]
    }

    function rebuild() {
        var list = []
        list.push(entry("Go to Download", "Inspect a URL and download", appBridge.shortcutFor("goto_download"), "", 0))
        list.push(entry("Go to Library", "Files already downloaded", appBridge.shortcutFor("goto_library"), "", 1))
        list.push(entry("Go to Settings", "Appearance, output, shortcuts", appBridge.shortcutFor("goto_settings"), "", 2))

        // A job in flight no longer locks the form, so the commit commands stay
        // offered all the time; only Cancel is a thing that can be done now.
        var primary = primaryCommand()
        list.push(entry("Inspect formats", "Read the formats and subtitle tracks", appBridge.shortcutFor("inspect"), "inspect"))
        list.push(entry(primary[0], primary[1], appBridge.shortcutFor("download"), "download"))
        list.push(entry("Fetch subtitle only", "Download just the subtitle track", appBridge.shortcutFor("download_subtitle"), "download_subtitle"))
        if (appBridge.downloadRunning)
            list.push(entry("Cancel download", "Stop this job and start the next", appBridge.shortcutFor("cancel"), "cancel"))
        if (appBridge.pendingCount > 0)
            list.push(entry("Clear queue", "Drop every job that has not started", "", "clear_queue"))

        list.push(entry("Open download folder", appBridge.downloadDir, appBridge.shortcutFor("open_folder"), "open_folder"))
        list.push(entry("Open last downloaded file", "The newest row in the library", appBridge.shortcutFor("open_last"), "open_last"))
        list.push(entry("Toggle light / dark", "Appearance", "", "toggle_theme"))
        list.push(entry("Toggle comfortable spacing", "Appearance", "", "toggle_comfortable"))
        list.push(entry("Toggle reduced motion", "Appearance", "", "toggle_reduced_motion"))
        list.push(entry("View log", "Everything the app has reported", "", "view_log"))
        list.push(entry("Clear download history", "Library", "", "clear_history"))
        model.clear()
        for (var i = 0; i < list.length; i++)
            model.append(list[i])
        entries = list
        activeIndex = 0
    }

    function filtered() {
        var needle = query.trim().toLowerCase()
        var rows = []
        for (var i = 0; i < entries.length; i++) {
            var row = entries[i]
            var haystack = (row.name + " " + row.detail).toLowerCase()
            if (needle === "" || haystack.indexOf(needle) !== -1)
                rows.push({ index: i, name: row.name, detail: row.detail, shortcut: row.shortcut })
        }
        return rows
    }

    function activate(index) {
        if (index < 0 || index >= model.count)
            return
        var row = model.get(index)
        close()
        if (row.page >= 0)
            root.navigateRequested(row.page)
        else if (row.action !== "")
            root.actionRequested(row.action)
    }

    function open() {
        rebuild()
        query = ""
        activeIndex = 0
        visible = true
        searchField.forceActiveFocus()
    }

    function close() {
        visible = false
    }

    function toggle() {
        if (visible)
            close()
        else
            open()
    }

    ListModel { id: model }

    onVisibleChanged: if (visible) rebuild()

    Rectangle {
        anchors.fill: parent
        color: Theme.scrim

        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    // Level-3 elevation rings. Declared before the panel so they paint behind
    // its opaque surface.
    Rectangle {
        anchors.fill: panel
        anchors.margins: -4
        radius: Theme.dialogRadius + 4
        color: Theme.shadowColor
        opacity: root._overlayShadow.opacity * 0.5
    }

    Rectangle {
        anchors.fill: panel
        anchors.margins: -2
        radius: Theme.dialogRadius + 2
        color: Theme.shadowColor
        opacity: root._overlayShadow.opacity
    }

    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 90
        width: Math.min(640, parent.width - 80)
        height: column.implicitHeight
        radius: Theme.dialogRadius
        color: Theme.surface
        border.width: 1
        border.color: Theme.borderStrong

        ColumnLayout {
            id: column
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            spacing: 0

            // `.dlg .in` — the search row is flush with the dialog, 52px tall,
            // and separated from the list by a hairline rather than a box.
            CompactTextField {
                id: searchField
                objectName: "palette.search"
                Layout.fillWidth: true
                // A Layout lays the item out from its ``Layout.preferredHeight``:
                // a plain ``height`` binding here is silently overridden, and the
                // row collapsed to the field's own implicit height.
                Layout.preferredHeight: 52
                leftPadding: 16
                rightPadding: 16
                placeholderText: "Type a command…"
                label: "Command palette search"
                onTextChanged: {
                    root.query = text
                    root.activeIndex = 0
                }
                Keys.onDownPressed: root.activeIndex = Math.min(root.activeIndex + 1, list.count - 1)
                Keys.onUpPressed: root.activeIndex = Math.max(root.activeIndex - 1, 0)
                Keys.onReturnPressed: root.activate(revealed(root.activeIndex))
                Keys.onEnterPressed: root.activate(revealed(root.activeIndex))
                Keys.onEscapePressed: root.close()

                background: Rectangle {
                    color: "transparent"
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: searchField.activeFocus ? Theme.accentLine : Theme.border
                    }
                }

                function revealed(index) {
                    var rows = root.filtered()
                    return index < rows.length ? rows[index].index : -1
                }
            }

            ListView {
                id: list
                objectName: "palette.list"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(count * 40 + 12, 340)
                clip: true
                model: root.filtered()
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar { }

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index

                    width: list.width
                    height: 40
                    color: index === root.activeIndex ? Theme.accentSoft
                                                     : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 12

                        Label {
                            text: row.modelData.name
                            // The selected row is tinted, so the mark on it is
                            // weight, not colour: accent on accentSoft is a
                            // shape's contrast, not a word's.
                            color: Theme.text
                            font.pixelSize: Theme.fontBody
                            font.weight: index === root.activeIndex ? Font.DemiBold : Font.Normal
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                        }

                        Label {
                            visible: row.modelData.shortcut !== ""
                            text: row.modelData.shortcut
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontTiny
                            font.family: Theme.monoFont
                        }
                    }

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.activate(row.modelData.index)
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                Layout.bottomMargin: 12
                visible: root.filtered().length === 0
                text: "No command matches “" + root.query + "”."
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
            }
        }
    }
}
