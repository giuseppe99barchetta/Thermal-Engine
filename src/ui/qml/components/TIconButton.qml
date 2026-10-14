import QtQuick
import QtQuick.Controls

TButton {
    id: control
    property string iconName: ""
    implicitWidth: Theme.controlHeight
    Accessible.name: text.length ? text : ToolTip.text
    contentItem: TIcon {
        name: control.iconName
        stroke: control.enabled ? Theme.secondary : Theme.muted
        opacity: control.enabled ? 1 : 0.4
    }
}
