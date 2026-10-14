import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

ColumnLayout {
    id: inspector
    property var controller
    property int activeTab: 0
    property var sectionState: ({})
    spacing: 0
    function isOpen(title, fallback) {
        return sectionState[title] === undefined ? fallback : sectionState[title];
    }
    function remember(title, open) {
        let copy = Object.assign({}, sectionState);
        copy[title] = open;
        sectionState = copy;
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.margins: 12
        spacing: 4
        UI.TButton {
            Layout.fillWidth: true
            text: "Properties"
            selected: inspector.activeTab === 0
            onClicked: inspector.activeTab = 0
        }
        UI.TButton {
            Layout.fillWidth: true
            text: "Display"
            selected: inspector.activeTab === 1
            onClicked: inspector.activeTab = 1
        }
    }
    Flickable {
        id: scroll
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        contentHeight: body.implicitHeight + 32
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: body
            x: 16
            y: 8
            width: scroll.width - 32
            spacing: 16
            DisplayControls {
                visible: inspector.activeTab === 1
                controller: inspector.controller
            }
            ColumnLayout {
                visible: inspector.activeTab === 0
                Layout.fillWidth: true
                spacing: 16
                Label {
                    text: controller.state.selectionCount > 1 ? controller.state.selectionCount + " elements selected" : controller.state.selectionCount ? "Element properties" : "Theme properties"
                    color: UI.Theme.text
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }
                ColumnLayout {
                    visible: controller.state.selectionCount === 0
                    Layout.fillWidth: true
                    spacing: 16
                    UI.TSection {
                        title: "Theme"
                        UI.TCaption {
                            text: "Name"
                        }
                        UI.TField {
                            Layout.fillWidth: true
                            text: controller.state.name
                            placeholderText: "Theme name"
                            onEditingFinished: controller.command("name", text)
                        }
                        UI.TCaption {
                            text: "Background color"
                        }
                        RowLayout {
                            UI.TField {
                                Layout.fillWidth: true
                                text: controller.state.background
                                onEditingFinished: controller.command("background", text)
                            }
                            UI.TButton {
                                text: "Color"
                                onClicked: controller.command("color", "theme")
                            }
                        }
                        UI.TSwatches {
                            Layout.fillWidth: true
                            colors: controller.colorSwatches
                            onPicked: function (color) {
                                controller.command("background", color);
                            }
                        }
                    }
                    UI.TSection {
                        title: "Background media"
                        Label {
                            Layout.fillWidth: true
                            text: controller.state.video.enabled ? controller.state.video.video_path.split(/[\\/]/).pop() : "No background media"
                            color: UI.Theme.secondary
                            wrapMode: Text.WrapAnywhere
                            font.pixelSize: 11
                        }
                        UI.TButton {
                            text: "Choose GIF or video..."
                            Layout.fillWidth: true
                            onClicked: controller.command("video", null)
                        }
                        UI.TCombo {
                            Layout.fillWidth: true
                            model: ["Fit height", "Fit width"]
                            currentIndex: controller.state.video.fit_mode === "fit_width" ? 1 : 0
                            onActivated: controller.command("videoFit", currentIndex ? "fit_width" : "fit_height")
                        }
                        UI.TButton {
                            text: "Remove background media"
                            Layout.fillWidth: true
                            enabled: controller.state.video.enabled
                            onClicked: controller.command("clearVideo", null)
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: "Select a layer to edit its properties. Rotation and brightness are in the Display tab."
                        color: UI.Theme.muted
                        wrapMode: Text.WordWrap
                        font.pixelSize: 11
                    }
                }
                ColumnLayout {
                    visible: controller.state.selectionCount > 0
                    Layout.fillWidth: true
                    spacing: 16
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: controller.state.selectionCount === 1
                        UI.TCaption {
                            text: "Name"
                        }
                        UI.TField {
                            Layout.fillWidth: true
                            text: controller.selected.name || ""
                            Accessible.name: "Element name"
                            enabled: !controller.selected.locked
                            onEditingFinished: controller.edit("name", text)
                        }
                        RowLayout {
                            UI.TCheck {
                                text: "Visible"
                                checked: controller.selected.visible || false
                                onClicked: controller.edit("visible", checked)
                            }
                            UI.TCheck {
                                text: "Locked"
                                checked: controller.selected.locked || false
                                onClicked: controller.edit("locked", checked)
                            }
                        }
                        Label {
                            text: controller.typeLabels[controller.selected.type] || ""
                            color: UI.Theme.muted
                            font.pixelSize: 11
                        }
                    }
                    UI.TSection {
                        title: "Position & size"
                        visible: controller.state.selectionCount === 1
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 10
                            Repeater {
                                model: controller.propertyRows.filter(function(row) { return row.section === "Position & size"; })
                                UI.PropertyRow {
                                    required property var modelData
                                    Layout.preferredWidth: 1
                                    spec: modelData
                                    controller: inspector.controller
                                    enabled: !inspector.controller.selected.locked
                                }
                            }
                        }
                    }
                    UI.TSection {
                        title: "Data source"
                        visible: controller.state.selectionCount === 1 && ["image", "gif", "rectangle", "clock", "digital_clock", "analog_clock"].indexOf(controller.selected.type) < 0
                        SourcePicker {
                            controller: inspector.controller
                            enabled: !controller.selected.locked
                        }
                        UI.TButton {
                            text: controller.selected.condition && Object.keys(controller.selected.condition).length ? "Edit conditional rule..." : "Add conditional rule..."
                            Layout.fillWidth: true
                            enabled: !controller.selected.locked
                            onClicked: controller.command("condition", null)
                        }
                    }
                    UI.TButton {
                        visible: controller.state.selectionCount === 1 && ["image", "gif", "rectangle", "clock", "digital_clock", "analog_clock"].indexOf(controller.selected.type) >= 0
                        text: "Conditional visibility..."
                        Layout.fillWidth: true
                        enabled: !controller.selected.locked
                        onClicked: controller.command("condition", null)
                    }
                    UI.TSection {
                        title: "Align & group"
                        visible: controller.state.selectionCount > 1
                        Flow {
                            Layout.fillWidth: true
                            Layout.preferredHeight: childrenRect.height
                            spacing: 6
                            Repeater {
                                model: ["left", "center", "right", "top", "middle", "bottom", "horizontal", "vertical"]
                                UI.TButton {
                                    required property string modelData
                                    text: modelData
                                    onClicked: controller.command("align", modelData)
                                }
                            }
                        }
                        UI.TButton {
                            text: "Group elements..."
                            Layout.fillWidth: true
                            onClicked: controller.command("group", null)
                        }
                    }
                    Repeater {
                        model: controller.propertySections.filter(function(section) { return section.title !== "Position & size"; })
                        UI.TSection {
                            required property var modelData
                            title: modelData.title
                            expanded: inspector.isOpen(title, modelData.open)
                            onToggled: function (open) {
                                inspector.remember(title, open);
                            }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: title === "Position & size" ? 2 : 1
                                columnSpacing: 10
                                rowSpacing: 12
                                Repeater {
                                    model: modelData.rows
                                    UI.PropertyRow {
                                        required property var modelData
                                        Layout.preferredWidth: 1  // equal columns
                                        spec: modelData
                                        controller: inspector.controller
                                        enabled: !inspector.controller.selected.locked
                                    }
                                }
                            }
                        }
                    }
                    UI.TSection {
                        title: "Organization"
                        expanded: false
                        visible: controller.state.selectionCount === 1
                        UI.TField {
                            Layout.fillWidth: true
                            placeholderText: "Group name (optional)"
                            text: controller.selected.group || ""
                            enabled: !controller.selected.locked
                            onEditingFinished: controller.edit("group", text)
                        }
                    }
                    UI.TButton {
                        text: "Delete selected elements"
                        destructive: true
                        Layout.fillWidth: true
                        onClicked: controller.command("delete", null)
                    }
                }
            }
        }
    }
}
