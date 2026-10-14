import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

ColumnLayout {
    id: display
    property var controller
    Layout.fillWidth: true
    spacing: 16
    Label {
        text: "Display output"
        color: UI.Theme.text
        font.pixelSize: 17
        font.weight: Font.DemiBold
    }
    Label {
        Layout.fillWidth: true
        text: "These controls affect the physical display. The editor keeps the original layout."
        wrapMode: Text.WordWrap
        color: UI.Theme.secondary
        font.pixelSize: 12
    }
    UI.TSection {
        title: "Device & resolution"
        Label {
            Layout.fillWidth: true
            text: controller.state.device
            color: UI.Theme.secondary
            wrapMode: Text.WordWrap
        }
        Label {
            text: controller.state.width + " × " + controller.state.height
            color: UI.Theme.text
            font.pixelSize: 20
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
        Label {
            text: "Rotate image"
            color: UI.Theme.secondary
            font.pixelSize: 11
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
            Label {
                text: "Brightness (%)"
                color: UI.Theme.secondary
                Layout.fillWidth: true
            }
            UI.TField {
                Layout.preferredWidth: 72
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
            font.pixelSize: 11
        }
        UI.TButton {
            Layout.fillWidth: true
            text: "Send frame now"
            enabled: controller.state.connected
            onClicked: controller.command("send", null)
        }
    }
}
