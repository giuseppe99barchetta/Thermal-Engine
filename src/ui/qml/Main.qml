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
    palette.window: UI.Theme.surface
    palette.base: UI.Theme.input
    palette.text: UI.Theme.text
    palette.windowText: UI.Theme.text
    palette.button: UI.Theme.raised
    palette.buttonText: UI.Theme.text
    palette.highlight: UI.Theme.accentDark
    palette.dark: UI.Theme.border
    palette.mid: UI.Theme.border
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
    function savePanelWidths() {
        editor.saveSettings({layers_panel_width: Math.round(layersWidth), inspector_panel_width: Math.round(inspectorWidth)});
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
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 68
            color: UI.Theme.surface
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 12
                Image {
                    objectName: "applicationLogo"
                    source: "../../../assets/icon.png"
                    sourceSize: Qt.size(80, 80)
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    fillMode: Image.PreserveAspectFit
                }
                ColumnLayout {
                    visible: root.width >= 1000
                    spacing: 2
                    Label {
                        text: "THERMAL ENGINE"
                        color: UI.Theme.text
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1
                    }
                    Label {
                        text: "DISPLAY STUDIO"
                        color: UI.Theme.muted
                        font.pixelSize: 9
                        font.letterSpacing: 2
                    }
                }
                Rectangle {
                    visible: root.width >= 1000
                    width: 1
                    height: 28
                    color: UI.Theme.border
                    Layout.leftMargin: 12
                    Layout.rightMargin: 8
                }
                Label {
                    text: editor.state.name
                    color: UI.Theme.text
                    font.pixelSize: 14
                    Layout.maximumWidth: 200
                    elide: Text.ElideRight
                }
                UI.TButton {
                    visible: root.narrow
                    text: "Canvas"
                    onClicked: {
                        root.layersOpen = false;
                        root.propertiesOpen = false;
                    }
                }
                Label {
                    visible: root.width >= 800
                    text: editor.state.dirty ? "Unsaved" : "Saved"
                    color: editor.state.dirty ? UI.Theme.warning : UI.Theme.muted
                    font.pixelSize: 11
                }
                Item {
                    Layout.fillWidth: true
                }
                Rectangle {
                    width: 7
                    height: 7
                    radius: 4
                    color: editor.state.connected ? UI.Theme.success : UI.Theme.muted
                }
                ColumnLayout {
                    visible: root.width >= 800
                    spacing: 1
                    Label {
                        text: editor.state.device
                        color: UI.Theme.text
                        font.pixelSize: 12
                    }
                    Label {
                        text: editor.state.width + " × " + editor.state.height + "  ·  " + (editor.state.connected ? "Connected" : "Disconnected")
                        color: UI.Theme.secondary
                        font.pixelSize: 10
                    }
                }
                UI.TButton {
                    // Wide windows show the Display tab in the inspector already
                    visible: root.narrow
                    text: "Display"
                    onClicked: {
                        root.inspectorTab = 1;
                        root.propertiesOpen = true;
                        root.layersOpen = false;
                    }
                }
                UI.TButton {
                    text: editor.state.connected ? "Disconnect" : "Connect"
                    onClicked: editor.command("connect", null)
                }
                UI.TButton {
                    text: "Save theme"
                    primary: true
                    ToolTip.text: "Save theme · Ctrl+S"
                    ToolTip.visible: hovered
                    onClicked: editor.command("save", null)
                }
                UI.TButton {
                    id: menuButton
                    text: "···"
                    ToolTip.text: "Project and settings"
                    onClicked: projectMenu.open()
                    UI.TMenu {
                        id: projectMenu
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
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: UI.Theme.border
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Rectangle {
                visible: !root.narrow || root.layersOpen
                Layout.preferredWidth: root.narrow ? root.width : Math.min(root.layersWidth, Math.max(220, (root.width - 416) * 0.45))
                Layout.fillHeight: true
                color: UI.Theme.surface
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: ["Layers", "Presets", "Sensors"]
                            UI.TButton {
                                required property string modelData
                                required property int index
                                Layout.fillWidth: true
                                text: modelData
                                selected: root.leftTab === index
                                onClicked: {
                                    root.leftTab = index;
                                    root.searchText = "";
                                    search.text = "";
                                }
                            }
                        }
                    }
                    UI.TField {
                        id: search
                        Layout.fillWidth: true
                        placeholderText: root.leftTab === 0 ? "Find a layer…" : root.leftTab === 1 ? "Find a preset…" : "Find a sensor…"
                        onTextChanged: root.searchText = text.toLowerCase()
                    }
                    RowLayout {
                        visible: root.leftTab === 0
                        Layout.fillWidth: true
                        Label {
                            text: "PAGE " + editor.state.page
                            color: UI.Theme.muted
                            font.pixelSize: 10
                            font.letterSpacing: 1
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        UI.TButton {
                            text: "+ Add"
                            onClicked: addMenu.open()
                            UI.TMenu {
                                id: addMenu
                                objectName: "addMenu"
                                y: parent.height
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
                    UI.TCheck {
                        visible: root.leftTab === 1
                        text: "All resolutions"
                        checked: root.allResolutions
                        onClicked: root.allResolutions = checked
                    }
                    StackLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        currentIndex: root.leftTab
                        ListView {
                            id: layerList
                            objectName: "layerList"
                            clip: true
                            spacing: 4
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
                                property bool isGroup: row.kind === "group"
                                width: layerList.width
                                height: visible ? (isGroup ? 38 : 46) : 0
                                visible: row.name.toLowerCase().indexOf(root.searchText) >= 0
                                radius: 6
                                color: row.selected ? UI.Theme.accentDark : layerMouse.containsMouse ? UI.Theme.raised : "transparent"
                                border.color: row.selected ? "#316776" : "transparent"
                                opacity: layerMouse.dragging ? 0.5 : 1
                                ToolButton {
                                    id: groupToggle
                                    visible: layerRow.isGroup
                                    x: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 24
                                    height: 28
                                    z: 2
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
                                Column {
                                    x: layerRow.isGroup ? 30 : (row.indented ? 28 : 12)
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - x - 62
                                    spacing: 3
                                    Text {
                                        text: layerRow.isGroup ? row.name + "  ·  " + row.count : row.name
                                        color: row.visible ? UI.Theme.text : UI.Theme.muted
                                        font.pixelSize: 12
                                        font.weight: layerRow.isGroup ? Font.DemiBold : Font.Normal
                                        width: parent.width
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        visible: !layerRow.isGroup
                                        text: editor.typeLabels[row.type] || row.type.replace(/_/g, " ")
                                        color: row.selected ? UI.Theme.secondary : UI.Theme.muted
                                        font.pixelSize: 10
                                    }
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
                                Row {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 6
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 2
                                    UI.TIconButton {
                                        width: 28
                                        height: 28
                                        iconName: row.visible ? "eye" : "hidden"
                                        onClicked: {
                                            editor.selectLayer(row.index, false, layerRow.isGroup);
                                            editor.edit("visible", !row.visible);
                                        }
                                        Accessible.name: (row.visible ? "Hide " : "Show ") + row.name
                                        ToolTip.text: layerRow.isGroup ? "Toggle visibility of the group" : "Toggle visibility"
                                        ToolTip.visible: hovered
                                    }
                                    UI.TIconButton {
                                        width: 28
                                        height: 28
                                        iconName: row.locked ? "lock" : "unlock"
                                        onClicked: {
                                            editor.selectLayer(row.index, false, layerRow.isGroup);
                                            editor.edit("locked", !row.locked);
                                        }
                                        Accessible.name: (row.locked ? "Unlock " : "Lock ") + row.name
                                        ToolTip.text: layerRow.isGroup ? "Lock or unlock the whole group" : "Toggle lock"
                                        ToolTip.visible: hovered
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
                            Label {
                                anchors.centerIn: parent
                                width: parent.width - 20
                                visible: layerList.count === 0
                                text: "Your canvas is ready.\nAdd your first element."
                                color: UI.Theme.secondary
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                lineHeight: 1.4
                            }
                        }
                        GridView {
                            id: presetList
                            objectName: "presetBrowserGrid"
                            clip: true
                            cellWidth: width / Math.max(1, Math.floor(width / 180))
                            cellHeight: 170
                            model: editor.presetBrowser
                            ScrollBar.vertical: ScrollBar {}
                            delegate: Rectangle {
                                required property var row
                                width: presetList.cellWidth - 8
                                height: presetList.cellHeight - 10
                                radius: 8
                                color: presetMouse.containsMouse ? UI.Theme.raised : UI.Theme.input
                                border.color: row.name === editor.state.name ? "#316776" : UI.Theme.border
                                Image {
                                    anchors.top: parent.top
                                    anchors.topMargin: 10
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: parent.width - 20
                                    height: 104
                                    fillMode: Image.PreserveAspectFit
                                    source: "image://thumbs/preset/" + row.name + "?" + editor.state.revision
                                }
                                Text {
                                    x: 12
                                    y: 120
                                    text: row.name
                                    width: parent.width - 24
                                    elide: Text.ElideRight
                                    color: UI.Theme.text
                                    font.pixelSize: 12
                                }
                                Text {
                                    x: 12
                                    y: 139
                                    width: parent.width - 24
                                    text: row.width + " × " + row.height + " · " + (row.builtin ? "Built-in" : "Personal")
                                    font.pixelSize: 10
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
                                            editor.command("loadPreset", row.name);
                                    }
                                }
                                UI.TMenu {
                                    id: presetMenu
                                    UI.TMenuItem {
                                        text: "Load theme"
                                        onTriggered: editor.command("loadPreset", row.name)
                                    }
                                    UI.TMenuItem {
                                        text: "Use at startup"
                                        onTriggered: editor.command("defaultPreset", row.name)
                                    }
                                    UI.TMenuItem {
                                        text: "Delete preset"
                                        enabled: !row.builtin
                                        onTriggered: editor.command("deletePreset", row.name)
                                    }
                                }
                            }
                        }
                        SensorBrowser {
                            controller: editor
                            query: root.searchText
                        }
                    }
                }
            }
            UI.TSplitter {
                objectName: "layersSplitter"
                visible: !root.narrow
                panelName: "layers panel"
                value: root.layersWidth
                maximum: Math.min(440, root.width - root.inspectorWidth - 416)
                onAdjusted: function(value) { root.layersWidth = value; }
                onCommitted: root.savePanelWidths()
            }
            ColumnLayout {
                visible: !root.narrow || (!root.layersOpen && !root.propertiesOpen)
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 52
                    color: UI.Theme.background
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 8
                        UI.TButton {
                            visible: root.narrow
                            text: "Layers"
                            onClicked: {
                                root.layersOpen = !root.layersOpen;
                                root.propertiesOpen = false;
                            }
                        }
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
                        Item {
                            Layout.fillWidth: true
                        }
                        UI.TCombo {
                            id: previewValues
                            objectName: "previewValues"
                            property var fractions: [-1, 0.25, 0.5, 0.9]
                            Layout.preferredWidth: 150
                            model: ["Live data", "Simulate 25%", "Simulate 50%", "Simulate 90%"]
                            currentIndex: Math.max(0, fractions.indexOf(editor.state.previewFraction))
                            onActivated: editor.command("previewValues", fractions[currentIndex])
                            ToolTip.text: "Preview gauges, colors and rules with simulated readings. The display keeps live data."
                            ToolTip.visible: hovered
                        }
                        UI.TCheck {
                            visible: root.width >= 800
                            text: "Grid"
                            checked: editor.state.grid
                            onClicked: editor.command("grid", checked)
                        }
                        UI.TCheck {
                            visible: root.width >= 800
                            text: "Snap"
                            checked: editor.state.snap
                            onClicked: editor.command("snap", checked)
                        }
                        UI.TButton {
                            text: "−"
                            ToolTip.text: "Zoom out · Ctrl+wheel"
                            ToolTip.visible: hovered
                            onClicked: canvas.zoomBy(1 / 1.2)
                        }
                        UI.TButton {
                            text: editor.state.zoom + "%"
                            ToolTip.text: "Fit display · Ctrl+0"
                            onClicked: canvas.fit()
                        }
                        UI.TButton {
                            text: "+"
                            ToolTip.text: "Zoom in · Ctrl+wheel"
                            ToolTip.visible: hovered
                            onClicked: canvas.zoomBy(1.2)
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
                        color: "#2257d4ef"
                        border.color: UI.Theme.accent
                        border.width: 2
                        Label {
                            anchors.centerIn: parent
                            text: "Drop images or GIFs to add them · a video to set the background"
                            color: UI.Theme.text
                            font.pixelSize: 14
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
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8
                        RowLayout {
                            Label {
                                text: "PAGES"
                                color: UI.Theme.muted
                                font.pixelSize: 10
                                font.letterSpacing: 1
                            }
                            UI.TCombo {
                                visible: root.height < 500
                                Layout.preferredWidth: 72
                                model: editor.state.pages
                                currentIndex: model.indexOf(editor.state.page)
                                onActivated: editor.command("page", Number(currentText))
                            }
                            UI.TButton {
                                visible: root.height < 500
                                text: "+"
                                onClicked: editor.command("addPage", null)
                            }
                            UI.TButton {
                                visible: root.height < 500
                                text: "-"
                                enabled: editor.state.pages.length > 1
                                onClicked: editor.command("deletePage", editor.state.page)
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                            UI.TButton {
                                visible: !pageStrip.multiPage && root.height >= 500
                                text: "+ Add page"
                                ToolTip.text: "Pages rotate on the display, e.g. a stats page and a clock page"
                                ToolTip.visible: hovered
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
                                Layout.preferredWidth: 48
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
                                font.pixelSize: 11
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
                                required property var row
                                objectName: "pageThumbnail" + row.number
                                width: 112
                                height: 76
                                radius: 6
                                color: row.current ? UI.Theme.accentDark : UI.Theme.input
                                border.color: row.current ? UI.Theme.accent : UI.Theme.border
                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    source: "image://thumbs/page/" + row.number + "?" + editor.state.revision
                                    fillMode: Image.PreserveAspectFit
                                }
                                Text {
                                    x: 6
                                    y: 4
                                    text: row.number
                                    color: UI.Theme.text
                                    style: Text.Outline
                                    styleColor: UI.Theme.background
                                    font.pixelSize: 11
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: function (mouse) {
                                        if (mouse.button === Qt.RightButton)
                                            pageMenu.popup();
                                        else
                                            editor.command("page", row.number);
                                    }
                                }
                                UI.TMenu {
                                    id: pageMenu
                                    UI.TMenuItem {
                                        text: "Delete page"
                                        enabled: pageList.count > 1
                                        onTriggered: editor.command("deletePage", row.number)
                                    }
                                }
                            }
                            footer: UI.TButton {
                                text: "+"
                                width: 44
                                height: 76
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
                maximum: Math.min(520, root.width - root.layersWidth - 416)
                reversed: true
                onAdjusted: function(value) { root.inspectorWidth = value; }
                onCommitted: root.savePanelWidths()
            }
            Rectangle {
                visible: !root.narrow || root.propertiesOpen
                Layout.preferredWidth: root.narrow ? root.width : Math.min(root.inspectorWidth, Math.max(280, (root.width - 416) * 0.55))
                Layout.fillHeight: true
                color: UI.Theme.surface
                Inspector {
                    activeTab: root.inspectorTab
                    onActiveTabChanged: root.inspectorTab = activeTab
                    anchors.fill: parent
                    controller: editor
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 36
            color: UI.Theme.background
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                Label {
                    text: editor.state.status
                    color: UI.Theme.secondary
                    font.pixelSize: 10
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                Label {
                    text: (editor.state.connected ? editor.state.actualFps + " FPS · " : "") + editor.state.width + " × " + editor.state.height
                    color: UI.Theme.muted
                    font.pixelSize: 10
                }
                Repeater {
                    model: editor.healthChecks
                    UI.TStatusBadge {
                        required property var modelData
                        visible: !root.narrow
                        text: modelData.name + ": " + modelData.status
                        severity: modelData.severity
                        ToolTip.text: modelData.detail
                        onClicked: editor.command(modelData.action, null)
                    }
                }
                UI.TButton {
                    visible: root.narrow
                    text: "Status"
                    implicitHeight: 24
                    onClicked: editor.command("diagnostics", null)
                }
                Label {
                    text: "v" + editor.state.version
                    visible: !root.narrow
                    color: UI.Theme.muted
                    font.pixelSize: 10
                    Layout.leftMargin: 16
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
                        font.family: "Consolas"
                        font.pixelSize: 12
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
                        font.pixelSize: 12
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
