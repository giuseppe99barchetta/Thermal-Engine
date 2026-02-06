"""
Device backend abstraction for LCD AIO displays.

Supports multiple display types with different communication protocols:
- HID-based displays (e.g., Thermalright Trofeo)
- Experimental USB bulk/interrupt displays (e.g., Thermalright FW 360 Ultra)
"""

import sys
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Device Definitions
# ============================================================================

class DeviceDefinition:
    """Defines a supported display device with its communication parameters."""

    def __init__(self,
                 name: str,
                 vendor_id: int,
                 product_id: int,
                 backend_type: str,
                 width: int = 1280,
                 height: int = 480,
                 experimental: bool = False,
                 **kwargs):
        """
        Args:
            name: Human-readable device name
            vendor_id: USB Vendor ID
            product_id: USB Product ID
            backend_type: Backend class to use ('hid', 'usb_bulk', etc.)
            width: Display width in pixels
            height: Display height in pixels
            experimental: Whether this device support is experimental
            **kwargs: Additional device-specific parameters
        """
        self.name = name
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.backend_type = backend_type
        self.width = width
        self.height = height
        self.experimental = experimental
        self.extra_params = kwargs

    def __repr__(self):
        exp = " [EXPERIMENTAL]" if self.experimental else ""
        return f"{self.name} ({self.vendor_id:04X}:{self.product_id:04X}){exp}"


# Supported device definitions
SUPPORTED_DEVICES = [
    # Thermalright Trofeo AIO LCD (HID-based, fully supported)
    DeviceDefinition(
        name="Thermalright Trofeo AIO",
        vendor_id=0x0416,
        product_id=0x5302,
        backend_type="hid",
        experimental=False,
        init_sequence=[0xDA, 0xDB, 0xDC, 0xDD, 0x00],  # Known init bytes
    ),

    # Thermalright FW 360 Ultra (USB bulk, ChiZhu Tech USBDISPLAY)
    DeviceDefinition(
        name="Thermalright FW 360 Ultra",
        vendor_id=0x87AD,
        product_id=0x70DB,
        backend_type="usb_bulk",
        width=480,   # Square display (480x480)
        height=480,  # Square display
        experimental=False,  # ✅ FULLY WORKING! Protocol reverse-engineered!
        # Protocol: ChiZhu Tech USBDISPLAY (reverse-engineered from USB capture)
        # Init: Magic (0x12345678) + Command (0x00) + padding + flag (0x01)
        # Frame: Magic + Command (0x02) + Height x2 + padding + Command + JPEG size + JPEG data
        endpoint_out=None,  # Auto-discovered (0x01)
        endpoint_in=None,   # Auto-discovered (0x81)
    ),
]


def find_device_definition(vendor_id: int, product_id: int) -> Optional[DeviceDefinition]:
    """Find a device definition by VID/PID."""
    for device in SUPPORTED_DEVICES:
        if device.vendor_id == vendor_id and device.product_id == product_id:
            return device
    return None


# ============================================================================
# Backend Base Class
# ============================================================================

class DisplayBackend(ABC):
    """Abstract base class for display device backends."""

    def __init__(self, device_def: DeviceDefinition):
        self.device_def = device_def
        self.connected = False
        logger.info(f"Initializing backend for {device_def.name}")

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the device. Returns True on success."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the device."""
        pass

    @abstractmethod
    def send_frame(self, frame_data: bytes) -> bool:
        """Send a frame to the device. Returns True on success."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if device is still connected."""
        pass


# ============================================================================
# HID Backend (for existing devices)
# ============================================================================

