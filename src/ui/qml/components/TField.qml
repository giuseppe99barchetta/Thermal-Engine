import QtQuick
import QtQuick.Controls

TextField {
    id: control
    property string errorText: ""
    implicitHeight: Theme.fieldHeight
    font.family: Theme.uiFont
    font.hintingPreference: Font.PreferNoHinting
    font.pixelSize: 13
    color: Theme.text
    placeholderTextColor: Theme.muted
    selectionColor: Theme.selection
    selectedTextColor: Theme.text
    leftPadding: 10
    rightPadding: 10
    verticalAlignment: TextInput.AlignVCenter
    background: Rectangle {
        color: Theme.input
        radius: Theme.radiusSmall
        border.width: control.errorText.length || control.activeFocus ? 2 : 1
        border.color: control.errorText.length ? Theme.danger : control.activeFocus ? Theme.accent : Theme.borderStrong
    }
    opacity: enabled ? 1 : 0.45
}
