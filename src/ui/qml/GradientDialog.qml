import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components" as UI

UI.TDialog {
    id: dialog
    title: "Gradient stops"
    property var controller
    property var stops: []
    function initialize(data) {
        stops = JSON.parse(JSON.stringify(data.length ? data : [[0, "#57d4ef"], [1, "#74c9a5"]]));
    }
    function setStop(index, field, value) {
        let copy = JSON.parse(JSON.stringify(stops));
        copy[index][field] = value;
        stops = copy;
        preview.requestPaint();
    }
    ColorDialog {
        id: colors
        property int stopIndex
        onAccepted: dialog.setStop(stopIndex, 1, selectedColor.toString())
    }
    footerContent: RowLayout {
        UI.TButton {
            text: "+ Add stop"
            onClicked: {
                dialog.stops = dialog.stops.concat([[0.5, "#ffffff"]]);
                preview.requestPaint();
            }
        }
        Item {
            Layout.fillWidth: true
        }
        UI.TButton {
            text: "Cancel"
            onClicked: dialog.close()
        }
        UI.TButton {
            text: "Apply gradient"
            primary: true
            onClicked: {
                controller.edit("gradient_stops", dialog.stops.slice().sort(function (a, b) {
                    return a[0] - b[0];
                }));
                dialog.close();
            }
        }
    }
    ColumnLayout {
        width: parent.width
        spacing: 16
        Canvas {
            id: preview
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            onPaint: {
                let c = getContext("2d");
                c.reset();
                let g = c.createLinearGradient(0, 0, width, 0);
                let ordered = dialog.stops.slice().sort(function (a, b) {
                    return a[0] - b[0];
                });
                for (let i = 0; i < ordered.length; i++)
                    g.addColorStop(Math.max(0, Math.min(1, ordered[i][0])), ordered[i][1]);
                c.fillStyle = g;
                c.fillRect(0, 0, width, height);
            }
        }
        Label {
            text: "Position from 0 (start) to 1 (end). Stops are sorted when applied."
            color: UI.Theme.secondary
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(220, contentHeight)
            clip: true
            spacing: 8
            model: dialog.stops
            delegate: RowLayout {
                required property var modelData
                required property int index
                width: list.width
                UI.TField {
                    Layout.preferredWidth: 100
                    text: modelData[0]
                    validator: DoubleValidator {
                        bottom: 0
                        top: 1
                        decimals: 3
                    }
                    onEditingFinished: if (acceptableInput)
                        dialog.setStop(index, 0, Number(text))
                }
                UI.TField {
                    Layout.fillWidth: true
                    text: modelData[1]
                    onEditingFinished: dialog.setStop(index, 1, text)
                }
                UI.TButton {
                    text: "Color"
                    onClicked: {
                        colors.stopIndex = index;
                        colors.selectedColor = modelData[1];
                        colors.open();
                    }
                }
                UI.TButton {
                    text: "Remove"
                    enabled: dialog.stops.length > 2
                    onClicked: {
                        let copy = dialog.stops.slice();
                        copy.splice(index, 1);
                        dialog.stops = copy;
                        preview.requestPaint();
                    }
                }
            }
        }
    }
    onOpened: preview.requestPaint()
}
