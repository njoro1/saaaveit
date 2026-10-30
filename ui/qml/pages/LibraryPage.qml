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

                    Label { Layout.fillWidth: true; text: "FILE"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Label { Layout.preferredWidth: 70; text: "KIND"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Label { Layout.preferredWidth: 160; text: "FORMAT / TRACK"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Label { Layout.preferredWidth: 70; text: "SIZE"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Label { Layout.preferredWidth: 120; text: "WHEN"; color: Theme.textMuted; font.pixelSize: Theme.fontTiny; font.letterSpacing: 0.6 }
                    Item { Layout.preferredWidth: 180 }
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

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index

                    width: list.width
                    // The first cell can carry two lines (name + "missing from
                    // disk"). A fixed 40px row let the second line bleed into
                    // the row below once body text moved to 13px.
                    height: Math.max(40, rowBody.implicitHeight + 12)
                    color: index === list.currentIndex ? Theme.accentSoft
                         : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")

                    RowLayout {
                        id: rowBody
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: Theme.sm

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            Label {
                                Layout.fillWidth: true
                                text: row.modelData.name
                                color: row.modelData.exists ? Theme.text : Theme.textMuted
                                font.pixelSize: Theme.fontSmall
                                font.family: Theme.monoFont
                                elide: Text.ElideMiddle
                            }

                            Label {
                                Layout.fillWidth: true
                                visible: !row.modelData.exists
                                text: "missing from disk"
                                color: Theme.warning
                                font.pixelSize: Theme.fontTiny
                            }
                        }

                        Label {
                            Layout.preferredWidth: 70
                            text: row.modelData.kindLabel
                            color: row.modelData.kind === "video" ? Theme.accent : Theme.info
                            font.pixelSize: Theme.fontSmall
                        }

                        Label {
                            Layout.preferredWidth: 160
                            text: row.modelData.detail
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                            elide: Text.ElideRight
                        }

                        Label {
                            Layout.preferredWidth: 70
                            text: row.modelData.sizeText
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        Label {
                            Layout.preferredWidth: 120
                            text: row.modelData.when
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                        }

                        RowLayout {
                            Layout.preferredWidth: 180
                            spacing: 2

                            AppButton {
                                text: "Open"
                                small: true
                                variant: "ghost"
                                enabled: row.modelData.exists
                                onClicked: appBridge.openDownloadedFile(row.modelData.index)
                            }

                            AppButton {
                                text: "Folder"
                                small: true
                                variant: "ghost"
                                enabled: row.modelData.exists
                                onClicked: appBridge.openDownloadedFolder(row.modelData.index)
                            }

                            AppButton {
                                text: "Copy path"
                                small: true
                                variant: "ghost"
                                onClicked: appBridge.copyDownloadPath(row.modelData.index)
                            }
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
        standardButtons: Dialog.Cancel | Dialog.Ok
        width: 420

        background: Rectangle {
            color: Theme.surface
            border.color: Theme.borderStrong
            radius: Theme.radiusLg
        }

        contentItem: Label {
            text: "This only clears the list. The downloaded files stay on disk."
            color: Theme.textDim
            font.pixelSize: Theme.fontBody
            wrapMode: Text.WordWrap
        }

        onAccepted: appBridge.clearHistory()
    }
}
