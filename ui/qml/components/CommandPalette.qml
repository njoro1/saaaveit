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

    function rebuild() {
        var list = []
        list.push(entry("Go to Download", "Inspect a URL and download", appBridge.shortcutFor("goto_download"), "", 0))
        list.push(entry("Go to Library", "Files already downloaded", appBridge.shortcutFor("goto_library"), "", 1))
        list.push(entry("Go to Settings", "Appearance, output, shortcuts", appBridge.shortcutFor("goto_settings"), "", 2))

        if (appBridge.downloadRunning) {
            list.push(entry("Cancel download", "Stop the running download", appBridge.shortcutFor("cancel"), "cancel"))
        } else {
            list.push(entry("Inspect formats", "Read the formats and subtitle tracks", appBridge.shortcutFor("inspect"), "inspect"))
            list.push(entry("Download", "Video and the selected subtitle", appBridge.shortcutFor("download"), "download"))
            list.push(entry("Fetch subtitle only", "Download just the subtitle track", appBridge.shortcutFor("download_subtitle"), "download_subtitle"))
        }
        list.push(entry("Open download folder", appBridge.downloadDir, appBridge.shortcutFor("open_folder"), "open_folder"))
        list.push(entry("Toggle light / dark", "Appearance", "", "toggle_theme"))
        list.push(entry("Toggle comfortable spacing", "Appearance", "", "toggle_comfortable"))
        list.push(entry("Toggle reduced motion", "Appearance", "", "toggle_reduced_motion"))
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
        radius: Theme.radiusLg + 4
        color: Theme.shadowColor
        opacity: root._overlayShadow.opacity * 0.5
    }

    Rectangle {
        anchors.fill: panel
        anchors.margins: -2
        radius: Theme.radiusLg + 2
        color: Theme.shadowColor
        opacity: root._overlayShadow.opacity
    }

    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 90
        width: Math.min(640, parent.width - 80)
        height: Math.min(460, parent.height - 140)
        radius: Theme.radiusLg
        color: Theme.surface
        border.width: 1
        border.color: Theme.borderStrong

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            CompactTextField {
                id: searchField
                objectName: "palette.search"
                Layout.fillWidth: true
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

                function revealed(index) {
                    var rows = root.filtered()
                    return index < rows.length ? rows[index].index : -1
                }
            }

            ListView {
                id: list
                objectName: "palette.list"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                model: root.filtered()
                ScrollBar.vertical: AppScrollBar { }

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index

                    width: list.width
                    height: 46
                    radius: Theme.radiusSm
                    color: index === root.activeIndex ? Theme.accentSoft
                                                     : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")

                    ColumnLayout {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 1

                        Label {
                            text: row.modelData.name
                            color: index === root.activeIndex ? Theme.accent : Theme.text
                            font.pixelSize: Theme.fontBody
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }

                        Label {
                            text: row.modelData.detail
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontTiny
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                        }
                    }

                    Label {
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: row.modelData.shortcut
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontTiny
                        font.family: Theme.monoFont
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
                visible: root.filtered().length === 0
                text: "No command matches “" + root.query + "”."
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
            }
        }
    }
}
