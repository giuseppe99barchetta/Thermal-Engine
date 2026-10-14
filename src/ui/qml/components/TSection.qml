import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: section
    property string title: ""
    property bool expanded: true
    default property alias body: content.data
    signal toggled(bool open)
    Layout.fillWidth: true
    spacing: 12
    Button {
        id: header
        Layout.fillWidth: true
        implicitHeight: 36
        Accessible.name: section.title
        onClicked: {
            section.expanded = !section.expanded;
            section.toggled(section.expanded);
        }
        contentItem: RowLayout {
            Label {
                text: section.title
                color: Theme.text
                font.pixelSize: 12
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            TIcon {
                name: "chevron"
                width: 14
                height: 14
                rotation: section.expanded ? 0 : -90
            }
        }
        background: Rectangle {
            color: header.hovered ? Theme.raised : "transparent"
            radius: 6
        }
    }
    ColumnLayout {
        id: content
        visible: section.expanded
        Layout.fillWidth: true
        spacing: 12
    }
    Rectangle {
        Layout.fillWidth: true
        height: 1
        color: Theme.border
    }
}
