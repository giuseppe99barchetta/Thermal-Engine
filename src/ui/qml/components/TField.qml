import QtQuick
import QtQuick.Controls

TextField {
    id: control
    property string errorText: ""
    implicitHeight: Theme.controlHeight
    font.family: Theme.font
    font.pixelSize: 13
    color: Theme.text
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accentDark
    selectedTextColor: Theme.text
    leftPadding: 10
    rightPadding: 10
    background: Rectangle {
        color: Theme.input
        radius: Theme.radius
        border.width: 1
        border.color: control.errorText.length ? Theme.danger : control.activeFocus ? Theme.accent : Theme.border
    }
    opacity: enabled ? 1 : 0.45
}