class HIDBackend(DisplayBackend):
    """Backend for HID-based LCD displays (e.g., Thermalright Trofeo)."""

    def __init__(self, device_def: DeviceDefinition):
        super().__init__(device_def)
        self.device = None
        self.hid = None

    def connect(self) -> bool:
        """Connect to HID device."""
        try:
            import hid
            self.hid = hid
        except ImportError:
            logger.error("hidapi not installed. Run: pip install hidapi")
            return False

        try:
            self.device = hid.device()
            self.device.open(self.device_def.vendor_id, self.device_def.product_id)

            # Send initialization sequence if defined
            init_seq = self.device_def.extra_params.get('init_sequence')
            if init_seq:
                init = bytearray(512)
                for i, byte in enumerate(init_seq):
                    init[i] = byte
                if len(init_seq) > 4:
                    init[12] = 0x01  # Known init flag for Trofeo
                self.device.write(bytes([0x00]) + bytes(init))
                logger.info(f"Sent initialization sequence to {self.device_def.name}")

            self.connected = True
            logger.info(f"Successfully connected to {self.device_def.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to HID device: {e}")
            self.device = None
            return False

    def disconnect(self):
        """Disconnect from HID device."""
        if self.device:
            try:
                self.device.close()
                logger.info(f"Disconnected from {self.device_def.name}")
            except Exception as e:
                logger.error(f"Error closing HID device: {e}")
            finally:
                self.device = None
                self.connected = False

    def send_frame(self, frame_data: bytes) -> bool:
        """Send frame via HID."""
        if not self.device:
            return False

        try:
            # HID write typically requires report ID prefix
            self.device.write(bytes([0x00]) + frame_data)
            return True
        except Exception as e:
            logger.error(f"HID write error: {e}")
            self.connected = False
            return False

    def is_connected(self) -> bool:
        """Check HID connection status."""
        return self.connected and self.device is not None


# ============================================================================
# Experimental USB Bulk Backend
# ============================================================================

