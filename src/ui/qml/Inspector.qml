import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

ColumnLayout {
    id: inspector
    property var controller
    property int activeTab: 0
    property var sectionState: ({})
    readonly property int count: controller.state.selectionCount
    readonly property bool locked: Boolean(controller.selected.locked)
    // These types have no data source, only a visibility rule
    readonly property bool ruleOnly: ["image", "gif", "rectangle", "clock", "digital_clock", "analog_clock"].indexOf(controller.selected.type) >= 0
    readonly property string headerIcon: activeTab === 1 ? "settings" : count === 1 ? typeIcon(controller.selected.type) : "layers"
    readonly property string headerTitle: activeTab === 1 ? "Display output" : count > 1 ? count + " elements selected" : count === 1 ? (controller.selected.name || "Element") : "Theme properties"
    readonly property string headerSub: activeTab === 1 ? controller.state.device : count > 1 ? "Align, group or delete them together" : count === 1 ? (controller.typeLabels[controller.selected.type] || "") : controller.state.name
    spacing: 0
    function typeIcon(type) {
        if (type === "text" || type === "clock" || type === "digital_clock")
            return "type";
        if (type === "image" || type === "gif")
            return "image";
        if (type === "rectangle")
            return "presets";
        if (type === "line_chart")
            return "sensors";
        return "gauge";
    }
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
        Layout.leftMargin: 16
        Layout.rightMargin: 16
        Layout.topMargin: 14
        Layout.bottomMargin: 12
        spacing: 10
        Rectangle {
            Layout.preferredWidth: 32
            Layout.preferredHeight: 32
            radius: UI.Theme.radius + 1
            color: UI.Theme.selected
            UI.TIcon {
                anchors.centerIn: parent
                name: inspector.headerIcon
                color: UI.Theme.accent
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Label {
                Layout.fillWidth: true
                text: inspector.headerTitle
                color: UI.Theme.text
                font.pixelSize: 14
                font.weight: Font.DemiBold
                font.hintingPreference: Font.PreferNoHinting
                elide: Text.ElideRight
            }
            Label {
                Layout.fillWidth: true
                text: inspector.headerSub
                color: UI.Theme.muted
                font.pixelSize: 12
                font.hintingPreference: Font.PreferNoHinting
                elide: Text.ElideRight
            }
        }
    }
    UI.TSegmented {
        id: tabs
        Layout.fillWidth: true
        Layout.leftMargin: 16
        Layout.rightMargin: 16
        Layout.bottomMargin: 14
        model: ["Properties", "Display"]
        onActivated: function (index) {
            inspector.activeTab = index;
        }
    }
    Binding {  // keeps the segments in step when activeTab is set from outside
        target: tabs
        property: "currentIndex"
        value: inspector.activeTab
    }
    Rectangle {
        Layout.fillWidth: true
        height: 1
        color: UI.Theme.border
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
            spacing: 6
            DisplayControls {
                visible: inspector.activeTab === 1
                controller: inspector.controller
            }
            ColumnLayout {
                visible: inspector.activeTab === 0 && inspector.count === 0
                Layout.fillWidth: true
                spacing: 6
                UI.TSection {
                    title: "Theme"
                    UI.TCaption {
                        text: "Name"
                        font.hintingPreference: Font.PreferNoHinting
                    }
                    UI.TField {
                        Layout.fillWidth: true
                        text: controller.state.name
                        placeholderText: "Theme name"
                        Accessible.name: "Theme name"
                        onEditingFinished: controller.command("name", text)
                    }
                    UI.TCaption {
                        text: "Background color"
                        font.hintingPreference: Font.PreferNoHinting
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        UI.TField {
                            Layout.fillWidth: true
                            text: controller.state.background
                            font.family: UI.Theme.monoFont
                            font.hintingPreference: Font.PreferNoHinting
                            Accessible.name: "Background color"
                            onEditingFinished: controller.command("background", text)
                        }
                        UI.TButton {
                            text: "Color"
                            implicitHeight: UI.Theme.fieldHeight
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
                        font.pixelSize: 12
                        font.hintingPreference: Font.PreferNoHinting
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
                    Layout.topMargin: 6
                    text: "Select a layer to edit its properties. Rotation and brightness are in the Display tab."
                    color: UI.Theme.muted
                    wrapMode: Text.WordWrap
                    font.pixelSize: 12
                    font.hintingPreference: Font.PreferNoHinting
                }
            }
            ColumnLayout {
                visible: inspector.activeTab === 0 && inspector.count > 0
                Layout.fillWidth: true
                spacing: 6
                UI.TSection {
                    title: "General"
                    visible: inspector.count === 1
                    UI.TCaption {
                        text: "Name"
                        font.hintingPreference: Font.PreferNoHinting
                    }
                    UI.TField {
                        Layout.fillWidth: true
                        text: controller.selected.name || ""
                        Accessible.name: "Element name"
                        enabled: !inspector.locked
                        onEditingFinished: controller.edit("name", text)
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16
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
                }
                UI.TSection {
                    title: "Position & size"
                    visible: inspector.count === 1
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
                                enabled: !inspector.locked
                            }
                        }
                    }
                }
                UI.TSection {
                    title: "Data source"
                    visible: inspector.count === 1 && !inspector.ruleOnly
                    SourcePicker {
                        controller: inspector.controller
                        enabled: !inspector.locked
                    }
                    UI.TButton {
                        text: controller.selected.condition && Object.keys(controller.selected.condition).length ? "Edit conditional rule..." : "Add conditional rule..."
                        Layout.fillWidth: true
                        enabled: !inspector.locked
                        onClicked: controller.command("condition", null)
                    }
                }
                UI.TSection {
                    title: "Visibility rule"
                    visible: inspector.count === 1 && inspector.ruleOnly
                    UI.TButton {
                        text: "Conditional visibility..."
                        Layout.fillWidth: true
                        enabled: !inspector.locked
                        onClicked: controller.command("condition", null)
                    }
                }
                UI.TSection {
                    title: "Align & group"
                    visible: inspector.count > 1
                    Flow {
                        Layout.fillWidth: true
                        Layout.preferredHeight: childrenRect.height
                        spacing: 6
                        Repeater {
                            model: ["left", "center", "right", "top", "middle", "bottom", "horizontal", "vertical"]
                            UI.TButton {
                                required property string modelData
                                text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                                Accessible.name: "Align " + modelData
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
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 10
                            Repeater {
                                model: modelData.rows
                                UI.PropertyRow {
                                    required property var modelData
                                    Layout.preferredWidth: 1  // equal columns
                                    Layout.columnSpan: modelData.kind === "number" ? 1 : 2
                                    spec: modelData
                                    controller: inspector.controller
                                    enabled: !inspector.locked
                                }
                            }
                        }
                    }
                }
                UI.TSection {
                    title: "Organization"
                    expanded: inspector.isOpen("Organization", false)
                    visible: inspector.count === 1
                    onToggled: function (open) {
                        inspector.remember("Organization", open);
                    }
                    UI.TField {
                        Layout.fillWidth: true
                        placeholderText: "Group name (optional)"
                        Accessible.name: "Group name"
                        text: controller.selected.group || ""
                        enabled: !inspector.locked
                        onEditingFinished: controller.edit("group", text)
                    }
                }
                UI.TButton {
                    Layout.topMargin: 6
                    text: "Delete selected elements"
                    destructive: true
                    Layout.fillWidth: true
                    onClicked: controller.command("delete", null)
                }
            }
        }
    }
}
