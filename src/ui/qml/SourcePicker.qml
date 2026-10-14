import QtQuick
import QtQuick.Layouts
import "components" as UI

ColumnLayout {
    id: picker
    property var controller
    property string lastSource: ""
    property string category: "Static"
    Layout.fillWidth: true
    spacing: 8
    function groupFor(id) {
        for (let row of controller.sources)
            if (row.id === id)
                return row.category;
        return "Static";
    }
    function groups() {
        let names = [];
        for (let row of controller.sources)
            if (names.indexOf(row.category) < 0)
                names.push(row.category);
        return names;
    }
    function entries() {
        return controller.sources.filter(function (row) {
            return row.category === picker.category;
        });
    }
    Connections {
        target: picker.controller
        function onSelectionChanged() {
            let source = picker.controller.selected.source || "static";
            if (picker.lastSource !== source) {
                picker.lastSource = source;
                picker.category = picker.groupFor(source);
            }
        }
    }
    Component.onCompleted: category = groupFor(controller.selected.source || "static")
    UI.TCombo {
        Layout.fillWidth: true
        model: picker.groups()
        currentIndex: Math.max(0, model.indexOf(picker.category))
        onActivated: picker.category = currentText
    }
    UI.TCombo {
        Layout.fillWidth: true
        model: picker.entries()
        textRole: "name"
        currentIndex: {
            for (let i = 0; i < model.length; i++)
                if (model[i].id === picker.controller.selected.source)
                    return i;
            return -1;
        }
        displayText: currentIndex < 0 ? "Choose a sensor..." : currentText
        onActivated: picker.controller.edit("source", model[currentIndex].id)
    }
}
