import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components" as UI

UI.TDialog {
    id: dialog
    title: "Gradient stops"
    width: Math.min(560, parent.width - 40)
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
    component SectionLabel: Label {
        color: UI.Theme.muted
        font.family: UI.Theme.uiFont
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.letterSpacing: 0.9
        font.capitalization: Font.AllUppercase
        font.hintingPreference: Font.PreferNoHinting
    }
    ColorDialog {
        id: colors
        property int stopIndex
        onAccepted: dialog.setStop(stopIndex, 1, selectedColor.toString())
    }
    footerContent: RowLayout {
        width: parent.width
        spacing: 8
        UI.TButton {
            text: "+ Add stop"
            flat: true
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
            flat: true
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
        spacing: 14
        Canvas {
            id: preview
            Layout.fillWidth: true
            Layout.preferredHeight: 56
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
                c.beginPath();
                c.roundedRect(0, 0, width, height, UI.Theme.radius, UI.Theme.radius);
                c.fill();
                // Stop markers: a ring at each position
                for (let j = 0; j < ordered.length; j++) {
                    let x = 8 + Math.max(0, Math.min(1, ordered[j][0])) * (width - 16);
                    c.beginPath();
                    c.arc(x, height - 10, 4, 0, Math.PI * 2);
                    c.lineWidth = 4;
                    c.strokeStyle = "#99000000";
                    c.stroke();
                    c.lineWidth = 2;
                    c.strokeStyle = "#ffffff";
                    c.stroke();
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: "Position from 0 (start) to 1 (end). Stops are sorted when applied."
            color: UI.Theme.secondary
            wrapMode: Text.WordWrap
            font.family: UI.Theme.uiFont
            font.pixelSize: 13
            font.hintingPreference: Font.PreferNoHinting
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            SectionLabel {
                text: "Position"
                Layout.preferredWidth: 90
            }
            SectionLabel {
                text: "Color"
                Layout.fillWidth: true
            }
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
                height: 32
                spacing: 8
                UI.TField {
                    Layout.preferredWidth: 90
                    text: modelData[0]
                    font.family: UI.Theme.monoFont
                    Accessible.name: "Stop position"
                    validator: DoubleValidator {
                        bottom: 0
                        top: 1
                        decimals: 3
                    }
                    onEditingFinished: if (acceptableInput)
                        dialog.setStop(index, 0, Number(text))
                }
                Button {
                    id: swatch
                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 30
                    padding: 0
                    hoverEnabled: true
                    text: "Choose color for stop " + (index + 1)
                    Accessible.name: text
                    ToolTip.text: text
                    ToolTip.visible: hovered
                    ToolTip.delay: 600
                    onClicked: {
                        colors.stopIndex = index;
                        colors.selectedColor = modelData[1];
                        colors.open();
                    }
                    contentItem: Item {}
                    background: Rectangle {
                        radius: UI.Theme.radiusSmall
                        color: modelData[1]
                        border.width: swatch.hovered ? 2 : 1
                        border.color: swatch.hovered ? UI.Theme.accent : UI.Theme.borderStrong
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: -3
                            radius: parent.radius + 3
                            color: "transparent"
                            border.width: 2
                            border.color: UI.Theme.accent
                            visible: swatch.visualFocus
                        }
                    }
                }
                UI.TField {
                    Layout.fillWidth: true
                    text: modelData[1]
                    font.family: UI.Theme.monoFont
                    Accessible.name: "Stop color"
                    onEditingFinished: dialog.setStop(index, 1, text)
                }
                UI.TIconButton {
                    iconName: "close"
                    Accessible.name: "Remove stop " + (index + 1)
                    ToolTip.text: "Remove stop"
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
