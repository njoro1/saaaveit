import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Subtitle picker: only "None" and the English track shown as radios;
// all other tracks live in a dropdown.
ColumnLayout {
    id: root
    objectName: "download.subtitleTracks"
    spacing: 4

    readonly property var tracks: appBridge.subtitleTracks
    readonly property string selected: appBridge.selectedSubtitleTrack

    function choose(code) {
        appBridge.selectedSubtitleTrack = code
    }

    function englishTrack() {
        for (var i = 0; i < root.tracks.length; i++) {
            var t = root.tracks[i]
            if (t && t.language === "en" && t.kind === "manual")
                return t
            // fallback: any track whose label/code indicates English
            if (t && t.code && (t.code.indexOf("en") === 0 || t.label.indexOf("English") >= 0))
                return t
        }
        return null
    }

    function nonEnglishTracks() {
        var result = []
        for (var i = 0; i < root.tracks.length; i++) {
            var t = root.tracks[i]
            if (t && !(t.code === root.selected || (t.language === "en" && t.kind === "manual") || (t.code && (t.code.indexOf("en") === 0 || t.label.indexOf("English") >= 0)))) {
                // Only add if it's not the selected one and not the default English one
                // Actually we want to include all non-English tracks regardless
                if (t.code && !(t.code.indexOf("en") === 0 || (t.label && t.label.indexOf("English") >= 0))) {
                    result.push(t)
                }
            }
        }
        return result
    }

    // Helper to collect tracks for dropdown
    property var dropdownTracks: {
        var list = []
        var eng = englishTrack()
        for (var i = 0; i < root.tracks.length; i++) {
            var t = root.tracks[i]
            if (t) {
                if (!eng || t.code !== eng.code) {
                    // exclude default English from dropdown
                    if (!(t.code && (t.code.indexOf("en") === 0 || (t.label && t.label.indexOf("English") >= 0)))) {
                        list.push(t)
                    }
                }
            }
        }
        return list
    }

    // None option
    Rectangle {
        id: noneItem
        Layout.fillWidth: true
        implicitHeight: 34
        radius: Theme.radiusSm
        color: root.selected === "" ? Theme.accentSoft : (noneMouse.containsMouse ? Theme.surfaceAlt : "transparent")
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 10
            spacing: 8
            Rectangle {
                implicitWidth: 14; implicitHeight: 14; radius: 7
                color: "transparent"
                border.width: root.selected === "" ? 4 : 1
                border.color: root.selected === "" ? Theme.accent : Theme.borderStrong
            }
            Label {
                Layout.fillWidth: true
                text: "None — video only"
                color: root.selected === "" ? Theme.text : Theme.textDim
                font.pixelSize: Theme.fontSmall
                font.bold: root.selected === ""
            }
        }
        MouseArea {
            id: noneMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.choose("")
        }
    }

    // Default English option
    Rectangle {
        id: engItem
        Layout.fillWidth: true
        implicitHeight: 34
        radius: Theme.radiusSm
        visible: englishTrack() !== null
        property var track: englishTrack()
        color: (data && data.code === root.selected) ? Theme.accentSoft : (engMouse.containsMouse ? Theme.surfaceAlt : "transparent")
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 10
            spacing: 8
            Rectangle {
                implicitWidth: 14; implicitHeight: 14; radius: 7
                color: "transparent"
                border.width: (engItem.track && engItem.track.code === root.selected) ? 4 : 1
                border.color: (engItem.track && engItem.track.code === root.selected) ? Theme.accent : Theme.borderStrong
            }
            Label {
                Layout.fillWidth: true
                text: (engItem.track ? engItem.track.label : "English")
                color: (engItem.track && engItem.track.code === root.selected) ? Theme.text : Theme.textDim
                font.pixelSize: Theme.fontSmall
                font.bold: (engItem.track && engItem.track.code === root.selected)
            }
            Label {
                visible: !!(engItem.track && engItem.track.isOriginal)
                text: "original"
                color: Theme.textMuted
                font.pixelSize: Theme.fontTiny
            }
        }
        MouseArea {
            id: engMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: engItem.track ? root.choose(engItem.track.code) : root.choose("")
        }
    }

    // Dropdown for remaining tracks
    ComboBox {
        Layout.fillWidth: true
        visible: dropdownTracks.length > 0
        model: dropdownTracks
        textRole: "label"
        valueRole: "code"
        currentIndex: dropdownTracks.findIndex(function(t) { return t.code === root.selected })
        onActivated: function(index) {
            if (index >= 0 && dropdownTracks[index])
                root.choose(dropdownTracks[index].code)
        }
        displayText: currentIndex >= 0 ? dropdownTracks[currentIndex].label : "More subtitle tracks…"
        indicator: Canvas {
            x: parent.width - width - parent.padding
            y: parent.topPadding + (parent.availableHeight - height) / 2
            width: 12; height: 8
            onPaint: {
                var ctx = getContext("2d")
                ctx.fillStyle = Theme.textDim
                ctx.beginPath()
                ctx.moveTo(0, 0)
                ctx.lineTo(width, 0)
                ctx.lineTo(width/2, height)
                ctx.closePath()
                ctx.fill()
            }
        }
        background: Rectangle {
            color: parent.hovered ? Theme.surfaceAlt : Theme.inset
            border.color: Theme.border
            border.width: 1
            radius: Theme.radiusSm
        }
    }

    Label {
        Layout.fillWidth: true
        visible: root.tracks.length === 0
        text: "This video publishes no subtitle tracks. You can still download the video."
        color: Theme.textMuted
        font.pixelSize: Theme.fontSmall
        wrapMode: Text.WordWrap
    }
}
