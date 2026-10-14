pragma Singleton
import QtQuick

QtObject {
    readonly property color background: "#101419"
    readonly property color surface: "#171d24"
    readonly property color raised: "#202833"
    readonly property color input: "#11171e"
    readonly property color border: "#2b3643"
    readonly property color text: "#edf2f7"
    readonly property color secondary: "#9eafc0"
    readonly property color muted: "#8599ad"  // >= 5:1 on panels and inputs (WCAG AA)
    readonly property color accent: "#57d4ef"
    readonly property color accentDark: "#133c48"
    readonly property color success: "#74c9a5"
    readonly property color warning: "#e4bb75"
    readonly property color danger: "#ef9292"
    readonly property string font: Qt.platform.os === "windows" ? "Segoe UI" : "Noto Sans"
    readonly property int controlHeight: 36
    readonly property int radius: 8
}
