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
            background: "#0a0b0f", surface: "#0f1116", raised: "#12151b", input: "#0b0c10", hover: "#161921", selected: "#1e222c",
            border: "#232733", borderStrong: "#5b6378",
            text: "#eceef3", secondary: "#a3a9b8", muted: "#8b92a3",
            accent: "#ff8a4c", accentDark: "#2d1b10", accentPressed: "#e6723a", accentBorder: "#c4673a", onAccent: "#1a0a02",
            success: "#5fd3a0", warning: "#ffb454", danger: "#ff6b6b",
            scrim: "#b0000000", selection: "#26ff8a4c", radius: 8
        },
        // --- obsidian:end
        // --- studio:begin
        studio: {
            background: "#ece8df", surface: "#fbf9f4", raised: "#f3f0e8", input: "#ffffff", hover: "#ece8de", selected: "#e6dfd0",
            border: "#ddd7c9", borderStrong: "#857e6d",
            text: "#1d1b17", secondary: "#4f4a40", muted: "#5f5a4f",
            accent: "#c4490f", accentDark: "#fde9dc", accentPressed: "#a53b09", accentBorder: "#c4490f", onAccent: "#ffffff",
            success: "#1c6b3a", warning: "#8a5200", danger: "#b42318",
            scrim: "#a01d1b17", selection: "#33c4490f", radius: 8
        },
        // --- studio:end
        // --- hud:begin
        hud: {
            background: "#07060c", surface: "#0f0d17", raised: "#171424", input: "#0a0910", hover: "#1c1930", selected: "#262142",
            border: "#2e2a44", borderStrong: "#6a6490",
            text: "#e7e3f7", secondary: "#b9b3d6", muted: "#9a94bb",
            accent: "#ffa31a", accentDark: "#33210a", accentPressed: "#e08a0a", accentBorder: "#b8741a", onAccent: "#1a0f02",
            success: "#5fe0a0", warning: "#ffd166", danger: "#ff3c78",
            scrim: "#c007060c", selection: "#26ffa31a", radius: 4
        }
        // --- hud:end
    })
    readonly property var p: palettes[variant] || palettes.obsidian
    readonly property color background: p.background  // canvas stage
    readonly property color surface: p.surface  // panels
    readonly property color raised: p.raised  // cards, menus
    readonly property color input: p.input
    readonly property color hover: p.hover
    readonly property color selected: p.selected
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

    // Bundled fonts (SIL OFL, see fonts/); the system families keep the UI correct if loading fails.
    // Static instances (400/500/600/700) of the variable font: the variable file lost word spaces in the software renderer.
    readonly property FontLoader uiLoader: FontLoader { source: "../fonts/InstrumentSans-Regular.ttf" }
    readonly property FontLoader uiMediumLoader: FontLoader { source: "../fonts/InstrumentSans-Medium.ttf" }
    readonly property FontLoader uiSemiBoldLoader: FontLoader { source: "../fonts/InstrumentSans-SemiBold.ttf" }
    readonly property FontLoader uiBoldLoader: FontLoader { source: "../fonts/InstrumentSans-Bold.ttf" }
    readonly property FontLoader monoLoader: FontLoader { source: "../fonts/JetBrainsMono-Regular.ttf" }
    readonly property FontLoader monoMediumLoader: FontLoader { source: "../fonts/JetBrainsMono-Medium.ttf" }
    readonly property string uiFont: uiLoader.status === FontLoader.Ready ? uiLoader.name
        : (Qt.platform.os === "windows" ? (variant === "hud" ? "Bahnschrift" : "Segoe UI") : "Noto Sans")
    readonly property string monoFont: monoLoader.status === FontLoader.Ready ? monoLoader.name
        : (Qt.platform.os === "windows" ? "Consolas" : "DejaVu Sans Mono")
    readonly property string font: uiFont

    readonly property int controlHeight: 32
    readonly property int fieldHeight: 30
    readonly property int radius: p.radius
    readonly property int radiusSmall: Math.max(2, p.radius - 1)
}
