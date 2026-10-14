import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

ColumnLayout {
    id: field
    property var form
    property var spec
    Layout.fillWidth: true
    Layout.preferredWidth: 1
    spacing: 4
    UI.TCaption {
        text: field.spec.label
    }
    Loader {
        Layout.fillWidth: true
        sourceComponent: field.spec.number ? numeric : textual
    }
    Label {
        visible: text.length > 0
        Layout.fillWidth: true
        text: field.form.errorFor(field.spec.key)
        color: UI.Theme.danger
        font.pixelSize: 11
        wrapMode: Text.WordWrap
    }
    Component {
        id: textual
        UI.TField {
            objectName: "network_" + field.spec.key
            text: String(field.form.field(field.spec.key, ""))
            Accessible.name: field.spec.label
            echoMode: field.spec.secret ? TextInput.Password : TextInput.Normal
            errorText: field.form.errorFor(field.spec.key)
            placeholderText: field.spec.secret && field.form.field(field.spec.key + "_ref", "") ? "Re-enter if the saved secret is missing" : field.spec.placeholder || ""
            onEditingFinished: field.form.setField(field.spec.key, text)
        }
    }
    Component {
        id: numeric
        UI.TNumberField {
            objectName: "network_" + field.spec.key
            label: field.spec.label
            value: Number(field.form.field(field.spec.key, field.spec.defaultValue || 0))
            minimum: field.spec.minimum
            maximum: field.spec.maximum
            step: field.spec.step || 1
            integer: Boolean(field.spec.integer)
            unit: field.spec.unit || ""
            onValueEdited: function (value) {
                field.form.setField(field.spec.key, value);
            }
        }
    }
}
