import QtQuick
import QtQuick.Controls

MenuItem {
    id: control
    implicitHeight: Theme.controlHeight
    font.family: Theme.font
    font.pixelSize: 13
    leftPadding: 10
    rightPadding: 10
    background: Rectangle {
        implicitWidth: 212
        implicitHeight: Theme.controlHeight
        radius: 6
        color: control.down ? Theme.border : control.highlighted ? Theme.accentDark : "transparent"
    }
}
