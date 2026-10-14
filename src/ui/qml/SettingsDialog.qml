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
            text: "Save settings"
            primary: true
            onClicked: {
                let changes = {};
                for (let key of ["launch_at_login", "launch_minimized", "minimize_to_tray", "close_to_tray", "check_for_updates"])
                    changes[key] = dialog.draft[key];
                if (controller.saveSettings(changes))
                    dialog.close();
            }
        }
    }
    ColumnLayout {
        width: parent.width
        spacing: 16
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            Label {
                text: "STARTUP & WINDOW"
                color: UI.Theme.muted
                font.pixelSize: 10
                bottomPadding: 8
            }
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
                    text: modelData.label
                    checked: Boolean(dialog.draft[modelData.key])
                    onClicked: dialog.setValue(modelData.key, checked)
                }
            }
            Label {
                text: "Frame rate, brightness and orientation of the display are in the Display tab of the right panel."
                color: UI.Theme.muted
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                topPadding: 12
            }
        }
    }
}
