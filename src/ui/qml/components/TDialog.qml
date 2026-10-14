import QtQuick
import QtQuick.Controls

Dialog {
    id: control
    modal: true
    anchors.centerIn: parent
    width: Math.min(680, parent.width - 40)
    padding: 24
    topPadding: 8
    default property alias body: bodyItem.data
    property alias footerContent: actionsBody.data
    closePolicy: Popup.CloseOnEscape
    font.family: Theme.font
    palette.text: Theme.text
    palette.windowText: Theme.text
    palette.buttonText: Theme.text
    palette.base: Theme.input
    palette.window: Theme.surface
    palette.button: Theme.raised
    palette.highlight: Theme.accentDark
    background: Rectangle {
        color: Theme.surface
        radius: 12
        border.color: Theme.border
    }
    contentItem: ScrollView {
        id: scroller
        implicitHeight: Math.min(bodyItem.height, Math.max(80, control.parent.height - control.header.implicitHeight - control.footer.implicitHeight - control.topPadding - control.bottomPadding - 40))
        contentWidth: availableWidth
        clip: true
        Item {
            id: bodyItem
            width: scroller.availableWidth
            height: childrenRect.height
        }
    }
    footer: Item {
        implicitHeight: actionsBody.height > 0 ? actionsBody.height + 32 : 0
        Item {
            id: actionsBody
            x: 24
            y: 8
            width: parent.width - 48
            height: childrenRect.height
        }
    }
    header: Label {
        text: control.title
        color: Theme.text
        font.pixelSize: 20
        font.weight: Font.DemiBold
        leftPadding: 24
        topPadding: 20
        bottomPadding: 16
    }
    Overlay.modal: Rectangle {
        color: "#b0101419"
    }
}
