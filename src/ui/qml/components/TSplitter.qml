import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: splitter
    property real value: 0
    property real minimum: 220
    property real maximum: 440
    property bool reversed: false
    property string panelName: "panel"
    signal adjusted(real value)
    signal committed()
    Layout.preferredWidth: 8
    Layout.fillHeight: true
    activeFocusOnTab: true
    Accessible.role: Accessible.Splitter
    Accessible.name: "Resize " + panelName
    function adjust(delta) {
        adjusted(Math.max(minimum, Math.min(maximum, delta)));
    }
    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
            event.accepted = true;
            splitter.adjust(splitter.value + (event.key === Qt.Key_Right ? 10 : -10) * (splitter.reversed ? -1 : 1));
            splitter.committed();
        }
    }
    Rectangle {
        anchors.centerIn: parent
        width: 1
        height: parent.height
        color: mouse.containsMouse || mouse.pressed || splitter.activeFocus ? Theme.accent : Theme.border
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        cursorShape: Qt.SplitHCursor
        hoverEnabled: true
        property real startValue
        property real startX
        onPressed: function(event) {
            splitter.forceActiveFocus();
            startValue = splitter.value;
            startX = mapToItem(null, event.x, event.y).x;
        }
        onPositionChanged: function(event) {
            if (pressed)
                splitter.adjust(startValue + (mapToItem(null, event.x, event.y).x - startX) * (splitter.reversed ? -1 : 1));
        }
        onReleased: splitter.committed()
        onCanceled: splitter.adjusted(startValue)
    }
    ToolTip.visible: mouse.containsMouse
    ToolTip.delay: 700
    ToolTip.text: "Drag to resize " + panelName + ". Arrow keys also work."
}
