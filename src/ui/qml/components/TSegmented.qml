import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Segmented tab strip (borderless pill; selected segment is a fill)
Item {
    id: seg
    property var model: []
    property int currentIndex: 0
    signal activated(int index)
    implicitWidth: row.implicitWidth + 6
    implicitHeight: 32
    Accessible.role: Accessible.PageTabList
    function pick(i) {
        if (i < 0 || i >= model.length)
            return;
        currentIndex = i;
        activated(i);
    }
    Rectangle {
        anchors.fill: parent
        radius: Theme.radius + 1
        color: Theme.input
    }
    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 3
        spacing: 2
        Repeater {
            model: seg.model
            Button {
                id: tab
                required property int index
                required property string modelData
                Layout.fillWidth: true
                Layout.fillHeight: true
                leftPadding: 4
                rightPadding: 4
                implicitWidth: label.implicitWidth + 20
                hoverEnabled: true
                text: modelData
                Accessible.role: Accessible.PageTab
                Accessible.name: modelData
                Accessible.selected: index === seg.currentIndex
                onClicked: seg.pick(index)
                Keys.onLeftPressed: { seg.pick(index - 1); }
                Keys.onRightPressed: { seg.pick(index + 1); }
                contentItem: Text {
                    id: label
                    text: tab.text
                    font.family: Theme.uiFont
                    font.hintingPreference: Font.PreferNoHinting
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: tab.index === seg.currentIndex || tab.hovered ? Theme.text : Theme.secondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: Theme.radiusSmall
                    color: tab.index === seg.currentIndex ? Theme.selected : tab.hovered ? Theme.hover : "transparent"
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -1
                        radius: parent.radius + 1
                        color: "transparent"
                        border.width: 2
                        border.color: Theme.accent
                        visible: tab.visualFocus
                    }
                }
            }
        }
    }
}
