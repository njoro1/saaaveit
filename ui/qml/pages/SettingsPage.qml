import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."
import "../components"

// Appearance, where files go, the default subtitle choice, recordable keyboard
// shortcuts, readiness, environment, the CLI, and the one destructive action.
// Everything persists on its own — the Saved toast is the autosave saying it
// landed. Card order follows the reference.
Item {
    id: page

    objectName: "settingsPage"

    readonly property string windowTitle: "Settings"

    FolderDialog {
        id: folderPicker
        title: "Choose where downloads are saved"
        onAccepted: appBridge.setDownloadDir(selectedFolder)
    }

    // ------------------------------------------------------- saved toast
    // The bridge fires ``savedToast`` from its 400 ms autosave debounce; the
    // label shows for 1.6 s on the same beat the "Changes save automatically"
    // promise is kept.
    Timer {
        id: savedToastTimer
        interval: 1600
        onTriggered: savedToast.opacity = 0
    }

    Connections {
        target: appBridge
        function onSavedToast() {
            savedToast.opacity = 1
            savedToastTimer.restart()
        }
    }

    ColumnLayout {
        id: pageHeader
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.lg
        spacing: 2

        RowLayout {
            spacing: 10

            Label {
                objectName: "settings.pageTitle"
                text: "Settings"
                color: Theme.text
                font.pixelSize: Theme.fontH1
                font.bold: true
            }

            Label {
                id: savedToast
                objectName: "settings.savedToast"
                text: "Saved ✓"
                color: Theme.success
                font.pixelSize: Theme.fontSmall
                font.bold: true
                opacity: 0
                Behavior on opacity {
                    NumberAnimation { duration: Theme.reducedMotion ? 0 : 180 }
                }
            }

            Item { Layout.fillWidth: true }
        }

        Label {
            objectName: "settings.pageSubtitle"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: "Changes save automatically."
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideRight
        }
    }

    ScrollView {
        id: scroller
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: pageHeader.bottom
        anchors.bottom: parent.bottom
        anchors.margins: Theme.lg
        anchors.topMargin: Theme.md
        clip: true
        contentWidth: availableWidth
        ScrollBar.vertical: AppScrollBar { }

        ColumnLayout {
            x: Theme.xs
            width: scroller.availableWidth - Theme.xs * 2
            spacing: Theme.md

            // Room for the card shadow inside the clipped scroll area.
            Item { Layout.preferredHeight: Theme.xs }

            // ------------------------------------------------ APPEARANCE
            AppCard {
                Layout.fillWidth: true
                title: "Appearance"

                SettingsRow {
                    label: "Theme"
                    SegmentedControl {
                        objectName: "settings.theme"
                        options: [
                            { id: "dark", label: "Dark" },
                            { id: "light", label: "Light" }
                        ]
                        current: appBridge.themeName
                        onActivated: function (id) { appBridge.themeName = id }
                    }
                }

                SettingsRow {
                    label: "Accent"
                    RowLayout {
                        spacing: 8
                        Repeater {
                            model: appBridge.accentChoices
                            delegate: Rectangle {
                                required property var modelData

                                objectName: "settings.accent." + modelData.id
                                implicitWidth: 26
                                implicitHeight: 26
                                radius: 13
                                color: Theme.isDark ? modelData.dark : modelData.light
                                border.width: appBridge.accentName === modelData.id ? 3 : 0
                                border.color: Theme.text
                                activeFocusOnTab: true

                                Keys.onReturnPressed: appBridge.setAccent(modelData.id)
                                Keys.onSpacePressed: appBridge.setAccent(modelData.id)

                                // The selection ring is the swatch's own border,
                                // so focus needs somewhere else to live: a second
                                // ring outside it, in the accent line colour.
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -4
                                    radius: width / 2
                                    color: "transparent"
                                    border.width: parent.activeFocus ? 2 : 0
                                    border.color: Theme.accentLine
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: appBridge.setAccent(modelData.id)
                                }
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: modelData.label
                                Accessible.checked: appBridge.accentName === modelData.id
                            }
                        }
                    }
                }

                SettingsRow {
                    label: "Comfortable spacing"
                    hint: "Larger hit targets and slightly bigger text."
                    AppSwitch {
                        objectName: "settings.comfortable"
                        checked: appBridge.comfortable
                        onToggled: function (checked) { appBridge.setComfortable(checked) }
                    }
                }

                SettingsRow {
                    label: "Reduced motion"
                    hint: "Stops shimmer and sliding progress."
                    AppSwitch {
                        objectName: "settings.reducedMotion"
                        checked: appBridge.reducedMotion
                        onToggled: function (checked) { appBridge.setReducedMotion(checked) }
                    }
                }
            }

            // ------------------------------------------------- DOWNLOADS
            AppCard {
                Layout.fillWidth: true
                title: "Downloads"

                SettingsRow {
                    label: "Save to"
                    Label {
                        objectName: "settings.downloadDir"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: appBridge.downloadDir
                        color: Theme.text
                        font.pixelSize: Theme.fontSmall
                        font.family: Theme.monoFont
                        elide: Text.ElideMiddle
                    }
                    AppButton {
                        text: "Change…"
                        small: true
                        iconName: "folder"
                        onClicked: folderPicker.open()
                    }
                    AppButton {
                        text: "Open"
                        small: true
                        variant: "ghost"
                        iconName: "external"
                        onClicked: appBridge.openDownloadFolder()
                    }
                }

                SettingsRow {
                    label: "Filename template"
                    hint: "yt-dlp fields: %(title)s, %(id)s, %(ext)s"

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 4

                        CompactTextField {
                            objectName: "settings.filenameTemplate"
                            Layout.fillWidth: true
                            Layout.maximumWidth: 300
                            text: appBridge.filenameTemplate
                            onEditingFinished: appBridge.filenameTemplate = text
                        }

                        Label {
                            objectName: "settings.templatePreview"
                            text: appBridge.filenamePreview
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                            font.family: Theme.monoFont
                            elide: Text.ElideMiddle
                            Layout.maximumWidth: 300
                        }
                    }
                }

                SettingsRow {
                    label: "Default subtitle track"
                    hint: "Which track the Subtitle section preselects after Inspect."
                    BoundComboBox {
                        objectName: "settings.defaultSubtitleTrack"
                        Layout.preferredWidth: 300
                        label: "Default subtitle track"
                        textRole: "label"
                        valueRole: "id"
                        model: appBridge.defaultSubtitleChoices
                        selectFirstWhenMissing: true
                        readValue: function () { return appBridge.defaultSubtitleTrack }
                        writeValue: function (value) { appBridge.defaultSubtitleTrack = value }
                    }
                }
            }

            // ------------------------------------------------- SHORTCUTS
            AppCard {
                Layout.fillWidth: true
                title: "Shortcuts"

                Repeater {
                    model: appBridge.shortcutRows

                    delegate: SettingsRow {
                        required property var modelData
                        label: modelData.label

                        ShortcutRecorder {
                            action: modelData.action
                            sequence: modelData.sequence
                            isDefault: modelData.isDefault
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.sm

                    Label {
                        Layout.fillWidth: true
                        text: "Click Record, then press the new keys. Shortcuts need Ctrl or Alt."
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }

                    AppButton {
                        objectName: "settings.resetAllShortcuts"
                        text: "Reset all"
                        small: true
                        variant: "ghost"
                        iconName: "undo"
                        onClicked: appBridge.resetAllShortcuts()
                    }
                }
            }

            // ------------------------------------------------- READINESS
            AppCard {
                Layout.fillWidth: true
                title: "Readiness"

                ReadinessChecklist { Layout.fillWidth: true }

                SettingsRow {
                    label: "Log"
                    hint: "Read it here, copy it, or export it."

                    AppButton {
                        objectName: "settings.viewLog"
                        text: "View log"
                        small: true
                        variant: "ghost"
                        iconName: "file"
                        onClicked: if (Window.window) Window.window.openLog()
                    }
                    AppButton {
                        objectName: "settings.exportLog"
                        text: "Export"
                        small: true
                        variant: "ghost"
                        iconName: "save"
                        onClicked: appBridge.exportLog()
                    }
                    AppButton {
                        objectName: "settings.openDebugLog"
                        text: "Open file"
                        small: true
                        variant: "ghost"
                        iconName: "external"
                        onClicked: appBridge.openDebugLog()
                    }
                }
            }

            // ----------------------------------------------- ENVIRONMENT
            AppCard {
                Layout.fillWidth: true
                title: "Environment"

                Repeater {
                    // The reference names exactly these three; the other
                    // bridge rows (app folder, yt-dlp) live in the picker and
                    // readiness cards instead.
                    model: {
                        var wanted = ["settings_store", "log_file", "python"]
                        return appBridge.environmentRows.filter(function (row) {
                            return wanted.indexOf(row.id) !== -1
                        })
                    }
                    delegate: SettingsRow {
                        required property var modelData
                        label: modelData.label

                        Label {
                            objectName: "settings.environment." + modelData.id
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: modelData.value
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                            font.family: Theme.monoFont
                            elide: Text.ElideMiddle
                            wrapMode: Text.NoWrap
                        }
                    }
                }
            }

            // ---------------------------------------------- COMMAND LINE
            AppCard {
                Layout.fillWidth: true
                title: "Command line"

                Label {
                    Layout.fillWidth: true
                    text: "The same engine runs without the window."
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }

                Repeater {
                    model: [
                        "saaaveit --list-formats URL",
                        "saaaveit URL --subs-only",
                        "saaaveit URL -o D:\\Clips"
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: 8

                        TextInput {
                            id: line
                            objectName: "settings.cmdLine." + index
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: modelData
                            readOnly: true
                            selectByMouse: true
                            persistentSelection: false
                            color: Theme.text
                            font.pixelSize: Theme.fontSmall
                            font.family: Theme.monoFont
                            clip: true
                        }

                        AppButton {
                            objectName: "settings.cmdCopy." + index
                            text: "Copy"
                            small: true
                            variant: "ghost"
                            iconName: "copy"
                            Accessible.name: "Copy command " + (index + 1)
                            onClicked: {
                                line.selectAll()
                                line.copy()
                            }
                        }
                    }
                }
            }

            // -------------------------------------------------- DANGER
            DangerZone {
                Layout.fillWidth: true
                title: "Reset"
                description: "Clears your folder, appearance and shortcuts. "
                           + "Downloaded files stay."
                actionLabel: "Clear settings"
                confirmWord: "RESET"
                onConfirmed: appBridge.clearStoredSettings()
            }

            Item { Layout.preferredHeight: Theme.md }
        }
    }
}
