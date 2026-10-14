import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components" as UI

Item {
    id: hub
    property var controller
    property var payload: ({})
    property string consoleText: ""
    function showConsole() {
        consoleDialog.open();
    }
    Connections {
        target: hub.controller
        function onConsoleLine(line) {
            hub.consoleText = (hub.consoleText + line + "\n").slice(-100000);
        }
        function onRequestDialog(kind, data) {
            hub.payload = data;
            if (kind === "confirm" || kind === "error") {
                messageDialog.payload = data;
                messageDialog.confirmation = kind === "confirm";
                messageDialog.open();
            } else if (kind === "unsaved") {
                unsavedDialog.payload = data;
                unsavedDialog.open();
            } else if (kind === "prompt") {
                promptDialog.payload = data;
                promptField.text = data.initial || "";
                promptDialog.open();
            } else if (kind === "file") {
                fileDialog.action = data.action;
                fileDialog.fileMode = ["saveAs", "exportImage", "exportPackage"].indexOf(data.action) >= 0 ? FileDialog.SaveFile : FileDialog.OpenFile;
                fileDialog.nameFilters = data.action === "image" ? ["Images (*.png *.jpg *.jpeg *.bmp *.webp)"] : data.action === "gif" ? ["GIF files (*.gif)"] : data.action === "video" ? ["GIF and video (*.gif *.mp4 *.mkv *.avi *.mov *.webm)"] : data.action === "exportImage" ? ["PNG images (*.png)"] : data.action === "exportPackage" || data.action === "importPackage" ? ["Theme packages (*.thermal *.zip)"] : ["JSON themes (*.json)"];
                fileDialog.open();
            } else if (kind === "condition") {
                conditionDialog.rule = data.rule || ({});
                conditionDialog.initialize();
                conditionDialog.open();
            } else if (kind === "color") {
                colorDialog.key = data.key;
                colorDialog.selectedColor = data.value;
                colorDialog.open();
            } else if (kind === "diagnostics") {
                diagnosticText.text = data.text;
                diagnosticsDialog.open();
            } else if (kind === "console") {
                consoleDialog.open();
            } else if (kind === "hardware")
                hardwareDialog.open();
            else if (kind === "network") {
                networkDialog.initialize();
                networkDialog.open();
            } else if (kind === "devices")
                devicesDialog.open();
            else if (kind === "resolution") {
                resolutionWidth.text = hub.controller.state.width;
                resolutionHeight.text = hub.controller.state.height;
                resolutionDialog.open();
            } else if (kind === "settings") {
                settingsDialog.initialize(data);
                settingsDialog.open();
            } else if (kind === "profiles") {
                profilesDialog.initialize(data);
                profilesDialog.open();
            } else if (kind === "onboarding") {
                devicesDialog.close();
                onboardingDialog.initialize();
                onboardingDialog.open();
            } else if (kind === "update") {
                updateDialog.payload = data;
                updateDialog.open();
            } else if (kind === "gradient") {
                gradientDialog.initialize(data.stops);
                gradientDialog.open();
            }
        }
    }
    FileDialog {
        id: fileDialog
        property string action
        onAccepted: hub.controller.fileChosen(action, selectedFile)
    }
    ColorDialog {
        id: colorDialog
        property string key
        title: "Choose color"
        onAccepted: if (key === "theme")
            hub.controller.command("background", selectedColor.toString())
        else
            hub.controller.edit(key, selectedColor.toString())
    }
    UI.TDialog {
        id: unsavedDialog
        objectName: "unsavedDialog"
        property var payload: ({})
        title: "Unsaved changes"
        function resolve(choice) {
            let token = payload.token;
            close();
            hub.controller.answer(token, choice !== "cancel", choice);
        }
        onRejected: hub.controller.answer(payload.token, false, "")
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                onClicked: unsavedDialog.resolve("cancel")
            }
            UI.TButton {
                text: "Discard changes"
                destructive: true
                onClicked: unsavedDialog.resolve("discard")
            }
            UI.TButton {
                text: "Save"
                primary: true
                onClicked: unsavedDialog.resolve("save")
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 20
            Label {
                text: "Save changes to " + (unsavedDialog.payload.name || "this theme") + " before continuing?"
                color: UI.Theme.secondary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
    UI.TDialog {
        id: messageDialog
        property var payload: ({})
        property bool confirmation: false
        title: messageDialog.payload.title || "Thermal Engine"
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                visible: messageDialog.confirmation
                text: "Cancel"
                onClicked: {
                    hub.controller.answer(messageDialog.payload.token, false, "");
                    messageDialog.close();
                }
            }
            UI.TButton {
                text: messageDialog.confirmation ? "Continue" : "Close"
                primary: true
                onClicked: {
                    let token = messageDialog.payload.token;
                    let accepted = messageDialog.confirmation;
                    messageDialog.close();
                    if (accepted)
                        hub.controller.answer(token, true, "");
                }
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 20
            Label {
                text: messageDialog.payload.message || ""
                color: UI.Theme.secondary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
        onRejected: if (confirmation)
            hub.controller.answer(messageDialog.payload.token, false, "")
    }
    UI.TDialog {
        id: promptDialog
        property var payload: ({})
        title: promptDialog.payload.title || "Name"
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                onClicked: {
                    hub.controller.answer(promptDialog.payload.token, false, "");
                    promptDialog.close();
                }
            }
            UI.TButton {
                text: "Save"
                primary: true
                enabled: promptField.text.trim().length > 0
                onClicked: {
                    let token = promptDialog.payload.token;
                    promptDialog.close();
                    hub.controller.answer(token, true, promptField.text);
                }
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 16
            Label {
                text: promptDialog.payload.label || "Name"
                color: UI.Theme.secondary
            }
            UI.TField {
                id: promptField
                Layout.fillWidth: true
                selectByMouse: true
                onAccepted: {
                    if (text.trim()) {
                        let token = promptDialog.payload.token;
                        promptDialog.close();
                        hub.controller.answer(token, true, text);
                    }
                }
            }
        }
        onOpened: promptField.forceActiveFocus()
        onRejected: hub.controller.answer(promptDialog.payload.token, false, "")
    }
    UI.TDialog {
        id: conditionDialog
        title: "Conditional rule"
        property var rule: ({})
        function initialize() {
            conditionEnabled.checked = Object.keys(rule).length > 0;
            conditionSource.currentIndex = 0;
            for (let i = 0; i < hub.controller.sources.length; i++)
                if (hub.controller.sources[i].id === rule.source)
                    conditionSource.currentIndex = i;
            conditionComparison.currentIndex = Math.max(0, ["==", "!=", ">", ">=", "<", "<="].indexOf(rule.operator || ">"));
            conditionValue.text = rule.value === undefined ? "80" : String(rule.value);
            conditionAction.currentIndex = Math.max(0, ["color", "text", "show", "hide"].indexOf(rule.action || "color"));
            conditionColor.text = rule.color || "#ff4444";
            conditionText.text = rule.text || "";
        }
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                onClicked: conditionDialog.close()
            }
            UI.TButton {
                text: "Apply rule"
                primary: true
                onClicked: {
                    hub.controller.edit("condition", conditionEnabled.checked ? {
                        source: hub.controller.sources[conditionSource.currentIndex].id,
                        operator: conditionComparison.currentText,
                        value: conditionValue.text,
                        action: ["color", "text", "show", "hide"][conditionAction.currentIndex],
                        color: conditionColor.text,
                        text: conditionText.text
                    } : {});
                    conditionDialog.close();
                }
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 12
            UI.TCheck {
                id: conditionEnabled
                text: "Enable rule"
            }
            Label {
                text: "Sensor"
                color: UI.Theme.secondary
            }
            UI.TCombo {
                id: conditionSource
                Layout.fillWidth: true
                model: hub.controller.sources
                textRole: "name"
            }
            RowLayout {
                UI.TCombo {
                    id: conditionComparison
                    Layout.preferredWidth: 80
                    model: ["==", "!=", ">", ">=", "<", "<="]
                }
                UI.TField {
                    id: conditionValue
                    Layout.fillWidth: true
                    placeholderText: "Number, exact text or true/false"
                }
            }
            Label {
                text: "When the rule matches"
                color: UI.Theme.secondary
            }
            UI.TCombo {
                id: conditionAction
                Layout.fillWidth: true
                model: ["Change color", "Change text", "Show only when matched", "Hide when matched"]
            }
            UI.TField {
                id: conditionColor
                visible: conditionAction.currentIndex === 0
                Layout.fillWidth: true
                placeholderText: "Hex color"
            }
            UI.TField {
                id: conditionText
                visible: conditionAction.currentIndex === 1
                Layout.fillWidth: true
                placeholderText: "Replacement text"
            }
            Label {
                text: "Missing data never matches. A manually hidden element stays hidden."
                color: UI.Theme.muted
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
    UI.TDialog {
        id: diagnosticsDialog
        title: "Diagnostics"
        width: Math.min(760, parent.width - 40)
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Copy report"
                onClicked: hub.controller.command("copyDiagnostics", null)
            }
            UI.TButton {
                text: "Close"
                primary: true
                onClicked: diagnosticsDialog.close()
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 12
            Repeater {
                model: hub.controller.healthChecks
                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: statusCard.implicitHeight + 24
                    color: UI.Theme.input
                    radius: UI.Theme.radius
                    ColumnLayout {
                        id: statusCard
                        x: 12
                        y: 12
                        width: parent.width - 24
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: modelData.name; color: UI.Theme.text; font.weight: Font.DemiBold; Layout.fillWidth: true }
                            Label { text: modelData.status; color: modelData.severity === "success" ? UI.Theme.success : modelData.severity === "warning" ? UI.Theme.warning : UI.Theme.muted }
                        }
                        Label { text: modelData.detail; color: UI.Theme.secondary; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 12 }
                        UI.TButton { text: modelData.actionLabel; onClicked: { diagnosticsDialog.close(); hub.controller.command(modelData.action, null); } }
                    }
                }
            }
            UI.TSection {
                title: "Network readings"
                visible: hub.controller.networkHealth.length > 0
                expanded: false
                Repeater {
                    model: hub.controller.networkHealth
                    Label {
                        required property var modelData
                        text: modelData.name + " · " + modelData.status + (modelData.age === null ? " · No reading yet" : " · " + modelData.age + " seconds ago")
                        color: UI.Theme.secondary
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
            UI.TSection {
                title: "Technical report"
                expanded: false
                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 280
                    clip: true
                    TextArea {
                        id: diagnosticText
                        readOnly: true
                        selectByMouse: true
                        color: UI.Theme.secondary
                        font.family: "Consolas"
                        font.pixelSize: 12
                        wrapMode: Text.WrapAnywhere
                        background: Rectangle { color: UI.Theme.input }
                    }
                }
            }
        }
    }
    UI.TDialog {
        id: consoleDialog
        title: "Console"
        footerContent: RowLayout {
            width: parent.width
            Item { Layout.fillWidth: true }
            UI.TButton { text: "Close"; primary: true; onClicked: consoleDialog.close() }
        }
        ColumnLayout {
            width: parent.width
            spacing: 12
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 360
                clip: true
                TextArea {
                    text: hub.consoleText
                    readOnly: true
                    selectByMouse: true
                    color: UI.Theme.secondary
                    font.family: "Consolas"
                    font.pixelSize: 12
                    wrapMode: Text.WrapAnywhere
                    background: Rectangle {
                        color: UI.Theme.input
                    }
                }
            }
        }
    }
    UI.TDialog {
        id: resolutionDialog
        title: "Display resolution"
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                onClicked: resolutionDialog.close()
            }
            UI.TButton {
                text: "Apply resolution"
                primary: true
                enabled: resolutionWidth.acceptableInput && resolutionHeight.acceptableInput
                onClicked: {
                    hub.controller.resizeDisplay(Number(resolutionWidth.text), Number(resolutionHeight.text), stretchLayout.checked);
                    resolutionDialog.close();
                }
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 16
            Label {
                text: "Choose the native resolution of your panel. Some displays share a USB identifier."
                color: UI.Theme.secondary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            UI.TCombo {
                Layout.fillWidth: true
                model: hub.controller.sizeProfiles
                textRole: "name"
                onActivated: {
                    resolutionWidth.text = model[currentIndex].width;
                    resolutionHeight.text = model[currentIndex].height;
                }
            }
            RowLayout {
                UI.TField {
                    id: resolutionWidth
                    Layout.fillWidth: true
                    placeholderText: "Width"
                    validator: IntValidator {
                        bottom: 160
                        top: 4096
                    }
                }
                Label {
                    text: "×"
                    color: UI.Theme.secondary
                }
                UI.TField {
                    id: resolutionHeight
                    Layout.fillWidth: true
                    placeholderText: "Height"
                    validator: IntValidator {
                        bottom: 160
                        top: 4096
                    }
                }
            }
            UI.TCheck {
                id: stretchLayout
                text: "Stretch the existing layout to the new resolution"
            }
        }
    }
    UI.TDialog {
        id: devicesDialog
        title: "Connect a display"
        footerContent: RowLayout {
            width: parent.width
            Item { Layout.fillWidth: true }
            UI.TButton { text: "Refresh devices"; onClicked: hub.controller.openDevices() }
            UI.TButton { text: "Continue offline"; primary: true; onClicked: devicesDialog.close() }
        }
        ColumnLayout {
            width: parent.width
            spacing: 16
            Label {
                text: "Connect your display by USB, then refresh the list."
                color: UI.Theme.secondary
            }
            ListView {
                Layout.fillWidth: true
                Layout.preferredHeight: count ? Math.min(220, contentHeight) : 96
                model: hub.controller.devices
                spacing: 8
                clip: true
                delegate: UI.TButton {
                    required property var row
                    width: ListView.view.width
                    text: row.name + " · " + row.width + " × " + row.height + (row.experimental ? " · Experimental" : "")
                    onClicked: {
                        hub.controller.connectDevice(row.index);
                        devicesDialog.close();
                    }
                }
                Label {
                    anchors.centerIn: parent
                    visible: parent.count === 0
                    text: "No display found. You can keep editing offline."
                    color: UI.Theme.muted
                }
            }
        }
    }
    GradientDialog {
        id: gradientDialog
        controller: hub.controller
    }
    UI.TDialog {
        id: hardwareDialog
        title: "Hardware monitoring setup"
        footerContent: RowLayout {
            width: parent.width
            Item { Layout.fillWidth: true }
            UI.TButton { text: "Continue"; primary: !hub.controller.hardwareStatus.needsAdmin; onClicked: hardwareDialog.close() }
        }
        ColumnLayout {
            width: parent.width
            spacing: 16
            Label {
                text: hub.controller.hardwareStatus.message
                color: UI.Theme.secondary
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Refresh sensors"
                Layout.fillWidth: true
                onClicked: hub.controller.command("refreshSensors", null)
            }
            UI.TButton {
                text: "Open official PawnIO installer page"
                Layout.fillWidth: true
                onClicked: hub.controller.command("pawnio", null)
            }
            UI.TButton {
                text: "Restart as Administrator"
                visible: hub.controller.hardwareStatus.isWindows
                enabled: !hub.controller.hardwareStatus.isAdmin
                primary: hub.controller.hardwareStatus.needsAdmin
                Layout.fillWidth: true
                onClicked: hub.controller.command("restartAdmin", null)
            }
            UI.TButton {
                text: "Diagnostics"
                Layout.fillWidth: true
                onClicked: {
                    hardwareDialog.close();
                    hub.controller.command("diagnostics", null);
                }
            }
        }
    }
    NetworkDialog {
        id: networkDialog
        controller: hub.controller
    }
    SettingsDialog {
        id: settingsDialog
        controller: hub.controller
    }
    ProfilesDialog {
        id: profilesDialog
        controller: hub.controller
    }
    OnboardingDialog {
        id: onboardingDialog
        controller: hub.controller
    }
    UI.TDialog {
        id: updateDialog
        property var payload: ({})
        title: "Update available"
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Later"
                onClicked: updateDialog.close()
            }
            UI.TButton {
                text: "Download update"
                primary: true
                onClicked: {
                    hub.controller.downloadUpdate(updateDialog.payload);
                    updateDialog.close();
                }
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 16
            Label {
                text: "Thermal Engine " + (updateDialog.payload.version || "")
                color: UI.Theme.text
                font.pixelSize: 18
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 240
                TextArea {
                    text: updateDialog.payload.notes || ""
                    readOnly: true
                    wrapMode: Text.WordWrap
                    color: UI.Theme.secondary
                    background: Rectangle {
                        color: UI.Theme.input
                    }
                }
            }
        }
    }
}
