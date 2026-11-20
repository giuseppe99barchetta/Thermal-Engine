import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

// Display tab of the inspector: physical output settings (the layout itself is untouched)
ColumnLayout {
    id: display
    property var controller
    Layout.fillWidth: true
    spacing: 14
    Label {
        Layout.fillWidth: true
        text: "These controls affect the physical display. A 90° turn on a wide panel switches the canvas to portrait; other options keep the layout."
        wrapMode: Text.WordWrap
        color: UI.Theme.secondary
        font.pixelSize: 12
        font.hintingPreference: Font.PreferNoHinting
    }
    UI.TSection {
        title: "Device & resolution"
        Label {
            Layout.fillWidth: true
            text: controller.state.device
            color: UI.Theme.text
            font.pixelSize: 13
            font.hintingPreference: Font.PreferNoHinting
            wrapMode: Text.WordWrap
        }
        Label {
            text: controller.state.width + " × " + controller.state.height
            color: UI.Theme.text
            font.family: UI.Theme.monoFont
            font.pixelSize: 20
            font.hintingPreference: Font.PreferNoHinting
        }
        UI.TButton {
            text: controller.state.connected ? "Disconnect display" : "Connect a display..."
            Layout.fillWidth: true
            onClicked: controller.command("connect", null)
        }
        UI.TButton {
            text: "Change resolution..."
            Layout.fillWidth: true
            onClicked: controller.requestDialog("resolution", {})
        }
    }
    UI.TSection {
        title: "Rotation & mirroring"
        UI.TCaption {
            text: "Rotate image"
            font.hintingPreference: Font.PreferNoHinting
        }
        UI.TCombo {
            objectName: "displayOrientation"
            Layout.fillWidth: true
            // On a wide panel a 90° turn makes the canvas portrait (the panel size is swapped)
            model: ["Original orientation", "Rotate 90° clockwise", "Rotate 180°", "Rotate 90° counterclockwise", "Mirror horizontally", "Flip vertically"].map((label, i) => i % 2 === 1 && i < 4 && controller.state.width !== controller.state.height ? label + " (portrait)" : label)
            property var values: ["normal", "rotate_90_cw", "rotate_180", "rotate_90_ccw", "flip_h", "flip_v"]
            currentIndex: Math.max(0, values.indexOf(controller.state.orientation))
            onActivated: controller.saveSettings({
                display_orientation: values[currentIndex]
            })
        }
    }
    UI.TSection {
        title: "More displays"
        Label {
            Layout.fillWidth: true
            text: "Experimental: each extra display shows a saved theme with live readings."
            wrapMode: Text.WordWrap
            color: UI.Theme.secondary
            font.pixelSize: 12
            font.hintingPreference: Font.PreferNoHinting
        }
        Repeater {
            model: controller.state.secondary
            ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 4
                RowLayout {
                    Layout.fillWidth: true
                    UI.TCaption {
                        Layout.fillWidth: true
                        text: modelData.name + " · " + modelData.status
                        elide: Text.ElideRight
                    }
                    UI.TIconButton {
                        iconName: "close"
                        ToolTip.text: "Stop using this display"
                        Accessible.name: "Remove " + modelData.name
                        onClicked: controller.removeSecondaryDisplay(modelData.identity)
                    }
                }
                UI.TCombo {
                    Layout.fillWidth: true
                    model: controller.state.presetNames
                    currentIndex: controller.state.presetNames.indexOf(modelData.preset)
                    onActivated: controller.setSecondaryPreset(modelData.identity, controller.state.presetNames[currentIndex])
                }
            }
        }
        UI.TButton {
            objectName: "addSecondaryDisplay"
            Layout.fillWidth: true
            text: "Add display…"
            onClicked: controller.openSecondaryPicker()
        }
    }
    UI.TSection {
        title: "Brightness & performance"
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            UI.TCaption {
                text: "Brightness (%)"
                Layout.fillWidth: true
                font.hintingPreference: Font.PreferNoHinting
            }
            UI.TField {
                Layout.preferredWidth: 72
                font.family: UI.Theme.monoFont
                font.hintingPreference: Font.PreferNoHinting
                Accessible.name: "Brightness (%)"
                text: controller.state.brightness
                validator: IntValidator {
                    bottom: 0
                    top: 100
                }
                onEditingFinished: if (acceptableInput)
                    controller.saveSettings({
                        display_brightness: Number(text)
                    })
            }
        }
        Label {
            visible: controller.state.outputBrightness !== controller.state.brightness
            Layout.fillWidth: true
            text: "Now " + controller.state.outputBrightness + " % (" + (controller.state.dimReason === "night" ? "night" : "idle") + " dimming)"
            wrapMode: Text.WordWrap
            color: UI.Theme.accent
            font.pixelSize: 12
            font.hintingPreference: Font.PreferNoHinting
        }
        // Scheduled dimming: the display gets the lowest of Brightness and every active rule
        UI.TCheck {
            objectName: "dimNight"
            text: "Dim at night"
            checked: controller.state.dim.dim_night_enabled
            onClicked: controller.saveSettings({
                dim_night_enabled: checked
            })
        }
        RowLayout {
            visible: controller.state.dim.dim_night_enabled
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: [{key: "dim_night_start", label: "From"}, {key: "dim_night_end", label: "to"}]
                RowLayout {
                    required property var modelData
                    spacing: 6
                    UI.TCaption {
                        text: modelData.label
                    }
                    UI.TField {
                        Layout.preferredWidth: 64
                        font.family: UI.Theme.monoFont
                        Accessible.name: modelData.key === "dim_night_start" ? "Night starts" : "Night ends"
                        text: controller.state.dim[modelData.key]
                        validator: RegularExpressionValidator {
                            regularExpression: /([01][0-9]|2[0-3]):[0-5][0-9]/
                        }
                        onEditingFinished: if (acceptableInput) {
                            let change = {};
                            change[modelData.key] = text;
                            controller.saveSettings(change);
                        }
                    }
                }
            }
        }
        RowLayout {
            visible: controller.state.dim.dim_night_enabled
            Layout.fillWidth: true
            UI.TCaption {
                text: "Night brightness (%)"
                Layout.fillWidth: true
            }
            UI.TField {
                Layout.preferredWidth: 72
                font.family: UI.Theme.monoFont
                Accessible.name: "Night brightness (%)"
                text: controller.state.dim.dim_night_level
                validator: IntValidator {
                    bottom: 0
                    top: 100
                }
                onEditingFinished: if (acceptableInput)
                    controller.saveSettings({
                        dim_night_level: Number(text)
                    })
            }
        }
        UI.TCheck {
            objectName: "dimIdle"
            visible: controller.state.idleSupported
            text: "Dim when the PC is idle"
            checked: controller.state.dim.dim_idle_enabled
            onClicked: controller.saveSettings({
                dim_idle_enabled: checked
            })
        }
        Repeater {
            model: controller.state.idleSupported && controller.state.dim.dim_idle_enabled ? [{key: "dim_idle_minutes", label: "After minutes without input", bottom: 1, top: 240}, {key: "dim_idle_level", label: "Idle brightness (%)", bottom: 0, top: 100}] : []
            RowLayout {
                required property var modelData
                Layout.fillWidth: true
                UI.TCaption {
                    text: modelData.label
                    Layout.fillWidth: true
                }
                UI.TField {
                    Layout.preferredWidth: 72
                    font.family: UI.Theme.monoFont
                    Accessible.name: modelData.label
                    text: controller.state.dim[modelData.key]
                    validator: IntValidator {
                        bottom: modelData.bottom
                        top: modelData.top
                    }
                    onEditingFinished: if (acceptableInput) {
                        let change = {};
                        change[modelData.key] = Number(text);
                        controller.saveSettings(change);
                    }
                }
            }
        }
        UI.TCaption {
            text: "Frame rate"
            font.hintingPreference: Font.PreferNoHinting
        }
        UI.TCombo {
            Layout.fillWidth: true
            model: ["10 FPS", "20 FPS", "30 FPS", "60 FPS"]
            currentIndex: Math.max(0, [10, 20, 30, 60].indexOf(controller.state.fps))
            onActivated: controller.saveSettings({
                target_fps: [10, 20, 30, 60][currentIndex]
            })
        }
        Label {
            visible: controller.state.fps === 60
            Layout.fillWidth: true
            text: "60 FPS uses more CPU and USB bandwidth."
            wrapMode: Text.WordWrap
            color: UI.Theme.warning
            font.pixelSize: 12
            font.hintingPreference: Font.PreferNoHinting
        }
        UI.TButton {
            Layout.fillWidth: true
            text: "Send frame now"
            enabled: controller.state.connected
            onClicked: controller.command("send", null)
        }
    }
}
