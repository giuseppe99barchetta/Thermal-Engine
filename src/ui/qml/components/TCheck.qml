import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    font.family: Theme.uiFont
    font.hintingPreference: Font.PreferNoHinting
    font.pixelSize: 13
    implicitHeight: Theme.controlHeight
    spacing: 10
    indicator: Rectangle {
        x: control.leftPadding
        y: (control.height - height) / 2
        width: 18
        height: 18
        radius: 4
        color: control.checked ? Theme.accent : Theme.input
        border.width: 1
        border.color: control.checked ? Theme.accent : Theme.borderStrong
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: 7
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: control.visualFocus
        }
        TIcon {
            anchors.centerIn: parent
            name: "check"
            visible: control.checked
            color: Theme.onAccent
            width: 14
            height: 14
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
