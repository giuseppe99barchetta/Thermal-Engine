import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components" as UI

ColumnLayout {
    id: browser
    property var controller
    property string query: ""
    property string scope: "Summary"
    property string category: "All groups"
    readonly property var scopes: ["Summary", "Hardware", "External"]
    spacing: 10
    function refreshFilter() {
        controller.filterSensors(scope, category, query, unavailable.checked);
    }
    onQueryChanged: refreshFilter()
    // Own segment strip: TSegmented's button padding elides "Summary" / "Hardware" at the panel width
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 32
        radius: UI.Theme.radius + 1
        color: UI.Theme.input
        RowLayout {
            anchors.fill: parent
            anchors.margins: 3
            spacing: 2
            Repeater {
                model: browser.scopes
                UI.TButton {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    implicitHeight: 26
                    flat: true
                    leftPadding: 2
                    rightPadding: 2
                    text: modelData
                    selected: browser.scope === modelData
                    Accessible.role: Accessible.PageTab
                    Accessible.selected: selected
                    onClicked: {
                        browser.scope = modelData;
                        browser.category = "All groups";
                        browser.refreshFilter();
                    }
                }
            }
        }
    }
    UI.TCombo {
        Layout.fillWidth: true
        model: controller.sensorCategories
        currentIndex: Math.max(0, model.indexOf(browser.category))
        onActivated: {
            browser.category = currentText;
            browser.refreshFilter();
        }
    }
    UI.TCheck {
        id: unavailable
        text: "Show unavailable"
        onClicked: browser.refreshFilter()
    }
    Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: controller.state.selectionCount === 1 ? "Double-click a reading to use it in the selected element." : "Select an element to assign a reading."
        color: UI.Theme.muted
        font.pixelSize: 12
        font.hintingPreference: Font.PreferNoHinting
    }
    ListView {
        id: list
        objectName: "sensorBrowser"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 1
        model: controller.sensorBrowser
        ScrollBar.vertical: ScrollBar {}
        delegate: Column {
            id: entry
            required property var row
            width: list.width
            spacing: 1
            Label {
                visible: entry.row.heading
                height: visible ? 30 : 0
                text: entry.row.category
                color: UI.Theme.muted
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.letterSpacing: 0.9
                font.capitalization: Font.AllUppercase
                font.hintingPreference: Font.PreferNoHinting
                verticalAlignment: Text.AlignBottom
                bottomPadding: 6
                leftPadding: 10
            }
            Rectangle {
                width: parent.width
                height: 36
                radius: UI.Theme.radius
                color: mouse.containsMouse ? UI.Theme.hover : "transparent"
                Accessible.name: entry.row.name + ", " + (entry.row.available ? entry.row.value : "unavailable")
                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8
                    Text {
                        width: parent.width - valueText.implicitWidth - 8
                        height: parent.height
                        text: entry.row.name
                        color: entry.row.available ? UI.Theme.text : UI.Theme.muted
                        font.family: UI.Theme.uiFont
                        font.pixelSize: 13
                        font.hintingPreference: Font.PreferNoHinting
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    Text {
                        id: valueText
                        height: parent.height
                        text: entry.row.available ? entry.row.value : "Unavailable"
                        color: entry.row.available ? UI.Theme.warning : UI.Theme.muted
                        font.family: UI.Theme.monoFont
                        font.pixelSize: 12
                        font.hintingPreference: Font.PreferNoHinting
                        verticalAlignment: Text.AlignVCenter
                    }
                }
                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onDoubleClicked: if (browser.controller.state.selectionCount === 1)
                        browser.controller.edit("source", entry.row.id)
                }
                ToolTip.visible: mouse.containsMouse
                ToolTip.delay: 700
                ToolTip.text: entry.row.name + "\n" + entry.row.id
            }
        }
        Label {
            anchors.centerIn: parent
            width: parent.width - 16
            visible: list.count === 0
            text: browser.scope === "External" ? "No external readings.\nAdd an MQTT, HTTP, TCP or UDP sensor." : "No matching readings.\nTry another group or show unavailable sensors."
            color: UI.Theme.secondary
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 13
            font.hintingPreference: Font.PreferNoHinting
        }
    }
    UI.TButton {
        Layout.fillWidth: true
        text: browser.scope === "External" ? "Manage network sensors..." : "Refresh hardware sensors"
        onClicked: controller.command(browser.scope === "External" ? "network" : "refreshSensors", null)
    }
}
