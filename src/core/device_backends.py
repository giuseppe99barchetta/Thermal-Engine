"""
Device backend abstraction for LCD AIO displays.

Supports multiple display types with different communication protocols:
- HID-based displays (e.g., Thermalright Trofeo)
- Experimental USB bulk/interrupt displays (e.g., Thermalright FW 360 Ultra)
"""

import copy
import logging
import re
import sys
from abc import ABC, abstractmethod
from typing import Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Resolution profiles reported by the PM byte in the 87AD:70DB handshake.
# Unknown firmware safely retains the configured/manual fallback size.
BULK_PM_DISPLAY_SIZES = {
    5: (320, 240),
    7: (640, 480),    # Thermalright Stream Vision 360
    9: (854, 480),
    10: (960, 540),
    11: (854, 480),
    12: (800, 480),
    32: (320, 320),
    64: (1600, 720),
    65: (1920, 462),
}


def get_bulk_display_size(handshake_response):
    """Resolve a known panel size from a ChiZhu USB handshake response."""
    if handshake_response is None or len(handshake_response) < 37:
        return None
    return BULK_PM_DISPLAY_SIZES.get(int(handshake_response[24]))


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

    # Thermalright WinUSB panels share this VID:PID across several models.
    # The exact panel size can be selected in Display > Screen Size.
    DeviceDefinition(
        name="Thermalright WinUSB Display (FW / Stream Vision)",
        vendor_id=0x87AD,
        product_id=0x70DB,
        backend_type="usb_bulk",
        width=480,
        height=480,
        experimental=False,  # ✅ FULLY WORKING! Protocol reverse-engineered!
        # Protocol: ChiZhu Tech USBDISPLAY (reverse-engineered from USB capture)
        # Init: Magic (0x12345678) + Command (0x00) + padding + flag (0x01)
        # Frame: Magic + Command (0x02) + Height x2 + padding + Command + JPEG size + JPEG data
        endpoint_out=None,  # Auto-discovered (0x01)
        endpoint_in=None,   # Auto-discovered (0x81)
    ),

    # Thermalright FW 360 (USB bulk, ChiZhu Tech USBDISPLAY, same VID:PID as Trofeo)
    DeviceDefinition(
        name="Thermalright FW 360",
        vendor_id=0x0416,
        product_id=0x5302,
        backend_type="usb_bulk",
        width=480,   # Square display (480x480)
        height=480,  # Square display
        experimental=False,
        # Protocol: ChiZhu Tech USBDISPLAY (same as FW 360 Ultra)
        # Shares VID:PID with Trofeo AIO - select this device if you have an FW 360
        endpoint_out=None,  # Auto-discovered
        endpoint_in=None,   # Auto-discovered
    ),
]


def find_device_definition(
    vendor_id: int,
    product_id: int,
    backend_type: Optional[str] = None,
) -> Optional[DeviceDefinition]:
    """Find a device definition by VID/PID and, when known, transport."""
    for device in SUPPORTED_DEVICES:
        if (
            device.vendor_id == vendor_id
            and device.product_id == product_id
            and (backend_type is None or device.backend_type == backend_type)
        ):
            return device
    return None


def _has_bulk_out_endpoint(device, usb_util) -> bool:
    """Return whether a USB device exposes the bulk OUT transport we require."""
    try:
        for configuration in device:
            for interface in configuration:
                for endpoint in interface:
                    if (
                        usb_util.endpoint_direction(endpoint.bEndpointAddress)
                        == usb_util.ENDPOINT_OUT
                        and usb_util.endpoint_type(endpoint.bmAttributes)
                        == usb_util.ENDPOINT_TYPE_BULK
                    ):
                        return True
    except Exception:
        return False
    return False


