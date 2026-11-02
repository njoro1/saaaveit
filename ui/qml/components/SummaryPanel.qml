import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The download summary (reference ``aside.panel``).
//
// Everything that describes the *job* - what will be fetched, how big, how far
// along, what to do next - lives here, so the four steps beside it stay about
// deciding. The reference pins this column with ``position: sticky``; QML has no
// sticky layout, so the page makes it a sibling of the scroll view and keeps it
// on screen by itself.
Rectangle {
    id: root

    objectName: "download.summaryPanel"
    color: "transparent"
    implicitWidth: Theme.panelWidth
    implicitHeight: card.implicitHeight

    property bool busy: appBridge.downloadRunning

    // The row the matrix says is pressed. ``formatRows`` carries the selection
    // flag, so the summary cannot disagree with the grid beside it.
    readonly property var chosen: {
        var rows = appBridge.formatRows
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].selected)
                return rows[i]
        }
        return null
    }

    readonly property string videoText: chosen === null
        ? "Not chosen"
        : (chosen.isBest ? "Best available" : chosen.codecLabel + " · " + chosen.resLabel)
    readonly property string subtitleText: appBridge.selectedSubtitleTrack === ""
        ? "None" : appBridge.selectedSubtitleLabel
    // The reference keeps the estimate honest: a specific stream reports its
    // filesize, "best" cannot be sized before the request is made, and a pair
    // that cannot be had reports nothing.
    readonly property string sizeText: chosen === null
        ? "—"
        : (chosen.isBest ? "Unknown until download" : chosen.sizeText)

    // Preparing and merging have no meaningful percentage: show the sweep the
    // reference shows rather than a bar frozen at zero.
    readonly property bool indeterminate: busy
        && (appBridge.downloadStage === "preparing"
            || appBridge.downloadStage === "merging")
    readonly property int shownProgress: busy
        ? Math.min(99, appBridge.downloadProgress)
        : appBridge.downloadProgress
    readonly property bool finished: appBridge.statusState === "done"
    readonly property bool failed: appBridge.statusState === "failed"
        || appBridge.statusState === "cancelled"

    readonly property string whyNot: busy || appBridge.canDownload
        ? "" : (appBridge.hasInfo ? "Choose a format to continue." : "Inspect a video first.")

    readonly property var legs: {
        var out = []
        if (appBridge.videoOutcome !== "")
            out.push({ id: "video", label: "Video", outcome: appBridge.videoOutcome })
        if (appBridge.subtitleOutcome !== "")
            out.push({ id: "subtitle", label: "Subtitle",
                       outcome: appBridge.subtitleOutcome })
        return out
    }

    function markFor(outcome) {
        if (outcome === "ok") return "ok"
        if (outcome === "skipped") return "na"
        if (outcome === "cancelled") return "unchecked"
        return "error"
    }

    function stageText() {
        if (busy) {
            if (appBridge.downloadStage === "preparing") return "Preparing…"
            if (appBridge.downloadStage === "video") return "Downloading video…"
            if (appBridge.downloadStage === "audio") return "Downloading audio…"
            if (appBridge.downloadStage === "merging") return "Merging audio and video…"
            if (appBridge.downloadStage === "subtitle") return "Downloading subtitle…"
            return "Working…"
        }
        if (appBridge.statusState === "cancelled") return "Cancelled"
        if (appBridge.statusState === "failed") return "Failed"
        return appBridge.downloadProgress >= 100 ? "Complete" : "Idle"
    }

    AppCard {
        id: card
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        // Outside a Layout a Rectangle keeps its own default height; this card
        // is sized by its content.
        height: implicitHeight
        padding: Theme.lg

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            // ------------------------------------------------------- identity
            MediaThumb {
                objectName: "download.panelThumb"
                Layout.fillWidth: true
                Layout.bottomMargin: 12
                source: appBridge.videoThumbnail
                duration: appBridge.videoDuration
            }

            // -------------------------------------- the three facts it was built from
            KeyValue {
                Layout.fillWidth: true
                key: "Video"
                valueName: "download.summaryVideo"
                value: root.videoText
            }

            KeyValue {
                Layout.fillWidth: true
                key: "Subtitle"
                valueName: "download.summarySubtitle"
                value: root.subtitleText
            }

            KeyValue {
                Layout.fillWidth: true
                key: "Size"
                valueName: "download.summarySize"
                value: root.sizeText
                mono: true
            }

            // ------------------------------------------------------- progress
            Rectangle {
                objectName: "download.progressTrack"
                Layout.fillWidth: true
                Layout.topMargin: 14
                Layout.bottomMargin: 6
                implicitHeight: 8
                radius: height / 2
                color: Theme.inset
                clip: true

                Rectangle {
                    id: barFill
                    objectName: "download.progressFill"
                    height: parent.height
                    radius: parent.radius
                    opacity: root.indeterminate ? 0.7 : 1.0
                    width: root.indeterminate
                           ? parent.width * 0.3
                           : parent.width * Math.max(0, Math.min(100, root.shownProgress)) / 100
                    color: root.finished ? Theme.success
                           : (root.failed ? Theme.error : Theme.accent)

                    // ``@keyframes ind`` walks a 30% block across the track.
                    SequentialAnimation on x {
                        running: root.indeterminate && !Theme.reducedMotion
                        loops: Animation.Infinite
                        NumberAnimation {
                            from: -barFill.width
                            to: barFill.parent.width
                            duration: 1100
                            easing.type: Easing.InOutQuad
                        }
                    }

                    Behavior on width {
                        enabled: !Theme.reducedMotion && !root.indeterminate
                        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                    }
                    Behavior on color {
                        enabled: !Theme.reducedMotion
                        ColorAnimation { duration: 140 }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    objectName: "download.stageLabel"
                    text: root.stageText()
                    color: Theme.text
                    font.pixelSize: Theme.fontSmall
                }

                Item { Layout.fillWidth: true }

                Label {
                    objectName: "download.progressValue"
                    text: root.indeterminate ? "…"
                          : (root.shownProgress > 0 || root.finished
                             ? root.shownProgress + "%" : "")
                    color: Theme.text
                    font.pixelSize: Theme.fontSmall
                    font.family: Theme.monoFont
                }
            }

            // ----------------------------------------------------------- legs
            ColumnLayout {
                Layout.fillWidth: true
                Layout.topMargin: 6
                spacing: 0
                visible: root.legs.length > 0

                Repeater {
                    model: root.legs

                    RowLayout {
                        required property var modelData
                        required property int index

                        Layout.fillWidth: true
                        Layout.topMargin: index > 0 ? 6 : 0
                        spacing: 8

                        Label {
                            objectName: "download.leg." + modelData.id
                            text: modelData.label
                            color: Theme.text
                            font.pixelSize: Theme.fontSmall
                        }

                        StatusMark {
                            status: root.markFor(modelData.outcome)
                            text: modelData.outcome
                        }

                        Item { Layout.fillWidth: true }
                    }
                }
            }

            AppButton {
                objectName: "download.openFolderButton"
                Layout.topMargin: 10
                visible: appBridge.downloadedVideo !== ""
                         || appBridge.downloadedSubtitle !== ""
                text: "Open video folder"
                small: true
                onClicked: appBridge.openDownloadFolder()
            }

            Label {
                objectName: "download.notice"
                Layout.fillWidth: true
                Layout.topMargin: 10
                Layout.minimumWidth: 0
                visible: appBridge.downloadNotice !== ""
                text: appBridge.downloadNotice
                color: Theme.warning
                font.pixelSize: Theme.fontSmall
                wrapMode: Text.WordWrap
            }

            // ------------------------------------------------------ the action
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 16
                spacing: 8

                AppButton {
                    objectName: "download.downloadButton"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.primaryActionHeight
                    text: root.busy ? "Downloading…" : "Download"
                    variant: "primary"
                    centered: true
                    enabled: appBridge.canDownload
                    onClicked: appBridge.download()
                }

                AppButton {
                    objectName: "download.cancelButton"
                    Layout.preferredHeight: Theme.primaryActionHeight
                    visible: root.busy
                    text: "Cancel"
                    variant: "danger"
                    onClicked: appBridge.cancelDownload()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 10
                spacing: 0

                Label {
                    objectName: "download.whyNot"
                    visible: root.whyNot !== ""
                    text: root.whyNot
                    color: Theme.warning
                    font.pixelSize: Theme.fontSmall
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    wrapMode: Text.WordWrap
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 6
                spacing: 0

                // The reason is derived from the readiness list and can be long.
                // A Layout sizes a non-filling item to its full implicit width and
                // lets it overflow the row, so this one fills and elides instead.
                Label {
                    objectName: "download.blockedReason"
                    visible: appBridge.blockedReason !== ""
                    text: appBridge.blockedReason
                    color: Theme.warning
                    font.pixelSize: Theme.fontSmall
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.maximumWidth: 420
                }
            }

            // ``.ban``: the explanation outlives the failed run on purpose, so
            // a user who tabs back later still finds the reason - and the doors.
            FailureBanner {
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                visible: appBridge.failureActive
            }
        }
    }
}
