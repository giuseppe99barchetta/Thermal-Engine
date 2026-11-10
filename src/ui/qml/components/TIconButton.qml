import QtQuick
import QtQuick.Controls

TButton {
    id: control
    property string iconName: ""
    property bool accented: false  // accent-coloured glyph for on/off toggles (grid, snap)
    flat: true
    implicitWidth: Theme.controlHeight
    Accessible.name: text.length ? text : ToolTip.text
    contentItem: TIcon {
        name: control.iconName
        color: control.primary ? Theme.onAccent : control.accented ? Theme.accent : control.selected || control.hovered ? Theme.text : Theme.secondary
    }
}
