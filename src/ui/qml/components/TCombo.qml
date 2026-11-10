import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: Theme.fieldHeight
    font.family: Theme.uiFont
    font.hintingPreference: Font.PreferNoHinting
    font.pixelSize: 13
    leftPadding: 10
    rightPadding: 28
    opacity: enabled ? 1 : 0.45
    Accessible.name: displayText
    contentItem: Text {
        text: control.displayText
        font: control.font
        color: Theme.text
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
        radius: Theme.radiusSmall
        border.width: control.visualFocus || control.popup.visible ? 2 : 1
        border.color: control.visualFocus || control.popup.visible ? Theme.accent : Theme.borderStrong
    }
    delegate: ItemDelegate {
        id: option
        required property int index
        width: control.width - 8
        implicitHeight: Theme.controlHeight
        text: control.textRole ? control.model[index][control.textRole] : control.model[index]
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: option.text
            color: Theme.text
            font: control.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: 6
            color: option.highlighted ? Theme.selected : "transparent"
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
