import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

UI.TDialog {
    id: dialog
    property var controller
    property var draft: ({})
    property var rules: []
    title: "Auto profiles"
    width: Math.min(840, parent.width - 40)
    function initialize(data) {
        draft = JSON.parse(JSON.stringify(data));
        rules = draft.profiles || [];
    }
    function setValue(key, value) {
        let copy = Object.assign({}, draft);
        copy[key] = value;
        draft = copy;
    }
    function setRule(index, key, value) {
        let copy = JSON.parse(JSON.stringify(rules));
        copy[index][key] = value;
        rules = copy;
    }
    function presetNames() {
        let names = ["None"];
        for (let i = 0; i < controller.presets.rowCount(); i++)
            names.push(controller.presets.get(i).name);
        return names;
    }
    Timer {
        id: detectTimer
        interval: 5000
        onTriggered: {
            let app = controller.foregroundApp();
            if (app.process.length) {
                dialog.rules = dialog.rules.concat([
                    {
                        app_name: app.process,
                        match_mode: "process",
                        preset_name: "Default"
                    }
                ]);
            }
        }
    }
    onClosed: detectTimer.stop()
    footerContent: RowLayout {
        width: parent.width
        Item {
            Layout.fillWidth: true
        }
        UI.TButton {
            text: "Cancel"
            onClicked: dialog.close()
        }
        UI.TButton {
            text: "Save profiles"
            primary: true
            onClicked: {
                let changes = {
                    profiles: dialog.rules,
                    profiles_enabled: dialog.draft.profiles_enabled,
                    profiles_default_preset: dialog.draft.profiles_default_preset,
                    system_profile_enabled: dialog.draft.system_profile_enabled,
                    system_idle_preset: dialog.draft.system_idle_preset,
                    system_gaming_preset: dialog.draft.system_gaming_preset
                };
                for (let key of ["system_idle_threshold", "system_idle_seconds", "system_gaming_threshold", "system_gaming_seconds"])
                    changes[key] = dialog.draft[key];
                if (controller.saveSettings(changes))
                    dialog.close();
            }
        }
    }
    ColumnLayout {
        width: parent.width
        spacing: 12
        UI.TCheck {
            text: "Automatically switch themes for applications"
            checked: Boolean(dialog.draft.profiles_enabled)
            onClicked: dialog.setValue("profiles_enabled", checked)
        }
        Label {
            text: "Match a process name or window title. Manual theme changes pause automatic switching briefly."
            color: UI.Theme.secondary
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Label {
            visible: dialog.rules.length === 0
            Layout.fillWidth: true
            text: "No application rules yet. Add one, or let the app detect the program you switch to."
            color: UI.Theme.muted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }
        ListView {
            id: rulesList
            visible: dialog.rules.length > 0
            Layout.fillWidth: true
            // Grows with the rules (44px each) up to four rows, then scrolls
            Layout.preferredHeight: Math.min(4, dialog.rules.length) * 44
            clip: true
            spacing: 8
            model: dialog.rules
            delegate: RowLayout {
                required property var modelData
                required property int index
                width: rulesList.width
                spacing: 8
                UI.TField {
                    Layout.fillWidth: true
                    text: modelData.app_name
                    placeholderText: "simhub.exe"
                    onEditingFinished: dialog.setRule(index, "app_name", text.toLowerCase())
                }
                UI.TCombo {
                    Layout.preferredWidth: 120
                    model: ["process", "title"]
                    currentIndex: modelData.match_mode === "title" ? 1 : 0
                    onActivated: dialog.setRule(index, "match_mode", currentText)
                }
                UI.TCombo {
                    Layout.preferredWidth: 200
                    model: dialog.presetNames()
                    currentIndex: Math.max(0, model.indexOf(modelData.preset_name))
                    onActivated: dialog.setRule(index, "preset_name", currentText)
                }
                UI.TButton {
                    text: "×"
                    onClicked: {
                        let copy = dialog.rules.slice();
                        copy.splice(index, 1);
                        dialog.rules = copy;
                    }
                }
            }
        }
        RowLayout {
            UI.TButton {
                text: "+ Add application rule"
                onClicked: {
                    let copy = dialog.rules.slice();
                    copy.push({
                        app_name: "",
                        match_mode: "process",
                        preset_name: "Default"
                    });
                    dialog.rules = copy;
                }
            }
            UI.TButton {
                text: detectTimer.running ? "Switch to the target app..." : "Detect application in 5 seconds"
                enabled: !detectTimer.running
                onClicked: detectTimer.start()
            }
        }
        RowLayout {
            Label {
                text: "Fallback theme"
                color: UI.Theme.secondary
                Layout.preferredWidth: 140
            }
            UI.TCombo {
                Layout.fillWidth: true
                model: dialog.presetNames()
                currentIndex: Math.max(0, model.indexOf(dialog.draft.profiles_default_preset))
                onActivated: dialog.setValue("profiles_default_preset", currentIndex ? currentText : null)
            }
        }
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: UI.Theme.border
            Layout.topMargin: 8
            Layout.bottomMargin: 8
        }
        UI.TCheck {
            text: "Switch themes by system activity"
            checked: Boolean(dialog.draft.system_profile_enabled)
            onClicked: dialog.setValue("system_profile_enabled", checked)
        }
        Repeater {
            model: [
                {
                    key: "system_idle_preset",
                    label: "When idle"
                },
                {
                    key: "system_gaming_preset",
                    label: "Under high CPU load"
                }
            ]
            RowLayout {
                required property var modelData
                Layout.fillWidth: true
                enabled: Boolean(dialog.draft.system_profile_enabled)
                Label {
                    text: modelData.label
                    color: UI.Theme.secondary
                    Layout.preferredWidth: 140
                }
                UI.TCombo {
                    Layout.fillWidth: true
                    model: dialog.presetNames()
                    currentIndex: Math.max(0, model.indexOf(dialog.draft[modelData.key]))
                    onActivated: dialog.setValue(modelData.key, currentIndex ? currentText : null)
                }
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 24
            rowSpacing: 8
            enabled: Boolean(dialog.draft.system_profile_enabled)
            Repeater {
                model: [
                    {
                        key: "system_idle_threshold",
                        label: "Idle CPU threshold (%)",
                        lower: 1,
                        upper: 99
                    },
                    {
                        key: "system_idle_seconds",
                        label: "Idle delay (seconds)",
                        lower: 5,
                        upper: 3600
                    },
                    {
                        key: "system_gaming_threshold",
                        label: "High CPU threshold (%)",
                        lower: 1,
                        upper: 99
                    },
                    {
                        key: "system_gaming_seconds",
                        label: "High CPU delay (seconds)",
                        lower: 1,
                        upper: 300
                    }
                ]
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Label {
                        text: modelData.label
                        color: UI.Theme.secondary
                        Layout.fillWidth: true
                    }
                    UI.TField {
                        Layout.preferredWidth: 100
                        text: String(dialog.draft[modelData.key] ?? "")
                        validator: IntValidator {
                            bottom: modelData.lower
                            top: modelData.upper
                        }
                        onEditingFinished: if (acceptableInput)
                            dialog.setValue(modelData.key, Number(text))
                    }
                }
            }
        }
    }
}
