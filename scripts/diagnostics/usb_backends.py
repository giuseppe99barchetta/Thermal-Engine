#!/usr/bin/env python3
"""Test different libusb backends."""

import usb.core
import usb.backend.libusb1
import usb.backend.libusb0
import usb.backend.openusb

print("=" * 60)
print("Testing different libusb backends")
print("=" * 60)

backends = [
    ("libusb1", usb.backend.libusb1.get_backend()),
    ("libusb0", usb.backend.libusb0.get_backend()),
    ("openusb", usb.backend.openusb.get_backend()),
]

print("\n[1] Checking available backends...")
for name, backend in backends:
    if backend is None:
        print(f"  {name}: NOT AVAILABLE")
    else:
        print(f"  {name}: AVAILABLE")

print("\n[2] Trying to find device with each backend...")
for name, backend in backends:
    if backend is None:
        continue

    print(f"\n  Testing {name}...")
    try:
        dev = usb.core.find(idVendor=0x87AD, idProduct=0x70DB, backend=backend)
        if dev is None:
            print(f"    Device not found")
            continue

        print(f"    Device found!")

        # Try to set configuration
        try:
            dev.set_configuration()
            print(f"    SUCCESS: Configuration set!")
            print(f"    *** {name} WORKS! ***")

            # Cleanup
            usb.util.dispose_resources(dev)
            break
        except Exception as e:
            print(f"    FAILED: {e}")
            try:
                usb.util.dispose_resources(dev)
            except:
                pass
    except Exception as e:
        print(f"    ERROR: {e}")

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)
