"""
USB Device Diagnostic Tool
Checks if Thermalright FW 360 Ultra is detected by the system.
"""

import sys
import io

# Force UTF-8 output to avoid encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("USB Device Diagnostic Tool")
print("=" * 60)
print()

# Check pyusb installation
print("[1/4] Checking pyusb installation...")
try:
    import usb.core
    import usb.util
    print("  [OK] pyusb is installed")
except ImportError as e:
    print("  [FAIL] pyusb is NOT installed")
    print(f"  Error: {e}")
    print()
    print("  Please install pyusb:")
    print("    pip install pyusb")
    sys.exit(1)

print()

# Check hidapi installation
print("[2/4] Checking hidapi installation...")
try:
    import hid
    print("  [OK] hidapi is installed")
except ImportError as e:
    print("  [FAIL] hidapi is NOT installed")
    print(f"  Error: {e}")
    print()
    print("  Please install hidapi:")
    print("    pip install hidapi")
    sys.exit(1)

print()

# List all USB devices
print("[3/4] Enumerating ALL USB devices...")
print()

try:
    devices = list(usb.core.find(find_all=True))
    if not devices:
        print("  [FAIL] No USB devices found at all!")
        print("  This is unusual - check USB drivers")
    else:
        print(f"  Found {len(devices)} USB device(s):")
        print()
        for dev in devices:
            vid = dev.idVendor
            pid = dev.idProduct
            try:
                manufacturer = usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else "N/A"
            except:
                manufacturer = "(unable to read)"
            try:
                product = usb.util.get_string(dev, dev.iProduct) if dev.iProduct else "N/A"
            except:
                product = "(unable to read)"

            print(f"  - VID: 0x{vid:04X}, PID: 0x{pid:04X}")
            print(f"    Manufacturer: {manufacturer}")
            print(f"    Product: {product}")
            print()
except Exception as e:
    print(f"  [FAIL] Error enumerating USB devices: {e}")
    print()
    print("  On Windows, this might mean:")
    print("  1. libusb driver not installed")
    print("  2. Insufficient permissions")
    print("  3. WinUSB driver not assigned to device")

print()

# Check for Thermalright FW 360 Ultra specifically
print("[4/4] Looking for Thermalright FW 360 Ultra (87AD:70DB)...")
print()

try:
    target_device = usb.core.find(idVendor=0x87AD, idProduct=0x70DB)

    if target_device is None:
        print("  [FAIL] Thermalright FW 360 Ultra NOT FOUND")
        print()
        print("  Possible reasons:")
        print("  1. Device is not connected via USB")
        print("  2. Device is in use by TR Control Center (close it)")
        print("  3. Wrong VID/PID (check Device Manager)")
        print("  4. WinUSB driver not installed for this device")
        print()
        print("  To check VID/PID in Device Manager:")
        print("  1. Open Device Manager (devmgmt.msc)")
        print("  2. Find your AIO device (might be under 'Universal Serial Bus devices')")
        print("  3. Right-click > Properties > Details")
        print("  4. Select 'Hardware IDs' from dropdown")
        print("  5. Look for VID_XXXX&PID_YYYY")
    else:
        print("  [OK] FOUND Thermalright FW 360 Ultra!")
        print()
        print(f"  Bus: {target_device.bus}")
        print(f"  Address: {target_device.address}")
        print(f"  VID: 0x{target_device.idVendor:04X}")
        print(f"  PID: 0x{target_device.idProduct:04X}")
        print(f"  USB Version: {target_device.bcdUSB:04X}")
        print(f"  Device Class: 0x{target_device.bDeviceClass:02X}")

        try:
            manufacturer = usb.util.get_string(target_device, target_device.iManufacturer)
            print(f"  Manufacturer: {manufacturer}")
        except:
            print("  Manufacturer: (unable to read)")

        try:
            product = usb.util.get_string(target_device, target_device.iProduct)
            print(f"  Product: {product}")
        except:
            print("  Product: (unable to read)")

        try:
            serial = usb.util.get_string(target_device, target_device.iSerialNumber)
            print(f"  Serial: {serial}")
        except:
            print("  Serial: (unable to read)")

        print()
        print("  Device is detected! Thermal-Engine should be able to see it.")

except Exception as e:
    print(f"  [FAIL] Error checking for device: {e}")
    print()
    print("  This might indicate:")
    print("  1. Device driver issue")
    print("  2. Device is locked by another application")
    print("  3. Insufficient permissions")

print()

# Check for Trofeo AIO (existing support)
print("[BONUS] Looking for Thermalright Trofeo AIO (0416:5302)...")
print()

try:
    trofeo_device = usb.core.find(idVendor=0x0416, idProduct=0x5302)

    if trofeo_device is None:
        print("  [FAIL] Trofeo AIO not found (this is OK if you don't have one)")
    else:
        print("  [OK] FOUND Thermalright Trofeo AIO!")
        print(f"  Bus: {trofeo_device.bus}, Address: {trofeo_device.address}")
        print("  This device is fully supported.")
except Exception as e:
    print(f"  Error: {e}")

print()
print("=" * 60)
print("Diagnostic Complete")
print("=" * 60)
print()

# Check HID devices too
print("[BONUS] Checking HID devices...")
print()

try:
    import hid
    hid_devices = hid.enumerate()

    fw360_hid = [d for d in hid_devices if d['vendor_id'] == 0x87AD and d['product_id'] == 0x70DB]
    trofeo_hid = [d for d in hid_devices if d['vendor_id'] == 0x0416 and d['product_id'] == 0x5302]

    if fw360_hid:
        print(f"  [OK] FW 360 Ultra found as HID device!")
        for d in fw360_hid:
            print(f"    Path: {d['path']}")
            print(f"    Manufacturer: {d.get('manufacturer_string', 'N/A')}")
            print(f"    Product: {d.get('product_string', 'N/A')}")
        print("  Note: This device should use USB backend, not HID")
    else:
        print("  [FAIL] FW 360 Ultra not found as HID device (expected)")

    if trofeo_hid:
        print(f"  [OK] Trofeo AIO found as HID device!")
        print("  This device is fully supported via HID.")
    else:
        print("  [FAIL] Trofeo AIO not found as HID device")

except Exception as e:
    print(f"  Error checking HID devices: {e}")

print()
print("If your device was not found:")
print("1. Make sure it's connected via USB")
print("2. Close TR Control Center completely")
print("3. Check Device Manager for VID/PID")
print("4. Try a different USB port")
print("5. Check if WinUSB driver is assigned (use Zadig if needed)")
print()
print("If your device WAS found but Thermal-Engine doesn't see it:")
print("1. Make sure pyusb is installed: pip install pyusb")
print("2. Restart Thermal-Engine")
print("3. Check console output (Settings > Show Console)")
print("4. Open an issue with the output from this diagnostic")
