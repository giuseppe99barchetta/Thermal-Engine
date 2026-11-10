import QtQuick
import QtQuick.Controls

// Borderless: state is carried by fill. "flat" = ghost (transparent until hovered).
Button {
    id: control
    property bool primary: false
    property bool selected: false
    property bool destructive: false
    implicitHeight: Theme.controlHeight
    implicitWidth: Math.max(Theme.controlHeight, contentItem.implicitWidth + 24)
    font.family: Theme.uiFont
    font.hintingPreference: Font.PreferNoHinting
    font.pixelSize: 13
    font.weight: primary ? Font.DemiBold : Font.Medium
    hoverEnabled: true
    opacity: enabled ? 1 : 0.45
    Accessible.name: text
    contentItem: Text {
        text: control.text
        font: control.font
        color: control.primary ? Theme.onAccent : control.destructive ? Theme.danger : control.selected || control.hovered ? Theme.text : control.flat ? Theme.secondary : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Theme.radius
        color: control.primary ? (control.down ? Theme.accentPressed : Theme.accent)
            : control.selected ? Theme.selected
            : control.down ? Theme.selected
            : control.hovered ? (control.flat ? Theme.hover : Theme.selected)
            : control.flat ? "transparent" : Theme.hover
        // 2px focus ring; accent on an accent fill is invisible, so primary uses the text colour
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: parent.radius + 2
            color: "transparent"
            border.width: 2
            border.color: control.primary ? Theme.text : Theme.accent
            visible: control.visualFocus
        }
    }
    ToolTip.visible: hovered && ToolTip.text.length > 0
    ToolTip.delay: 600
}
