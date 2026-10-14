import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: Theme.controlHeight
    font.family: Theme.font
    font.pixelSize: 13
    leftPadding: 10
    rightPadding: 28
    Accessible.name: displayText
    contentItem: Text {
        text: control.displayText
        font: control.font
        color: control.enabled ? Theme.text : Theme.muted
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: TIcon {
        x: control.width - 24
        y: (control.height - height) / 2
        name: "chevron"
        width: 14
        height: 14
    }
    background: Rectangle {
        color: Theme.input
        radius: Theme.radius
        border.color: control.activeFocus ? Theme.accent : Theme.border
    }
    delegate: ItemDelegate {
        id: option
        required property int index
        width: control.width
        text: control.textRole ? control.model[index][control.textRole] : control.model[index]
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: option.text
            color: Theme.text
            font: control.font
            elide: Text.ElideRight
        }
        background: Rectangle {
            color: option.highlighted ? Theme.accentDark : Theme.raised
        }
    }
    popup: Popup {
        y: control.height + 4
        width: control.width
        padding: 4
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 300)
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle {
            color: Theme.raised
            radius: Theme.radius
            border.color: Theme.border
        }
    }
}