class DeviceIOError(IOError):
    """Frame could not reach the display: the device is gone or not responding."""


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
            path = self.device_def.extra_params.get("path")
            if path:  # one specific physical device (several of the same model may be connected)
                self.device.open_path(path)
            else:
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
            if sys.platform.startswith("linux"):
                logger.error("Linux tip: verify hidraw access and udev rules for device VID:PID")
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
            payload = bytes([0x00]) + frame_data
            written = self.device.write(payload)
            if written != len(payload):
                raise IOError(f"Short HID write: {written}/{len(payload)} bytes")
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

    # Class-level cache for found USB devices to avoid repeated slow enumeration
    # Key: (vendor_id, product_id), Value: usb.core.Device
    _device_cache = {}

    def __init__(self, device_def: DeviceDefinition):
        super().__init__(device_def)
        self.device = None
        self.usb = None
        self.endpoint_out = None
        self.endpoint_in = None
        self.verbose = False

        if device_def.experimental:
            logger.warning(f"⚠️  {device_def.name} support is EXPERIMENTAL")
            logger.warning("   Protocol may be incomplete or incorrect")
            logger.warning("   Expect errors and missing functionality")

    def _cache_key(self):
        """(vid, pid) for the classic single device; plus (bus, address) when a specific one was enumerated."""
        address = self.device_def.extra_params.get("usb_address")
        base = (self.device_def.vendor_id, self.device_def.product_id)
        return base + tuple(address) if address else base

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
            # Check cache first to avoid slow enumeration
            cache_key = self._cache_key()
            self.device = self._device_cache.get(cache_key)

            if self.device:
                logger.info(f"Using cached device: {self.device_def.name}")
            else:
                # Find device
                logger.info(f"Searching for device {self.device_def.vendor_id:04X}:{self.device_def.product_id:04X}")
                address = self.device_def.extra_params.get("usb_address")
                if address:
                    self.device = usb.core.find(
                        idVendor=self.device_def.vendor_id, idProduct=self.device_def.product_id,
                        custom_match=lambda dev: (dev.bus, dev.address) == tuple(address))
                else:
                    self.device = usb.core.find(
                        idVendor=self.device_def.vendor_id,
                        idProduct=self.device_def.product_id
                    )

                if self.device:
                    self._device_cache[cache_key] = self.device

            if self.device is None:
                logger.error(f"Device not found: {self.device_def.name}")
                logger.error("Check USB connection and ensure device is not in use by other software")
                if sys.platform.startswith("linux"):
                    logger.error("Linux tip: verify udev permissions for raw USB access")
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
                # If set_configuration fails, the device might be stale
                logger.warning(f"Could not set configuration: {e}")
                if "Entity not found" in str(e) or "No such device" in str(e):
                    cache_key = self._cache_key()
                    if cache_key in self._device_cache:
                        del self._device_cache[cache_key]
                        logger.info("Removed stale device from cache")
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
            if sys.platform.startswith("linux"):
                logger.error("Linux tip: install udev rules or run with proper USB permissions")
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
            logger.info(f"Manufacturer: {self.usb.util.get_string(self.device, self.device.iManufacturer)}")
        except Exception:
            logger.info("Manufacturer: (unavailable)")

        try:
            logger.info(f"Product: {self.usb.util.get_string(self.device, self.device.iProduct)}")
        except Exception:
            logger.info("Product: (unavailable)")

        try:
            logger.info(f"Serial: {self.usb.util.get_string(self.device, self.device.iSerialNumber)}")
        except Exception:
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
                        logger.info("    >>> Will use this for frame output")

                # Store first IN endpoint
                if direction == "IN" and self.endpoint_in is None:
                    self.endpoint_in = ep_addr
                    logger.info("    >>> Will use this for input (if needed)")

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

            # Thermalright ships several panel resolutions behind the same
            # VID/PID. The handshake PM byte identifies known models such as
            # Stream Vision, while a user override remains authoritative.
            if self.endpoint_in:
                try:
                    response = self.device.read(
                        self.endpoint_in,
                        1024,
                        timeout=1000,
                    )
                    detected_size = get_bulk_display_size(response)
                    manual_override = self.device_def.extra_params.get(
                        "manual_size_override",
                        False,
                    )
                    if detected_size and not manual_override:
                        self.device_def.width, self.device_def.height = detected_size
                        logger.info(
                            "Detected panel dimensions from handshake: "
                            f"{detected_size[0]}x{detected_size[1]} "
                            f"(PM={int(response[24])})"
                        )
                    elif detected_size:
                        logger.info(
                            "Keeping manual display-size override instead of "
                            f"handshake profile {detected_size[0]}x{detected_size[1]}"
                        )
                    else:
                        logger.info(
                            "Unknown panel handshake profile; keeping configured "
                            f"size {self.device_def.width}x{self.device_def.height}"
                        )
                except Exception as e:
                    logger.info(
                        "Panel-size handshake unavailable; keeping configured "
                        f"size {self.device_def.width}x{self.device_def.height}: {e}"
                    )

            # Small delay for device to process init
            # Use QEventLoop if a Qt app is running to prevent UI freeze
            qt_app_running = False
            try:
                from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
                if QCoreApplication.instance() is not None:
                    loop = QEventLoop()
                    QTimer.singleShot(100, loop.quit)
                    loop.exec()
                    qt_app_running = True
            except ImportError:
                pass

            if not qt_app_running:
                import time
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to send init command: {e}")
            raise

    def disconnect(self):
        """Disconnect from USB device."""
        self._device_cache.pop(self._cache_key(), None)
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
            # 0x08-0x0B: Width
            # 0x0C-0x0F: Height
            # 0x10-0x37: Padding (zeros)
            # 0x38-0x3B: Command again = 0x02
            # 0x3C-0x3F: JPEG size (4 bytes)
            # After 64 byte header: JPEG data immediately follows

            header = bytearray(64)  # Exactly 64 bytes

            # Magic bytes
            header[0:4] = bytes([0x12, 0x34, 0x56, 0x78])

            # Command (0x02 = display frame)
            header[4:8] = (0x02).to_bytes(4, 'little')

            # Square-panel captures contained 480 in both fields, which hid the
            # fact that these are width and height. Non-square Stream Vision
            # panels require the real width in the first field.
            header[8:12] = self.device_def.width.to_bytes(4, "little")
            header[12:16] = self.device_def.height.to_bytes(4, "little")

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
            bytes_written = self.device.write(self.endpoint_out, full_frame, timeout=1000)

            if self.verbose:
                logger.info(f"✓ Wrote {bytes_written} bytes to display")

            if bytes_written != len(full_frame):
                raise IOError(f"Short USB write: {bytes_written}/{len(full_frame)} bytes")
            return True

        except self.usb.core.USBError as e:
            logger.error(f"USB write error: {e}")
            self.connected = False
            self._device_cache.pop(self._cache_key(), None)
            return False
        except Exception as e:
            logger.error(f"Unexpected error during frame send: {e}")
            self.connected = False
            self._device_cache.pop(self._cache_key(), None)
            return False

    def is_connected(self) -> bool:
        """Check USB connection status."""
        if not self.device:
            return False

        try:
            # Try to read device descriptor to check if still connected
            _ = self.device.idVendor
            return True
        except Exception:
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


