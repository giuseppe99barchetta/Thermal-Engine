import QtQuick

Item {
    id: icon
    property string name: ""
    property color stroke: Theme.secondary
    implicitWidth: 18
    implicitHeight: 18
    readonly property var paths: ({
            undo: "M8 5L3 10L8 15M3 10H14C23 10 23 21 14 21",
            redo: "M16 5L21 10L16 15M21 10H10C1 10 1 21 10 21",
            eye: "M2 12C8 3 16 3 22 12C16 21 8 21 2 12ZM15 12A3 3 0 1 1 9 12A3 3 0 1 1 15 12",
            hidden: "M2 12C8 3 16 3 22 12C16 21 8 21 2 12ZM3 3L21 21",
            lock: "M5 10H19V21H5ZM8 10V7C8 1 16 1 16 7V10",
            unlock: "M5 10H19V21H5ZM8 10V7C8 1 16 1 16 7",
            check: "M5 12L10 17L19 7",
            chevron: "M6 9L12 15L18 9"
        })
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(width * 2, height * 2)
        source: "data:image/svg+xml;utf8," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='none' stroke='" + icon.stroke + "' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round' d='" + (icon.paths[icon.name] || "") + "'/></svg>")
    }
}
