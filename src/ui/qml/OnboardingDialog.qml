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
        profileCombo.currentIndex = -1;
    }
    component Body: Label {
        Layout.fillWidth: true
        color: UI.Theme.secondary
        wrapMode: Text.WordWrap
        lineHeight: 1.25
        font.family: UI.Theme.uiFont
        font.pixelSize: 13
        font.hintingPreference: Font.PreferNoHinting
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
    // Selectable row; the picked one gets a fill and an accent outline.
    component PickRow: Button {
        id: pick
        property bool picked: false
        property string detail: ""
        implicitHeight: 48
        leftPadding: 16
        rightPadding: 16
        hoverEnabled: true
        Accessible.name: text + (detail.length ? ", " + detail : "")
        Accessible.checked: picked
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
            color: pick.picked || pick.down || pick.hovered ? UI.Theme.selected : UI.Theme.raised
            border.width: pick.picked || pick.visualFocus ? 2 : 0
            border.color: UI.Theme.accent
        }
    }
    footerContent: RowLayout {
        width: parent.width
        spacing: 8
        UI.TButton {
            text: "Later"
            flat: true
            onClicked: dialog.close()
        }
        Item {
            Layout.fillWidth: true
        }
        UI.TButton {
            text: "Back"
            flat: true
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
            spacing: 10
            Repeater {
                model: ["Display", "Resolution", "Starting theme"]
                ColumnLayout {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 8
                    Rectangle {
                        Layout.fillWidth: true
                        height: 3
                        radius: 1.5
                        color: dialog.step >= index ? UI.Theme.accent : UI.Theme.border
                    }
                    Label {
                        text: (index + 1) + "  " + modelData
                        color: dialog.step === index ? UI.Theme.text : UI.Theme.muted
                        font.family: UI.Theme.uiFont
                        font.pixelSize: 12
                        font.weight: dialog.step === index ? Font.DemiBold : Font.Normal
                        font.hintingPreference: Font.PreferNoHinting
                    }
                }
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(140, Math.min(dialog.step === 0 ? Math.max(200, deviceList.contentHeight + 140) : dialog.step === 1 ? 220 : 320, dialog.parent.height - 260))
            currentIndex: dialog.step
            ColumnLayout {
                spacing: 12
                Body {
                    text: "Choose your display, or start creating offline."
                }
                PickRow {
                    text: "Offline editor"
                    detail: "No device"
                    Layout.fillWidth: true
                    picked: dialog.deviceIndex === -1
                    onClicked: dialog.deviceIndex = -1
                }
                ListView {
                    id: deviceList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: controller.devices
                    spacing: 8
                    clip: true
                    delegate: PickRow {
                        required property var row
                        width: deviceList.width
                        text: row.name
                        detail: row.width + " × " + row.height
                        picked: dialog.deviceIndex === row.index
                        onClicked: {
                            dialog.deviceIndex = row.index;
                            nativeWidth.text = row.width;
                            nativeHeight.text = row.height;
                            profileCombo.currentIndex = -1;
                        }
                    }
                    Body {
                        anchors.centerIn: parent
                        width: parent.width - 40
                        visible: deviceList.count === 0
                        text: "No supported display detected.\nPlug the cooler's USB cable in and reopen this wizard, or design offline now and connect later with the Connect button."
                        color: UI.Theme.muted
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
            ColumnLayout {
                spacing: 14
                Body {
                    text: "Match your panel's native resolution."
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    SectionLabel {
                        text: "Size profile"
                    }
                    UI.TCombo {
                        id: profileCombo
                        Layout.fillWidth: true
                        model: controller.sizeProfiles
                        textRole: "name"
                        currentIndex: -1
                        displayText: currentIndex < 0 ? "Custom size" : currentText
                        onActivated: {
                            nativeWidth.text = model[currentIndex].width;
                            nativeHeight.text = model[currentIndex].height;
                            dialog.presetName = "";
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
                            id: nativeWidth
                            Layout.fillWidth: true
                            font.family: UI.Theme.monoFont
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
                            id: nativeHeight
                            Layout.fillWidth: true
                            font.family: UI.Theme.monoFont
                            Accessible.name: "Height"
                            errorText: text.length > 0 && !acceptableInput ? "160 to 4096" : ""
                            validator: IntValidator {
                                bottom: 160
                                top: 4096
                            }
                        }
                    }
                }
                Body {
                    text: "Custom sizes are saved for this device. You can change them later."
                    color: UI.Theme.muted
                    font.pixelSize: 12
                }
                Item {
                    Layout.fillHeight: true
                }
            }
            ColumnLayout {
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    Body {
                        text: "Choose a theme or a blank canvas."
                    }
                    UI.TButton {
                        text: "Blank theme"
                        primary: dialog.presetName === ""
                        selected: dialog.presetName === ""
                        onClicked: dialog.presetName = ""
                    }
                }
                GridView {
                    id: themes
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: controller.presets
                    cellWidth: width / Math.max(1, Math.floor(width / 200))
                    cellHeight: 176
                    clip: true
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Button {
                        id: card
                        required property var row
                        width: themes.cellWidth - 12
                        height: 164
                        padding: 0
                        hoverEnabled: true
                        text: row.name
                        Accessible.name: row.name
                        Accessible.checked: dialog.presetName === row.name
                        onClicked: dialog.presetName = row.name
                        background: Rectangle {
                            radius: UI.Theme.radius
                            color: card.hovered || dialog.presetName === card.row.name ? UI.Theme.selected : UI.Theme.raised
                            border.width: dialog.presetName === card.row.name || card.visualFocus ? 2 : 0
                            border.color: UI.Theme.accent
                        }
                        contentItem: Item {
                            Rectangle {
                                x: 8
                                y: 8
                                width: parent.width - 16
                                height: 100
                                radius: UI.Theme.radiusSmall
                                color: UI.Theme.background
                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    source: "image://thumbs/preset/" + card.row.name
                                    fillMode: Image.PreserveAspectFit
                                }
                            }
                            Text {
                                x: 10
                                y: 116
                                width: parent.width - 20
                                text: card.row.name
                                elide: Text.ElideRight
                                color: UI.Theme.text
                                font.family: UI.Theme.uiFont
                                font.pixelSize: 13
                                font.weight: Font.Medium
                                font.hintingPreference: Font.PreferNoHinting
                            }
                            Text {
                                x: 10
                                y: 138
                                width: parent.width - 20
                                text: card.row.width + " × " + card.row.height + " · " + (card.row.builtin ? "Built-in" : "Personal")
                                elide: Text.ElideRight
                                color: UI.Theme.muted
                                font.family: UI.Theme.monoFont
                                font.pixelSize: 11
                                font.hintingPreference: Font.PreferNoHinting
                            }
                        }
                    }
                }
            }
        }
    }
}
