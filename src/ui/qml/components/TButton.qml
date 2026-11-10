import QtQuick
import QtQuick.Controls

Button {
    id: control
    property bool primary: false
    property bool selected: false
    property bool destructive: false
    implicitHeight: Theme.controlHeight
    implicitWidth: Math.max(36, contentItem.implicitWidth + 24)
    font.family: Theme.font
    font.pixelSize: 13
    hoverEnabled: true
    Accessible.name: text
    contentItem: Text {
        text: control.text
        font: control.font
        color: !control.enabled ? Theme.muted : control.primary ? Theme.onAccent : control.destructive ? Theme.danger : control.selected ? Theme.accent : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Theme.radius
        color: control.primary ? (control.down ? Theme.accentPressed : Theme.accent) : control.down ? Theme.border : control.selected ? Theme.accentDark : control.hovered ? Theme.raised : "transparent"
        border.width: control.activeFocus ? 2 : 1
        // accent on an accent fill is invisible: primary buttons use the text color for the focus ring
        border.color: control.activeFocus ? (control.primary ? Theme.text : Theme.accent) : control.primary ? "transparent" : control.selected ? Theme.accentBorder : Theme.borderStrong
        opacity: control.enabled ? 1 : 0.45
    }
    ToolTip.visible: hovered && ToolTip.text.length > 0
    ToolTip.delay: 600
}
