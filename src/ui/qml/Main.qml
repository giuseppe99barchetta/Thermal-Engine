import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ThermalEngine 1.0
import "components" as UI

ApplicationWindow {
    id: root
    objectName: "editorWindow"
    width: 1440
    height: 900
    minimumWidth: 600
    minimumHeight: 340
    title: "Thermal Engine — " + editor.state.name
    visible: false
    color: UI.Theme.background
    font.family: UI.Theme.font
    font.pixelSize: 13
    font.hintingPreference: Font.PreferNoHinting
    palette.window: UI.Theme.surface
    palette.base: UI.Theme.input
    palette.text: UI.Theme.text
    palette.windowText: UI.Theme.text
    palette.button: UI.Theme.raised
    palette.buttonText: UI.Theme.text
    palette.highlight: UI.Theme.accentDark
    palette.dark: UI.Theme.border
    palette.mid: UI.Theme.border
    Component.onCompleted: UI.Theme.variant = editor.settingsData().ui_theme || "obsidian"
    property int leftTab: 0
    property bool allResolutions: false
    property string searchText: ""
    onSearchTextChanged: editor.filterPresets(searchText, allResolutions)
    onAllResolutionsChanged: editor.filterPresets(searchText, allResolutions)
    property bool exiting: false
    property bool narrow: width < 1000
    property bool layersOpen: false
    property bool propertiesOpen: false
    property int inspectorTab: 0
    property real layersWidth: editor.state.layersWidth
    property real inspectorWidth: editor.state.inspectorWidth
    readonly property int railWidth: 56
    readonly property int centerReserve: 416
    function savePanelWidths() {
        editor.saveSettings({layers_panel_width: Math.round(layersWidth), inspector_panel_width: Math.round(inspectorWidth)});
    }
    function setLeftTab(index) {
        leftTab = index;
        searchText = "";
        search.text = "";
    }
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
    signal closeRequested
    readonly property var shortcutList: [
        ["Ctrl+S", "Save theme"], ["Ctrl+Shift+S", "Save JSON as…"], ["Ctrl+O", "Open theme"], ["Ctrl+N", "New theme"],
        ["Ctrl+Z", "Undo"], ["Ctrl+Y / Ctrl+Shift+Z", "Redo"], ["Ctrl+C / Ctrl+V", "Copy / paste elements"],
        ["Ctrl+A", "Select all on the page"], ["Delete / Backspace", "Delete selected"], ["Arrows (Shift)", "Nudge 1 px (10 px)"],
        ["Ctrl+G / Ctrl+Shift+G", "Group / ungroup"], ["Ctrl+] / Ctrl+[", "Move forward / backward"],
        ["Ctrl+Shift+] / [", "Bring to front / send to back"], ["Ctrl+wheel", "Zoom"], ["Middle drag", "Pan"],
        ["Ctrl+0", "Fit canvas to window"], ["Alt while dragging", "Move without smart guides"],
        ["F5", "Send the frame to the display"], ["? / F1", "This list"]]
    onClosing: function (close) {
        if (!exiting) {
            close.accepted = false;
            closeRequested();
        }
    }
    Shortcut {
        sequence: "Ctrl+S"
        onActivated: editor.command("save", null)
    }
    Shortcut {
        sequences: ["F1", "?"]
        // "?" must still type into text fields
        enabled: !(root.activeFocusItem instanceof TextInput)
        onActivated: shortcutsDialog.open()
    }
    Shortcut {
        sequence: "Ctrl+Shift+S"
        onActivated: editor.command("saveAs", null)
    }
    Shortcut {
        sequence: "Ctrl+O"
        onActivated: editor.command("open", null)
    }
    Shortcut {
        sequence: "Ctrl+N"
        onActivated: editor.command("new", null)
    }
    Shortcut {
        sequence: "Ctrl+Z"
        onActivated: editor.command("undo", null)
    }
    Shortcut {
        sequence: "Ctrl+Y"
        onActivated: editor.command("redo", null)
    }
    Shortcut {
        sequence: "Ctrl+Shift+Z"
        onActivated: editor.command("redo", null)
    }
    Shortcut {
        sequence: "Ctrl+0"
        onActivated: editor.command("fit", null)
    }
    Shortcut {
        sequence: "F5"
        onActivated: editor.command("send", null)
    }
    Shortcut {
        sequences: ["Delete", "Backspace"]
        enabled: editor.state.selectionCount > 0 && !root.Overlay.overlay.visible
                 && !(root.activeFocusItem instanceof TextInput) && !(root.activeFocusItem instanceof TextEdit)
        onActivated: editor.command("delete", null)
    }
    Shortcut {
        sequence: "Ctrl+C"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("copy", null)
    }
    Shortcut {
        sequence: "Ctrl+V"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("paste", null)
    }
    Shortcut {
        sequence: "Ctrl+A"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("selectAll", null)
    }
    Shortcut {
        sequence: "Ctrl+G"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("group", null)
    }
    Shortcut {
        sequence: "Ctrl+]"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("up", null)
    }
    Shortcut {
        sequence: "Ctrl+["
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("down", null)
    }
    Shortcut {
        sequence: "Ctrl+Shift+G"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("ungroup", null)
    }
    Shortcut {
        sequence: "Ctrl+Shift+]"
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("front", null)
    }
    Shortcut {
        sequence: "Ctrl+Shift+["
        enabled: canvas && canvas.activeFocus
        onActivated: editor.command("back", null)
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- Title bar -------------------------------------------------------------------------
        Rectangle {
            id: titleBar
            Layout.fillWidth: true
            implicitHeight: 52
            color: UI.Theme.surface
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: UI.Theme.border
            }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 14
                spacing: 10
                Image {
                    objectName: "applicationLogo"
                    source: "../../../assets/icon.png"
                    sourceSize: Qt.size(56, 56)
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    fillMode: Image.PreserveAspectFit
                }
                Label {
                    visible: root.width >= 1000
                    text: "Thermal Engine"
                    color: UI.Theme.text
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    font.hintingPreference: Font.PreferNoHinting
                    Layout.rightMargin: 14
                }
                UI.TButton {
                    visible: root.narrow
                    flat: true
                    text: "Canvas"
                    selected: !root.layersOpen && !root.propertiesOpen
                    onClicked: {
                        root.layersOpen = false;
                        root.propertiesOpen = false;
                    }
                }
                Label {
                    text: editor.state.name
                    color: UI.Theme.text
                    font.pixelSize: 14
                    font.weight: Font.Medium
                    font.hintingPreference: Font.PreferNoHinting
                    Layout.maximumWidth: root.width >= 800 ? 280 : 96
                    elide: Text.ElideRight
                }
                RowLayout {
                    visible: root.width >= 800
                    spacing: 6
                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        color: editor.state.dirty ? UI.Theme.warning : UI.Theme.success
                    }
                    Label {
                        text: editor.state.dirty ? "Unsaved" : "Saved"
                        color: UI.Theme.muted
                        font.pixelSize: 12
                        font.hintingPreference: Font.PreferNoHinting
                    }
                }
                Item {
                    Layout.fillWidth: true
                }
                UI.TButton {
                    id: connectionPill
                    objectName: "connectionPill"
                    visible: root.width >= 800
                    implicitWidth: pillRow.implicitWidth + 28
                    // Long device names ("Thermalright WinUSB Display (FW / Stream Vision)") elide instead of pushing the title bar off-screen
                    Layout.maximumWidth: root.width >= 1000 ? 420 : root.width >= 900 ? 230 : 150
                    Accessible.name: editor.state.device + ", " + editor.state.width + " by " + editor.state.height + ", " + (editor.state.connected ? "connected" : "disconnected")
                    ToolTip.text: editor.state.connected ? "Disconnect the display" : "Connect a display"
                    onClicked: editor.command("connect", null)
                    contentItem: Item {
                        RowLayout {
                            id: pillRow
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 14
                            spacing: 8
                            Item {
                                Layout.preferredWidth: 13
                                Layout.preferredHeight: 13
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 7
                                    color: editor.state.connected ? UI.Theme.success : UI.Theme.muted
                                    opacity: 0.2
                                }
                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 7
                                    height: 7
                                    radius: 4
                                    color: editor.state.connected ? UI.Theme.success : UI.Theme.muted
                                }
                            }
                            Text {
                                text: editor.state.device
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                color: UI.Theme.text
                                font.family: UI.Theme.uiFont
                                font.pixelSize: 13
                                font.hintingPreference: Font.PreferNoHinting
                            }
                            Text {
                                text: editor.state.width + "×" + editor.state.height
                                color: UI.Theme.muted
                                font.family: UI.Theme.monoFont
                                font.pixelSize: 12
                                font.hintingPreference: Font.PreferNoHinting
                            }
                        }
                    }
                    background: Rectangle {
                        radius: UI.Theme.radius
                        color: connectionPill.hovered ? UI.Theme.selected : UI.Theme.raised
                        border.width: 1
                        border.color: UI.Theme.border
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: -2
                            radius: parent.radius + 2
                            color: "transparent"
                            border.width: 2
                            border.color: UI.Theme.accent
                            visible: connectionPill.visualFocus
                        }
                    }
                }
                UI.TButton {
                    // Wide windows show the Display tab in the inspector already
                    visible: root.narrow
                    flat: true
                    text: "Display"
                    onClicked: {
                        root.inspectorTab = 1;
                        root.propertiesOpen = true;
                        root.layersOpen = false;
                    }
                }
                UI.TButton {
                    visible: editor.state.dirty
                    flat: true
                    text: "Save"
                    ToolTip.text: "Save theme · Ctrl+S"
                    onClicked: editor.command("save", null)
                }
                UI.TButton {
                    primary: true
                    text: editor.state.connected ? "Send to display" : "Connect"
                    ToolTip.text: editor.state.connected ? "Send the frame to the display · F5" : "Connect to a display"
                    onClicked: editor.command(editor.state.connected ? "send" : "connect", null)
                }
                UI.TIconButton {
                    id: menuButton
                    iconName: "more"
                    ToolTip.text: "Project and settings"
                    onClicked: projectMenu.open()
                    UI.TMenu {
                        id: projectMenu
                        x: menuButton.width - width
                        y: menuButton.height + 6
                        UI.TMenuItem {
                            text: "New theme"
                            onTriggered: editor.command("new", null)
                        }
                        UI.TMenuItem {
                            text: "Open theme…"
                            onTriggered: editor.command("open", null)
                        }
                        UI.TMenuItem {
                            text: "Save JSON as…"
                            onTriggered: editor.command("saveAs", null)
                        }
                        UI.TMenuItem {
                            text: "Export image…"
                            onTriggered: editor.command("exportImage", null)
                        }
                        UI.TMenuItem {
                            text: "Export theme package…"
                            onTriggered: editor.command("exportPackage", null)
                        }
                        UI.TMenuItem {
                            text: "Import theme package…"
                            onTriggered: editor.command("importPackage", null)
                        }
                        MenuSeparator {}
                        UI.TMenuItem {
                            text: "Network sensors…"
                            onTriggered: editor.command("network", null)
                        }
                        UI.TMenuItem {
                            text: "Refresh hardware sensors"
                            onTriggered: editor.command("refreshSensors", null)
                        }
                        UI.TMenuItem {
                            text: "Hardware setup..."
                            onTriggered: editor.command("hardwareSetup", null)
                        }
                        UI.TMenuItem {
                            text: "Display resolution…"
                            onTriggered: editor.requestDialog("resolution", {})
                        }
                        UI.TMenuItem {
                            text: "Auto profiles…"
                            onTriggered: editor.command("profiles", null)
                        }
                        UI.TMenuItem {
                            text: "Settings…"
                            onTriggered: editor.command("settings", null)
                        }
                        UI.TMenuItem {
                            text: "Check for updates"
                            onTriggered: editor.command("updates", null)
                        }
                        UI.TMenuItem {
                            text: "Diagnostics…"
                            onTriggered: editor.command("diagnostics", null)
                        }
                        UI.TMenuItem {
                            text: "Keyboard shortcuts"
                            onTriggered: shortcutsDialog.open()
                        }
                        UI.TMenuItem {
                            text: "Reset workspace layout"
                            onTriggered: {
                                root.layersWidth = 244;
                                root.inspectorWidth = 296;
                                root.savePanelWidths();
                            }
                        }
                        UI.TMenuItem {
                            text: "Console…"
                            onTriggered: dialogs.showConsole()
                        }
                        UI.TMenuItem {
                            text: "Setup wizard…"
                            onTriggered: {
                                editor.openDevices();
                                editor.requestDialog("onboarding", {});
                            }
                        }
                        MenuSeparator {}
                        UI.TMenuItem {
                            text: "Quit"
                            onTriggered: editor.command("quit", null)
                        }
                    }
                }
            }
        }

        // ---- Workspace -------------------------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Rail
            Rectangle {
                visible: !root.narrow
                Layout.preferredWidth: root.railWidth
                Layout.fillHeight: true
                color: UI.Theme.surface
                Rectangle {
                    anchors.right: parent.right
                    width: 1
                    height: parent.height
                    color: UI.Theme.border
                }
                ColumnLayout {
                    anchors.fill: parent
                    anchors.topMargin: 12
                    anchors.bottomMargin: 12
                    spacing: 6
                    Repeater {
                        model: [{icon: "layers", label: "Layers"}, {icon: "presets", label: "Presets"}, {icon: "sensors", label: "Sensors"}]
                        UI.TIconButton {
                            required property var modelData
                            required property int index
                            Layout.alignment: Qt.AlignHCenter
                            Layout.preferredWidth: 36
                            Layout.preferredHeight: 36
                            iconName: modelData.icon
                            selected: root.leftTab === index
                            Accessible.name: modelData.label
                            Accessible.checkable: true
                            Accessible.checked: root.leftTab === index
                            ToolTip.text: modelData.label
                            onClicked: root.setLeftTab(index)
                        }
                    }
                    Item {
                        Layout.fillHeight: true
                    }
                    UI.TIconButton {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 36
                        iconName: "settings"
                        Accessible.name: "Settings"
                        ToolTip.text: "Settings"
                        onClicked: editor.command("settings", null)
                    }
                }
            }

            // Left panel: layers, presets, sensors
            Rectangle {
                id: leftPanel
                visible: !root.narrow || root.layersOpen
                Layout.preferredWidth: root.narrow ? root.width : Math.min(root.layersWidth, Math.max(220, (root.width - root.railWidth - root.centerReserve) * 0.45))
                Layout.fillHeight: true
                color: UI.Theme.surface
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        Layout.leftMargin: 14
                        Layout.rightMargin: 10
                        Layout.topMargin: 10
                        Layout.bottomMargin: 8
                        spacing: 8
                        Label {
                            visible: !root.narrow
                            text: ["Layers", "Presets", "Sensors"][root.leftTab]
                            color: UI.Theme.text
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            font.hintingPreference: Font.PreferNoHinting
                        }
                        Label {
                            visible: !root.narrow && root.leftTab === 0
                            text: "Page " + editor.state.page
                            color: UI.Theme.muted
                            font.pixelSize: 12
                            font.hintingPreference: Font.PreferNoHinting
                        }
                        UI.TSegmented {
                            id: leftTabs
                            visible: root.narrow
                            Layout.fillWidth: true
                            Layout.maximumWidth: 360
                            model: ["Layers", "Presets", "Sensors"]
                            onActivated: function (index) {
                                root.setLeftTab(index);
                            }
                        }
                        Binding {
                            target: leftTabs
                            property: "currentIndex"
                            value: root.leftTab
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        UI.TIconButton {
                            visible: root.leftTab === 0
                            iconName: "plus"
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 28
                            Accessible.name: "Add element"
                            ToolTip.text: "Add element"
                            onClicked: addMenu.open()
                            UI.TMenu {
                                id: addMenu
                                objectName: "addMenu"
                                x: parent.width - width
                                y: parent.height + 4
                                Repeater {
                                    model: editor.elementTypes
                                    UI.TMenuItem {
                                        required property string modelData
                                        text: editor.typeLabels[modelData] || modelData.replace(/_/g, " ")
                                        onTriggered: editor.command("add", modelData)
                                    }
                                }
                            }
                        }
                    }
                    UI.TField {
                        id: search
                        Layout.fillWidth: true
                        Layout.leftMargin: 12
                        Layout.rightMargin: 12
                        Layout.bottomMargin: 8
                        leftPadding: 32
                        placeholderText: root.leftTab === 0 ? "Find a layer…" : root.leftTab === 1 ? "Find a preset…" : "Find a sensor…"
                        Accessible.name: placeholderText
                        onTextChanged: root.searchText = text.toLowerCase()
                        UI.TIcon {
                            x: 10
                            anchors.verticalCenter: parent.verticalCenter
                            name: "search"
                            color: UI.Theme.muted
                        }
                    }
                    UI.TCheck {
                        visible: root.leftTab === 1
                        Layout.leftMargin: 12
                        text: "All resolutions"
                        checked: root.allResolutions
                        onClicked: root.allResolutions = checked
                    }
                    StackLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                        Layout.bottomMargin: 8
                        currentIndex: root.leftTab
                        Item {
                            ListView {
                                id: layerList
                                objectName: "layerList"
                                anchors.fill: parent
                                clip: true
                                spacing: 1
                                model: editor.layers
                                property real dropLineY: -1  // drag-reorder insertion marker, in content coordinates
                                ScrollBar.vertical: ScrollBar {}
                                Rectangle {
                                    visible: layerList.dropLineY >= 0
                                    y: layerList.dropLineY - 1
                                    z: 10
                                    width: layerList.width
                                    height: 2
                                    radius: 1
                                    color: UI.Theme.accent
                                }
                                delegate: Rectangle {
                                    id: layerRow
                                    required property var row
                                    readonly property bool isGroup: row.kind === "group"
                                    readonly property int nameX: isGroup ? 30 : (row.indented ? 52 : 36)
                                    width: layerList.width
                                    height: visible ? 36 : 0
                                    visible: row.name.toLowerCase().indexOf(root.searchText) >= 0
                                    radius: UI.Theme.radius
                                    color: row.selected ? UI.Theme.selected : rowHover.hovered ? UI.Theme.hover : "transparent"
                                    opacity: layerMouse.dragging ? 0.5 : 1
                                    Accessible.role: Accessible.ListItem
                                    Accessible.name: row.name
                                    Accessible.selected: row.selected
                                    HoverHandler {
                                        id: rowHover
                                    }
                                    MouseArea {
                                        id: layerMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        property real pressY: 0
                                        property bool dragging: false
                                        property bool dragged: false
                                        function dropTarget(mouse) {
                                            let point = mapToItem(layerList.contentItem, mouse.x, mouse.y);
                                            let index = layerList.indexAt(10, point.y);
                                            if (index < 0)
                                                return null;
                                            let item = layerList.itemAtIndex(index);
                                            let target = editor.layers.get(index);
                                            // A group header always means "above the group"
                                            let after = target.kind !== "group" && point.y > item.y + item.height / 2;
                                            return {
                                                target: target,
                                                after: after,
                                                line: item.y + (after ? item.height : 0)
                                            };
                                        }
                                        onPressed: function (mouse) {
                                            pressY = mouse.y;
                                            dragged = false;
                                        }
                                        onPositionChanged: function (mouse) {
                                            if (!pressed || mouse.buttons !== Qt.LeftButton || layerRow.isGroup || row.locked)
                                                return;
                                            if (!dragging && Math.abs(mouse.y - pressY) > 6)
                                                dragging = dragged = true;
                                            if (dragging) {
                                                let drop = dropTarget(mouse);
                                                layerList.dropLineY = drop ? drop.line : -1;
                                            }
                                        }
                                        onReleased: function (mouse) {
                                            if (dragging) {
                                                let drop = dropTarget(mouse);
                                                if (drop)
                                                    editor.moveLayer(row.index, drop.target.index, drop.after);
                                            }
                                            dragging = false;
                                            layerList.dropLineY = -1;
                                        }
                                        onCanceled: {
                                            dragging = false;
                                            layerList.dropLineY = -1;
                                        }
                                        onClicked: function (mouse) {
                                            if (dragged)
                                                return;
                                            canvas.forceActiveFocus();
                                            editor.selectLayer(row.index, Boolean(mouse.modifiers & Qt.ControlModifier), layerRow.isGroup || Boolean(mouse.modifiers & Qt.ShiftModifier));
                                            if (mouse.button === Qt.RightButton)
                                                layerMenu.popup();
                                        }
                                        onDoubleClicked: if (layerRow.isGroup)
                                            editor.toggleGroup(row.name)
                                    }
                                    ToolButton {
                                        id: groupToggle
                                        visible: layerRow.isGroup
                                        x: 4
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 24
                                        height: 28
                                        z: 2
                                        background: Rectangle {
                                            radius: UI.Theme.radiusSmall
                                            color: groupToggle.hovered ? UI.Theme.selected : "transparent"
                                        }
                                        contentItem: UI.TIcon {
                                            name: "chevron"
                                            width: 14
                                            height: 14
                                            rotation: row.collapsed ? -90 : 0
                                        }
                                        onClicked: editor.toggleGroup(row.name)
                                        Accessible.name: (row.collapsed ? "Expand " : "Collapse ") + row.name
                                        ToolTip.text: row.collapsed ? "Show group members" : "Hide group members"
                                        ToolTip.visible: hovered
                                    }
                                    UI.TIcon {
                                        visible: !layerRow.isGroup
                                        x: row.indented ? 26 : 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        name: root.typeIcon(row.type)
                                        color: row.selected ? UI.Theme.accent : UI.Theme.muted
                                    }
                                    Text {
                                        x: layerRow.nameX
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.max(0, parent.width - x - actions.width - 10)
                                        text: layerRow.isGroup ? row.name + "  ·  " + row.count : row.name
                                        color: !row.visible ? UI.Theme.muted : row.selected ? UI.Theme.text : UI.Theme.secondary
                                        font.family: UI.Theme.uiFont
                                        font.pixelSize: 13
                                        font.weight: layerRow.isGroup || row.selected ? Font.Medium : Font.Normal
                                        font.hintingPreference: Font.PreferNoHinting
                                        elide: Text.ElideRight
                                    }
                                    Row {
                                        id: actions
                                        anchors.right: parent.right
                                        anchors.rightMargin: 4
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 0
                                        UI.TIconButton {
                                            visible: rowHover.hovered || row.selected || !row.visible
                                            width: 28
                                            height: 28
                                            iconName: row.visible ? "eye" : "hidden"
                                            onClicked: {
                                                editor.selectLayer(row.index, false, layerRow.isGroup);
                                                editor.edit("visible", !row.visible);
                                            }
                                            Accessible.name: (row.visible ? "Hide " : "Show ") + row.name
                                            ToolTip.text: layerRow.isGroup ? "Toggle visibility of the group" : "Toggle visibility"
                                        }
                                        UI.TIconButton {
                                            visible: rowHover.hovered || row.selected || row.locked
                                            width: 28
                                            height: 28
                                            iconName: row.locked ? "lock" : "unlock"
                                            onClicked: {
                                                editor.selectLayer(row.index, false, layerRow.isGroup);
                                                editor.edit("locked", !row.locked);
                                            }
                                            Accessible.name: (row.locked ? "Unlock " : "Lock ") + row.name
                                            ToolTip.text: layerRow.isGroup ? "Lock or unlock the whole group" : "Toggle lock"
                                        }
                                    }
                                    UI.TMenu {
                                        id: layerMenu
                                        UI.TMenuItem {
                                            text: "Copy"
                                            onTriggered: editor.command("copy", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Paste"
                                            onTriggered: editor.command("paste", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Bring to front"
                                            onTriggered: editor.command("front", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Move forward"
                                            onTriggered: editor.command("up", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Move backward"
                                            onTriggered: editor.command("down", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Send to back"
                                            onTriggered: editor.command("back", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Group…"
                                            onTriggered: editor.command("group", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Ungroup"
                                            onTriggered: editor.command("ungroup", null)
                                        }
                                        UI.TMenuItem {
                                            text: "Delete"
                                            onTriggered: editor.command("delete", null)
                                        }
                                    }
                                }
                            }
                            Label {
                                anchors.centerIn: parent
                                width: parent.width - 20
                                visible: layerList.count === 0
                                text: "Your canvas is ready.\nAdd your first element."
                                color: UI.Theme.secondary
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                lineHeight: 1.4
                                font.pixelSize: 13
                                font.hintingPreference: Font.PreferNoHinting
                            }
                        }
                        GridView {
                            id: presetList
                            objectName: "presetBrowserGrid"
                            clip: true
                            cellWidth: width / Math.max(1, Math.floor(width / 170))
                            cellHeight: 168
                            model: editor.presetBrowser
                            ScrollBar.vertical: ScrollBar {}
                            delegate: Item {
                                id: presetCard
                                required property var row
                                readonly property bool current: row.name === editor.state.name
                                width: presetList.cellWidth
                                height: presetList.cellHeight
                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    radius: UI.Theme.radius
                                    color: presetCard.current ? UI.Theme.selected : presetMouse.containsMouse ? UI.Theme.hover : UI.Theme.input
                                    border.width: presetCard.current ? 2 : 1
                                    border.color: presetCard.current ? UI.Theme.accent : UI.Theme.border
                                    Accessible.role: Accessible.Button
                                    Accessible.name: "Load theme " + presetCard.row.name
                                    Image {
                                        anchors.top: parent.top
                                        anchors.topMargin: 10
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: parent.width - 20
                                        height: 100
                                        fillMode: Image.PreserveAspectFit
                                        source: "image://thumbs/preset/" + presetCard.row.name + "?" + editor.state.revision
                                    }
                                    Text {
                                        x: 12
                                        y: 116
                                        text: presetCard.row.name
                                        width: parent.width - 24
                                        elide: Text.ElideRight
                                        color: UI.Theme.text
                                        font.family: UI.Theme.uiFont
                                        font.pixelSize: 13
                                        font.weight: Font.Medium
                                        font.hintingPreference: Font.PreferNoHinting
                                    }
                                    Text {
                                        x: 12
                                        y: 136
                                        width: parent.width - 24
                                        text: presetCard.row.width + " × " + presetCard.row.height + " · " + (presetCard.row.builtin ? "Built-in" : "Personal")
                                        font.family: UI.Theme.uiFont
                                        font.pixelSize: 12
                                        font.hintingPreference: Font.PreferNoHinting
                                        color: UI.Theme.muted
                                        elide: Text.ElideRight
                                    }
                                    MouseArea {
                                        id: presetMouse
                                        hoverEnabled: true
                                        anchors.fill: parent
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        onClicked: function (mouse) {
                                            if (mouse.button === Qt.RightButton)
                                                presetMenu.popup();
                                            else
                                                editor.command("loadPreset", presetCard.row.name);
                                        }
                                    }
                                    UI.TMenu {
                                        id: presetMenu
                                        UI.TMenuItem {
                                            text: "Load theme"
                                            onTriggered: editor.command("loadPreset", presetCard.row.name)
                                        }
                                        UI.TMenuItem {
                                            text: "Use at startup"
                                            onTriggered: editor.command("defaultPreset", presetCard.row.name)
                                        }
                                        UI.TMenuItem {
                                            text: "Delete preset"
                                            enabled: !presetCard.row.builtin
                                            onTriggered: editor.command("deletePreset", presetCard.row.name)
                                        }
                                    }
                                }
                            }
                        }
                        Item {
                            SensorBrowser {
                                anchors.fill: parent
                                anchors.margins: 4
                                controller: editor
                                query: root.searchText
                            }
                        }
                    }
                }
            }
            UI.TSplitter {
                objectName: "layersSplitter"
                visible: !root.narrow
                panelName: "layers panel"
                value: root.layersWidth
                maximum: Math.min(440, root.width - root.railWidth - root.inspectorWidth - root.centerReserve)
                onAdjusted: function(value) { root.layersWidth = value; }
                onCommitted: root.savePanelWidths()
            }

            // ---- Centre: toolbar, canvas, pages ----------------------------------------------
            ColumnLayout {
                visible: !root.narrow || (!root.layersOpen && !root.propertiesOpen)
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0
                Rectangle {
                    id: toolbarRow
                    objectName: "toolbarRow"
                    Layout.fillWidth: true
                    implicitHeight: 52
                    color: UI.Theme.background
                    // The full pill needs ~460px; the centre column can shrink to the 416px reserve
                    readonly property bool compact: width < 490  // centre column can be ~400px wide
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8
                        UI.TButton {
                            visible: root.narrow
                            text: "Layers"
                            onClicked: {
                                root.layersOpen = !root.layersOpen;
                                root.propertiesOpen = false;
                            }
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            implicitWidth: tools.implicitWidth + 12
                            implicitHeight: 40
                            radius: UI.Theme.radius + 4
                            color: UI.Theme.raised
                            border.width: 1
                            border.color: UI.Theme.border
                            RowLayout {
                                id: tools
                                anchors.centerIn: parent
                                spacing: toolbarRow.compact ? 0 : 2
                                UI.TIconButton {
                                    iconName: "undo"
                                    enabled: editor.state.canUndo
                                    ToolTip.text: "Undo · Ctrl+Z"
                                    onClicked: editor.command("undo", null)
                                }
                                UI.TIconButton {
                                    iconName: "redo"
                                    enabled: editor.state.canRedo
                                    ToolTip.text: "Redo · Ctrl+Y"
                                    onClicked: editor.command("redo", null)
                                }
                                Rectangle {
                                    visible: !toolbarRow.compact
                                    Layout.preferredWidth: 1
                                    Layout.preferredHeight: 18
                                    Layout.leftMargin: 4
                                    Layout.rightMargin: 4
                                    color: UI.Theme.border
                                }
                                UI.TCombo {
                                    id: previewValues
                                    objectName: "previewValues"
                                    property var fractions: [-1, 0.25, 0.5, 0.9]
                                    Layout.preferredWidth: toolbarRow.compact ? 116 : 140
                                    model: ["Live data", "Simulate 25%", "Simulate 50%", "Simulate 90%"]
                                    currentIndex: Math.max(0, fractions.indexOf(editor.state.previewFraction))
                                    onActivated: editor.command("previewValues", fractions[currentIndex])
                                    ToolTip.text: "Preview gauges, colors and rules with simulated readings. The display keeps live data."
                                    ToolTip.visible: hovered
                                }
                                Rectangle {
                                    visible: root.width >= 800 && !toolbarRow.compact
                                    Layout.preferredWidth: 1
                                    Layout.preferredHeight: 18
                                    Layout.leftMargin: 4
                                    Layout.rightMargin: 4
                                    color: UI.Theme.border
                                }
                                UI.TIconButton {
                                    visible: root.width >= 800
                                    iconName: "grid"
                                    accented: editor.state.grid
                                    Accessible.name: "Grid"
                                    Accessible.checkable: true
                                    Accessible.checked: editor.state.grid
                                    ToolTip.text: editor.state.grid ? "Grid on" : "Grid off"
                                    onClicked: editor.command("grid", !editor.state.grid)
                                }
                                UI.TIconButton {
                                    visible: root.width >= 800
                                    iconName: "snap"
                                    accented: editor.state.snap
                                    Accessible.name: "Snap"
                                    Accessible.checkable: true
                                    Accessible.checked: editor.state.snap
                                    ToolTip.text: editor.state.snap ? "Snap on" : "Snap off"
                                    onClicked: editor.command("snap", !editor.state.snap)
                                }
                                Rectangle {
                                    visible: !toolbarRow.compact
                                    Layout.preferredWidth: 1
                                    Layout.preferredHeight: 18
                                    Layout.leftMargin: 4
                                    Layout.rightMargin: 4
                                    color: UI.Theme.border
                                }
                                UI.TIconButton {
                                    iconName: "minus"
                                    Accessible.name: "Zoom out"
                                    ToolTip.text: "Zoom out · Ctrl+wheel"
                                    onClicked: canvas.zoomBy(1 / 1.2)
                                }
                                UI.TButton {
                                    flat: true
                                    Layout.preferredWidth: toolbarRow.compact ? 40 : 56
                                    text: editor.state.zoom + "%"
                                    font.family: UI.Theme.monoFont
                                    font.pixelSize: 12
                                    font.hintingPreference: Font.PreferNoHinting
                                    Accessible.name: "Fit display, zoom " + editor.state.zoom + " percent"
                                    ToolTip.text: "Fit display · Ctrl+0"
                                    onClicked: canvas.fit()
                                }
                                UI.TIconButton {
                                    iconName: "plus"
                                    Accessible.name: "Zoom in"
                                    ToolTip.text: "Zoom in · Ctrl+wheel"
                                    onClicked: canvas.zoomBy(1.2)
                                }
                            }
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        UI.TButton {
                            visible: root.narrow
                            text: "Properties"
                            onClicked: {
                                root.propertiesOpen = !root.propertiesOpen;
                                root.layersOpen = false;
                            }
                        }
                    }
                }
                QuickCanvas {
                    id: canvas
                    objectName: "quickCanvas"
                    controller: editor
                    chromeColors: ({stage: UI.Theme.background, border: UI.Theme.border, ruler: UI.Theme.surface, rulerText: UI.Theme.secondary, accent: UI.Theme.accent})
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    DropArea {
                        id: fileDrop
                        anchors.fill: parent
                        onEntered: function (drag) {
                            if (drag.hasUrls)
                                drag.accept(Qt.CopyAction);
                        }
                        onDropped: function (drop) {
                            if (!drop.hasUrls)
                                return;
                            editor.dropFiles(drop.urls, drop.x, drop.y);
                            drop.accept(Qt.CopyAction);
                        }
                    }
                    Rectangle {
                        visible: fileDrop.containsDrag
                        anchors.fill: parent
                        anchors.margins: 12
                        radius: 12
                        color: UI.Theme.selection
                        border.color: UI.Theme.accent
                        border.width: 2
                        Label {
                            anchors.centerIn: parent
                            text: "Drop images or GIFs to add them · a video to set the background"
                            color: UI.Theme.text
                            font.pixelSize: 14
                            font.hintingPreference: Font.PreferNoHinting
                        }
                    }
                }
                Rectangle {
                    id: pageStrip
                    // Thumbnails only pay for their height once there is more than one page
                    property bool multiPage: editor.state.pages.length > 1
                    Layout.fillWidth: true
                    objectName: "pageStrip"
                    implicitHeight: root.height < 500 || !multiPage ? 52 : 144
                    Layout.minimumHeight: implicitHeight
                    Layout.maximumHeight: implicitHeight
                    color: UI.Theme.surface
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: UI.Theme.border
                    }
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Label {
                                text: "PAGES"
                                color: UI.Theme.muted
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.9
                                font.hintingPreference: Font.PreferNoHinting
                            }
                            UI.TCombo {
                                visible: root.height < 500
                                Layout.preferredWidth: 72
                                model: editor.state.pages
                                currentIndex: model.indexOf(editor.state.page)
                                onActivated: editor.command("page", Number(currentText))
                            }
                            UI.TIconButton {
                                visible: root.height < 500
                                iconName: "plus"
                                Accessible.name: "Add page"
                                ToolTip.text: "Add page"
                                onClicked: editor.command("addPage", null)
                            }
                            UI.TIconButton {
                                visible: root.height < 500
                                iconName: "minus"
                                enabled: editor.state.pages.length > 1
                                Accessible.name: "Delete page"
                                ToolTip.text: "Delete this page"
                                onClicked: editor.command("deletePage", editor.state.page)
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                            UI.TButton {
                                visible: !pageStrip.multiPage && root.height >= 500
                                text: "Add page"
                                ToolTip.text: "Pages rotate on the display, e.g. a stats page and a clock page"
                                onClicked: editor.command("addPage", null)
                            }
                            UI.TCheck {
                                visible: pageStrip.multiPage
                                text: "Auto-rotate"
                                checked: editor.state.rotation
                                onClicked: editor.command("rotation", checked)
                            }
                            UI.TField {
                                visible: pageStrip.multiPage
                                Layout.preferredWidth: 52
                                font.family: UI.Theme.monoFont
                                font.hintingPreference: Font.PreferNoHinting
                                Accessible.name: "Rotation interval in seconds"
                                text: editor.state.rotationInterval
                                validator: IntValidator {
                                    bottom: 1
                                    top: 60
                                }
                                onEditingFinished: editor.command("rotationInterval", Number(text))
                            }
                            Label {
                                visible: pageStrip.multiPage
                                text: "sec"
                                color: UI.Theme.muted
                                font.pixelSize: 12
                                font.hintingPreference: Font.PreferNoHinting
                            }
                        }
                        ListView {
                            id: pageList
                            objectName: "pageList"
                            Layout.minimumHeight: visible ? 76 : 0
                            visible: root.height >= 500 && pageStrip.multiPage
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            orientation: ListView.Horizontal
                            spacing: 8
                            model: editor.pages
                            clip: true
                            delegate: Rectangle {
                                id: pageCard
                                required property var row
                                objectName: "pageThumbnail" + row.number
                                width: 112
                                height: 76
                                radius: UI.Theme.radius
                                color: row.current ? UI.Theme.selected : UI.Theme.input
                                border.width: row.current ? 2 : 1
                                border.color: row.current ? UI.Theme.accent : UI.Theme.border
                                Accessible.role: Accessible.Button
                                Accessible.name: "Page " + row.number
                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    source: "image://thumbs/page/" + pageCard.row.number + "?" + editor.state.revision
                                    fillMode: Image.PreserveAspectFit
                                }
                                Text {
                                    x: 8
                                    y: 5
                                    text: pageCard.row.number
                                    color: UI.Theme.text
                                    style: Text.Outline
                                    styleColor: UI.Theme.background
                                    font.family: UI.Theme.monoFont
                                    font.pixelSize: 12
                                    font.hintingPreference: Font.PreferNoHinting
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: function (mouse) {
                                        if (mouse.button === Qt.RightButton)
                                            pageMenu.popup();
                                        else
                                            editor.command("page", pageCard.row.number);
                                    }
                                }
                                UI.TMenu {
                                    id: pageMenu
                                    UI.TMenuItem {
                                        text: "Delete page"
                                        enabled: pageList.count > 1
                                        onTriggered: editor.command("deletePage", pageCard.row.number)
                                    }
                                }
                            }
                            footer: UI.TIconButton {
                                iconName: "plus"
                                width: 44
                                height: 76
                                Accessible.name: "Add page"
                                ToolTip.text: "Add page"
                                onClicked: editor.command("addPage", null)
                            }
                        }
                    }
                }
            }
            UI.TSplitter {
                objectName: "inspectorSplitter"
                visible: !root.narrow
                panelName: "properties panel"
                value: root.inspectorWidth
                minimum: 280
                maximum: Math.min(520, root.width - root.railWidth - root.layersWidth - root.centerReserve)
                reversed: true
                onAdjusted: function(value) { root.inspectorWidth = value; }
                onCommitted: root.savePanelWidths()
            }

            // ---- Right panel -----------------------------------------------------------------
            Rectangle {
                visible: !root.narrow || root.propertiesOpen
                Layout.preferredWidth: root.narrow ? root.width : Math.min(root.inspectorWidth, Math.max(280, (root.width - root.railWidth - root.centerReserve) * 0.55))
                Layout.fillHeight: true
                color: UI.Theme.surface
                Binding {  // a plain binding is lost the first time the tabs assign activeTab
                    target: inspectorPanel
                    property: "activeTab"
                    value: root.inspectorTab
                }
                Inspector {
                    id: inspectorPanel
                    onActiveTabChanged: root.inspectorTab = activeTab
                    anchors.fill: parent
                    controller: editor
                }
            }
        }

        // ---- Status bar ------------------------------------------------------------------------
        Rectangle {
            id: statusBar
            objectName: "statusBar"
            Layout.fillWidth: true
            implicitHeight: 28
            color: UI.Theme.surface
            Rectangle {
                width: parent.width
                height: 1
                color: UI.Theme.border
            }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 12
                spacing: 12
                Label {
                    text: editor.state.status
                    color: UI.Theme.secondary
                    font.pixelSize: 12
                    font.hintingPreference: Font.PreferNoHinting
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                Label {
                    visible: editor.state.connected
                    text: editor.state.actualFps + " FPS"
                    color: UI.Theme.muted
                    font.family: UI.Theme.monoFont
                    font.pixelSize: 12
                    font.hintingPreference: Font.PreferNoHinting
                }
                Label {
                    text: editor.state.width + " × " + editor.state.height
                    color: UI.Theme.muted
                    font.family: UI.Theme.monoFont
                    font.pixelSize: 12
                    font.hintingPreference: Font.PreferNoHinting
                }
                Repeater {
                    model: editor.healthChecks
                    UI.TChip {
                        required property var modelData
                        visible: !root.narrow
                        clickable: true
                        text: modelData.name + ": " + modelData.status
                        tone: modelData.severity
                        ToolTip.text: modelData.detail
                        ToolTip.visible: hovered && ToolTip.text.length > 0
                        ToolTip.delay: 600
                        onClicked: editor.command(modelData.action, null)
                    }
                }
                UI.TButton {
                    visible: root.narrow
                    flat: true
                    text: "Status"
                    implicitHeight: 24
                    onClicked: editor.command("diagnostics", null)
                }
                Label {
                    text: "v" + editor.state.version
                    visible: !root.narrow
                    color: UI.Theme.muted
                    font.family: UI.Theme.monoFont
                    font.pixelSize: 12
                    font.hintingPreference: Font.PreferNoHinting
                }
            }
        }
    }
    UI.TDialog {
        id: shortcutsDialog
        objectName: "shortcutsDialog"
        title: "Keyboard shortcuts"
        width: Math.min(560, root.width - 40)
        ColumnLayout {
            width: parent.width
            spacing: 16
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 20
                rowSpacing: 8
                Repeater {
                    model: root.shortcutList
                    delegate: Label {
                        required property var modelData
                        required property int index
                        Layout.row: index
                        Layout.column: 0
                        text: modelData[0]
                        color: UI.Theme.accent
                        font.family: UI.Theme.monoFont
                        font.pixelSize: 12
                        font.hintingPreference: Font.PreferNoHinting
                    }
                }
                Repeater {
                    model: root.shortcutList
                    delegate: Label {
                        required property var modelData
                        required property int index
                        Layout.row: index
                        Layout.column: 1
                        Layout.fillWidth: true
                        text: modelData[1]
                        color: UI.Theme.text
                        font.pixelSize: 13
                        font.hintingPreference: Font.PreferNoHinting
                    }
                }
            }
            UI.TButton {
                Layout.alignment: Qt.AlignRight
                text: "Close"
                primary: true
                onClicked: shortcutsDialog.close()
            }
        }
    }
    Dialogs {
        id: dialogs
        controller: editor
        anchors.fill: parent
    }
}
