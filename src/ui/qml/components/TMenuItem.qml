import QtQuick
import QtQuick.Controls

MenuItem {
    id: control
    implicitHeight: Theme.controlHeight
    font.family: Theme.uiFont
    font.hintingPreference: Font.PreferNoHinting
    font.pixelSize: 13
    leftPadding: 10
    rightPadding: 10
    contentItem: Text {
        text: control.text
        font: control.font
        color: control.enabled ? Theme.text : Theme.muted
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        implicitWidth: 212
        implicitHeight: Theme.controlHeight
        radius: Theme.radiusSmall
        color: control.down ? Theme.border : control.highlighted ? Theme.selected : "transparent"
    }
}
