import QtQuick

// Stroke icons on a 16px grid (stroke 1.6). "color" tints the glyph; "stroke" is kept for older callers.
Item {
    id: icon
    property string name: ""
    property color color: Theme.secondary
    property color stroke: color
    implicitWidth: 16
    implicitHeight: 16
    readonly property var paths: ({
            layers: "M8 2L2 5.2L8 8.4L14 5.2ZM2 8.2L8 11.4L14 8.2M2 11L8 14.2L14 11",
            presets: "M2.5 2.5H7V7H2.5ZM9 2.5H13.5V7H9ZM2.5 9H7V13.5H2.5ZM9 9H13.5V13.5H9Z",
            sensors: "M1.5 8H4.5L6.3 3.5L9.7 12.5L11.5 8H14.5",
            settings: "M10.2 8A2.2 2.2 0 1 1 5.8 8A2.2 2.2 0 1 1 10.2 8ZM8 1.8V3.4M8 12.6V14.2M1.8 8H3.4M12.6 8H14.2M3.6 3.6L4.7 4.7M11.3 11.3L12.4 12.4M3.6 12.4L4.7 11.3M11.3 4.7L12.4 3.6",
            cursor: "M3.5 2.5L12.5 6.7L8.5 8.1L7.1 12.1Z",
            hand: "M8 2V14M2 8H14M8 2L6.3 3.7M8 2L9.7 3.7M8 14L6.3 12.3M8 14L9.7 12.3M2 8L3.7 6.3M2 8L3.7 9.7M14 8L12.3 6.3M14 8L12.3 9.7",
            grid: "M2.5 2.5H13.5V13.5H2.5ZM2.5 6.2H13.5M2.5 9.8H13.5M6.2 2.5V13.5M9.8 2.5V13.5",
            snap: "M4 2.5V7.5A4 4 0 0 0 12 7.5V2.5M4 5.5H6.5M9.5 5.5H12",
            undo: "M5.5 3L2.5 6L5.5 9M2.5 6H10A3.5 3.5 0 0 1 10 13H7",
            redo: "M10.5 3L13.5 6L10.5 9M13.5 6H6A3.5 3.5 0 0 0 6 13H9",
            eye: "M1.5 8S4 3.5 8 3.5S14.5 8 14.5 8S12 12.5 8 12.5S1.5 8 1.5 8ZM9.8 8A1.8 1.8 0 1 1 6.2 8A1.8 1.8 0 1 1 9.8 8Z",
            hidden: "M1.5 8S4 3.5 8 3.5S14.5 8 14.5 8S12 12.5 8 12.5S1.5 8 1.5 8ZM3 13L13 3",
            lock: "M3.5 7H12.5V13.5H3.5ZM5.5 7V5A2.5 2.5 0 0 1 10.5 5V7",
            unlock: "M3.5 7H12.5V13.5H3.5ZM5.5 7V5A2.5 2.5 0 0 1 10.5 5",
            plus: "M8 3V13M3 8H13",
            minus: "M3.5 8H12.5",
            search: "M11.2 7A4.2 4.2 0 1 1 2.8 7A4.2 4.2 0 1 1 11.2 7ZM10.2 10.2L13.5 13.5",
            chevron: "M4 6L8 10L12 6",
            check: "M3.5 8.5L6.5 11.5L12.5 4.5",
            send: "M2.5 8H11.5M8 4L12 8L8 12",
            more: "M3.5 8H3.6M8 8H8.1M12.5 8H12.6",
            close: "M4 4L12 12M12 4L4 12",
            trash: "M3 4.5H13M6.5 4.5V3H9.5V4.5M4.5 4.5L5.1 13H10.9L11.5 4.5M7 7V11M9 7V11",
            copy: "M5.5 5.5H12.5V12.5H5.5ZM10.5 5.5V2.5H2.5V10.5H5.5",
            type: "M3 4H13M8 4V13",
            image: "M2 3H14V13H2ZM7.1 6.1A1.1 1.1 0 1 1 4.9 6.1A1.1 1.1 0 1 1 7.1 6.1ZM3 12L6.5 8.8L9 10.8L11 9L14 12",
            gauge: "M2.5 11.5A5.5 5.5 0 1 1 13.5 11.5M8 8L10.5 5.5"
        })
    function css(c) {
        return "rgb(" + Math.round(c.r * 255) + "," + Math.round(c.g * 255) + "," + Math.round(c.b * 255) + ")";
    }
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(width * 2, height * 2)
        source: "data:image/svg+xml;utf8," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='none' stroke='" + icon.css(icon.stroke) + "' stroke-opacity='" + icon.stroke.a + "' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round' d='" + (icon.paths[icon.name] || "") + "'/></svg>")
    }
}
