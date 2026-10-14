import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: control
    property var spec
    property var controller
    property real startValue: 0
    property real startX: 0
    spacing: 6
    Layout.fillWidth: true
    Label {
        text: control.spec.label
        color: Theme.secondary
        font.pixelSize: 11
        Layout.fillWidth: true
        MouseArea {
            anchors.fill: parent
            enabled: control.spec.kind === "number"
            cursorShape: Qt.SizeHorCursor
            onPressed: function (mouse) {
                control.startValue = Number(control.spec.value);
                control.startX = mouse.x;
                control.controller.beginEdit();
            }
            onPositionChanged: function (mouse) {
                if (pressed)
                    control.controller.edit(control.spec.key, Math.max(control.spec.minimum, Math.min(control.spec.maximum, control.startValue + Math.round(mouse.x - control.startX) * control.spec.step * ((mouse.modifiers & Qt.ShiftModifier) ? 10 : 1))));
            }
            onReleased: control.controller.endEdit()
            onCanceled: control.controller.endEdit()
        }
    }
    TSwatches {
        visible: control.spec.kind === "color" && control.enabled
        Layout.fillWidth: true
        colors: control.controller.colorSwatches
        onPicked: function (color) {
            control.controller.edit(control.spec.key, color);
        }
    }
    Loader {
        Layout.fillWidth: true
        sourceComponent: control.spec.kind === "number" ? numberField : control.spec.key === "gradient_stops" ? gradientField : control.spec.kind === "boolean" ? booleanField : control.spec.kind === "choice" ? choiceField : control.spec.kind === "path" ? pathField : textField
    }
    Component {
        id: numberField
        TNumberField {
            objectName: "property_" + control.spec.key
            value: control.spec.value
            minimum: control.spec.minimum
            maximum: control.spec.maximum
            step: control.spec.step
            integer: control.spec.integer
            unit: control.spec.unit
            label: control.spec.label
            onValueEdited: function(value) { control.controller.edit(control.spec.key, value); }
        }
    }
    Component {
        id: textField
        TField {
            text: String(control.spec.value)
            selectByMouse: true
            Accessible.name: control.spec.label
            onEditingFinished: control.controller.edit(control.spec.key, text)
            rightPadding: control.spec.kind === "color" ? 42 : 10
            Rectangle {
                visible: control.spec.kind === "color"
                anchors.right: parent.right
                anchors.rightMargin: 9
                anchors.verticalCenter: parent.verticalCenter
                width: 20
                height: 20
                radius: 4
                color: visible ? String(control.spec.value) : "transparent"
                border.color: Theme.border
                MouseArea {
                    anchors.fill: parent
                    onClicked: control.controller.command("color", control.spec.key)
                }
            }
        }
    }
    Component {
        id: booleanField
        TCheck {
            text: "Enabled"
            checked: Boolean(control.spec.value)
            onClicked: control.controller.edit(control.spec.key, checked)
        }
    }
    Component {
        id: gradientField
        TButton {
            text: "Edit gradient stops..."
            onClicked: control.controller.command("gradient", null)
        }
    }
    Component {
        id: choiceField
        TCombo {
            model: control.spec.choices
            currentIndex: Math.max(0, control.spec.choices.indexOf(control.spec.value))
            onActivated: control.controller.edit(control.spec.key, currentText)
        }
    }
    Component {
        id: pathField
        RowLayout {
            TField {
                Layout.fillWidth: true
                text: String(control.spec.value)
                onEditingFinished: control.controller.edit(control.spec.key, text)
            }
            TButton {
                text: "…"
                implicitWidth: 36
                onClicked: control.controller.command(control.spec.key === "gif_path" ? "gif" : "image", null)
            }
        }
    }
}
