pragma Singleton
import QtQuick

QtObject {
    // Selectable look: "obsidian" (dark pro), "studio" (light), "hud" (hardware/gaming). Set from the ui_theme setting.
    property string variant: "obsidian"
    readonly property var names: [
        {id: "obsidian", label: "Obsidian (dark)"},
        {id: "studio", label: "Studio (light)"},
        {id: "hud", label: "HUD (amber)"}
    ]
    readonly property var palettes: ({
        // --- obsidian:begin
        obsidian: {
            background: "#0b0e14", surface: "#11151d", raised: "#1b2230", input: "#0e1219", border: "#2b3446", borderStrong: "#56648a",
            text: "#e6eaf2", secondary: "#b6bfd0", muted: "#9aa4b8",
            accent: "#3ee0c5", accentDark: "#123a35", accentPressed: "#2bbfa7", accentBorder: "#2a7f72", onAccent: "#04201b",
            success: "#5fd3a0", warning: "#ffb454", danger: "#ff6b6b",
            scrim: "#b00b0e14", selection: "#223ee0c5",
            font: Qt.platform.os === "windows" ? "Segoe UI" : "Noto Sans", radius: 10
        },
        // --- obsidian:end
        // --- studio:begin
        studio: {
            background: "#efebe2", surface: "#fbf9f4", raised: "#ebe7df", input: "#ffffff", border: "#d9d3c6", borderStrong: "#8a8372",
            text: "#1d1b17", secondary: "#4f4a40", muted: "#625d52",
            accent: "#c2410c", accentDark: "#fff0e8", accentPressed: "#9a3412", accentBorder: "#d9622f", onAccent: "#ffffff",
            success: "#1c6b3a", warning: "#8a5200", danger: "#b42318",
            scrim: "#a01d1b17", selection: "#33c2410c",
            font: Qt.platform.os === "windows" ? "Segoe UI" : "Noto Sans", radius: 9
        },
        // --- studio:end
        // --- hud:begin
        hud: {
            background: "#07060c", surface: "#100e18", raised: "#1a1727", input: "#0b0a12", border: "#2e2a44", borderStrong: "#6a6490",
            text: "#e7e3f7", secondary: "#b9b3d6", muted: "#9a94bb",
            accent: "#ff9a3d", accentDark: "#3a2412", accentPressed: "#e0832a", accentBorder: "#8a5424", onAccent: "#1a0f05",
            success: "#5fe0a0", warning: "#ffd166", danger: "#ff3c78",
            scrim: "#c007060c", selection: "#22ff9a3d",
            font: Qt.platform.os === "windows" ? "Bahnschrift" : "Noto Sans", radius: 4
        }
        // --- hud:end
    })
    readonly property var p: palettes[variant] || palettes.obsidian
    readonly property color background: p.background
    readonly property color surface: p.surface
    readonly property color raised: p.raised
    readonly property color input: p.input
    readonly property color border: p.border  // dividers and panel edges
    readonly property color borderStrong: p.borderStrong  // control outlines, >= 3:1 against their surface
    readonly property color text: p.text
    readonly property color secondary: p.secondary
    readonly property color muted: p.muted
    readonly property color accent: p.accent
    readonly property color accentDark: p.accentDark
    readonly property color accentPressed: p.accentPressed
    readonly property color accentBorder: p.accentBorder
    readonly property color onAccent: p.onAccent
    readonly property color success: p.success
    readonly property color warning: p.warning
    readonly property color danger: p.danger
    readonly property color scrim: p.scrim
    readonly property color selection: p.selection
    readonly property string font: p.font
    readonly property int controlHeight: 36
    readonly property int radius: p.radius
}
