import QtQuick
import QtQuick.Controls

// One-click colors: recent picks first, then the theme's own palette
Flow {
    id: swatches
    property var colors: []
    signal picked(string color)
    spacing: 4
    Repeater {
        model: swatches.colors
        Rectangle {
            required property string modelData
            width: 18
            height: 18
            radius: 4
            color: modelData
            border.color: swatchMouse.containsMouse ? Theme.accent : Theme.border
            border.width: swatchMouse.containsMouse ? 2 : 1
            Accessible.role: Accessible.Button
            Accessible.name: "Use color " + modelData
            MouseArea {
                id: swatchMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: swatches.picked(parent.modelData)
            }
            ToolTip.text: modelData
            ToolTip.visible: swatchMouse.containsMouse
            ToolTip.delay: 400
        }
    }
}
