#!/usr/bin/env python3
"""Test script to isolate USB device opening issue."""

import usb.core
import usb.util

print("=" * 60)
print("Testing USB Device Access")
print("=" * 60)

# Find device
print("\n[1] Finding device 87AD:70DB...")
dev = usb.core.find(idVendor=0x87AD, idProduct=0x70DB)

if dev is None:
    print("ERROR: Device not found!")
    exit(1)

print(f"OK: Found device at Bus {dev.bus}, Address {dev.address}")

# Try to read device info
print("\n[2] Reading device information...")
try:
    print(f"  VID:PID: {dev.idVendor:04X}:{dev.idProduct:04X}")
    print(f"  USB Version: {dev.bcdUSB:04X}")
    print(f"  Device Version: {dev.bcdDevice:04X}")
    print(f"  Class: {dev.bDeviceClass:02X}")
    print(f"  Max Packet Size: {dev.bMaxPacketSize0}")
except Exception as e:
    print(f"ERROR reading device info: {e}")

# Try to read string descriptors
print("\n[3] Trying to read string descriptors...")
try:
    mfg = usb.util.get_string(dev, dev.iManufacturer)
    print(f"  Manufacturer: {mfg}")
except Exception as e:
    print(f"  Manufacturer: FAILED - {e}")

try:
    prod = usb.util.get_string(dev, dev.iProduct)
    print(f"  Product: {prod}")
except Exception as e:
    print(f"  Product: FAILED - {e}")

# Try to set configuration
print("\n[4] Attempting to set configuration...")
try:
    dev.set_configuration()
    print("  OK: Configuration set successfully!")
except Exception as e:
    print(f"  ERROR: {e}")
    print(f"  This is the problem - set_configuration() is failing!")

    # Try alternative approach
    print("\n[5] Trying alternative approach: get configuration first...")
    try:
        cfg = dev.get_active_configuration()
        print(f"  OK: Got active configuration: {cfg}")
    except Exception as e:
        print(f"  ERROR: {e}")
        print("\n" + "=" * 60)
        print("DIAGNOSIS:")
        print("=" * 60)
        print("The device is found but cannot be opened.")
        print("This indicates a driver or permissions issue.")
        print("\nPossible causes:")
        print("1. WinUSB driver not properly installed")
        print("2. Another program has exclusive access")
        print("3. Windows is blocking libusb access")
        print("\nSolutions to try:")
        print("1. Reinstall WinUSB driver using Zadig")
        print("2. Try a different USB port")
        print("3. Reboot and try immediately")
        exit(1)

# Try to get configuration
print("\n[6] Getting active configuration...")
try:
    cfg = dev.get_active_configuration()
    print(f"  OK: Active configuration: {cfg}")

    # Enumerate interfaces
    print("\n[7] Enumerating interfaces...")
    for intf in cfg:
        print(f"  Interface {intf.bInterfaceNumber}:")
        print(f"    Class: {intf.bInterfaceClass:02X}")

        # Enumerate endpoints
        for ep in intf:
            direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
            ep_type = usb.util.endpoint_type(ep.bmAttributes)
            type_names = {
                usb.util.ENDPOINT_TYPE_CTRL: "CONTROL",
                usb.util.ENDPOINT_TYPE_BULK: "BULK",
                usb.util.ENDPOINT_TYPE_INTR: "INTERRUPT",
                usb.util.ENDPOINT_TYPE_ISO: "ISOCHRONOUS"
            }
            print(f"    Endpoint 0x{ep.bEndpointAddress:02X}: {direction} {type_names.get(ep_type, 'UNKNOWN')}")

    print("\n" + "=" * 60)
    print("SUCCESS: Device is fully accessible!")
    print("=" * 60)

except Exception as e:
    print(f"  ERROR: {e}")

# Cleanup
print("\n[8] Cleaning up...")
try:
    usb.util.dispose_resources(dev)
    print("  OK: Resources disposed")
except Exception as e:
    print(f"  WARNING: {e}")

print("\nTest complete.")
