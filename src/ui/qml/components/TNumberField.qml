import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: control
    property real value: 0
    property real minimum: -10000
    property real maximum: 10000
    property real step: 1
    property bool integer: true
    property string unit: ""
    property string label: "Value"
    signal valueEdited(real value)
    spacing: 4
    function increment(direction) {
        let base = field.acceptableInput ? Number(field.text) : value;
        valueEdited(Number(Math.max(minimum, Math.min(maximum, base + direction * step)).toFixed(integer ? 0 : 6)));
    }
    TField {
        id: field
        objectName: "numberInput"
        Layout.fillWidth: true
        text: String(control.value)
        selectByMouse: true
        rightPadding: 28 + suffix.implicitWidth
        Accessible.name: control.label
        validator: DoubleValidator {
            bottom: control.minimum
            top: control.maximum
            decimals: control.integer ? 0 : 6
            notation: DoubleValidator.StandardNotation
            locale: "C"
        }
        errorText: acceptableInput ? "" : "Use " + control.minimum + " to " + control.maximum
        onEditingFinished: if (acceptableInput && Number(text) !== control.value) control.valueEdited(Number(text))
        Keys.onUpPressed: control.increment(1)
        Keys.onDownPressed: control.increment(-1)
        Text {
            id: suffix
            anchors.right: arrows.left
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            text: control.unit
            color: Theme.muted
            font.pixelSize: 10
        }
        Column {
            id: arrows
            anchors.right: parent.right
            anchors.rightMargin: 2
            anchors.verticalCenter: parent.verticalCenter
            TButton { text: "+"; width: 20; height: 16; font.pixelSize: 10; Accessible.name: "Increase " + control.label; onClicked: control.increment(1) }
            TButton { text: "−"; width: 20; height: 16; font.pixelSize: 10; Accessible.name: "Decrease " + control.label; onClicked: control.increment(-1) }
        }
    }
    Label {
        visible: field.errorText.length > 0
        Layout.fillWidth: true
        text: field.errorText
        color: Theme.danger
        font.pixelSize: 10
        wrapMode: Text.WordWrap
    }
}
