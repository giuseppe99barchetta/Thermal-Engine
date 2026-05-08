# Thermal Engine

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/suggestarr)

A visual theme editor for **LCD AIO cooler displays**. Create custom monitoring themes with real-time CPU/GPU sensor data, gauges, clocks, images, and video backgrounds.

![Preview](https://img.shields.io/badge/Display-Multiple%20Sizes-blue) ![Python](https://img.shields.io/badge/Python-3.10+-green) ![License](https://img.shields.io/badge/License-MIT-yellow) ![Auto%20Release](https://img.shields.io/badge/Auto%20Release-Enabled-success)

<img width="1306" height="732" alt="image" src="/assets/thermal-engine.png" />


## Features

- **Visual drag-and-drop editor** with live preview
- **Universal display support**:
  - HID and USB bulk transfer protocols
  - Auto-detects any display size (480x480, 1280x480, custom resolutions)
  - Works with WinUSB-compatible displays
- **Expandable canvas**: Full-screen editing area with margins for precise image cropping
- **Display orientation controls**: Flip/rotate output for any mounting position
- **Real-time sensor data**: CPU/GPU temperature, utilization, clock speed, power
- **No admin required** - runs as a standard user application
- **Auto-recovery**: Sensors automatically reconnect after sleep/wake
- **Element types**:
  - Circle gauges with auto-color thresholds
  - Bar gauges with rounded corners and gradient fill
  - Text elements (static or sensor-linked)
  - Digital and analog clocks
  - Images and GIFs
  - Line charts for historical data
  - Rectangles
- **Video backgrounds** with fit modes
- **Preset system** for saving and loading themes
- **Multi-select** with alignment tools (align left/right/top/bottom/center, distribute evenly)
- **Copy / Paste elements** (`Ctrl+C` / `Ctrl+V`) with automatic offset
- **Z-order controls**: Bring to Front, Bring Forward, Send Backward, Send to Back via Edit menu or keyboard shortcuts
- **Auto Profiles**: automatically switch presets based on the foreground app or system load state (idle / gaming)
- **Theme packages**: export and import themes as `.thermal` or `.zip` archives with embedded images
- **Element grouping** for organizing complex themes
- **Undo/Redo** support
- **System tray** support with minimize-to-tray

## Supported Displays

### Communication Protocols

**HID-based displays:**
- Thermalright Trofeo AIO (1280x480) ✅
- Other HID displays (may require protocol configuration)

**USB Bulk Transfer (WinUSB):**
- **Thermalright FW 360 Ultra** (480x480) ✅ - ChiZhu Tech USBDISPLAY protocol
- **Any AIO display using WinUSB driver** - Just needs WinUSB driver installation via Zadig
- Supports custom protocols and dimensions

**Universal Features:**
- Automatic dimension detection (works with any resolution: 480x480, 1280x480, 1920x480, etc.)
- Dynamic canvas scaling for comfortable editing
- Display orientation controls (flip/rotate) for any mounting position
- Protocol can be extended for new display types

## Requirements

- Windows 10/11 or Linux
- Python 3.10+ (only if running from source)

### Hardware Sensor Support

**Supported safe sensors**:
- **CPU/RAM/Network**: user-mode metrics via `psutil`
- **CPU/GPU temperature, clocks, power, and load**: bundled LibreHardwareMonitor library
- **Fallback GPU utilization**: Windows Performance Counters when LibreHardwareMonitor is unavailable

**Linux note**:
- CPU/RAM/Network metrics work out of box
- LibreHardwareMonitor and Windows Performance Counters are Windows-specific
- USB/HID display access on Linux may require `udev` permissions

## Installation

### Download (Recommended)

1. Go to [Releases](https://github.com/giuseppe99barchetta/ThermalEngine/releases)
2. Download release asset for your platform:
   - Windows: `ThermalEngine-vX.X.X-Setup.exe`
   - Linux: `ThermalEngine-vX.X.X-linux-x64.tar.gz`
3. Windows: run installer or extracted executable
4. Linux: extract archive and run `ThermalEngine`
5. Run ThermalEngine. No third-party kernel monitoring driver is required.

### From Source

1. Clone this repository:
   ```bash
   git clone https://github.com/giuseppe99barchetta/Thermal-Engine.git
   cd Thermal-Engine
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the editor:
   ```bash
   python main.py
   ```

### Arch Linux Notes

Install common runtime packages first:

```bash
sudo pacman -S python python-pip base-devel libusb hidapi
```

If your display is detected but cannot be opened, create suitable `udev` rules for its VID/PID.

### Local Test Build

Build local standalone package for your platform:

```powershell
# Basic build (ZIP only)
.\scripts\build-local.ps1 -SkipInstaller

# Clean build (removes previous artifacts first)
.\scripts\build-local.ps1 -Clean -SkipInstaller

# Build with installer (requires Inno Setup)
.\scripts\build-local.ps1
```

**Output:**
- `dist\ThermalEngine\ThermalEngine.exe` - Run directly to test
- `ThermalEngine-local-dev.zip` - Portable distribution

**Clean up test build:**
```powershell
.\scripts\clean-local.ps1
```

```bash
# Linux build
chmod +x scripts/build-linux.sh
./scripts/build-linux.sh
```

**Linux output:**
- `ThermalEngine-linux-x64.tar.gz`

## Usage

### Connecting to Display

1. **Close any manufacturer software** (e.g., TRCC) if running - it locks the display
2. Launch the editor
3. The editor will auto-connect, or click "Connect" in the toolbar
4. Display dimensions are automatically detected and applied

### Display Orientation

If your display appears upside-down or rotated, adjust the orientation:

1. Go to **Display > Display Orientation**
2. Choose from available options:
   - **Normal** - Default orientation
   - **Flip Vertical** - Mirror vertically
   - **Flip Horizontal** - Mirror horizontally
   - **Rotate 180°** - Upside down
   - **Rotate 90° CW** - Clockwise rotation
   - **Rotate 90° CCW** - Counter-clockwise rotation

The setting is saved automatically and applied to all frames.

### Auto Profiles

Auto Profiles automatically switch the active preset based on context:

**App-based switching** — loads a preset when a specific application becomes the foreground window:
1. Go to **Settings > Auto Profiles...**
2. Enable **"Enable auto profile switching"**
3. Add rules: enter the process name (e.g. `chrome.exe`) and choose the preset to load
4. Optionally set a **default preset** to revert to when no rule matches

**System State switching** — loads a preset based on CPU load:
- **Idle preset**: loaded after the CPU stays below the idle threshold for the configured duration (default: ≤15% for 60 s)
- **Gaming preset**: loaded after the CPU exceeds the gaming threshold for the configured duration (default: ≥60% for 10 s)
- Thresholds and delays are configurable inside the same dialog

### Creating a Theme

1. **Add elements** from the Elements panel (left side)
2. **Drag elements** on the canvas to position them
3. **Resize** using corner handles
4. **Configure properties** in the Properties panel (right side)
5. **Save as preset** via File > Save as Preset

### Canvas Features

- **Full-screen editing area**: Canvas expands to fill available space for comfortable work
- **Visible margins**: Dark background around canvas shows elements extending beyond boundaries
- **Image cropping**: Drag images/GIFs outside canvas edges to crop and position precisely
- **Auto-scaling**: Canvas automatically scales based on connected display size
  - 480x480 displays: 1.5x scale (720x720 editing area)
  - 1280x480 displays: 0.5x scale (640x240 editing area)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New theme |
| Ctrl+O | Open theme |
| Ctrl+S | Save theme |
| Ctrl+Shift+S | Save as preset |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+G | Group selected elements |
| Ctrl+Shift+G | Ungroup |
| Delete | Delete selected |
| Ctrl+Click | Multi-select elements |
| Ctrl+C | Copy selected elements |
| Ctrl+V | Paste elements (+20px offset) |
| Ctrl+Shift+] | Bring to Front |
| Ctrl+] | Bring Forward |
| Ctrl+[ | Send Backward |
| Ctrl+Shift+[ | Send to Back |

### Sensor Sources

| Source | Description |
|--------|-------------|
| `cpu_percent` | CPU usage (%) |
| `cpu_temp` | CPU temperature (C) |
| `cpu_clock` | CPU clock speed (MHz) |
| `cpu_power` | CPU power draw (W) |
| `gpu_percent` | GPU usage (%) |
| `gpu_temp` | GPU temperature (C) |
| `gpu_clock` | GPU clock speed (MHz) |
| `gpu_memory_clock` | GPU memory clock (MHz) |
| `gpu_power` | GPU power draw (W) |
| `ram_percent` | RAM usage (%) |
| `net_upload` | Network upload (MB/s) |
| `net_download` | Network download (MB/s) |

## Troubleshooting

### "Display not found"
- Make sure manufacturer software is completely closed
- Check USB connection
- Restart the editor

### Sensors showing 0 or not working
1. Go to **Display > Diagnose Sensors** to check connection status
2. Run ThermalEngine as administrator if motherboard, CPU, or GPU sensors are hidden
3. Update Windows and GPU drivers so fallback Performance Counters are available
4. Verify `libs/LibreHardwareMonitorLib.dll` is present in source builds or bundled release builds

### Low FPS / Performance issues
- Reduce target FPS (10 FPS is usually sufficient)
- Avoid video backgrounds on older machines
- Simplify theme (fewer elements)

### USB Display not detected
If your USB-based AIO display isn't detected:

1. **Install WinUSB driver** using [Zadig](https://zadig.akeo.ie/)
   - Download and run Zadig
   - Options → List All Devices
   - Select your display device (e.g., "ChiZhu Tech", or check Device Manager for VID/PID)
   - Select "WinUSB" as target driver
   - Click "Replace Driver" or "Install Driver"
2. **Unplug and replug** the USB cable
3. **Restart** ThermalEngine
4. See `FIX_USB_WINDOWS.md` for detailed USB troubleshooting

**Note:** ThermalEngine will automatically detect your display dimensions and protocol. No manual configuration needed!

### Display appears upside-down or rotated
Use **Display > Display Orientation** to adjust for your mounting position:
- **Rotate 180°** - Common fix for upside-down displays
- **Flip Vertical/Horizontal** - For mirrored displays
- **Rotate 90°** - For rotated mounting

## Project Structure

```
Thermal-Engine/
├── main.py              # Entry point
├── main_window.py       # Main application window
├── canvas.py            # Visual preview widget with expandable editing area
├── device_backends.py   # Multi-device backend system (HID, USB bulk)
├── properties.py        # Properties panel
├── element_list.py      # Element list panel
├── presets.py           # Preset management
├── element.py           # Theme element data model
├── sensors.py           # Sensor polling and smoothing
├── libre_hw_monitor.py  # Safe user-mode hardware monitor compatibility layer
├── video_background.py  # Video background support
├── constants.py         # Configuration constants (dynamic dimensions)
├── scripts/             # Build and utility scripts
│   ├── build-local.ps1  # Local build script
│   └── clean-local.ps1  # Clean up build artifacts
├── assets/              # Icons and images
│   ├── icon.ico
│   └── icon.png
├── elements/            # Custom element plugins
│   ├── line_chart.py
│   └── gif.py
├── presets/             # Saved presets
└── .github/workflows/   # CI/CD workflows
    ├── auto-tag.yml     # Automatic semantic versioning
    └── release.yml      # Automated build and release
```

## Development

### Automatic Releases

This project uses **semantic versioning** with automatic tagging and releases:

**Commit message format:**
```bash
fix: description     # Patch bump (1.0.0 -> 1.0.1)
feat: description    # Minor bump (1.0.0 -> 1.1.0)
major: description   # Major bump (1.0.0 -> 2.0.0)
```

**Workflow:**
1. Commit with proper prefix (`fix:`, `feat:`, `major:`)
2. Push to `main` branch
3. GitHub Actions automatically:
   - Creates version tag
   - Builds Windows release
   - Builds Linux release
   - Creates GitHub Release with both assets attached

**Manual build:**
```bash
pyinstaller --name="Thermal-Engine" --windowed --add-data="elements;elements" --hidden-import=PySide6.QtCore --hidden-import=PySide6.QtGui --hidden-import=PySide6.QtWidgets --hidden-import=device_backends --hidden-import=video_background --collect-all PySide6 main.py
```

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue or PR.
