import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

UI.TDialog {
    id: dialog
    property var controller
    property int step: 0
    property int deviceIndex: -1
    property string presetName: ""
    title: "Welcome to Display Studio"
    width: Math.min(760, parent.width - 40)
    onClosed: controller.checkHardwareAccess()
    function initialize() {
        step = 0;
        deviceIndex = -1;
        presetName = "";
        nativeWidth.text = controller.state.width;
        nativeHeight.text = controller.state.height;
    }
    footerContent: RowLayout {
        width: parent.width
        UI.TButton {
            text: "Later"
            onClicked: dialog.close()
        }
        Item {
            Layout.fillWidth: true
        }
        UI.TButton {
            text: "Back"
            visible: dialog.step > 0
            onClicked: dialog.step--
        }
        UI.TButton {
            text: dialog.step === 2 ? "Start creating" : "Next"
            primary: true
            enabled: nativeWidth.acceptableInput && nativeHeight.acceptableInput
            onClicked: {
                if (dialog.step < 2) {
                    dialog.step++;
                    if (dialog.step === 2)
                        dialog.presetName = "";
                } else {
                    controller.finishOnboarding(dialog.deviceIndex, Number(nativeWidth.text), Number(nativeHeight.text), dialog.presetName);
                    dialog.close();
                }
            }
        }
    }
    ColumnLayout {
        width: parent.width
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            Repeater {
                model: ["Display", "Resolution", "Starting theme"]
                Label {
                    required property string modelData
                    required property int index
                    text: (index + 1) + "  " + modelData
                    color: dialog.step === index ? UI.Theme.accent : UI.Theme.muted
                    Layout.fillWidth: true
                    Layout.preferredWidth: 0
                    font.pixelSize: 12
                }
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(140, Math.min(dialog.step === 0 ? Math.max(180, deviceList.contentHeight + 80) : dialog.step === 1 ? 180 : 320, dialog.parent.height - 260))
            currentIndex: dialog.step
            ColumnLayout {
                Label {
                    text: "Choose your display, or start creating offline."
                    color: UI.Theme.secondary
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
                UI.TButton {
                    text: "Offline editor"
                    Layout.fillWidth: true
                    selected: dialog.deviceIndex === -1
                    onClicked: dialog.deviceIndex = -1
                }
                ListView {
                    id: deviceList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: controller.devices
                    spacing: 8
                    clip: true
                    delegate: UI.TButton {
                        required property var row
                        width: deviceList.width
                        text: row.name
                        selected: dialog.deviceIndex === row.index
                        onClicked: {
                            dialog.deviceIndex = row.index;
                            nativeWidth.text = row.width;
                            nativeHeight.text = row.height;
                        }
                    }
                    Label {
                        anchors.centerIn: parent
                        width: parent.width - 40
                        visible: deviceList.count === 0
                        text: "No supported display detected.\nPlug the cooler's USB cable in and reopen this wizard, or design offline now and connect later with the Connect button."
                        color: UI.Theme.muted
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        lineHeight: 1.4
                    }
                }
            }
            ColumnLayout {
                Label {
                    text: "Match your panel's native resolution."
                    color: UI.Theme.secondary
                }
                UI.TCombo {
                    Layout.fillWidth: true
                    model: controller.sizeProfiles
                    textRole: "name"
                    onActivated: {
                        nativeWidth.text = model[currentIndex].width;
                        nativeHeight.text = model[currentIndex].height;
                        dialog.presetName = "";
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    UI.TField {
                        id: nativeWidth
                        Layout.fillWidth: true
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
                        id: nativeHeight
                        Layout.fillWidth: true
                        validator: IntValidator {
                            bottom: 160
                            top: 4096
                        }
                    }
                }
                Label {
                    text: "Custom sizes are saved for this device. You can change them later."
                    color: UI.Theme.muted
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Item {
                    Layout.fillHeight: true
                }
            }
            ColumnLayout {
                RowLayout {
                    Label {
                        text: "Choose a theme or a blank canvas."
                        color: UI.Theme.secondary
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    UI.TButton {
                        text: "Blank theme"
                        primary: dialog.presetName === ""
                        onClicked: dialog.presetName = ""
                    }
                }
                GridView {
                    id: themes
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: controller.presets
                    cellWidth: width / Math.max(1, Math.floor(width / 200))
                    cellHeight: 170
                    clip: true
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        required property var row
                        width: themes.cellWidth - 12
                        height: 158
                        radius: 8
                        color: UI.Theme.input
                        border.color: dialog.presetName === row.name ? UI.Theme.accent : UI.Theme.border
                        Image {
                            x: 8
                            y: 8
                            width: parent.width - 16
                            height: 100
                            source: "image://thumbs/preset/" + row.name
                            fillMode: Image.PreserveAspectFit
                        }
                        Text {
                            x: 10
                            y: 138
                            width: parent.width - 20
                            text: row.width + " × " + row.height + " · " + (row.builtin ? "Built-in" : "Personal")
                            elide: Text.ElideRight
                            color: UI.Theme.muted
                            font.pixelSize: 10
                        }
                        Text {
                            x: 10
                            y: 116
                            width: parent.width - 20
                            text: row.name
                            elide: Text.ElideRight
                            color: UI.Theme.text
                            font.pixelSize: 12
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: dialog.presetName = row.name
                        }
                    }
                }
            }
        }
    }
}