def _instance(definition, identity, ambiguous=False, **params):
    device = copy.copy(definition)
    device.extra_params = {**definition.extra_params, **params, "identity": identity, "ambiguous": ambiguous}
    return device


def _hid_candidates(hid_devices, platform=None):
    """One candidate per physical HID device. Grouping never uses the serial, so equal serials stay visible."""
    platform = platform or sys.platform
    groups = {}
    for info in hid_devices:
        vid, pid = info.get("vendor_id"), info.get("product_id")
        definition = find_device_definition(vid, pid, backend_type="hid")
        if not definition:
            continue
        path = info.get("path") or b""
        text = path.decode("utf-8", "replace") if isinstance(path, bytes) else str(path)
        # Windows paths carry one &mi_xx (interface) / &colxx (collection) token per HID interface
        key = re.sub(r"&(mi_[0-9a-f]+|col[0-9a-f]+)", "", text, flags=re.IGNORECASE).lower() if platform == "win32" else text
        groups.setdefault((vid, pid, key), (definition, []))[1].append(info)
    models = {}
    for (vid, pid, key), (definition, interfaces) in groups.items():
        serial = next((str(info.get("serial_number")) for info in interfaces if info.get("serial_number")), "")
        first = min(interfaces, key=lambda info: info.get("interface_number", 0) if info.get("interface_number", -1) >= 0 else 1 << 16)
        models.setdefault((vid, pid), (definition, []))[1].append((key, serial, first.get("path")))
    candidates = []
    for (vid, pid), (definition, found) in models.items():
        prefix = f"hid:{vid:04x}:{pid:04x}:"
        if len(found) == 1:
            key, serial, _ = found[0]
            # A single device opens exactly as before (by VID/PID): no path, so no wrong-interface risk
            candidates.append(_instance(definition, prefix + (f"sn:{serial}" if serial else f"path:{key}")))
        elif all(serial for _, serial, _ in found) and len({serial for _, serial, _ in found}) == len(found):
            # Several devices with distinct serials: each one is addressed by its own path
            candidates += [_instance(definition, prefix + f"sn:{serial}", path=path) for _, serial, path in found]
        else:
            # Missing or repeated serials: interfaces of one device and several devices cannot be told
            # apart (a repeated serial may be one device's interfaces or two devices); one entry, opened as
            # before, usable as the main display but never saved as a secondary output
            candidates.append(_instance(definition, prefix + "model", True))
    return candidates


