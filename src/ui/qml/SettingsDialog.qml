import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

UI.TDialog {
    id: dialog
    property var controller
    property var draft: ({})
    title: "Settings"
    width: Math.min(760, parent.width - 40)
    function initialize(data) {
        draft = JSON.parse(JSON.stringify(data));
    }
    function setValue(key, value) {
        let copy = Object.assign({}, draft);
        copy[key] = value;
        draft = copy;
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
    footerContent: RowLayout {
        width: parent.width
        spacing: 8
        Item {
            Layout.fillWidth: true
        }
        UI.TButton {
            text: "Cancel"
            flat: true
            onClicked: dialog.close()
        }
        UI.TButton {
            text: "Save settings"
            primary: true
            onClicked: {
                let changes = {};
                for (let key of ["launch_at_login", "launch_minimized", "minimize_to_tray", "close_to_tray", "check_for_updates", "ui_theme"])
                    changes[key] = dialog.draft[key];
                if (controller.saveSettings(changes)) {
                    UI.Theme.variant = dialog.draft.ui_theme || "obsidian";
                    dialog.close();
                }
            }
        }
    }
    ColumnLayout {
        width: parent.width
        spacing: 8
        SectionLabel {
            text: "Startup & window"
        }
        // Two columns keep the whole dialog inside a 480px-high window without scrolling.
        GridLayout {
            Layout.fillWidth: true
            columns: dialog.width > 560 ? 2 : 1
            columnSpacing: 24
            rowSpacing: 0
            Repeater {
                model: [
                    {
                        key: "launch_at_login",
                        label: "Launch at login"
                    },
                    {
                        key: "launch_minimized",
                        label: "Start minimized to the tray"
                    },
                    {
                        key: "minimize_to_tray",
                        label: "Minimize to the tray"
                    },
                    {
                        key: "close_to_tray",
                        label: "Keep running when the window closes"
                    },
                    {
                        key: "check_for_updates",
                        label: "Check for updates on startup"
                    }
                ]
                UI.TCheck {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    text: modelData.label
                    checked: Boolean(dialog.draft[modelData.key])
                    onClicked: dialog.setValue(modelData.key, checked)
                }
            }
        }
        SectionLabel {
            text: "Appearance"
            Layout.topMargin: 12
        }
        UI.TCombo {
            id: themeCombo
            objectName: "themeCombo"
            Layout.fillWidth: true
            model: UI.Theme.names
            textRole: "label"
            currentIndex: Math.max(0, UI.Theme.names.findIndex(n => n.id === (dialog.draft.ui_theme || "obsidian")))
            onActivated: dialog.setValue("ui_theme", UI.Theme.names[currentIndex].id)
        }
        Label {
            Layout.fillWidth: true
            Layout.topMargin: 8
            text: "Frame rate, brightness and orientation of the display are in the Display tab of the right panel."
            color: UI.Theme.muted
            wrapMode: Text.WordWrap
            font.family: UI.Theme.uiFont
            font.pixelSize: 12
            font.hintingPreference: Font.PreferNoHinting
        }
    }
}
