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
        text: "These controls affect the physical display. The editor keeps the original layout."
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
            model: ["Original orientation", "Rotate 90° clockwise", "Rotate 180°", "Rotate 90° counterclockwise", "Mirror horizontally", "Flip vertically"]
            property var values: ["normal", "rotate_90_cw", "rotate_180", "rotate_90_ccw", "flip_h", "flip_v"]
            currentIndex: Math.max(0, values.indexOf(controller.state.orientation))
            onActivated: controller.saveSettings({
                display_orientation: values[currentIndex]
            })
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
