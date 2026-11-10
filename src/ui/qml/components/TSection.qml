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
    spacing: 10
    Button {
        id: header
        Layout.fillWidth: true
        implicitHeight: 32
        hoverEnabled: true
        Accessible.name: section.title
        onClicked: {
            section.expanded = !section.expanded;
            section.toggled(section.expanded);
        }
        contentItem: RowLayout {
            spacing: 6
            Label {
                text: section.title
                color: header.hovered ? Theme.text : Theme.secondary
                font.family: Theme.uiFont
                font.hintingPreference: Font.PreferNoHinting
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.9
                font.capitalization: Font.AllUppercase
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            TIcon {
                name: "chevron"
                width: 14
                height: 14
                rotation: section.expanded ? 0 : -90
            }
        }
        background: Rectangle {
            color: header.hovered ? Theme.hover : "transparent"
            radius: Theme.radiusSmall
            Rectangle {
                anchors.fill: parent
                anchors.margins: -2
                radius: parent.radius + 2
                color: "transparent"
                border.width: 2
                border.color: Theme.accent
                visible: header.visualFocus
            }
        }
    }
    ColumnLayout {
        id: content
        visible: section.expanded
        Layout.fillWidth: true
        spacing: 10
    }
    Rectangle {
        Layout.fillWidth: true
        height: 1
        color: Theme.border
    }
}