class USBBulkBackend(DisplayBackend):
    """
    EXPERIMENTAL backend for USB bulk transfer displays.

    This backend is designed for devices using WinUSB/libusb with bulk or
    interrupt endpoints rather than HID. The protocol is discovered through
    experimentation.

    Supports:
    - Thermalright FW 360 Ultra (0x87AD:0x70DB)
    """

    def __init__(self, device_def: DeviceDefinition):
        super().__init__(device_def)
        self.device = None
        self.usb = None
        self.endpoint_out = None
        self.endpoint_in = None
        self.verbose = True  # Always verbose for experimental devices

        if device_def.experimental:
            logger.warning(f"⚠️  {device_def.name} support is EXPERIMENTAL")
            logger.warning("   Protocol may be incomplete or incorrect")
            logger.warning("   Expect errors and missing functionality")

    def connect(self) -> bool:
        """Connect to USB device via pyusb."""
        try:
            import usb.core
            import usb.util
            self.usb = usb
        except ImportError:
            logger.error("pyusb not installed. Run: pip install pyusb")
            return False

        try:
            # Find device
            logger.info(f"Searching for device {self.device_def.vendor_id:04X}:{self.device_def.product_id:04X}")
            self.device = usb.core.find(
                idVendor=self.device_def.vendor_id,
                idProduct=self.device_def.product_id
            )

            if self.device is None:
                logger.error(f"Device not found: {self.device_def.name}")
                logger.error("Check USB connection and ensure device is not in use by other software")
                return False

            logger.info(f"✓ Found device: {self.device_def.name}")

            # Log device information
            self._log_device_info()

            # Try to set configuration
            try:
                if self.device.is_kernel_driver_active(0):
                    logger.info("Detaching kernel driver...")
                    self.device.detach_kernel_driver(0)
            except (NotImplementedError, usb.core.USBError):
                pass  # Windows doesn't need kernel driver detach

            try:
                self.device.set_configuration()
                logger.info("✓ Configuration set")
            except usb.core.USBError as e:
                logger.warning(f"Could not set configuration: {e}")
                # Continue anyway - device might already be configured

            # Enumerate endpoints
            self._enumerate_endpoints()

            if not self.endpoint_out:
                logger.warning("⚠️  No OUT endpoint found - device may not accept data")
                logger.warning("   Display output will likely not work")

            self.connected = True
            logger.info("✓ Device ready (experimental mode)")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Failed to connect to USB device: {e}", exc_info=True)
            self.device = None
            return False

    def _log_device_info(self):
        """Log detailed device information for debugging."""
        logger.info("=" * 60)
        logger.info("DEVICE INFORMATION")
        logger.info("=" * 60)
        logger.info(f"Device: {self.device_def.name}")
        logger.info(f"VID:PID: {self.device.idVendor:04X}:{self.device.idProduct:04X}")
        logger.info(f"Bus: {self.device.bus}, Address: {self.device.address}")
        logger.info(f"USB Version: {self.device.bcdUSB:04X}")
        logger.info(f"Device Version: {self.device.bcdDevice:04X}")

        try:
            logger.info(f"Manufacturer: {usb.util.get_string(self.device, self.device.iManufacturer)}")
        except:
            logger.info("Manufacturer: (unavailable)")

        try:
            logger.info(f"Product: {usb.util.get_string(self.device, self.device.iProduct)}")
        except:
            logger.info("Product: (unavailable)")

        try:
            logger.info(f"Serial: {usb.util.get_string(self.device, self.device.iSerialNumber)}")
        except:
            logger.info("Serial: (unavailable)")

        logger.info(f"Class: {self.device.bDeviceClass:02X} (Vendor Specific)")
        logger.info(f"Max Packet Size: {self.device.bMaxPacketSize0}")
        logger.info("-" * 60)

    def _enumerate_endpoints(self):
        """Enumerate and log all endpoints."""
        logger.info("ENDPOINT ENUMERATION")
        logger.info("-" * 60)

        cfg = self.device.get_active_configuration()

        for intf in cfg:
            logger.info(f"Interface {intf.bInterfaceNumber}:")
            logger.info(f"  Class: {intf.bInterfaceClass:02X}")
            logger.info(f"  SubClass: {intf.bInterfaceSubClass:02X}")
            logger.info(f"  Protocol: {intf.bInterfaceProtocol:02X}")

            for ep in intf:
                ep_addr = ep.bEndpointAddress
                ep_type = self.usb.util.endpoint_type(ep.bmAttributes)
                direction = "IN" if self.usb.util.endpoint_direction(ep_addr) == self.usb.util.ENDPOINT_IN else "OUT"

                type_names = {
                    self.usb.util.ENDPOINT_TYPE_CTRL: "CONTROL",
                    self.usb.util.ENDPOINT_TYPE_BULK: "BULK",
                    self.usb.util.ENDPOINT_TYPE_INTR: "INTERRUPT",
                    self.usb.util.ENDPOINT_TYPE_ISO: "ISOCHRONOUS"
                }
                type_name = type_names.get(ep_type, "UNKNOWN")

                logger.info(f"  Endpoint 0x{ep_addr:02X}: {direction} {type_name}")
                logger.info(f"    Max Packet Size: {ep.wMaxPacketSize}")
                logger.info(f"    Interval: {ep.bInterval}")

                # Store first OUT endpoint (prefer BULK)
                if direction == "OUT":
                    if self.endpoint_out is None or ep_type == self.usb.util.ENDPOINT_TYPE_BULK:
                        self.endpoint_out = ep_addr
                        logger.info(f"    >>> Will use this for frame output")

                # Store first IN endpoint
                if direction == "IN" and self.endpoint_in is None:
                    self.endpoint_in = ep_addr
                    logger.info(f"    >>> Will use this for input (if needed)")

        logger.info("-" * 60)

        if self.endpoint_out:
            logger.info(f"✓ Selected OUT endpoint: 0x{self.endpoint_out:02X}")
        else:
            logger.warning("⚠️  No OUT endpoint found")

        if self.endpoint_in:
            logger.info(f"✓ Selected IN endpoint: 0x{self.endpoint_in:02X}")

        # Send initialization command for ChiZhu Tech USBDISPLAY
        logger.info("Sending device initialization command...")
        try:
            init_cmd = bytearray(64)
            init_cmd[0:4] = bytes([0x12, 0x34, 0x56, 0x78])  # Magic
            init_cmd[4:8] = (0x00).to_bytes(4, 'little')  # Command 0x00 = INIT
            # Padding with zeros (already initialized)
            init_cmd[56:60] = (0x01).to_bytes(4, 'little')  # Flag at end

            bytes_written = self.device.write(self.endpoint_out, bytes(init_cmd), timeout=1000)
            logger.info(f"✓ Initialization command sent ({bytes_written} bytes)")

            # Small delay for device to process init
            import time
            time.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to send init command: {e}")
            raise

    def disconnect(self):
        """Disconnect from USB device."""
        if self.device:
            try:
                # Dispose resources (this releases interfaces automatically)
                self.usb.util.dispose_resources(self.device)
                logger.info(f"Disconnected from {self.device_def.name}")
            except Exception as e:
                logger.error(f"Error disconnecting USB device: {e}")
            finally:
                self.device = None
                self.connected = False
                self.endpoint_out = None
                self.endpoint_in = None

    def send_frame(self, frame_data: bytes) -> bool:
        """
        Send frame via USB bulk transfer.

        Protocol discovered from USB capture:
        - Magic bytes: 0x12345678
        - Command: 0x02 (display frame)
        - Dimensions: width, height (little-endian)
        - JPEG size
        - JPEG data
        """
        if not self.device or not self.endpoint_out:
            return False

        try:
            # ChiZhu Tech USBDISPLAY protocol (from USB capture analysis)
            # Header structure: EXACTLY 64 bytes total
            # 0x00-0x03: Magic = 0x12345678
            # 0x04-0x07: Command = 0x02 (display frame)
            # 0x08-0x0B: Height = 480 (0x01E0)
            # 0x0C-0x0F: Height again = 480 (0x01E0) [confirmed from capture]
            # 0x10-0x37: Padding (zeros)
            # 0x38-0x3B: Command again = 0x02
            # 0x3C-0x3F: JPEG size (4 bytes)
            # After 64 byte header: JPEG data immediately follows

            header = bytearray(64)  # Exactly 64 bytes

            # Magic bytes
            header[0:4] = bytes([0x12, 0x34, 0x56, 0x78])

            # Command (0x02 = display frame)
            header[4:8] = (0x02).to_bytes(4, 'little')

            # Dimensions - Height appears TWICE in the capture
            header[8:12] = (self.device_def.height).to_bytes(4, 'little')  # Height (480)
            header[12:16] = (self.device_def.height).to_bytes(4, 'little')  # Height again (480)

            # Padding 0x10-0x37 (already zeros)

            # Command again at offset 0x38 (56)
            header[56:60] = (0x02).to_bytes(4, 'little')

            # JPEG size at offset 0x3C (60)
            header[60:64] = len(frame_data).to_bytes(4, 'little')

            # Combine header + JPEG data
            full_frame = bytes(header) + frame_data

            if self.verbose:
                logger.info(f"Sending frame: {len(frame_data)} bytes JPEG + {len(header)} bytes header = {len(full_frame)} total")
                logger.debug(f"Header: {header[:20].hex()}...")

            # Send complete frame in one bulk transfer
            bytes_written = self.device.write(self.endpoint_out, full_frame, timeout=5000)

            if self.verbose:
                logger.info(f"✓ Wrote {bytes_written} bytes to display")

            return True

        except self.usb.core.USBError as e:
            logger.error(f"USB write error: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error during frame send: {e}")
            import traceback
            traceback.print_exc()
            return False

    def is_connected(self) -> bool:
        """Check USB connection status."""
        if not self.device:
            return False

        try:
            # Try to read device descriptor to check if still connected
            _ = self.device.idVendor
            return True
        except:
            return False


