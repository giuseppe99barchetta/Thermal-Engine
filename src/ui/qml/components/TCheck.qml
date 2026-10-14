import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    font.family: Theme.font
    font.pixelSize: 13
    implicitHeight: 36
    spacing: 10
    indicator: Rectangle {
        x: control.leftPadding
        y: (control.height - height) / 2
        width: 18
        height: 18
        radius: 4
        color: control.checked ? Theme.accent : Theme.input
        border.color: control.activeFocus ? Theme.accent : Theme.border
        TIcon {
            anchors.centerIn: parent
            name: "check"
            visible: control.checked
            stroke: Theme.background
            width: 16
            height: 16
        }
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: control.enabled ? Theme.secondary : Theme.muted
        leftPadding: 28
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
    }
}
