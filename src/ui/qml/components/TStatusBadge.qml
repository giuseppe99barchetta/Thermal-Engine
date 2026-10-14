import QtQuick
import QtQuick.Layouts

TButton {
    id: control
    property string severity: "muted"
    implicitHeight: 24
    contentItem: RowLayout {
        spacing: 6
        Rectangle {
            width: 6
            height: 6
            radius: 3
            color: control.severity === "success" ? Theme.success : control.severity === "warning" ? Theme.warning : Theme.muted
        }
        Text {
            text: control.text
            color: Theme.secondary
            font.family: Theme.font
            font.pixelSize: 11
        }
    }
}
