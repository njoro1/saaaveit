import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"

// Appearance, the filename and subtitle defaults, recordable keyboard
// shortcuts, readiness, environment, the CLI, and the one destructive action.
// Everything persists on its own — the Saved toast is the autosave saying it
// landed. Card order and row order follow the reference.
Item {
    id: page

    objectName: "settingsPage"

    readonly property string windowTitle: "Settings"

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

    // `main{padding:28px 32px}` with `.page{max-width:1180px;margin:0 auto}`.
    ColumnLayout {
        id: pageHeader
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: Theme.pagePaddingH
        anchors.rightMargin: Theme.pagePaddingH
        anchors.topMargin: Theme.pagePaddingV
        // `.sub{margin:4px 0 22px}`
        spacing: Theme.xs

        RowLayout {
            // `.toast{margin-left:14px}`
            spacing: 14

            Label {
                objectName: "settings.pageTitle"
                text: "Settings"
                color: Theme.text
                font.pixelSize: Theme.fontH1
                font.letterSpacing: Theme.h1Tracking
                font.bold: true
            }

            Label {
                id: savedToast
                objectName: "settings.savedToast"
                text: "Saved ✓"
                color: Theme.success
                // ``.toast{font-size:13px;font-weight:500}`` — a confirmation,
                // not a shout.
                font.pixelSize: Theme.fontSmall
                font.weight: Font.Medium
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
            // ``.sub`` inherits the 14px body size; only its colour is muted.
            font.pixelSize: Theme.fontBody
            elide: Text.ElideRight
        }
    }

    // ``main{overflow:auto;padding:28px 32px}`` scrolls, so the caption stays
    // with the header and only the cards travel. ``.sub{margin-bottom:22px}``
    // is the gap to the first card.
    ScrollView {
        id: scroller
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: pageHeader.bottom
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.pagePaddingH
        anchors.rightMargin: Theme.pagePaddingH
        anchors.topMargin: 22
        anchors.bottomMargin: Theme.pagePaddingV
        clip: true
        contentWidth: availableWidth
        // ``main{overflow:auto}`` gives its scrollbar a gutter of its own; the
        // same here keeps the handle off the cards' right border. The gutter
        // appears only when the bar does, exactly like ``overflow:auto``.
        rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width : 0
        // The Basic ScrollView hands its bars their geometry in QML, and the C++
        // attachment only lays out bars on a plain Flickable: a bar that
        // replaces one of the style's own has to place itself, and the
        // horizontal slot has to be replaced too or the style's grey trough
        // stays behind.
        ScrollBar.vertical: AppScrollBar {
            parent: scroller
            x: scroller.width - width
            y: scroller.topPadding
            height: scroller.availableHeight
        }
        ScrollBar.horizontal: AppScrollBar {
            parent: scroller
            x: scroller.leftPadding
            y: scroller.height - height
            width: scroller.availableWidth
        }

        ColumnLayout {
            // ``.page{max-width:1180px;margin:0 auto}``
            width: Math.min(Theme.contentMaxWidth, scroller.availableWidth)
            x: (scroller.availableWidth - width) / 2
            // ``.card{margin-bottom:18px}`` — one gap, whatever the density.
            spacing: 18

            // ------------------------------------------------ APPEARANCE
            AppCard {
                Layout.fillWidth: true
                title: "Appearance"
                bodySpacing: 0

                SettingsRow {
                    label: "Theme"
                    topBorder: false
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
                                activeFocusOnTab: true

                                Keys.onReturnPressed: appBridge.setAccent(modelData.id)
                                Keys.onSpacePressed: appBridge.setAccent(modelData.id)

                                // `.sw button[aria-pressed=true]` is a double
                                // ring: 2px of card surface, then 2px of `tx`.
                                // A border on the swatch itself would glue the
                                // ring to the dot and lose the gap.
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -2
                                    radius: width / 2
                                    color: "transparent"
                                    border.width: appBridge.accentName === modelData.id ? 2 : 0
                                    border.color: Theme.text
                                }

                                // The selection ring is the swatch's own
                                // outline, so focus needs somewhere else to
                                // live: a second ring outside it, in the accent
                                // line colour.
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -6
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
                bodySpacing: 0

                SettingsRow {
                    label: "Filename template"
                    hint: "Fields: %(title)s, %(id)s, %(ext)s"
                    topBorder: false

                    hintContent: Label {
                        objectName: "settings.templatePreview"
                        text: appBridge.filenamePreview
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        font.family: Theme.monoFont
                        elide: Text.ElideMiddle
                    }

                    CompactTextField {
                        objectName: "settings.filenameTemplate"
                        Layout.preferredWidth: 300
                        Layout.minimumWidth: 140
                        fieldHeight: Theme.rowInputHeight
                        font.family: Theme.monoFont
                        text: appBridge.filenameTemplate
                        onEditingFinished: appBridge.filenameTemplate = text
                    }
                }

                SettingsRow {
                    label: "Default subtitle"

                    BoundComboBox {
                        objectName: "settings.defaultSubtitleTrack"
                        Layout.preferredWidth: 300
                        Layout.minimumWidth: 140
                        label: "Default subtitle"
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
                bodySpacing: 0

                Repeater {
                    model: appBridge.shortcutRows

                    delegate: SettingsRow {
                        required property var modelData
                        required property int index
                        // The card heading owns the first row's upper air, so
                        // only rows after the first draw a hairline.
                        topBorder: index > 0
                        label: modelData.label

                        ShortcutRecorder {
                            action: modelData.action
                            sequence: modelData.sequence
                            isDefault: modelData.isDefault
                        }
                    }
                }

                SettingsRow {
                    hint: "Click Record, then press the new keys. Shortcuts need Ctrl or Alt."

                    AppButton {
                        objectName: "settings.resetAllShortcuts"
                        text: "Reset all"
                        small: true
                        onClicked: appBridge.resetAllShortcuts()
                    }
                }
            }

            // ------------------------------------------------- READINESS
            AppCard {
                Layout.fillWidth: true
                title: "Readiness"
                bodySpacing: 0

                ReadinessChecklist { Layout.fillWidth: true }

                SettingsRow {
                    label: "Log"
                    hint: "Read it here, copy it, or export it."

                    AppButton {
                        objectName: "settings.viewLog"
                        text: "View log"
                        small: true
                        onClicked: if (Window.window) Window.window.openLog()
                    }
                    AppButton {
                        objectName: "settings.exportLog"
                        text: "Export"
                        small: true
                        onClicked: appBridge.exportLog()
                    }
                }
            }

            // ----------------------------------------------- ENVIRONMENT
            AppCard {
                Layout.fillWidth: true
                title: "Environment"
                bodySpacing: 0

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
                        required property int index
                        objectName: "settings.environment." + modelData.id
                        topBorder: index > 0
                        label: modelData.label
                        value: modelData.value
                        valueMono: true
                    }
                }
            }

            // ---------------------------------------------- COMMAND LINE
            AppCard {
                Layout.fillWidth: true
                title: "Command line"
                bodySpacing: 0

                // One row, exactly as the reference draws it: the sentence is
                // the label and the three invocations are its hint lines. The
                // commands are selectable and carry a copy affordance, which is
                // the one thing here the prototype cannot show.
                SettingsRow {
                    topBorder: false
                    label: "The same engine runs without the window."

                    hintContent: ColumnLayout {
                        spacing: 4

                        Repeater {
                            model: [
                                "saaaveit --list-formats URL",
                                "saaaveit URL --subs-only",
                                "saaaveit URL -o D:\\Clips"
                            ]
                            delegate: RowLayout {
                                required property var modelData
                                required property int index
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
                                    color: Theme.textMuted
                                    font.pixelSize: Theme.fontTiny
                                    font.family: Theme.monoFont
                                    clip: true
                                }

                                AppButton {
                                    objectName: "settings.cmdCopy." + index
                                    text: "Copy"
                                    small: true
                                    variant: "ghost"
                                    Accessible.name: "Copy command " + (index + 1)
                                    onClicked: {
                                        line.selectAll()
                                        line.copy()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // -------------------------------------------------- DANGER
            DangerZone {
                Layout.fillWidth: true
                // ``.card{margin-bottom:18px}`` holds for the last card too, so
                // the scroll area ends 18px below its border.
                Layout.bottomMargin: 18
                title: "Reset"
                rowLabel: "Forget settings"
                description: "Clears your folder, appearance and shortcuts. "
                           + "Downloaded files stay."
                actionLabel: "Clear settings"
                confirmWord: "RESET"
                onConfirmed: appBridge.clearStoredSettings()
            }
        }
    }
}
