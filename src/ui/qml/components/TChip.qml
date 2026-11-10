import QtQuick
import QtQuick.Controls

// Dot + text status chip, no outline. Set clickable for an actionable chip.
Control {
    id: chip
    property string text: ""
    property string tone: "muted"  // success | warning | danger | muted
    property bool clickable: false
    signal clicked()
    implicitWidth: row.implicitWidth + 16
    implicitHeight: 24
    hoverEnabled: clickable
    focusPolicy: clickable ? Qt.TabFocus : Qt.NoFocus
    Accessible.role: clickable ? Accessible.Button : Accessible.StaticText
    Accessible.name: text
    Accessible.onPressAction: chip.clicked()
    Keys.onSpacePressed: if (clickable) chip.clicked()
    Keys.onReturnPressed: if (clickable) chip.clicked()
    background: Rectangle {
        radius: height / 2
        color: chip.clickable && chip.hovered ? Theme.hover : "transparent"
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: parent.radius + 2
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: chip.visualFocus
        }
    }
    contentItem: Item {
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: chip.tone === "success" ? Theme.success : chip.tone === "warning" ? Theme.warning : chip.tone === "danger" ? Theme.danger : Theme.muted
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: chip.text
                font.family: Theme.uiFont
                font.hintingPreference: Font.PreferNoHinting
                font.pixelSize: 12
                color: chip.clickable && chip.hovered ? Theme.text : Theme.secondary
            }
        }
    }
    TapHandler {
        enabled: chip.clickable
        onTapped: chip.clicked()
    }
}
