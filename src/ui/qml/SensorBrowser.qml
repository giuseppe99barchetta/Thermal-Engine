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
    spacing: 10
    function refreshFilter() {
        controller.filterSensors(scope, category, query, unavailable.checked);
    }
    onQueryChanged: refreshFilter()
    RowLayout {
        Layout.fillWidth: true
        spacing: 4
        Repeater {
            model: ["Summary", "Hardware", "External"]
            UI.TButton {
                required property string modelData
                text: modelData
                Layout.fillWidth: true
                font.pixelSize: 11
                selected: browser.scope === modelData
                onClicked: {
                    browser.scope = modelData;
                    browser.category = "All groups";
                    browser.refreshFilter();
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
        font.pixelSize: 11
    }
    ListView {
        id: list
        objectName: "sensorBrowser"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 4
        model: controller.sensorBrowser
        ScrollBar.vertical: ScrollBar {}
        delegate: Column {
            required property var row
            width: list.width
            spacing: 4
            Label {
                visible: row.heading
                height: visible ? 28 : 0
                text: row.category.toUpperCase()
                color: UI.Theme.muted
                font.pixelSize: 10
                topPadding: 8
                font.letterSpacing: 0.5
            }
            Rectangle {
                width: parent.width
                height: 66
                radius: 8
                color: mouse.containsMouse ? UI.Theme.raised : UI.Theme.input
                Column {
                    x: 10
                    y: 10
                    width: parent.width - 20
                    spacing: 5
                    Text {
                        width: parent.width
                        text: row.name
                        color: UI.Theme.secondary
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        text: row.available ? row.value : "Unavailable"
                        color: row.available ? UI.Theme.text : UI.Theme.muted
                        font.pixelSize: row.available ? 18 : 12
                        elide: Text.ElideRight
                    }
                }
                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onDoubleClicked: if (browser.controller.state.selectionCount === 1)
                        browser.controller.edit("source", row.id)
                }
                ToolTip.visible: mouse.containsMouse
                ToolTip.delay: 700
                ToolTip.text: row.name + "\n" + row.id
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
        }
    }
    UI.TButton {
        Layout.fillWidth: true
        text: browser.scope === "External" ? "Manage network sensors..." : "Refresh hardware sensors"
        onClicked: controller.command(browser.scope === "External" ? "network" : "refreshSensors", null)
    }
}