def _usb_candidates(usb_core, usb_util):
    candidates = []
    for definition in SUPPORTED_DEVICES:
        if definition.backend_type != "usb_bulk":
            continue
        for dev in usb_core.find(find_all=True, idVendor=definition.vendor_id, idProduct=definition.product_id) or []:
            if not _has_bulk_out_endpoint(dev, usb_util):
                continue
            serial = None
            try:
                serial = usb_util.get_string(dev, dev.iSerialNumber) if getattr(dev, "iSerialNumber", 0) else None
            except Exception:
                serial = None  # reading strings can need access rights; fall back to the port
            ports = getattr(dev, "port_numbers", None)
            prefix = f"usb:{definition.vendor_id:04x}:{definition.product_id:04x}:"
            if serial:
                identity, complete = prefix + f"sn:{serial}", True
            elif ports:
                identity, complete = prefix + f"port:{dev.bus}-{'.'.join(map(str, ports))}", True
            else:
                identity, complete = prefix + f"addr:{dev.bus}-{dev.address}", False
            device = _instance(definition, identity, usb_address=(dev.bus, dev.address))
            device.extra_params["complete"] = complete
            candidates.append(device)
    return candidates


def _finish(candidates):
    """Mark identities that do not single out one device, and number duplicate names."""
    seen, models = {}, {}
    for device in candidates:
        seen[device.extra_params["identity"]] = seen.get(device.extra_params["identity"], 0) + 1
        model = (device.vendor_id, device.product_id, device.backend_type)
        models[model] = models.get(model, 0) + 1
    names = {}
    for device in candidates:
        params = device.extra_params
        model = (device.vendor_id, device.product_id, device.backend_type)
        # A bus/address identity is not stable (the address can go to another panel after a replug):
        # never resolvable, even when this is the only device of its model right now
        if seen[params["identity"]] > 1 or not params.pop("complete", True):
            params["ambiguous"] = True
        names[device.name] = names.get(device.name, 0) + 1
        if names[device.name] > 1:
            device.name = f"{device.name} #{names[device.name]}"
    return candidates


def resolve_device(identity, candidates):
    """The one non-ambiguous candidate with this identity, else None (never a different device)."""
    matches = [device for device in candidates if device.extra_params.get("identity") == identity]
    return matches[0] if len(matches) == 1 and not matches[0].extra_params.get("ambiguous") else None


def enumerate_available_devices() -> List[DeviceDefinition]:
    """
    Enumerate connected supported devices: one entry per physical device, each with
    extra_params["identity"] (stable across replug/reorder where the hardware allows) and the
    path/address to open it now.
    """
    available = []

    try:
        import hid
        available += _hid_candidates(hid.enumerate())
    except ImportError:
        logger.debug("hidapi not available for enumeration")
    except Exception as e:
        logger.debug(f"HID enumeration error: {e}")

    try:
        import usb.core
        import usb.util
        available += _usb_candidates(usb.core, usb.util)
    except ImportError:
        logger.debug("pyusb not available for enumeration")
    except Exception as e:
        logger.debug(f"USB enumeration error: {e}")

    for device in available:
        logger.info(f"Found {device.backend_type} device: {device.name}")
    return _finish(available)
