import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../components"

// Everything this app has downloaded, newest first. Rows are read from the
// bridge, which is also the only thing that can delete them.
Item {
    id: page

    objectName: "libraryPage"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.lg
        spacing: Theme.md

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
                text: appBridge.historyCount + " file(s)"
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

        AppCard {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Downloaded files"

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 28
                color: Theme.inset

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: Theme.sm

                    Item { Layout.preferredWidth: 64 }
                    Label { Layout.fillWidth: true; text: "FILE"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Label { Layout.preferredWidth: 70; text: "SIZE"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Label { Layout.preferredWidth: 120; text: "WHEN"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Item { Layout.preferredWidth: 108 }
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

                    width: list.width
                    // Two lines of text or the 36 px preview, whichever is taller.
                    height: Math.max(Theme.rowHeight + Theme.xs * 3,
                                     rowBody.implicitHeight + Theme.sm)
                    color: index === list.currentIndex ? Theme.accentSoft
                         : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")

                    RowLayout {
                        id: rowBody
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: Theme.sm

                        MediaThumb {
                            Layout.preferredWidth: 64
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
                                text: row.modelData.name
                                color: row.modelData.exists ? Theme.text : Theme.textMuted
                                font.pixelSize: Theme.fontSmall
                                font.family: Theme.monoFont
                                elide: Text.ElideMiddle
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.sm

                                Label {
                                    Layout.fillWidth: true
                                    visible: row.modelData.detail !== ""
                                    text: row.modelData.detail
                                    color: Theme.textMuted
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
                            Layout.preferredWidth: 70
                            Layout.alignment: Qt.AlignVCenter
                            text: row.modelData.sizeText
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        Label {
                            Layout.preferredWidth: 120
                            Layout.alignment: Qt.AlignVCenter
                            text: row.modelData.when
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                        }

                        RowLayout {
                            Layout.preferredWidth: 108
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 2

                            AppButton {
                                text: "Open"
                                small: true
                                variant: "ghost"
                                enabled: row.modelData.exists
                                onClicked: appBridge.openDownloadedFile(row.modelData.index)
                            }

                            AppButton {
                                text: ""
                                iconName: "folder"
                                small: true
                                variant: "ghost"
                                enabled: row.modelData.exists
                                Layout.preferredWidth: Theme.controlHeightSmall
                                Accessible.name: "Open folder"
                                tooltip: "Open folder"
                                onClicked: appBridge.openDownloadedFolder(row.modelData.index)
                            }

                            AppButton {
                                id: moreButton
                                text: ""
                                iconName: "more"
                                small: true
                                variant: "ghost"
                                Layout.preferredWidth: Theme.controlHeightSmall
                                Accessible.name: "More actions"
                                tooltip: "More actions"
                                onClicked: rowMenu.popup(moreButton)
                            }
                        }
                    }

                    // Low-frequency action, so it lives behind the row's menu
                    // instead of competing with Open/Folder for width.
                    Menu {
                        id: rowMenu
                        objectName: "library.rowMenu"
                        width: 176
                        padding: 4

                        background: Item {
                            id: menuBg

                            readonly property var _shadow: Theme.shadowFor(Theme.elevationOverlay)

                            Rectangle {
                                anchors.fill: menuCard
                                anchors.margins: -3
                                radius: Theme.radiusMd + 3
                                color: Theme.shadowColor
                                opacity: menuBg._shadow.opacity * 0.5
                            }

                            Rectangle {
                                anchors.fill: menuCard
                                anchors.margins: -1
                                radius: Theme.radiusMd + 1
                                color: Theme.shadowColor
                                opacity: menuBg._shadow.opacity
                            }

                            Rectangle {
                                id: menuCard
                                anchors.fill: parent
                                color: Theme.surfaceRaised
                                border.width: 1
                                border.color: Theme.borderStrong
                                radius: Theme.radiusMd
                            }
                        }

                        // Styling goes on the item itself: a Menu shows
                        // statically declared MenuItems as-is, so `delegate`
                        // would only reach string/array models.
                        MenuItem {
                            id: copyItem
                            width: rowMenu.availableWidth
                            height: 32
                            text: "Copy path"

                            contentItem: Label {
                                text: copyItem.text
                                color: Theme.text
                                font.pixelSize: Theme.fontSmall
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 10
                            }

                            background: Rectangle {
                                color: copyItem.highlighted || copyItem.hovered
                                       ? Theme.accentSoft : "transparent"
                                radius: Theme.radiusSm
                            }

                            onTriggered: appBridge.copyDownloadPath(row.modelData.index)
                        }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.borderSoft
                    }

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.RightButton
                        onClicked: appBridge.selectHistory(row.modelData.index)
                    }
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
    }

    Dialog {
        id: confirmClear
        objectName: "library.clearDialog"
        title: "Clear download history?"
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
