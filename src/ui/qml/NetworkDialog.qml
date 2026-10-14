import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

UI.TDialog {
    id: dialog
    property var controller
    property var draft: []
    property int current: -1
    property var validation: ({})
    property bool showProbe: false
    title: "Network sensors"
    width: Math.min(940, parent.width - 40)
    function initialize() {
        draft = JSON.parse(JSON.stringify(controller.networkDraft));
        current = draft.length ? 0 : -1;
        validation = ({});
        showProbe = false;
    }
    function field(key, fallback) {
        return current >= 0 && current < draft.length && draft[current][key] !== undefined ? draft[current][key] : fallback;
    }
    function setField(key, value) {
        let copy = JSON.parse(JSON.stringify(draft));
        copy[current][key] = value;
        draft = copy;
        validation = ({});
        showProbe = false;
        controller.stopProbe();
    }
    function add() {
        let number = 1;
        while (draft.some(function (s) {
            return s.id === "sensor_" + number;
        }))
            number++;
        let copy = draft.slice();
        copy.push({
            id: "sensor_" + number,
            name: "New sensor",
            protocol: "http",
            value_type: "number",
            url: "http://127.0.0.1:8123/api/states/sensor.example",
            host: "127.0.0.1",
            port: 1883,
            interval: 1,
            stale_after: 30,
            scale: 1,
            offset: 0,
            decimals: null,
            tls: false
        });
        draft = copy;
        current = copy.length - 1;
    }
    function select(index) {
        controller.stopProbe();
        current = index;
        validation = ({});
        showProbe = false;
    }
    function errorFor(key) {
        return validation.index === current && validation.field === key ? validation.message : "";
    }
    function check() {
        let result = controller.validateNetworkDraft(draft);
        if (result.message) {
            current = result.index;
            validation = result;
            if (["token", "password", "username"].indexOf(result.field) >= 0)
                auth.expanded = true;
            if (["interval", "stale_after"].indexOf(result.field) >= 0)
                advanced.expanded = true;
            return false;
        }
        validation = ({});
        return true;
    }
    onClosed: controller.stopProbe()
    footerContent: ColumnLayout {
        width: parent.width
        spacing: 10
        Label {
            Layout.fillWidth: true
            visible: dialog.current >= 0 || Boolean(dialog.validation.message)
            text: dialog.validation.message || controller.state.networkError || (dialog.showProbe ? controller.state.probeResult : "Test unsaved fields before saving. UDP testing requires a free bind port.")
            color: dialog.validation.message ? UI.Theme.danger : controller.state.networkError ? UI.Theme.warning : text.indexOf("Test successful:") === 0 ? UI.Theme.success : text.indexOf("No valid reading:") === 0 ? UI.Theme.warning : UI.Theme.secondary
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            font.pixelSize: 12
        }
        RowLayout {
            Layout.fillWidth: true
            UI.TButton {
                text: "Test connection"
                visible: dialog.current >= 0
                onClicked: if (dialog.check()) {
                    dialog.showProbe = true;
                    controller.testNetwork(dialog.draft[dialog.current]);
                }
            }
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                onClicked: dialog.close()
            }
            UI.TButton {
                text: "Save sensors"
                primary: true
                onClicked: if (dialog.check() && controller.saveNetwork(dialog.draft))
                    dialog.close()
            }
        }
    }
    ColumnLayout {
        width: parent.width
        spacing: 12
        Label {
            text: "Bring external readings to your display. Connections stay local; themes contain only source IDs."
            color: UI.Theme.secondary
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: dialog.current < 0 ? 160 : Math.max(180, Math.min(520, dialog.parent.height - 300))
            spacing: 20
            ColumnLayout {
                visible: dialog.current >= 0
                Layout.preferredWidth: 180
                Layout.minimumWidth: 180
                Layout.maximumWidth: 180
                Layout.fillHeight: true
                ListView {
                    id: list
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 6
                    model: dialog.draft
                    delegate: UI.TButton {
                        required property var modelData
                        required property int index
                        width: list.width
                        text: modelData.name || modelData.id
                        selected: dialog.current === index
                        onClicked: dialog.select(index)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    UI.TButton {
                        text: "+ Add"
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        enabled: dialog.draft.length < 64
                        onClicked: dialog.add()
                    }
                    UI.TButton {
                        text: "Remove"
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        onClicked: {
                            controller.stopProbe();
                            let copy = dialog.draft.slice();
                            copy.splice(dialog.current, 1);
                            dialog.draft = copy;
                            dialog.select(copy.length ? Math.min(dialog.current, copy.length - 1) : -1);
                        }
                    }
                }
            }
            ColumnLayout {
                visible: dialog.current < 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12
                Item {
                    Layout.fillHeight: true
                }
                Label {
                    Layout.fillWidth: true
                    text: "No network sensors yet.\nAdd a sensor to read values from Home Assistant, MQTT, HTTP or TCP/UDP."
                    color: UI.Theme.muted
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    lineHeight: 1.4
                }
                UI.TButton {
                    text: "+ Add sensor"
                    primary: true
                    Layout.alignment: Qt.AlignHCenter
                    onClicked: dialog.add()
                }
                Item {
                    Layout.fillHeight: true
                }
            }
            ScrollView {
                id: formScroll
                visible: dialog.current >= 0
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: formScroll.availableWidth
                    spacing: 8
                    UI.TSection {
                        title: "Connection"
                        spacing: 8
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 12
                            rowSpacing: 10
                            NetworkField {
                                form: dialog
                                spec: ({
                                        key: "id",
                                        label: "Sensor ID"
                                    })
                            }
                            NetworkField {
                                form: dialog
                                spec: ({
                                        key: "name",
                                        label: "Display name"
                                    })
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                UI.TCaption {
                                    text: "Protocol"
                                }
                                UI.TCombo {
                                    Layout.fillWidth: true
                                    model: ["HTTP", "MQTT", "TCP", "UDP"]
                                    currentIndex: Math.max(0, ["http", "mqtt", "tcp", "udp"].indexOf(dialog.field("protocol", "http")))
                                    onActivated: {
                                        dialog.setField("protocol", currentText.toLowerCase());
                                        dialog.setField("port", currentIndex === 1 ? 1883 : 9000);
                                    }
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                UI.TCaption {
                                    text: "Value type"
                                }
                                UI.TCombo {
                                    Layout.fillWidth: true
                                    model: ["Number", "Text", "Boolean"]
                                    currentIndex: Math.max(0, ["number", "text", "boolean"].indexOf(dialog.field("value_type", "number")))
                                    onActivated: dialog.setField("value_type", currentText.toLowerCase())
                                }
                            }
                            Repeater {
                                model: [
                                    {
                                        key: "url",
                                        label: "HTTP URL",
                                        protocols: ["http"]
                                    },
                                    {
                                        key: "host",
                                        label: "Host / UDP bind address",
                                        protocols: ["mqtt", "tcp", "udp"]
                                    },
                                    {
                                        key: "port",
                                        label: "Port",
                                        number: true,
                                        minimum: 1,
                                        maximum: 65535,
                                        integer: true,
                                        protocols: ["mqtt", "tcp", "udp"]
                                    },
                                    {
                                        key: "topic",
                                        label: "MQTT topic",
                                        protocols: ["mqtt"]
                                    }
                                ]
                                NetworkField {
                                    required property var modelData
                                    form: dialog
                                    spec: modelData
                                    Layout.columnSpan: 2
                                    visible: modelData.protocols.indexOf(dialog.field("protocol", "http")) >= 0
                                }
                            }
                        }
                    }
                    UI.TSection {
                        id: auth
                        title: "Authentication"
                        expanded: false
                        visible: ["http", "mqtt"].indexOf(dialog.field("protocol", "http")) >= 0
                        Repeater {
                            model: [
                                {
                                    key: "token",
                                    label: "Bearer token",
                                    secret: true,
                                    protocol: "http"
                                },
                                {
                                    key: "username",
                                    label: "MQTT username",
                                    protocol: "mqtt"
                                },
                                {
                                    key: "password",
                                    label: "MQTT password",
                                    secret: true,
                                    protocol: "mqtt"
                                }
                            ]
                            NetworkField {
                                required property var modelData
                                form: dialog
                                spec: modelData
                                visible: modelData.protocol === dialog.field("protocol", "http")
                            }
                        }
                        UI.TCheck {
                            text: "TLS - verify broker certificate"
                            visible: dialog.field("protocol", "http") === "mqtt"
                            checked: dialog.field("tls", false)
                            onClicked: dialog.setField("tls", checked)
                        }
                        Label {
                            text: "Secrets use your operating system credential vault."
                            color: UI.Theme.muted
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                    UI.TSection {
                        title: "Value mapping"
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 12
                            rowSpacing: 10
                            NetworkField {
                                form: dialog
                                spec: ({
                                        key: "path",
                                        label: "JSON field path",
                                        placeholder: "attributes.temperature or values.0"
                                    })
                                Layout.columnSpan: 2
                            }
                            Repeater {
                                model: [
                                    {
                                        key: "unit",
                                        label: "Unit suffix"
                                    },
                                    {
                                        key: "scale",
                                        label: "Multiplier",
                                        number: true,
                                        minimum: -1e12,
                                        maximum: 1e12,
                                        step: 0.1,
                                        defaultValue: 1
                                    },
                                    {
                                        key: "offset",
                                        label: "Offset",
                                        number: true,
                                        minimum: -1e12,
                                        maximum: 1e12,
                                        step: 0.1
                                    }
                                ]
                                NetworkField {
                                    required property var modelData
                                    form: dialog
                                    spec: modelData
                                    visible: dialog.field("value_type", "number") === "number"
                                }
                            }
                            ColumnLayout {
                                visible: dialog.field("value_type", "number") === "number"
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                UI.TCaption {
                                    text: "Decimal places"
                                }
                                UI.TCombo {
                                    Layout.fillWidth: true
                                    model: ["Auto", "0", "1", "2", "3", "4", "5", "6"]
                                    currentIndex: dialog.field("decimals", null) === null ? 0 : Number(dialog.field("decimals", 0)) + 1
                                    onActivated: dialog.setField("decimals", currentIndex === 0 ? null : currentIndex - 1)
                                }
                            }
                        }
                    }
                    UI.TSection {
                        id: advanced
                        title: "Advanced"
                        expanded: false
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 12
                            Repeater {
                                model: [
                                    {
                                        key: "interval",
                                        label: "Poll / retry interval",
                                        number: true,
                                        minimum: 0.1,
                                        maximum: 3600,
                                        step: 0.1,
                                        defaultValue: 1,
                                        unit: "s"
                                    },
                                    {
                                        key: "stale_after",
                                        label: "Expire reading after",
                                        number: true,
                                        minimum: 1,
                                        maximum: 86400,
                                        defaultValue: 30,
                                        unit: "s"
                                    }
                                ]
                                NetworkField {
                                    required property var modelData
                                    form: dialog
                                    spec: modelData
                                }
                            }
                        }
                        Label {
                            text: "TCP/UDP accept unauthenticated data. Use trusted senders."
                            color: UI.Theme.muted
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
