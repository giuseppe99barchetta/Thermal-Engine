# ✅ Experimental Device Support - Setup Complete

## Summary

I've successfully added **experimental support** for the **Thermalright FW 360 Ultra** (VID: 0x87AD, PID: 0x70DB) to Thermal-Engine.

**Current Status**: Code complete, but requires USB driver setup on your system.

---

## What's Been Done

### 1. ✅ Device Backend System
Created a flexible backend architecture ([device_backends.py](device_backends.py)) that supports multiple display types:
- **HIDBackend**: For existing HID displays (Thermalright Trofeo)
- **USBBulkBackend**: For USB bulk/interrupt displays (FW 360 Ultra)
- Automatic device detection and enumeration
- Graceful error handling

### 2. ✅ FW 360 Ultra Support
- Device definition with VID/PID 0x87AD:0x70DB
- USB endpoint enumeration
- Verbose logging for debugging
- Frame sending infrastructure (protocol unknown)

### 3. ✅ Integration
- Updated [main_window.py](main_window.py) to use new backend system
- Added device selection dialog for multiple devices
- Integrated console window for experimental device logs
- Backward compatible with existing Trofeo AIO support

### 4. ✅ Documentation
- [EXPERIMENTAL_DEVICES.md](EXPERIMENTAL_DEVICES.md) - Full technical documentation
- [EXPERIMENTAL_QUICKSTART.md](EXPERIMENTAL_QUICKSTART.md) - Quick start guide
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Implementation details
- [FIX_USB_WINDOWS.md](FIX_USB_WINDOWS.md) - USB driver setup guide
- [diagnose_usb.py](diagnose_usb.py) - Diagnostic tool

### 5. ✅ Dependencies
- Added pyusb to [requirements.txt](requirements.txt)
- Installed pyusb in your venv

---

## ⚠️ Current Issue: USB Backend Not Working

### Problem
When you try to connect, you get:
```
No device found, no supported display devices detected
```

When running `diagnose_usb.py`, you see:
```
[FAIL] No USB devices found at all!
```

### Root Cause
**pyusb on Windows requires a USB backend driver** (libusb) to access USB devices. Windows doesn't include this by default.

### Quick Fix

**Option 1: Install libusb-1.0.dll** (Recommended)

1. Download: https://github.com/libusb/libusb/releases/latest
   - Get `libusb-1.0.XX.7z`

2. Extract and copy `VS2019\MS64\dll\libusb-1.0.dll` to:
   - `C:\Windows\System32\libusb-1.0.dll`

3. Test:
   ```bash
   python diagnose_usb.py
   ```

**Option 2: Use Zadig** (Changes device driver)

1. Download: https://zadig.akeo.ie/
2. Run as Administrator
3. Options > List All Devices
4. Select your Thermalright device
5. Install WinUSB driver
6. Test with `python diagnose_usb.py`

⚠️ **Note**: This may prevent TR Control Center from working until you switch drivers back.

---

## Next Steps

### Step 1: Install USB Backend ⬅️ **START HERE**

Follow the guide in [FIX_USB_WINDOWS.md](FIX_USB_WINDOWS.md) to install libusb or WinUSB.

### Step 2: Verify Device Detection

Run the diagnostic:
```bash
python diagnose_usb.py
```

You should see:
```
[OK] pyusb is installed
[OK] hidapi is installed

Found X USB device(s):
  - VID: 0x87AD, PID: 0x70DB
    Manufacturer: ...
    Product: Thermalright...

[OK] FOUND Thermalright FW 360 Ultra!
```

### Step 3: Test Thermal-Engine Connection

1. **Close TR Control Center** completely

2. **Run Thermal-Engine**:
   ```bash
   python main.py
   ```

3. **Click Display > Connect**

4. **Select "Thermalright FW 360 Ultra [EXPERIMENTAL]"**

5. **Accept the experimental warning**
   - Console window will open automatically

6. **Check console output**:
   - Should show device information
   - Endpoint enumeration
   - Connection success
   - Frame send attempts

### Step 4: Understand What Works

✅ **Working**:
- Device detection
- USB connection
- Endpoint discovery
- Verbose logging
- Frame send attempts

❌ **Not Working**:
- **Display output** (LCD stays blank)
- This is **expected** - protocol is unknown

### Step 5: Protocol Reverse Engineering (Optional)

To make the display actually work, capture USB traffic from TR Control Center:

1. **Install Wireshark + USBPcap**
   - https://www.wireshark.org/

2. **Capture USB traffic**:
   - Start Wireshark capture on USB
   - Launch TR Control Center
   - Display something on LCD
   - Stop capture and save

3. **Analyze the capture**:
   - Look for initialization commands
   - Identify frame format
   - Find headers/magic bytes

