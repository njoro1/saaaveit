import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// The codec x resolution matrix (reference ``.mx``).
//
// One column per detected codec, one row per resolution *any* codec offers, and
// a cell only where that exact pair exists - so an unavailable pair is a slot
// the user can see but not press, instead of an option that silently downloads
// something else. ``formatRows`` is flat and sorted best-first, so the grid is
// assembled from the same list the tests assert on.
//
// Above the grid sits the full-width escape hatch ("let the app choose"), below
// it the ffmpeg note and, when the pair cannot be had, the reason.
ColumnLayout {
    id: root

    objectName: "download.formatMatrix"
    spacing: 0

    signal picked(string codec, string resolution)

    readonly property var entries: appBridge.formatRows

    // ``appBridge.codecs`` is in the source's codec order (AV1, VP9, H.264) with
    // the "best" pseudo-codec last - that entry is the button, not a column.
    readonly property var columns: {
        var out = []
        var source = appBridge.codecs
        for (var i = 0; i < source.length; i++) {
            if (source[i].id !== "best")
                out.push({ id: source[i].id, label: source[i].label })
        }
        return out
    }

    readonly property var heights: {
        var out = []
        for (var i = 0; i < entries.length; i++) {
            var entry = entries[i]
            if (!entry.isBest && out.indexOf(entry.resolution) === -1)
                out.push(entry.resolution)
        }
        return out.sort(function (a, b) { return b - a })
    }

    readonly property var bestEntry: {
        for (var i = 0; i < entries.length; i++)
            if (entries[i].isBest)
                return entries[i]
        return null
    }

    readonly property bool hasFormats: entries.length > 0

    function entryAt(codec, height) {
        for (var i = 0; i < entries.length; i++) {
            var entry = entries[i]
            if (!entry.isBest && entry.codec === codec && entry.resolution === height)
                return { index: i, entry: entry }
        }
        return { index: -1, entry: null }
    }

    // One flat model for a single GridLayout: the empty corner, the codec
    // headers, then a resolution label followed by its cells.
    readonly property var slots: {
        var out = [{ kind: "corner", label: "" }]
        for (var c = 0; c < columns.length; c++)
            out.push({ kind: "head", label: columns[c].label })
        for (var h = 0; h < heights.length; h++) {
            out.push({ kind: "label", label: heights[h] + "p" })
            for (var c2 = 0; c2 < columns.length; c2++) {
                var found = entryAt(columns[c2].id, heights[h])
                out.push({ kind: "cell", label: columns[c2].label,
                           codec: columns[c2].id, resolution: heights[h],
                           index: found.index, entry: found.entry })
            }
        }
        return out
    }

    // ============================================================ best option
    AppButton {
        objectName: "download.bestCell"
        Layout.fillWidth: true
        visible: root.hasFormats
        text: "Best available — let the app choose"
        selected: root.bestEntry !== null && root.bestEntry.selected
        onClicked: root.picked("best", "best")

        Accessible.name: text + (selected ? ", selected" : "")
    }

    // ================================================================ the grid
    GridLayout {
        objectName: "download.matrixGrid"
        Layout.fillWidth: true
        Layout.topMargin: 10
        visible: root.columns.length > 0 && root.heights.length > 0
        columns: root.columns.length + 1
        columnSpacing: Theme.matrixGap
        rowSpacing: Theme.matrixGap

        Repeater {
            model: root.slots

            Item {
                id: slot
                required property var modelData

                readonly property string kind: modelData.kind
                // Only a ``cell`` slot carries an entry, and an offered pair has
                // a non-null one. Testing against null alone would make the
                // header and label slots look offered (``undefined !== null``).
                readonly property bool offered: kind === "cell" && modelData.entry !== null
                // Headers and cells share the leftover width; the label column
                // is the reference's fixed 72px.
                readonly property bool spans: kind === "cell" || kind === "head"
                readonly property int boxHeight: kind === "cell" || kind === "label"
                                                 ? Theme.matrixCellHeight
                                                 : Theme.fontSmall + 7

                Layout.fillWidth: spans
                Layout.preferredWidth: spans ? 0 : Theme.matrixLabelWidth
                Layout.minimumWidth: spans ? 44 : Theme.matrixLabelWidth
                Layout.preferredHeight: boxHeight

                // --- column header ---------------------------------------
                Label {
                    anchors.fill: parent
                    visible: slot.kind === "head"
                    text: slot.modelData.label
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                    font.weight: Font.Medium
                    leftPadding: 4
                    verticalAlignment: Text.AlignBottom
                }

                // --- row label -------------------------------------------
                Label {
                    anchors.fill: parent
                    visible: slot.kind === "label"
                    text: slot.modelData.label
                    color: Theme.text
                    font.pixelSize: Theme.fontTiny
                    font.family: Theme.monoFont
                    font.weight: Font.DemiBold
                    leftPadding: 4
                    verticalAlignment: Text.AlignVCenter
                }

                // --- offered pair ----------------------------------------
                Button {
                    id: cell
                    anchors.fill: parent
                    visible: slot.kind === "cell" && slot.offered
                    objectName: slot.modelData.index >= 0
                                 ? "download.formatRow." + slot.modelData.index : ""
                    // ``Button`` has no selection state; this is the one the
                    // background and the bold label read.
                    property bool selected: slot.offered && slot.modelData.entry.selected
                    padding: 0
                    spacing: 0

                    Keys.onReturnPressed: if (enabled) clicked()
                    Keys.onEnterPressed: if (enabled) clicked()
                    onClicked: root.picked(slot.modelData.codec,
                                           String(slot.modelData.resolution))

                    background: Rectangle {
                        radius: Theme.radiusMd
                        // `.cell` is `s1`, its hover `s2`, its pressed state the
                        // accent tint with a 2px accent line and bold words.
                        color: cell.selected ? Theme.accentSoft
                               : (cell.hovered ? Theme.surfaceAlt : Theme.surface)
                        border.width: cell.selected ? 2 : 1
                        border.color: cell.selected ? Theme.accentLine
                                      : (cell.hovered ? Theme.borderStrong : Theme.border)
                        Behavior on color {
                            ColorAnimation { duration: Theme.reducedMotion ? 0 : 140 }
                        }
                    }

                    contentItem: ColumnLayout {
                        spacing: 1

                        Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: slot.offered ? slot.modelData.entry.sizeText : ""
                            color: Theme.text
                            font.pixelSize: Theme.fontBody
                            font.weight: slot.offered && slot.modelData.entry.selected
                                         ? Font.Bold : Font.Normal
                        }

                        Label {
                            Layout.alignment: Qt.AlignHCenter
                            text: slot.offered
                                   ? (slot.modelData.entry.merge ? "merge" : "single file")
                                   : ""
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontTiny
                            // `.cell[aria-pressed=true]{font-weight:700}` lifts the
                            // whole cell, its `small` included.
                            font.weight: slot.offered && slot.modelData.entry.selected
                                         ? Font.Bold : Font.Normal
                        }
                    }

                    Accessible.role: Accessible.Button
                    Accessible.name: slot.offered
                        ? slot.modelData.label + " " + slot.modelData.resolution + "p, "
                          + slot.modelData.entry.sizeText : ""
                }

                // --- pair this codec does not serve -----------------------
                // The reference draws this as a disabled button with a dashed
                // `b1` border. Qt's Rectangle has no dashed border and a Shape
                // per cell is not worth a repaint, so the fact is carried by
                // the single muted glyph instead - which is the part that is
                // actually legible at 1.2:1.
                Rectangle {
                    anchors.fill: parent
                    visible: slot.kind === "cell" && !slot.offered
                    radius: Theme.radiusMd
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.border

                    Label {
                        anchors.centerIn: parent
                        text: "—"
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontBody
                    }

                    Accessible.role: Accessible.StaticText
                    Accessible.name: slot.modelData.label + " "
                                     + slot.modelData.resolution + "p is not offered"
                }
            }
        }
    }

    // ================================================================= notes
    Label {
        Layout.fillWidth: true
        Layout.topMargin: 8
        visible: root.hasFormats
        text: "“Merge” means video and audio are fetched separately and joined with ffmpeg."
        color: Theme.textMuted
        font.pixelSize: Theme.fontSmall
        wrapMode: Text.WordWrap
    }

    Label {
        objectName: "download.selectionError"
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        Layout.topMargin: 8
        visible: appBridge.selectionError !== ""
        text: appBridge.selectionError
        color: Theme.warning
        font.pixelSize: Theme.fontSmall
        wrapMode: Text.WordWrap
    }
}
