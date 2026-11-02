import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Subtitle picker: "None" and the English track as `.radio` rows; every other
// track lives in the dropdown, exactly like the reference.
ColumnLayout {
    id: root
    objectName: "download.subtitleTracks"
    spacing: 6

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
        implicitHeight: 40
        radius: Theme.radiusMd
        color: root.selected === "" ? Theme.accentSoft
               : (noneMouse.containsMouse ? Theme.surfaceAlt : Theme.surface)
        border.width: noneItem.activeFocus ? 2 : 1
        border.color: root.selected === "" || noneItem.activeFocus
                      ? Theme.accentLine : Theme.border
        activeFocusOnTab: true

        Keys.onReturnPressed: root.choose("")
        Keys.onSpacePressed: root.choose("")

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10

            // `.radio i` - the ring thickens to a filled dot when checked.
            Rectangle {
                implicitWidth: 16
                implicitHeight: 16
                radius: 8
                color: "transparent"
                border.width: root.selected === "" ? 5 : 2
                border.color: root.selected === "" ? Theme.accent : Theme.borderStrong
            }

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: "None — video only"
                color: root.selected === "" ? Theme.text : Theme.textDim
                font.pixelSize: Theme.fontBody
                font.weight: root.selected === "" ? Font.DemiBold : Font.Normal
            }
        }

        MouseArea {
            id: noneMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.choose("")
        }

        Accessible.role: Accessible.RadioButton
        Accessible.checked: root.selected === ""
        Accessible.name: "None — video only"
    }

    // Default English option
    Rectangle {
        id: engItem
        objectName: "download.trackEnglish"
        Layout.fillWidth: true
        implicitHeight: 40
        visible: englishTrack() !== null
        property var track: englishTrack()
        readonly property bool checked: track !== null && track.code === root.selected
        radius: Theme.radiusMd
        color: checked ? Theme.accentSoft
               : (engMouse.containsMouse ? Theme.surfaceAlt : Theme.surface)
        border.width: engItem.activeFocus ? 2 : 1
        border.color: checked || engItem.activeFocus ? Theme.accentLine : Theme.border
        activeFocusOnTab: true

        Keys.onReturnPressed: engItem.track ? root.choose(engItem.track.code) : root.choose("")
        Keys.onSpacePressed: engItem.track ? root.choose(engItem.track.code) : root.choose("")

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10

            Rectangle {
                implicitWidth: 16
                implicitHeight: 16
                radius: 8
                color: "transparent"
                border.width: engItem.checked ? 5 : 2
                border.color: engItem.checked ? Theme.accent : Theme.borderStrong
            }

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: engItem.track ? engItem.track.label : "English"
                color: engItem.checked ? Theme.text : Theme.textDim
                font.pixelSize: Theme.fontBody
                font.weight: engItem.checked ? Font.DemiBold : Font.Normal
            }

            // `.chip.a` pushed to the right edge, exactly as the reference does
            // for the original track.
            Chip {
                visible: !!(engItem.track && engItem.track.isOriginal)
                text: "original"
                tone: "acc"
            }
        }

        MouseArea {
            id: engMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: engItem.track ? root.choose(engItem.track.code) : root.choose("")
        }

        Accessible.role: Accessible.RadioButton
        Accessible.checked: engItem.checked
        Accessible.name: engItem.track ? engItem.track.label : "English"
    }

    // Dropdown for the remaining tracks. A BoundComboBox, like every other
    // dropdown: the raw control opened a Basic-style popup, and binding
    // ``currentIndex`` directly is the failure mode BoundComboBox exists to
    // avoid (the widget's own assignment destroys the binding after the first
    // pick, so it stops mirroring the store).
    BoundComboBox {
        objectName: "download.subtitleMore"
        Layout.fillWidth: true
        Layout.topMargin: 4
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
        Layout.minimumWidth: 0
        visible: root.tracks.length === 0
        text: "This video publishes no subtitle tracks. You can still download the video."
        color: Theme.textMuted
        font.pixelSize: Theme.fontSmall
        wrapMode: Text.WordWrap
    }
}
