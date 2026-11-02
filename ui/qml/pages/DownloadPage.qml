import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."
import "../components"

// The one screen that matters: paste a URL, inspect, pick the exact stream in
// the matrix, choose a subtitle track, save. The reference draws it as a
// numbered flow beside a sticky summary; QML has no sticky layout, so this page
// positions the summary beside the scroll view.
Item {
    id: page

    objectName: "downloadPage"

    readonly property bool busy: appBridge.downloadRunning
    readonly property bool inspected: appBridge.hasInfo

    // Step 2 reads "done" once a *usable* pair is selected - the same fact the
    // Download button keys on, so the step can never claim more than the panel
    // will act on.
    readonly property bool hasFormat: !!appBridge.selectedOption.format_selector

    readonly property string step1State: inspected ? "done" : "cur"
    readonly property string step2State: !inspected ? "lock" : (hasFormat ? "done" : "cur")
    readonly property string step3State: inspected ? "" : "lock"
    readonly property string step4State: inspected ? "" : "lock"

    // The reference collapses ``.dl`` to one column under 1000px. Here the rail
    // and the page padding are already spent, so the test is whether the row
    // still leaves a usable matrix beside the panel.
    readonly property bool stacked: host.width < Theme.panelWidth + 480
    readonly property real rowWidth: Math.min(Theme.contentMaxWidth, host.width)
    readonly property real rowX: (host.width - rowWidth) / 2
    readonly property real panelW: stacked
        ? Math.min(Theme.panelWidth, rowWidth) : Theme.panelWidth
    readonly property real flowW: stacked
        ? rowWidth : Math.max(320, rowWidth - Theme.columnGap - panelW)
    readonly property real flowH: stacked
        ? Math.max(220, host.height - panel.implicitHeight - Theme.columnGap)
        : host.height

    FolderDialog {
        id: folderPicker
        title: "Choose where downloads are saved"
        onAccepted: appBridge.setDownloadDir(selectedFolder)
    }

    ColumnLayout {
        id: pageHeader
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: Theme.pagePaddingH
        anchors.rightMargin: Theme.pagePaddingH
        anchors.topMargin: Theme.pagePaddingV
        spacing: Theme.xs

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
            Layout.minimumWidth: 0
            text: "Paste a link, pick the exact stream, save it."
            color: Theme.textMuted
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideRight
        }
    }

    Item {
        id: host
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: pageHeader.bottom
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.pagePaddingH
        anchors.rightMargin: Theme.pagePaddingH
        anchors.topMargin: 22
        anchors.bottomMargin: Theme.md

        ScrollView {
            id: scroller
            objectName: "download.flowScroller"
            x: page.rowX
            y: 0
            width: page.flowW
            height: page.flowH
            clip: true
            contentWidth: availableWidth
            ScrollBar.vertical: AppScrollBar { }

            ColumnLayout {
                width: scroller.availableWidth
                spacing: 0

                // =============================================== 1 SOURCE
                StepItem {
                    Layout.fillWidth: true
                    number: 1
                    title: "Source"
                    state: page.step1State

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        CompactTextField {
                            objectName: "download.urlField"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            label: "Video URL"
                            placeholderText: "Paste a video URL"
                            text: appBridge.url
                            enabled: !page.busy
                            onTextEdited: appBridge.url = text
                            onAccepted: appBridge.url = text
                        }

                        AppButton {
                            objectName: "download.clearButton"
                            text: "Clear"
                            enabled: !page.busy && appBridge.url !== ""
                            onClicked: appBridge.clearSource()
                        }

                        AppButton {
                            objectName: "download.inspectButton"
                            text: appBridge.infoLoading ? "Inspecting…" : "Inspect"
                            variant: "primary"
                            enabled: !page.busy && !appBridge.infoLoading && appBridge.url !== ""
                            onClicked: appBridge.inspect()
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "Formats and subtitle tracks are detected automatically."
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }

                    Label {
                        objectName: "download.infoError"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        visible: appBridge.infoError !== ""
                        text: appBridge.infoError
                        color: Theme.error
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }

                    // The skeleton holds the hero's geometry, so inspecting
                    // never shifts the steps below it.
                    ColumnLayout {
                        objectName: "download.heroSkeleton"
                        Layout.fillWidth: true
                        Layout.topMargin: 14
                        visible: appBridge.infoLoading
                        spacing: Theme.sm

                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Inspecting formats and subtitle tracks"

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.md

                            MediaThumb {
                                Layout.preferredWidth: Theme.heroThumbWidth
                                Layout.alignment: Qt.AlignTop
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.alignment: Qt.AlignTop
                                spacing: 8

                                SkeletonBar {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Theme.heroTitleSize
                                }
                                SkeletonBar {
                                    Layout.preferredWidth: 160
                                    Layout.preferredHeight: Theme.fontSmall
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: 14
                        visible: page.inspected && !appBridge.infoLoading
                        opacity: visible ? 1 : 0
                        implicitHeight: heroRow.implicitHeight + 24
                        radius: Theme.radiusLg
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.border

                        Behavior on opacity {
                            NumberAnimation {
                                duration: Theme.reducedMotion ? 0 : 140
                                easing.type: Easing.OutCubic
                            }
                        }

                        RowLayout {
                            id: heroRow
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: Theme.md

                            MediaThumb {
                                objectName: "download.mediaThumb"
                                Layout.preferredWidth: Theme.heroThumbWidth
                                Layout.alignment: Qt.AlignTop
                                source: appBridge.videoThumbnail
                                duration: appBridge.videoDuration
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.alignment: Qt.AlignTop
                                spacing: 2

                                Label {
                                    objectName: "download.heroTitle"
                                    Layout.fillWidth: true
                                    text: appBridge.videoTitle
                                    color: Theme.text
                                    font.pixelSize: Theme.heroTitleSize
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                    lineHeight: 1.3
                                }

                                Label {
                                    objectName: "download.heroChannel"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    visible: appBridge.videoChannel !== ""
                                    text: appBridge.videoChannel
                                    color: Theme.textMuted
                                    font.pixelSize: Theme.fontSmall
                                    elide: Text.ElideRight
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 8
                                    spacing: 6

                                    Chip {
                                        text: appBridge.sourceLanguage !== ""
                                              ? appBridge.sourceLanguage.toUpperCase() + " audio"
                                              : "language unknown"
                                    }

                                    Chip {
                                        objectName: "download.heroIdChip"
                                        visible: appBridge.videoId !== ""
                                        clickable: true
                                        mono: true
                                        iconName: "copy"
                                        text: "ID " + appBridge.videoId
                                        onClicked: appBridge.copyVideoId()

                                        Accessible.name: "Copy video ID " + appBridge.videoId
                                    }

                                    Chip {
                                        visible: appBridge.hasAv1
                                        text: "AV1"
                                        tone: appBridge.selectedCodec === "av1" ? "acc" : ""
                                    }
                                    Chip {
                                        visible: appBridge.hasVp9
                                        text: "VP9"
                                        tone: appBridge.selectedCodec === "vp9" ? "acc" : ""
                                    }
                                    Chip {
                                        visible: appBridge.hasH264
                                        text: "H.264"
                                        tone: appBridge.selectedCodec === "h264" ? "acc" : ""
                                    }
                                }
                            }
                        }
                    }
                }

                // =============================================== 2 FORMAT
                StepItem {
                    Layout.fillWidth: true
                    number: 2
                    title: "Format"
                    note: appBridge.infoLoading ? "Inspecting…"
                          : (page.inspected ? "Pick the exact stream you want."
                                            : "Inspect a video to see what it offers.")
                    state: page.step2State

                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: appBridge.infoLoading
                        spacing: Theme.sm

                        Accessible.role: Accessible.StaticText
                        Accessible.name: "Inspecting formats and subtitle tracks"

                        Repeater {
                            model: 3

                            SkeletonBar {
                                Layout.fillWidth: true
                                Layout.preferredHeight: Theme.matrixCellHeight
                            }
                        }
                    }

                    FormatMatrix {
                        Layout.fillWidth: true
                        visible: page.inspected && !appBridge.infoLoading
                        busy: page.busy
                        onPicked: function (codec, resolution) {
                            appBridge.pickFormat(codec, resolution)
                        }
                    }
                }

                // ============================================ 3 SUBTITLE
                StepItem {
                    Layout.fillWidth: true
                    number: 3
                    title: "Subtitle"
                    note: page.inspected
                          ? (appBridge.hasSubtitleTracks
                             ? "Downloaded together with the video."
                             : "This video has no subtitle tracks.")
                          : "Downloaded together with the video."
                    state: page.step3State

                    SubtitleTrackPicker {
                        Layout.fillWidth: true
                        enabled: page.inspected && !page.busy
                    }

                    AppButton {
                        objectName: "download.subtitleOnlyButton"
                        text: "Fetch subtitle only"
                        small: true
                        visible: page.inspected
                        enabled: appBridge.selectedSubtitleTrack !== "" && !page.busy
                        onClicked: appBridge.downloadSubtitleOnly()
                    }
                }

                // ============================================= 4 SAVE TO
                StepItem {
                    Layout.fillWidth: true
                    number: 4
                    title: "Save to"
                    state: page.step4State
                    showConnector: false

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sm

                        Label {
                            objectName: "download.folderLabel"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: appBridge.downloadDir
                            color: Theme.text
                            font.pixelSize: Theme.fontTiny
                            font.family: Theme.monoFont
                            elide: Text.ElideMiddle
                        }

                        AppButton {
                            text: "Change…"
                            small: true
                            variant: "ghost"
                            enabled: !page.busy
                            onClicked: folderPicker.open()
                        }

                        AppButton {
                            text: "Open"
                            small: true
                            variant: "ghost"
                            onClicked: appBridge.openDownloadFolder()
                        }
                    }
                }

                Item { Layout.preferredHeight: Theme.lg }
            }
        }

        SummaryPanel {
            id: panel
            x: page.stacked
               ? page.rowX + (page.rowWidth - page.panelW) / 2
               : page.rowX + page.flowW + Theme.columnGap
            y: page.stacked ? page.flowH + Theme.columnGap : 0
            width: page.panelW
            height: implicitHeight
        }
    }
}
