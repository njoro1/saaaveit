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

    // The command palette's "Clear download history" lands here and asks the
    // same question the header button does - the reference routes it that way
    // rather than clearing on a keypress.
    function openClearDialog() {
        confirmClear.open()
    }

    ColumnLayout {
        id: contentColumn
        // `.page{max-width:1180px;margin:0 auto}` inside `main{padding:28px 32px}`.
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.min(Theme.contentMaxWidth,
                        parent.width - 2 * Theme.pagePaddingH)
        // `.sub{margin:4px 0 22px}` — 4px under the title, 22px under the caption.
        spacing: Theme.xs

        // The reference card ends with its last row and lets `main` scroll; a
        // fixed window hands that scrolling to the list, so the card is capped
        // at whatever height the page has left over. ``libwrap.height`` cannot
        // be the cap: the row is only as tall as the card, so the two bindings
        // cancel out and both collapse to zero.
        readonly property int listBudget: Math.max(
            Theme.xxl,
            height - pageHeader.height - pageHeader.Layout.topMargin
            - pageHeader.Layout.bottomMargin - spacing - Theme.pagePaddingV)

        // ---------------------------------------------------------------- header
        // `.row` with a `<div>` of h1 + .sub at one end and the two buttons at
        // the other: the caption sits *under* the title, not beside it.
        RowLayout {
            id: pageHeader
            Layout.fillWidth: true
            Layout.topMargin: Theme.pagePaddingV
            Layout.bottomMargin: 22 - Theme.xs
            spacing: Theme.sm

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Theme.xs

                Label {
                    text: "Library"
                    color: Theme.text
                    font.pixelSize: Theme.fontH1
                    font.letterSpacing: Theme.h1Tracking
                    font.bold: true
                }

                Label {
                    // The reference's own caption; the count is the only number here.
                    text: appBridge.historyCount +
                          (appBridge.historyCount === 1 ? " file" : " files") +
                          " saved by this app, newest first"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontBody
                    elide: Text.ElideRight
                }
            }

            AppButton {
                objectName: "library.openFolderButton"
                text: "Open download folder"
                onClicked: appBridge.openDownloadFolder()
            }

            AppButton {
                id: clearButton
                objectName: "library.clearButton"
                text: "Clear history"
                variant: "danger"
                enabled: appBridge.historyCount > 0
                onClicked: confirmClear.open()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // ``Layout.alignment: Qt.AlignTop`` pins the card to its own height,
            // and a nested layout inherits that as its maximum - left alone the
            // row would refuse to grow and the column would spend the leftover
            // as gaps above the title. The ceiling is stated so the row can
            // still fill the page.
            Layout.maximumHeight: contentColumn.height
            Layout.bottomMargin: Theme.pagePaddingV
            // `.libwrap{gap:18px}`
            spacing: Theme.drawerGap

            // ----------------------------------------------------------- the list
            AppCard {
                Layout.fillWidth: true
                // `.card` is a block in the flow: it ends with its last row. The
                // list only starts scrolling once the rows would run past the
                // window, which is what the cap is for.
                Layout.alignment: Qt.AlignTop
                Layout.maximumHeight: contentColumn.listBudget
                bodySpacing: 0

                ListView {
                    id: list
                    objectName: "library.table"
                    // Rows bleed into the card's own 18px of side padding when
                    // selected, so the highlight reaches the card's border the
                    // way `.lib[aria-selected=true]{margin:0 -18px}` does. The
                    // list therefore spans the full inner width and each row
                    // re-applies the inset to its content.
                    Layout.leftMargin: -18
                    Layout.rightMargin: -18
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredHeight: list.contentHeight
                    clip: true
                    spacing: 0
                    model: appBridge.history
                    ScrollBar.vertical: AppScrollBar { }

                    delegate: Item {
                        id: row
                        required property var modelData
                        required property int index

                        readonly property bool isSelected: modelData.index === page.selected
                        // The selected row's tint and hairline reach the card
                        // border; an ordinary row's hairline stops at the
                        // content box, exactly like its `border-top`.
                        readonly property real bleed: isSelected ? 0 : 18

                        width: list.width
                        // `.lib{padding:10px 0}` around whichever is taller - the
                        // 36 px thumbnail or the two lines of text.
                        height: rowBody.implicitHeight + 20

                        activeFocusOnTab: true

                        Keys.onReturnPressed: appBridge.selectHistory(isSelected ? -1 : modelData.index)
                        Keys.onEnterPressed: appBridge.selectHistory(isSelected ? -1 : modelData.index)
                        Keys.onSpacePressed: appBridge.selectHistory(isSelected ? -1 : modelData.index)
                        Keys.onDeletePressed: appBridge.removeHistory(modelData.index)

                        // A selected row is tint + border + weight, never the raw
                        // accent as text - the accent is a shape, the word stays ink.
                        Rectangle {
                            anchors.fill: parent
                            color: row.isSelected ? Theme.accentSoft
                                 : (rowMouse.containsMouse ? Theme.surfaceAlt : "transparent")
                        }

                        Rectangle {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: row.bleed
                            anchors.rightMargin: row.bleed
                            height: 1
                            color: Theme.border
                        }

                        RowLayout {
                            id: rowBody
                            anchors.fill: parent
                            anchors.leftMargin: 18
                            anchors.rightMargin: 18
                            spacing: 14

                            MediaThumb {
                                Layout.preferredWidth: Theme.listThumbWidth
                                Layout.preferredHeight: 36
                                Layout.alignment: Qt.AlignVCenter
                                // `.lib .thumb{border-radius:5px}`
                                radius: 5
                                // `.lib .thumb svg{16px}`
                                glyphSize: 16
                                isVideo: row.modelData.kind !== "subtitle"
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
                                    // `.lib.miss .n` is the same name at half
                                    // opacity; the ramp's muted step is the value
                                    // that says "de-emphasised" and still clears AA.
                                    color: row.modelData.exists ? Theme.text : Theme.textMuted
                                    // `.n.mono` — the file name is data, not prose.
                                    font.pixelSize: Theme.fontTiny
                                    font.family: Theme.monoFont
                                    // `.lib[aria-selected=true]` changes only the
                                    // tint: the drawer is the confirmation, so the
                                    // row does not also shout.
                                    elide: Text.ElideMiddle
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.sm

                                    // "Video · AV1 · 1080p": the kind is a word,
                                    // so the line reads in greyscale too.
                                    Label {
                                        visible: row.modelData.detail !== ""
                                        Layout.minimumWidth: 0
                                        text: row.modelData.kindLabel +
                                              (row.modelData.detail === ""
                                               ? "" : " · " + row.modelData.detail)
                                        color: Theme.textMuted
                                        font.pixelSize: Theme.fontSmall
                                        elide: Text.ElideRight
                                    }

                                    // `.m.wa` — the warning is a filled mark with
                                    // its own word, so greyscale still reads it.
                                    Rectangle {
                                        visible: !row.modelData.exists
                                        Layout.alignment: Qt.AlignVCenter
                                        // Overridden to `width:auto;padding:0 6px`:
                                        // the badge is exactly as wide as its word.
                                        // Anchoring the label inside a Rectangle
                                        // that never sizes itself to it would lay
                                        // the text over the detail line.
                                        implicitWidth: missingLabel.implicitWidth
                                        implicitHeight: 18
                                        radius: Theme.radiusXs
                                        color: Theme.warning

                                        Label {
                                            id: missingLabel
                                            anchors.centerIn: parent
                                            text: "▲ missing from disk"
                                            color: Theme.statusOnFill
                                            font.pixelSize: Theme.fontTiny
                                            leftPadding: 6
                                            rightPadding: 6
                                        }
                                    }
                                }
                            }

                            Label {
                                Layout.preferredWidth: Theme.listSizeWidth
                                Layout.alignment: Qt.AlignVCenter
                                text: row.modelData.sizeText
                                color: Theme.text
                                font.pixelSize: Theme.fontTiny
                                font.family: Theme.monoFont
                                horizontalAlignment: Text.AlignLeft
                            }

                            Label {
                                visible: !page.hasSelection
                                Layout.preferredWidth: Theme.listWhenWidth
                                Layout.alignment: Qt.AlignVCenter
                                text: row.modelData.when
                                objectName: "library.when." + row.modelData.index
                                color: Theme.text
                                font.pixelSize: Theme.fontTiny
                                font.family: Theme.monoFont
                                elide: Text.ElideRight
                            }

                            // The inline actions disappear the moment a row is
                            // selected: the drawer becomes the action surface.
                            RowLayout {
                                visible: !page.hasSelection
                                Layout.preferredWidth: Theme.listActionWidth
                                Layout.alignment: Qt.AlignVCenter
                                spacing: 4

                                Item { Layout.fillWidth: true }

                                AppButton {
                                    text: "Open"
                                    small: true
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

                        // The whole row is the select target: a plain left click
                        // toggles it, exactly like the reference `.lib` row.
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
                    // `.empty` is two lines of centred text and nothing else.
                    iconName: ""
                    brand: true
                    title: "Nothing downloaded yet"
                    body: "Downloads show up here, with the format and subtitle track that were used."
                }
            }

            // ------------------------------------------------------- the drawer
            // A sibling of the list, pinned at ``drawerWidth``. Its ``entry`` is
            // resolved here (the page knows the selection index) and handed down.
            LibraryDrawer {
                id: drawer
                // `.libwrap{align-items:start}`: both columns end with their own
                // content, so the drawer never stretches to the list's height.
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: Theme.drawerWidth
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
        // ``.scrim{justify-content:center;padding-top:90px}`` and
        // ``#cf{margin-top:80px}``: the dialog opens on a fixed line 170px below
        // the top, cent horizontally - not in the middle of the window. The
        // clamp is only so a very short window cannot cut off the buttons.
        x: parent ? Math.max(0, (parent.width - width) / 2) : 0
        y: parent ? Math.max(Theme.xs,
                             Math.min(170, parent.height - height - Theme.xs)) : 0
        // Escape cancels; there is no default (Enter) action because the only
        // affirmative is destructive.
        closePolicy: Popup.CloseOnEscape
        // `#cf` carries `style="width:420px;margin-top:80px;padding:22px"`.
        padding: 22
        spacing: 0
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
                radius: Theme.dialogRadius + 4
                color: Theme.shadowColor
                opacity: dialogBg._shadow.opacity * 0.5
            }

            Rectangle {
                anchors.fill: surface
                anchors.margins: -2
                radius: Theme.dialogRadius + 2
                color: Theme.shadowColor
                opacity: dialogBg._shadow.opacity
            }

            Rectangle {
                id: surface
                anchors.fill: parent
                color: Theme.surface
                // `.dlg{border-radius:16px}`
                radius: Theme.dialogRadius
                border.width: 1
                border.color: Theme.borderStrong
            }
        }

        contentItem: Label {
            text: "This only clears the list. The downloaded files stay on disk."
            color: Theme.textMuted
            // `.note` is 13px muted; `#cf` gives it `margin:8px 0 18px`.
            font.pixelSize: Theme.fontSmall
            topPadding: 8
            bottomPadding: 18
            wrapMode: Text.WordWrap
        }

        // Basic style ships a light header band; replace it with tokens so the
        // title keeps the dialog surface in both themes.
        header: Label {
            text: confirmClear.title
            color: Theme.text
            // `<h2 style="font-size:17px">` — the browser default weight, 700.
            font.pixelSize: Theme.fontTitle
            font.bold: true
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
