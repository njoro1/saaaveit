import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"

// Everything this app has downloaded, newest first (reference ``.lib``).
//
// A row is a *button*: one click selects it and the 320 px drawer slides in
// beside the list with that file's full story. The selected row collapses the
// ``WHEN``/actions columns to give the drawer room, exactly as the reference
// grid does. The drawer is a sibling of the list, not another column, so it can
// stay put while the list scrolls.
Item {
    id: page

    objectName: "libraryPage"

    readonly property bool hasSelection: appBridge.selectedHistoryIndex >= 0
    readonly property int selected: appBridge.selectedHistoryIndex

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.pagePaddingH
        anchors.rightMargin: Theme.pagePaddingH
        anchors.topMargin: Theme.pagePaddingV
        anchors.bottomMargin: Theme.pagePaddingV
        spacing: Theme.md

        // ---------------------------------------------------------------- header
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sm

            Label {
                text: "Library"
                color: Theme.text
                font.pixelSize: Theme.fontH1
                font.bold: true
            }

            Label {
                // The reference's own caption; the count is the only number here.
                text: appBridge.historyCount +
                      (appBridge.historyCount === 1 ? " item" : " items") +
                      " saved by this app, newest first"
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
            }

            Item { Layout.fillWidth: true }

            AppButton {
                objectName: "library.openFolderButton"
                text: "Open download folder"
                iconName: "folder"
                variant: "ghost"
                onClicked: appBridge.openDownloadFolder()
            }

            AppButton {
                id: clearButton
                objectName: "library.clearButton"
                text: "Clear history"
                iconName: "x"
                variant: "ghost"
                enabled: appBridge.historyCount > 0
                onClicked: confirmClear.open()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.columnGap

            // ----------------------------------------------------------- the list
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Downloaded files"

                // Column header. The widths mirror the delegate exactly; when a
                // row is selected the ``WHEN`` and actions headers disappear with
                // the columns, so the header never lies about what is below it.
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 28
                    color: Theme.inset

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: Theme.sm

                        Item { Layout.preferredWidth: Theme.listThumbWidth }
                        Label {
                            Layout.fillWidth: true
                            text: "FILE"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontTiny
                            font.letterSpacing: 0.6
                        }
                        Label {
                            Layout.preferredWidth: Theme.listSizeWidth
                            text: "SIZE"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontTiny
                            font.letterSpacing: 0.6
                        }
                        Label {
                            visible: !page.hasSelection
                            Layout.preferredWidth: Theme.listWhenWidth
                            text: "WHEN"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontTiny
                            font.letterSpacing: 0.6
                        }
                        Item {
                            visible: !page.hasSelection
                            Layout.preferredWidth: Theme.listActionWidth
                        }
                    }
                }

                ListView {
                    id: list
                    objectName: "library.table"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 0
                    model: appBridge.history
                    ScrollBar.vertical: AppScrollBar { }

                    delegate: Rectangle {
                        id: row
                        required property var modelData
                        required property int index

                        readonly property bool isSelected: modelData.index === page.selected

                        width: list.width
                        // Two lines of text or the 36 px preview, whichever is taller.
                        height: Math.max(Theme.rowHeight + Theme.xs * 3,
                                         rowBody.implicitHeight + Theme.sm)
                        // A selected row is tint + border + weight, never the raw
                        // accent as text - the accent is a shape, the word stays ink.
                        color: isSelected ? Theme.accentSoft
                             : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")

                        activeFocusOnTab: true

                        Keys.onReturnPressed: appBridge.selectHistory(isSelected ? -1 : modelData.index)
                        Keys.onEnterPressed: appBridge.selectHistory(isSelected ? -1 : modelData.index)
                        Keys.onSpacePressed: appBridge.selectHistory(isSelected ? -1 : modelData.index)
                        Keys.onDeletePressed: appBridge.removeHistory(modelData.index)

                        RowLayout {
                            id: rowBody
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: Theme.sm

                            MediaThumb {
                                Layout.preferredWidth: Theme.listThumbWidth
                                Layout.preferredHeight: 36
                                Layout.alignment: Qt.AlignVCenter
                                source: row.modelData.thumbnail || ""
                                duration: row.modelData.duration || 0
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                spacing: 1

                                Label {
                                    Layout.fillWidth: true
                                    // Without this the layout treats the full file
                                    // name as the minimum and pushes the actions
                                    // out instead of eliding (T7.3).
                                    Layout.minimumWidth: 0
                                    text: row.modelData.name
                                    color: row.modelData.exists ? Theme.text : Theme.textDim
                                    font.pixelSize: Theme.fontSmall
                                    font.family: Theme.monoFont
                                    font.weight: row.isSelected ? Font.DemiBold : Font.Normal
                                    elide: Text.ElideMiddle
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.sm

                                    // The kind is a shape as well as a colour/word,
                                    // so video vs subtitle survives greyscale.
                                    Icon {
                                        visible: row.modelData.detail !== ""
                                        name: row.modelData.kind === "subtitle" ? "file" : "film"
                                        color: Theme.textMuted
                                        width: 12
                                        height: 12
                                        Layout.alignment: Qt.AlignVCenter
                                    }

                                    Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        visible: row.modelData.detail !== ""
                                        text: row.modelData.detail
                                        color: Theme.textDim
                                        font.pixelSize: Theme.fontTiny
                                        elide: Text.ElideRight
                                    }

                                    Label {
                                        visible: !row.modelData.exists
                                        text: "missing from disk"
                                        color: Theme.warning
                                        font.pixelSize: Theme.fontTiny
                                    }
                                }
                            }

                            Label {
                                Layout.preferredWidth: Theme.listSizeWidth
                                Layout.alignment: Qt.AlignVCenter
                                text: row.modelData.sizeText
                                color: Theme.textDim
                                font.pixelSize: Theme.fontSmall
                            }

                            Label {
                                visible: !page.hasSelection
                                Layout.preferredWidth: Theme.listWhenWidth
                                Layout.alignment: Qt.AlignVCenter
                                text: row.modelData.when
                                color: Theme.textDim
                                font.pixelSize: Theme.fontSmall
                            }

                            // The inline actions disappear the moment a row is
                            // selected: the drawer becomes the action surface.
                            RowLayout {
                                visible: !page.hasSelection
                                Layout.preferredWidth: Theme.listActionWidth
                                Layout.alignment: Qt.AlignVCenter
                                spacing: 2

                                AppButton {
                                    text: "Open"
                                    small: true
                                    variant: "ghost"
                                    enabled: row.modelData.exists
                                    onClicked: appBridge.launchFile(row.modelData.index)
                                }

                                AppButton {
                                    text: "Redownload"
                                    small: true
                                    variant: "ghost"
                                    onClicked: appBridge.redownload(row.modelData.index)
                                }
                            }
                        }

                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 1
                            color: Theme.borderSoft
                        }

                        // The whole row is the select target: a plain left click
                        // toggles it, exactly like the reference ``.lib`` row.
                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton
                            onClicked: appBridge.selectHistory(row.isSelected ? -1 : row.modelData.index)
                        }

                        Accessible.role: Accessible.ListItem
                        Accessible.name: row.modelData.name
                        Accessible.selected: row.isSelected
                    }
                }

                EmptyState {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    visible: appBridge.historyCount === 0
                    title: "Nothing downloaded yet"
                    body: "Downloads show up here, with the format and subtitle track that were used."
                    iconName: "history"
                }
            }

            // ------------------------------------------------------- the drawer
            // A sibling of the list, pinned at ``drawerWidth``. Its ``entry`` is
            // resolved here (the page knows the selection index) and handed down.
            LibraryDrawer {
                id: drawer
                Layout.fillHeight: true
                Layout.preferredWidth: Theme.drawerWidth
                Layout.alignment: Qt.AlignTop
                entry: {
                    var rows = appBridge.history
                    return page.selected >= 0 && page.selected < rows.length
                           ? rows[page.selected] : null
                }
            }
        }
    }

    Dialog {
        id: confirmClear
        objectName: "library.clearDialog"
        title: "Clear history?"
        modal: true
        anchors.centerIn: parent
        // Escape cancels; there is no default (Enter) action because the only
        // affirmative is destructive.
        closePolicy: Popup.CloseOnEscape
        padding: Theme.lg
        width: 420

        Overlay.modal: Rectangle { color: Theme.scrim }

        // Level-3 elevation; the background itself is transparent so the
        // surface can sit above its shadow rings.
        background: Rectangle {
            id: dialogBg
            color: "transparent"
            readonly property var _shadow: Theme.shadowFor(Theme.elevationOverlay)

            Rectangle {
                anchors.fill: surface
                anchors.margins: -4
                radius: Theme.radiusLg + 4
                color: Theme.shadowColor
                opacity: dialogBg._shadow.opacity * 0.5
            }

            Rectangle {
                anchors.fill: surface
                anchors.margins: -2
                radius: Theme.radiusLg + 2
                color: Theme.shadowColor
                opacity: dialogBg._shadow.opacity
            }

            Rectangle {
                id: surface
                anchors.fill: parent
                color: Theme.surface
                radius: Theme.radiusLg
            }
        }

        contentItem: Label {
            text: "This only clears the list. The downloaded files stay on disk."
            color: Theme.textDim
            font.pixelSize: Theme.fontBody
            wrapMode: Text.WordWrap
        }

        // Basic style ships a light header band; replace it with tokens so the
        // title keeps the dialog surface in both themes.
        header: Label {
            text: confirmClear.title
            color: Theme.text
            font.pixelSize: Theme.fontLabel
            font.weight: Font.DemiBold
        }

        footer: RowLayout {
            spacing: Theme.sm

            Item { Layout.fillWidth: true }

            AppButton {
                objectName: "library.clearCancel"
                text: "Cancel"
                variant: "ghost"
                onClicked: confirmClear.reject()
            }

            AppButton {
                objectName: "library.clearConfirm"
                text: "Clear history"
                variant: "danger"
                onClicked: confirmClear.accept()
            }
        }

        onAccepted: appBridge.clearHistory()
        // Keyboard focus comes back to the button that opened the dialog.
        onClosed: clearButton.forceActiveFocus()
    }
}
