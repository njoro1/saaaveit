import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."
import "../components"

// The one screen that matters: paste a URL, inspect, pick a format and a
// subtitle track, download. Everything else in the app explains or replays this.
Item {
    id: page

    objectName: "downloadPage"

    readonly property bool busy: appBridge.downloadRunning
    readonly property bool hasSelection: !!appBridge.selectedOption.format_selector
    readonly property bool wide: page.width >= 1280

    // Preparing and merging have no meaningful percentage: show a sweep, not a
    // frozen bar. A running download also never reads as 100% complete.
    readonly property bool indeterminateStage: page.busy
        && (appBridge.downloadStage === "preparing"
            || appBridge.downloadStage === "merging")
    readonly property int shownProgress: page.busy
        ? Math.min(99, appBridge.downloadProgress)
        : appBridge.downloadProgress

    function humanSize(bytes) {
        if (!bytes || bytes <= 0)
            return "unknown until download"
        return appBridge.formatBytes(bytes)
    }

    FolderDialog {
        id: folderPicker
        title: "Choose where downloads are saved"
        onAccepted: appBridge.setDownloadDir(selectedFolder)
    }

    // The page title matches Library's; card headers stay well below it.
    ColumnLayout {
        id: pageHeader
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.lg
        spacing: 2

        Label {
            objectName: "download.pageTitle"
            text: "Download"
            color: Theme.text
            font.pixelSize: Theme.fontH1
            font.bold: true
        }

        Label {
            objectName: "download.pageSubtitle"
            Layout.fillWidth: true
            text: "Paste a video link, inspect the formats, then save exactly what you want."
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
        anchors.bottom: actionBar.top
        anchors.margins: Theme.lg
        anchors.topMargin: Theme.md
        anchors.bottomMargin: Theme.sm
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(Theme.contentMaxWidth,
                            scroller.availableWidth - Theme.xs * 2)
            spacing: Theme.md

            // Room for the card shadow inside the clipped scroll area.
            Item { Layout.preferredHeight: Theme.xs }

            GridLayout {
                id: cardGrid
                Layout.fillWidth: true
                // Top-to-bottom flow puts Video/Format in the left column and
                // Subtitle/Save in the right one; one column below the breakpoint.
                rows: page.wide ? 2 : 4
                flow: GridLayout.TopToBottom
                columnSpacing: Theme.md
                rowSpacing: Theme.md

            // ================================================== SOURCE
            AppCard {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                title: "Video"

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    // Focal point once a link has been inspected: identity first,
                    // then the editable link underneath it.
                    RowLayout {
                        Layout.fillWidth: true
                        visible: appBridge.hasInfo
                        opacity: visible ? 1 : 0
                        Behavior on opacity {
                            NumberAnimation {
                                duration: Theme.reducedMotion ? 0 : 140
                                easing.type: Easing.OutCubic
                            }
                        }
                        spacing: Theme.md
                        Layout.alignment: Qt.AlignTop

                        MediaThumb {
                            objectName: "download.mediaThumb"
                            Layout.preferredWidth: page.wide ? 224 : 160
                            Layout.alignment: Qt.AlignTop
                            source: appBridge.videoThumbnail
                            duration: appBridge.videoDuration
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            spacing: 6

                            Label {
                                objectName: "download.heroTitle"
                                Layout.fillWidth: true
                                text: appBridge.videoTitle
                                color: Theme.text
                                font.pixelSize: Theme.fontH2
                                font.bold: true
                                wrapMode: Text.WordWrap
                            }

                            Label {
                                objectName: "download.heroChannel"
                                Layout.fillWidth: true
                                visible: appBridge.videoChannel !== ""
                                text: appBridge.videoChannel
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSmall
                                elide: Text.ElideRight
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.sm

                                Chip {
                                    text: appBridge.sourceLanguage !== ""
                                          ? appBridge.sourceLanguage.toUpperCase() : "language unknown"
                                    tone: ""
                                }
                                Chip {
                                    visible: appBridge.hasAv1
                                    text: "AV1"
                                    tone: "acc"
                                }
                                Chip {
                                    visible: appBridge.hasVp9
                                    text: "VP9"
                                    tone: ""
                                }
                                Chip {
                                    visible: appBridge.hasH264
                                    text: "H.264"
                                    tone: ""
                                }
                                Label {
                                    visible: page.hasSelection && appBridge.selectedFileSize > 0
                                    text: page.humanSize(appBridge.selectedFileSize) + " selected"
                                    color: Theme.textMuted
                                    font.pixelSize: Theme.fontSmall
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }
                    }

                    // The skeleton occupies the hero's exact geometry, so the
                    // real content arrives without a jump.
                    RowLayout {
                        objectName: "download.heroSkeleton"
                        Layout.fillWidth: true
                        visible: appBridge.infoLoading
                        spacing: Theme.md
                        Layout.alignment: Qt.AlignTop

                        MediaThumb {
                            Layout.preferredWidth: page.wide ? 224 : 160
                            Layout.alignment: Qt.AlignTop
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            spacing: 8

                            Accessible.role: Accessible.StaticText
                            Accessible.name: "Inspecting formats and subtitle tracks"

                            SkeletonBar {
                                Layout.fillWidth: true
                                Layout.maximumWidth: 440
                                Layout.preferredHeight: Theme.fontH2
                            }
                            SkeletonBar {
                                Layout.preferredWidth: 160
                                Layout.preferredHeight: Theme.fontSmall
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        CompactTextField {
                            id: urlField
                            objectName: "download.urlField"
                            Layout.fillWidth: true
                            // Without a hero the link is the page's focal control.
                            height: appBridge.hasInfo ? Theme.controlHeight
                                                      : Theme.controlHeight + Theme.sm
                            label: "Video URL"
                            placeholderText: "https://example.com/video?v=…"
                            text: appBridge.url
                            enabled: !page.busy
                            onTextEdited: appBridge.url = text
                            onAccepted: appBridge.url = text
                        }

                        AppButton {
                            objectName: "download.clearButton"
                            text: "Clear"
                            variant: "ghost"
                            enabled: !page.busy && appBridge.url !== ""
                            onClicked: appBridge.clearSource()
                        }

                        AppButton {
                            objectName: "download.inspectButton"
                            text: appBridge.infoLoading ? "Inspecting…" : "Inspect"
                            variant: "primary"
                            iconName: "search"
                            enabled: !page.busy && !appBridge.infoLoading && appBridge.url !== ""
                            onClicked: appBridge.inspect()
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: appBridge.infoError !== ""
                        text: appBridge.infoError
                        color: Theme.error
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: appBridge.url === "" && !appBridge.hasInfo
                        text: "Paste a video URL. The app detects formats and subtitle tracks automatically."
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ================================================== FORMAT
            AppCard {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                title: "Format"
                note: appBridge.infoLoading ? "Inspecting…" : (appBridge.hasInfo ? "Pick the exact stream you want" : "")

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        Label {
                            text: "Codec"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        BoundComboBox {
                            objectName: "download.codecCombo"
                            Layout.preferredWidth: 170
                            label: "Video codec"
                            enabled: appBridge.hasInfo && !page.busy
                            textRole: "label"
                            valueRole: "id"
                            model: appBridge.codecs
                            selectFirstWhenMissing: true
                            readValue: function () { return appBridge.selectedCodec }
                            writeValue: function (value) { appBridge.selectedCodec = value }
                        }

                        Label {
                            text: "Resolution"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        BoundComboBox {
                            objectName: "download.resolutionCombo"
                            Layout.preferredWidth: 130
                            label: "Resolution"
                            enabled: appBridge.hasInfo && !page.busy
                            textRole: "label"
                            valueRole: "value"
                            model: appBridge.resolutions
                            selectFirstWhenMissing: true
                            readValue: function () { return appBridge.selectedResolution }
                            writeValue: function (value) { appBridge.selectedResolution = value }
                        }

                        Item { Layout.fillWidth: true }
                    }

                    Label {
                        objectName: "download.selectedSummary"
                        visible: page.hasSelection
                        text: "Selected: " + (appBridge.selectedFormatLabel || "stream")
                              + " · " + page.humanSize(appBridge.selectedFileSize)
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    // Format rows arrive where the table will be; the text is
                    // exposed to assistive tech, not repeated as body copy.
                    ColumnLayout {
                        objectName: "download.formatSkeleton"
                        Layout.fillWidth: true
                        visible: appBridge.infoLoading
                        spacing: Theme.sm

                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Inspecting formats and subtitle tracks"

                        Repeater {
                            model: 4

                            SkeletonBar {
                                Layout.fillWidth: true
                                Layout.preferredHeight: Theme.rowHeight - Theme.xs * 2
                            }
                        }
                    }

                    FormatTable {
                        Layout.fillWidth: true
                        visible: !appBridge.infoLoading
                        opacity: visible ? 1 : 0
                        Behavior on opacity {
                            NumberAnimation {
                                duration: Theme.reducedMotion ? 0 : 140
                                easing.type: Easing.OutCubic
                            }
                        }
                        onPicked: function (codec, resolution) {
                            appBridge.selectedCodec = codec
                            appBridge.selectedResolution = String(resolution)
                        }
                    }

                    Label {
                        objectName: "download.selectionError"
                        Layout.fillWidth: true
                        visible: appBridge.selectionError !== ""
                        text: appBridge.selectionError
                        color: Theme.warning
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ============================================== SUBTITLE TRACK
            AppCard {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                title: "Subtitle"
                note: appBridge.hasInfo
                      ? (appBridge.hasSubtitleTracks
                         ? "Downloaded together with the video"
                         : "This video has no subtitle tracks")
                      : ""

                SubtitleTrackPicker {
                    Layout.fillWidth: true
                    enabled: appBridge.hasInfo && !page.busy
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: appBridge.hasInfo && appBridge.hasSubtitleTracks
                    spacing: Theme.sm

                    AppButton {
                        objectName: "download.subtitleOnlyButton"
                        text: "Fetch subtitle only"
                        iconName: "file"
                        variant: "ghost"
                        enabled: appBridge.selectedSubtitleTrack !== "" && !page.busy
                        onClicked: appBridge.downloadSubtitleOnly()
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "Selected: " + appBridge.selectedSubtitleLabel
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        elide: Text.ElideRight
                    }
                }
            }

            // ================================================== DOWNLOAD
            AppCard {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                title: "Save"

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        Label {
                            text: "Save to"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        Label {
                            objectName: "download.folderLabel"
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
                            variant: "ghost"
                            iconName: "folder"
                            enabled: !page.busy
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

                    Rectangle {
                        id: progressTrack
                        Layout.fillWidth: true
                        implicitHeight: Theme.xs + 4
                        radius: height / 2
                        color: Theme.inset
                        clip: true

                        Rectangle {
                            id: progressFill
                            height: parent.height
                            radius: parent.radius
                            width: page.indeterminateStage
                                   ? parent.width
                                   : parent.width * Math.max(0, Math.min(100, page.shownProgress)) / 100
                            color: page.indeterminateStage
                                   ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30)
                                   : appBridge.statusState === "failed" ? Theme.error
                                   : appBridge.statusState === "done" ? Theme.success
                                   : Theme.accent
                            // Easing would fight the indeterminate sweep and is
                            // exactly what reduced motion must remove.
                            Behavior on width {
                                enabled: !Theme.reducedMotion && !page.indeterminateStage
                                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                            }
                        }

                        Rectangle {
                            id: progressSweep
                            visible: page.indeterminateStage && !Theme.reducedMotion
                            width: parent.width * 0.28
                            height: parent.height
                            radius: height / 2
                            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.65)

                            SequentialAnimation on x {
                                running: progressSweep.visible
                                loops: Animation.Infinite
                                NumberAnimation {
                                    from: -progressSweep.width
                                    to: progressTrack.width
                                    duration: 1100
                                    easing.type: Easing.InOutQuad
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        Label {
                            objectName: "download.stageLabel"
                            text: page.busy
                                  ? (appBridge.downloadStage === "preparing" ? "Preparing…"
                                     : appBridge.downloadStage === "video" ? "Downloading video…"
                                     : appBridge.downloadStage === "audio" ? "Downloading audio…"
                                     : appBridge.downloadStage === "merging" ? "Merging audio and video…"
                                     : appBridge.downloadStage === "subtitle" ? "Downloading subtitle…"
                                     : "Working…")
                                  : (appBridge.downloadProgress >= 100 ? "Complete" : "Idle")
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        Item { Layout.fillWidth: true }

                        Label {
                            text: page.indeterminateStage
                                  ? "…"
                                  : page.shownProgress + "%"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                            font.family: Theme.monoFont
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        AppButton {
                            objectName: "download.resultVideoButton"
                            visible: appBridge.downloadedVideo !== ""
                            text: "Open video"
                            small: true
                            variant: "ghost"
                            iconName: "folder"
                            onClicked: appBridge.openFolderForPath(appBridge.downloadedVideo)
                        }

                        AppButton {
                            objectName: "download.resultSubtitleButton"
                            visible: appBridge.downloadedSubtitle !== ""
                            text: "Open subtitle"
                            small: true
                            variant: "ghost"
                            iconName: "file"
                            onClicked: appBridge.openFolderForPath(appBridge.downloadedSubtitle)
                        }

                        Item { Layout.fillWidth: true }
                    }

                    // Outcomes are reported per leg: a failed video download
                    // never hides the fact that the subtitle was saved, and the
                    // other way round.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        visible: appBridge.videoOutcome !== "" && !page.busy

                        Label {
                            text: "Video:"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                        }
                        StatusMark {
                            status: appBridge.videoOutcome === "ok" ? "ok"
                                 : appBridge.videoOutcome === "skipped" ? "na"
                                 : appBridge.videoOutcome === "cancelled" ? "todo" : "error"
                        }
                        Label {
                            text: appBridge.videoOutcome
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }

                        Item { Layout.preferredWidth: Theme.md }

                        Label {
                            visible: appBridge.subtitleOutcome !== "" && appBridge.subtitleOutcome !== "skipped"
                            text: "Subtitle:"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSmall
                        }
                        StatusMark {
                            visible: appBridge.subtitleOutcome !== "" && appBridge.subtitleOutcome !== "skipped"
                            status: appBridge.subtitleOutcome === "ok" ? "ok"
                                 : appBridge.subtitleOutcome === "cancelled" ? "todo" : "error"
                        }
                        Label {
                            visible: appBridge.subtitleOutcome !== "" && appBridge.subtitleOutcome !== "skipped"
                            text: appBridge.subtitleOutcome
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: appBridge.downloadNotice !== ""
                        text: appBridge.downloadNotice
                        color: Theme.warning
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }
                }
            }

            }  // cardGrid

            Item { Layout.preferredHeight: Theme.md }
        }
    }

    // D6: the primary action stays reachable without scrolling, at every
    // window size. The Save card keeps destination, progress, and outcomes.
    Item {
        id: actionBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.lg
        anchors.rightMargin: Theme.lg
        height: actionRow.implicitHeight + Theme.sm * 2

        Rectangle {
            anchors.fill: parent
            color: Theme.background
        }
        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: Theme.borderSoft
        }

        RowLayout {
            id: actionRow
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(Theme.contentMaxWidth,
                            actionBar.width - Theme.xs * 2)
            spacing: Theme.sm

            AppButton {
                objectName: "download.downloadButton"
                text: page.busy ? "Downloading…" : "Download"
                variant: "primary"
                iconName: "download"
                enabled: appBridge.canDownload
                onClicked: appBridge.download()
            }

            AppButton {
                objectName: "download.cancelButton"
                visible: page.busy
                text: "Cancel"
                variant: "danger"
                small: true
                iconName: "stop"
                onClicked: appBridge.cancelDownload()
            }

            Item { Layout.fillWidth: true }

            Label {
                visible: appBridge.blockedReason !== ""
                text: appBridge.blockedReason
                color: Theme.warning
                font.pixelSize: Theme.fontSmall
                elide: Text.ElideRight
                Layout.maximumWidth: 420
            }
        }
    }
}
