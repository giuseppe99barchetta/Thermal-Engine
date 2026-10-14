import QtQuick
import QtQuick.Controls

Menu {
    padding: 4
    font.family: Theme.font
    font.pixelSize: 13
    delegate: TMenuItem {}
    background: Rectangle {
        implicitWidth: 220
        implicitHeight: 40
        color: Theme.raised
        radius: Theme.radius
        border.color: Theme.border
    }
}
