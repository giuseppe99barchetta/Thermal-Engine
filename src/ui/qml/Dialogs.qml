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

    // Shared text styles: body copy, muted footnote, 11px uppercase section label.
    component Body: Label {
        Layout.fillWidth: true
        color: UI.Theme.secondary
        wrapMode: Text.WordWrap
        lineHeight: 1.25
        font.family: UI.Theme.uiFont
        font.pixelSize: 13
        font.hintingPreference: Font.PreferNoHinting
    }
    component Note: Body {
        color: UI.Theme.muted
        font.pixelSize: 12
    }
    component SectionLabel: Label {
        color: UI.Theme.muted
        font.family: UI.Theme.uiFont
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.letterSpacing: 0.9
        font.capitalization: Font.AllUppercase
        font.hintingPreference: Font.PreferNoHinting
    }
    // Selectable row used by the device list: name left, technical detail right.
    component PickRow: Button {
        id: pick
        property string detail: ""
        implicitHeight: 48
        leftPadding: 16
        rightPadding: 16
        hoverEnabled: true
        Accessible.name: text + (detail.length ? ", " + detail : "")
        contentItem: RowLayout {
            spacing: 12
            Text {
                Layout.fillWidth: true
                text: pick.text
                color: UI.Theme.text
                elide: Text.ElideRight
                font.family: UI.Theme.uiFont
                font.pixelSize: 14
                font.weight: Font.Medium
                font.hintingPreference: Font.PreferNoHinting
            }
            Text {
                text: pick.detail
                color: UI.Theme.muted
                font.family: UI.Theme.monoFont
                font.pixelSize: 12
                font.hintingPreference: Font.PreferNoHinting
            }
        }
        background: Rectangle {
            radius: UI.Theme.radius
            color: pick.down || pick.hovered ? UI.Theme.selected : UI.Theme.raised
            Rectangle {
                anchors.fill: parent
                anchors.margins: -2
                radius: parent.radius + 2
                color: "transparent"
                border.width: 2
                border.color: UI.Theme.accent
                visible: pick.visualFocus
            }
        }
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
                resolutionDialog.initialize();
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

    // Unsaved changes: Esc answers "cancel" through onRejected; the buttons answer once, then close().
    UI.TDialog {
        id: unsavedDialog
        objectName: "unsavedDialog"
        property var payload: ({})
        title: "Unsaved changes"
        width: Math.min(480, parent.width - 40)
        property bool answered: false
        function resolve(choice) {
            answered = true;
            let token = payload.token;
            close();
            hub.controller.answer(token, choice !== "cancel", choice === "cancel" ? "" : choice);
        }
        onAboutToShow: answered = false
        // Esc, the window close button or a programmatic close() all end here: an unanswered token would block guard_changes
        onClosed: if (!answered) {
            answered = true;
            hub.controller.answer(payload.token, false, "");
        }
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                flat: true
                onClicked: unsavedDialog.resolve("cancel")
            }
            UI.TButton {
                text: "Discard changes"
                flat: true
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
            Body {
                text: "Save changes to " + (unsavedDialog.payload.name || "this theme") + " before continuing?"
                font.pixelSize: 14
            }
        }
    }

    UI.TDialog {
        id: messageDialog
        property var payload: ({})
        property bool confirmation: false
        property bool answered: false
        title: messageDialog.payload.title || "Thermal Engine"
        width: Math.min(480, parent.width - 40)
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                visible: messageDialog.confirmation
                text: "Cancel"
                flat: true
                onClicked: messageDialog.close()
            }
            UI.TButton {
                text: messageDialog.confirmation ? "Continue" : "Close"
                primary: true
                onClicked: {
                    let token = messageDialog.payload.token;
                    let accepted = messageDialog.confirmation;
                    messageDialog.answered = true;
                    messageDialog.close();
                    if (accepted)
                        hub.controller.answer(token, true, "");
                }
            }
        }
        ColumnLayout {
            width: parent.width
            Body {
                text: messageDialog.payload.message || ""
                font.pixelSize: 14
            }
        }
        onAboutToShow: answered = false
        // Cancel, Esc and programmatic close() all answer false exactly once (the Continue button sets answered first)
        onClosed: if (confirmation && !answered) {
            answered = true;
            hub.controller.answer(payload.token, false, "");
        }
    }

    UI.TDialog {
        id: promptDialog
        property var payload: ({})
        title: promptDialog.payload.title || "Name"
        width: Math.min(460, parent.width - 40)
        property bool answered: false
        function submit() {
            if (!promptField.text.trim())
                return;
            answered = true;
            let token = payload.token;
            close();
            hub.controller.answer(token, true, promptField.text);
        }
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                flat: true
                onClicked: promptDialog.close()
            }
            UI.TButton {
                text: "Save"
                primary: true
                enabled: promptField.text.trim().length > 0
                onClicked: promptDialog.submit()
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 8
            SectionLabel {
                text: promptDialog.payload.label || "Name"
            }
            UI.TField {
                id: promptField
                Layout.fillWidth: true
                selectByMouse: true
                Accessible.name: promptDialog.payload.label || "Name"
                onAccepted: promptDialog.submit()
            }
        }
        onAboutToShow: answered = false
        onOpened: promptField.forceActiveFocus()
        onClosed: if (!answered) {
            answered = true;
            hub.controller.answer(payload.token, false, "");
        }
    }

    UI.TDialog {
        id: conditionDialog
        title: "Conditional rule"
        width: Math.min(520, parent.width - 40)
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
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                flat: true
                onClicked: conditionDialog.close()
            }
            UI.TButton {
                text: "Apply rule"
                primary: true
                enabled: !conditionEnabled.checked || hub.controller.sources.length > 0
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
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 12
                enabled: conditionEnabled.checked
                opacity: enabled ? 1 : 0.5
                SectionLabel {
                    text: "When"
                }
                UI.TCombo {
                    id: conditionSource
                    Layout.fillWidth: true
                    model: hub.controller.sources
                    textRole: "name"
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    UI.TCombo {
                        id: conditionComparison
                        Layout.preferredWidth: 84
                        model: ["==", "!=", ">", ">=", "<", "<="]
                    }
                    UI.TField {
                        id: conditionValue
                        Layout.fillWidth: true
                        font.family: UI.Theme.monoFont
                        placeholderText: "Number, exact text or true/false"
                    }
                }
                SectionLabel {
                    text: "Then"
                    Layout.topMargin: 4
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
                    font.family: UI.Theme.monoFont
                    placeholderText: "Hex color"
                }
                UI.TField {
                    id: conditionText
                    visible: conditionAction.currentIndex === 1
                    Layout.fillWidth: true
                    placeholderText: "Replacement text"
                }
            }
            Note {
                text: "Missing data never matches. A manually hidden element stays hidden."
            }
        }
    }

    UI.TDialog {
        id: diagnosticsDialog
        title: "Diagnostics"
        width: Math.min(760, parent.width - 40)
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Copy report"
                flat: true
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
            spacing: 10
            Repeater {
                model: hub.controller.healthChecks
                Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: statusCard.implicitHeight + 28
                    color: UI.Theme.raised
                    radius: UI.Theme.radius
                    ColumnLayout {
                        id: statusCard
                        x: 16
                        y: 14
                        width: parent.width - 32
                        spacing: 6
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                text: modelData.name
                                color: UI.Theme.text
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                font.family: UI.Theme.uiFont
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                font.hintingPreference: Font.PreferNoHinting
                            }
                            UI.TChip {
                                text: modelData.status
                                tone: modelData.severity === "success" ? "success" : modelData.severity === "warning" ? "warning" : modelData.severity === "danger" ? "danger" : "muted"
                            }
                        }
                        Body {
                            text: modelData.detail
                            font.pixelSize: 12
                        }
                        UI.TButton {
                            visible: (modelData.actionLabel || "").length > 0
                            text: modelData.actionLabel || ""
                            Layout.topMargin: 2
                            onClicked: {
                                diagnosticsDialog.close();
                                hub.controller.command(modelData.action, null);
                            }
                        }
                    }
                }
            }
            UI.TSection {
                title: "Network readings"
                visible: hub.controller.networkHealth.length > 0
                expanded: false
                Repeater {
                    model: hub.controller.networkHealth
                    Body {
                        required property var modelData
                        text: modelData.name + " · " + modelData.status + (modelData.age === null ? " · No reading yet" : " · " + modelData.age + " seconds ago")
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
                        font.family: UI.Theme.monoFont
                        font.pixelSize: 12
                        font.hintingPreference: Font.PreferNoHinting
                        wrapMode: Text.WrapAnywhere
                        padding: 12
                        Accessible.name: "Technical report"
                        background: Rectangle {
                            color: UI.Theme.input
                            radius: UI.Theme.radiusSmall
                        }
                    }
                }
            }
        }
    }

    UI.TDialog {
        id: consoleDialog
        title: "Console"
        width: Math.min(820, parent.width - 40)
        onOpened: consoleArea.cursorPosition = consoleArea.length
        footerContent: RowLayout {
            width: parent.width
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Close"
                primary: true
                onClicked: consoleDialog.close()
            }
        }
        ColumnLayout {
            width: parent.width
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(160, Math.min(380, hub.height - 240))
                clip: true
                TextArea {
                    id: consoleArea
                    text: hub.consoleText
                    readOnly: true
                    selectByMouse: true
                    color: UI.Theme.secondary
                    font.family: UI.Theme.monoFont
                    font.pixelSize: 12
                    font.hintingPreference: Font.PreferNoHinting
                    wrapMode: Text.WrapAnywhere
                    padding: 12
                    Accessible.name: "Console output"
                    background: Rectangle {
                        color: UI.Theme.input
                        radius: UI.Theme.radiusSmall
                    }
                }
            }
        }
    }

    UI.TDialog {
        id: resolutionDialog
        title: "Display resolution"
        width: Math.min(480, parent.width - 40)
        function initialize() {
            resolutionWidth.text = hub.controller.state.width;
            resolutionHeight.text = hub.controller.state.height;
            let profiles = hub.controller.sizeProfiles;
            resolutionProfile.currentIndex = -1;
            for (let i = 0; i < profiles.length; i++)
                if (profiles[i].width === hub.controller.state.width && profiles[i].height === hub.controller.state.height)
                    resolutionProfile.currentIndex = i;
        }
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Cancel"
                flat: true
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
            spacing: 14
            Body {
                text: "Choose the native resolution of your panel. Some displays share a USB identifier."
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                SectionLabel {
                    text: "Size profile"
                }
                UI.TCombo {
                    id: resolutionProfile
                    Layout.fillWidth: true
                    model: hub.controller.sizeProfiles
                    textRole: "name"
                    displayText: currentIndex < 0 ? "Custom size" : currentText
                    onActivated: {
                        resolutionWidth.text = model[currentIndex].width;
                        resolutionHeight.text = model[currentIndex].height;
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 6
                    SectionLabel {
                        text: "Width"
                    }
                    UI.TField {
                        id: resolutionWidth
                        Layout.fillWidth: true
                        font.family: UI.Theme.monoFont
                        placeholderText: "Width"
                        Accessible.name: "Width"
                        errorText: text.length > 0 && !acceptableInput ? "160 to 4096" : ""
                        validator: IntValidator {
                            bottom: 160
                            top: 4096
                        }
                    }
                }
                Label {
                    text: "×"
                    color: UI.Theme.muted
                    Layout.alignment: Qt.AlignBottom
                    Layout.bottomMargin: 5
                    font.family: UI.Theme.uiFont
                    font.pixelSize: 14
                    font.hintingPreference: Font.PreferNoHinting
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 6
                    SectionLabel {
                        text: "Height"
                    }
                    UI.TField {
                        id: resolutionHeight
                        Layout.fillWidth: true
                        font.family: UI.Theme.monoFont
                        placeholderText: "Height"
                        Accessible.name: "Height"
                        errorText: text.length > 0 && !acceptableInput ? "160 to 4096" : ""
                        validator: IntValidator {
                            bottom: 160
                            top: 4096
                        }
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
        width: Math.min(520, parent.width - 40)
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Refresh devices"
                flat: true
                onClicked: hub.controller.openDevices()
            }
            UI.TButton {
                text: "Continue offline"
                primary: true
                onClicked: devicesDialog.close()
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 14
            Body {
                text: "Connect your display by USB, then refresh the list."
            }
            ListView {
                id: deviceList
                Layout.fillWidth: true
                Layout.preferredHeight: count ? Math.min(240, contentHeight) : 96
                model: hub.controller.devices
                spacing: 8
                clip: true
                delegate: PickRow {
                    required property var row
                    width: ListView.view.width
                    text: row.name + (row.experimental ? " · Experimental" : "")
                    detail: row.width + " × " + row.height
                    onClicked: {
                        hub.controller.connectDevice(row.index);
                        devicesDialog.close();
                    }
                }
                Note {
                    anchors.centerIn: parent
                    width: parent.width - 40
                    visible: deviceList.count === 0
                    horizontalAlignment: Text.AlignHCenter
                    text: "No display found. You can keep editing offline."
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
        width: Math.min(520, parent.width - 40)
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Continue"
                primary: !hub.controller.hardwareStatus.needsAdmin
                onClicked: hardwareDialog.close()
            }
        }
        ColumnLayout {
            width: parent.width
            spacing: 14
            UI.TChip {
                visible: hub.controller.hardwareStatus.cpuAvailable !== undefined
                text: hub.controller.hardwareStatus.cpuAvailable ? "CPU sensors available" : hub.controller.hardwareStatus.needsAdmin ? "Administrator access needed" : "CPU sensors unavailable"
                tone: hub.controller.hardwareStatus.cpuAvailable ? "success" : "warning"
            }
            Body {
                text: hub.controller.hardwareStatus.message || ""
                font.pixelSize: 14
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
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
                    visible: hub.controller.hardwareStatus.isWindows === true
                    enabled: !hub.controller.hardwareStatus.isAdmin
                    primary: hub.controller.hardwareStatus.needsAdmin === true
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
        width: Math.min(540, parent.width - 40)
        footerContent: RowLayout {
            width: parent.width
            spacing: 8
            Item {
                Layout.fillWidth: true
            }
            UI.TButton {
                text: "Later"
                flat: true
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
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Label {
                    text: "Thermal Engine"
                    color: UI.Theme.text
                    font.family: UI.Theme.uiFont
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    font.hintingPreference: Font.PreferNoHinting
                }
                UI.TChip {
                    text: "v" + (updateDialog.payload.version || "")
                    tone: "success"
                }
                Item {
                    Layout.fillWidth: true
                }
            }
            SectionLabel {
                text: "What's new"
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(120, Math.min(240, hub.height - 300))
                clip: true
                TextArea {
                    text: updateDialog.payload.notes || ""
                    readOnly: true
                    wrapMode: Text.WordWrap
                    color: UI.Theme.secondary
                    font.family: UI.Theme.uiFont
                    font.pixelSize: 13
                    font.hintingPreference: Font.PreferNoHinting
                    padding: 12
                    Accessible.name: "Release notes"
                    background: Rectangle {
                        color: UI.Theme.input
                        radius: UI.Theme.radiusSmall
                    }
                }
            }
        }
    }
}