4. **Update the code**:
   - Edit `device_backends.py`
   - Implement protocol in `USBBulkBackend.send_frame()`

5. **Test and document**:
   - Test with Thermal-Engine
   - Share findings in an issue/PR

---

## Files Created/Modified

### New Files
- `device_backends.py` - Backend system (650+ lines)
- `EXPERIMENTAL_DEVICES.md` - Full documentation
- `EXPERIMENTAL_QUICKSTART.md` - Quick start guide
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `FIX_USB_WINDOWS.md` - USB driver fix guide
- `SETUP_COMPLETE.md` - This file
- `diagnose_usb.py` - Diagnostic tool

### Modified Files
- `main_window.py` - Integrated backend system
- `requirements.txt` - Added pyusb
- `README.md` - Updated supported devices

---

## Expected Behavior

### When Working Correctly

**Device Detection**:
```
python diagnose_usb.py
[OK] FOUND Thermalright FW 360 Ultra!
```

**Thermal-Engine Connection**:
```
Display > Connect
> Thermalright FW 360 Ultra [EXPERIMENTAL]
> Warning dialog > Accept
> Console opens with:
  [INFO] Found device: Thermalright FW 360 Ultra
  [INFO] ✓ Selected OUT endpoint: 0xXX
  [INFO] Device ready (experimental mode)
```

**Frame Sending**:
```
[DEBUG] Attempting to send XXXXX bytes to endpoint 0xXX
[DEBUG] ✓ Wrote XXXXX bytes
```
(LCD will still be blank - protocol unknown)

### Troubleshooting

**"No devices found"**:
→ Install libusb backend (see [FIX_USB_WINDOWS.md](FIX_USB_WINDOWS.md))

**"Access denied"**:
→ Close TR Control Center
→ Try running as Administrator

**"Device not found" but diagnose_usb.py finds it**:
→ Restart Thermal-Engine
→ Check Settings > Show Console for errors

---

## Architecture Overview

```
User clicks "Connect"
    ↓
enumerate_available_devices()
    ├─ HID devices (hidapi)
    └─ USB devices (pyusb) ← Requires libusb!
    ↓
Device selection dialog
    ↓
create_backend(device_def)
    ├─ HIDBackend (Trofeo)
    └─ USBBulkBackend (FW 360) ← Experimental
    ↓
backend.connect()
    ├─ Open USB device
    ├─ Enumerate endpoints
    └─ Log device info
    ↓
send_frame_with_sensors()
    ├─ Render theme
    ├─ Convert to JPEG
    └─ backend.send_frame()
        ├─ HID: Known protocol
        └─ USB: Unknown (tries anyway)
```

---

## Support & Contributing

### Getting Help

1. Check [FIX_USB_WINDOWS.md](FIX_USB_WINDOWS.md) for USB issues
2. Check [EXPERIMENTAL_QUICKSTART.md](EXPERIMENTAL_QUICKSTART.md) for usage
3. Run `diagnose_usb.py` and share output
4. Check console (Settings > Show Console) for errors
5. Open an issue with diagnostic output

### Contributing

If you reverse-engineer the protocol:
1. Document what you found
2. Update `USBBulkBackend.send_frame()` in `device_backends.py`
3. Test thoroughly
4. Submit a PR with documentation

Even partial progress helps!

---

## Summary Checklist

- [x] Device backend system implemented
- [x] FW 360 Ultra device definition added
- [x] USB communication infrastructure
- [x] Verbose logging and error handling
- [x] Documentation and guides
- [x] pyusb dependency installed
- [ ] **USB backend driver installed** ← **YOU ARE HERE**
- [ ] Device detected by diagnose_usb.py
- [ ] Thermal-Engine connects to device
- [ ] Console shows USB communication
- [ ] Protocol reverse-engineered (future)
- [ ] Display output working (future)

---

## Quick Reference

**Diagnostic Tool**:
```bash
python diagnose_usb.py
```

**Run Thermal-Engine**:
```bash
python main.py
```

**Install libusb**:
See [FIX_USB_WINDOWS.md](FIX_USB_WINDOWS.md)

**Show Console**:
Settings > Show Console (in Thermal-Engine)

**Check Device VID/PID**:
Device Manager > Properties > Details > Hardware IDs

---

## What This Enables

### Now
- Framework for adding new display devices
- Detection of FW 360 Ultra
- Verbose logging for debugging
- Safe experimental device support

### Future (After Protocol RE)
- Full FW 360 Ultra display output
- Other USB-based AIO displays
- Network displays (TCP/IP backend)
- Serial displays (UART backend)

---

**Status**: ✅ Code complete, awaiting USB backend installation

**Next Step**: Install libusb per [FIX_USB_WINDOWS.md](FIX_USB_WINDOWS.md)

**Questions?** Check the documentation or open an issue!

Good luck! 🚀
