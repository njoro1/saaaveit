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
        objectName: "download.trackNone"
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
        objectName: "download.trackEnglish"
        Layout.fillWidth: true
        implicitHeight: 34
        radius: Theme.radiusSm
        visible: englishTrack() !== null
        property var track: englishTrack()
        color: (engItem.track && engItem.track.code === root.selected)
               ? Theme.accentSoft
               : (engMouse.containsMouse ? Theme.surfaceAlt : "transparent")
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

    // Dropdown for the remaining tracks. A BoundComboBox, like every other
    // dropdown: the raw control opened a Basic-style popup, and binding
    // ``currentIndex`` directly is the failure mode BoundComboBox exists to
    // avoid (the widget's own assignment destroys the binding after the first
    // pick, so it stops mirroring the store).
    BoundComboBox {
        objectName: "download.subtitleMore"
        Layout.fillWidth: true
        visible: root.dropdownTracks.length > 0
        label: "More subtitle tracks"
        model: root.dropdownTracks
        textRole: "label"
        valueRole: "code"
        // A track that is not in this list (the English one, or "None") leaves
        // the index at -1, which is what the placeholder is for.
        selectFirstWhenMissing: false
        readValue: function() { return root.selected }
        writeValue: function(value) { root.choose(value) }
        displayText: currentIndex >= 0 && currentIndex < root.dropdownTracks.length
                     ? root.dropdownTracks[currentIndex].label
                     : "More subtitle tracks…"
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
