# Fix: No USB Devices Found on Windows

## Problem
When running `diagnose_usb.py`, you get:
```
[FAIL] No USB devices found at all!
```

This means pyusb can't access the USB system on Windows.

## Root Cause
pyusb on Windows requires a **libusb backend** to communicate with USB devices. Windows doesn't include this by default.

## Solution: Install libusb Backend

### Option 1: Install libusb (Recommended)

1. **Download libusb**:
   - Go to: https://github.com/libusb/libusb/releases
   - Download latest `libusb-1.0.XX.7z` (e.g., `libusb-1.0.27.7z`)

2. **Extract libusb DLL**:
   - Extract the 7z file
   - Navigate to: `VS2019\MS64\dll\` (for 64-bit Windows)
   - Copy `libusb-1.0.dll`

3. **Install the DLL**:
   Choose ONE of these locations:
   - **System-wide**: `C:\Windows\System32\libusb-1.0.dll`
   - **Python-specific**: `C:\Users\peppe\Thermal-Engine\venv\Scripts\libusb-1.0.dll`
   - **Local**: `C:\Users\peppe\Thermal-Engine\libusb-1.0.dll`

4. **Test**:
   ```bash
   python diagnose_usb.py
   ```
   You should now see USB devices listed.

### Option 2: Use Zadig (Easiest)

Zadig can install WinUSB driver for specific devices:

1. **Download Zadig**:
   - Go to: https://zadig.akeo.ie/
   - Download `zadig-X.X.exe`

2. **Run Zadig**:
   - Run as Administrator
   - Go to Options > List All Devices
   - Find your "Thermalright" device in dropdown

3. **Install WinUSB**:
   - Select your device
   - Select "WinUSB" in the driver dropdown
   - Click "Install Driver" or "Replace Driver"
   - Wait for installation to complete

4. **Test**:
   ```bash
   python diagnose_usb.py
   ```
   Your device should now be detected.

**IMPORTANT**: Installing WinUSB for your device may prevent TR Control Center from working. You can switch back using Zadig later.

### Option 3: Use libusb-win32 (Alternative)

1. Download from: http://sourceforge.net/projects/libusb-win32/
2. Install the filter driver
3. Test with diagnose_usb.py

## Verification

After installing a backend, run:
```bash
python diagnose_usb.py
```

You should see:
```
[3/4] Enumerating ALL USB devices...

  Found X USB device(s):

  - VID: 0xXXXX, PID: 0xXXXX
    Manufacturer: ...
    Product: ...
```

## Troubleshooting

### Still No Devices Found?

1. **Check if libusb-1.0.dll is in the right place**:
   - Should be in System32 or same folder as python.exe
   - Or in the Thermal-Engine directory

2. **Try different libusb backend**:
   - Try libusb-win32 instead
   - Or use Zadig to install WinUSB

3. **Check Device Manager**:
   - Press Win+X > Device Manager
   - Find your AIO device
   - Check if it has a yellow warning icon
   - Right-click > Update Driver

4. **Run Python as Administrator**:
   - Some USB operations need admin rights
   - Right-click Command Prompt > Run as Administrator
   - Then run `python diagnose_usb.py`

### Device Found but Can't Connect?

If diagnose_usb.py FINDS your device but Thermal-Engine can't connect:

1. **Close TR Control Center** completely
2. **Unplug and replug** the device
3. **Try different USB port** (prefer USB 2.0 ports)
4. **Check device is not suspended** in Device Manager

## Summary

Windows USB access requires:
1. pyusb (Python library) ✓ Already installed
2. USB backend (libusb-1.0.dll or WinUSB driver) ← **You need this!**

**Recommended**: Install libusb-1.0.dll to System32 folder for system-wide USB access.

## Quick Commands

Test if libusb is found:
```bash
python -c "import usb.backend.libusb1; print(usb.backend.libusb1.get_backend())"
```

Should output: `<usb.backend.libusb1.Backend object at 0xXXXXXXXX>`

If it errors, libusb is not found.

---

**Need Help?** Open an issue with the output of `diagnose_usb.py`
