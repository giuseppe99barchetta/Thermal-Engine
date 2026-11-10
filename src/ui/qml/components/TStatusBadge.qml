import QtQuick
import QtQuick.Layouts

// Quiet dot + text status item (still clickable)
TButton {
    id: control
    property string severity: "muted"
    flat: true
    implicitHeight: 24
    implicitWidth: contentItem.implicitWidth + 16
    contentItem: RowLayout {
        spacing: 6
        Rectangle {
            width: 6
            height: 6
            radius: 3
            color: control.severity === "success" ? Theme.success : control.severity === "warning" ? Theme.warning : control.severity === "danger" ? Theme.danger : Theme.muted
        }
        Text {
            text: control.text
            color: control.hovered ? Theme.text : Theme.secondary
            font.family: Theme.uiFont
            font.hintingPreference: Font.PreferNoHinting
            font.pixelSize: 12
        }
    }
}