# ============================================================================
# Backend Factory
# ============================================================================

def create_backend(device_def: DeviceDefinition) -> Optional[DisplayBackend]:
    """Create appropriate backend for a device definition."""

    backend_map = {
        'hid': HIDBackend,
        'usb_bulk': USBBulkBackend,
    }

    backend_class = backend_map.get(device_def.backend_type)
    if not backend_class:
        logger.error(f"Unknown backend type: {device_def.backend_type}")
        return None

    return backend_class(device_def)


def enumerate_available_devices() -> List[DeviceDefinition]:
    """
    Enumerate all connected devices that match supported definitions.

    Returns list of DeviceDefinition objects for detected devices.
    """
    available = []

    # Try HID devices
    try:
        import hid
        hid_devices = hid.enumerate()

        for hid_dev in hid_devices:
            vid = hid_dev['vendor_id']
            pid = hid_dev['product_id']
            device_def = find_device_definition(vid, pid)
            if device_def and device_def.backend_type == 'hid':
                if device_def not in available:
                    available.append(device_def)
                    logger.info(f"Found HID device: {device_def.name}")
    except ImportError:
        logger.debug("hidapi not available for enumeration")
    except Exception as e:
        logger.debug(f"HID enumeration error: {e}")

    # Try USB devices
    try:
        import usb.core

        for device_def in SUPPORTED_DEVICES:
            if device_def.backend_type == 'usb_bulk':
                dev = usb.core.find(
                    idVendor=device_def.vendor_id,
                    idProduct=device_def.product_id
                )
                if dev:
                    if device_def not in available:
                        available.append(device_def)
                        logger.info(f"Found USB device: {device_def.name}")
    except ImportError:
        logger.debug("pyusb not available for enumeration")
    except Exception as e:
        logger.debug(f"USB enumeration error: {e}")

    return available
