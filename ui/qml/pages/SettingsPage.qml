import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."
import "../components"

// Appearance, where files go, the default subtitle choice, keyboard shortcuts,
// and the two destructive actions. Everything persists on its own: this app
// owns its settings store end to end.
Item {
    id: page

    objectName: "settingsPage"

    FolderDialog {
        id: folderPicker
        title: "Choose where downloads are saved"
        onAccepted: appBridge.setDownloadDir(selectedFolder)
    }

    ScrollView {
        id: scroller
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: scroller.availableWidth
            spacing: Theme.md

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
                                implicitWidth: 26
                                implicitHeight: 26
                                radius: 13
                                color: Theme.isDark ? modelData.dark : modelData.light
                                border.width: appBridge.accentName === modelData.id ? 3 : 0
                                border.color: Theme.text

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
                    hint: "Stops pulsing dots and sliding progress."
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
                        Layout.fillWidth: true
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
                }

                SettingsRow {
                    label: "Filename template"
                    hint: "yt-dlp fields: %(title)s, %(id)s, %(ext)s"
                    CompactTextField {
                        objectName: "settings.filenameTemplate"
                        Layout.fillWidth: true
                        text: appBridge.filenameTemplate
                        onEditingFinished: appBridge.filenameTemplate = text
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

                        Label {
                            Layout.fillWidth: true
                            text: modelData.sequence === "" ? "unassigned" : modelData.sequence
                            color: Theme.text
                            font.pixelSize: Theme.fontSmall
                            font.family: Theme.monoFont
                        }

                        AppButton {
                            text: "Reset"
                            small: true
                            variant: "ghost"
                            onClicked: appBridge.resetShortcut(modelData.action)
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    AppButton {
                        text: "Reset all shortcuts"
                        small: true
                        variant: "ghost"
                        onClicked: appBridge.resetAllShortcuts()
                    }
                }
            }

            // ------------------------------------------------ DIAGNOSTICS
            AppCard {
                Layout.fillWidth: true
                title: "Diagnostics"

                ReadinessChecklist { Layout.fillWidth: true }

                Repeater {
                    model: appBridge.environmentRows
                    delegate: SettingsRow {
                        required property var modelData
                        label: modelData.label
                        Label {
                            Layout.fillWidth: true
                            text: modelData.value
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                            font.family: Theme.monoFont
                            elide: Text.ElideMiddle
                            wrapMode: Text.NoWrap
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.sm

                    AppButton {
                        text: "Open download folder"
                        small: true
                        variant: "ghost"
                        iconName: "folder"
                        onClicked: appBridge.openDownloadFolder()
                    }
                    AppButton {
                        text: "Export log"
                        small: true
                        variant: "ghost"
                        iconName: "save"
                        onClicked: appBridge.exportLog()
                    }
                    AppButton {
                        text: "Open debug log"
                        small: true
                        variant: "ghost"
                        iconName: "terminal"
                        onClicked: appBridge.openDebugLog()
                    }
                    Item { Layout.fillWidth: true }
                }
            }

            // -------------------------------------------------- DANGER
            DangerZone {
                Layout.fillWidth: true
                title: "Danger zone"
                description: "Clearing stored settings forgets your download folder, "
                           + "appearance and shortcuts. Downloaded files are not touched."
                actionLabel: "Clear stored settings"
                confirmWord: "RESET"
                onConfirmed: appBridge.clearStoredSettings()
            }

            Item { Layout.preferredHeight: Theme.md }
        }
    }
}
