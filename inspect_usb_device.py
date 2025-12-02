#!/usr/bin/env python3
"""
Inspect FLIR Boson USB device to understand its endpoints and configurations.
This doesn't require driver changes - just reads device descriptors.
"""
import usb.core
import usb.util
import sys

print("="*70)
print("FLIR Boson USB Device Inspector")
print("="*70)

# Find Boson (VID:09CB, PID:4007)
print("\n[Step 1] Searching for FLIR Boson...")
dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

if dev is None:
    print("  [ERROR] FLIR Boson not found!")
    print("\n  Troubleshooting:")
    print("    1. Is camera connected via USB?")
    print("    2. Check Device Manager for 'FLIR Boson'")
    print("    3. Try different USB port")
    print("\n  Searching for all USB video devices...")

    # Search for all video devices
    devices = usb.core.find(find_all=True, bDeviceClass=0xEF)  # Miscellaneous
    found_any = False
    for d in devices:
        try:
            print(f"\n  Found device: VID:{d.idVendor:04X} PID:{d.idProduct:04X}")
            try:
                print(f"    Manufacturer: {usb.util.get_string(d, d.iManufacturer)}")
                print(f"    Product: {usb.util.get_string(d, d.iProduct)}")
            except:
                print("    (Cannot read strings - may need admin)")
            found_any = True
        except:
            pass

    if not found_any:
        print("\n  No USB devices found with video class")

    sys.exit(1)

print(f"  [OK] Found FLIR Boson")
print(f"       VID: 0x{dev.idVendor:04X}")
print(f"       PID: 0x{dev.idProduct:04X}")

# Get device info
print("\n[Step 2] Reading device information...")
try:
    manufacturer = usb.util.get_string(dev, dev.iManufacturer)
    product = usb.util.get_string(dev, dev.iProduct)
    serial = usb.util.get_string(dev, dev.iSerialNumber)

    print(f"  Manufacturer: {manufacturer}")
    print(f"  Product: {product}")
    print(f"  Serial: {serial}")
except Exception as e:
    print(f"  Could not read strings: {e}")
    print(f"  (May need to run as Administrator)")

# Device details
print(f"\n  USB Specification: {dev.bcdUSB / 256:.1f}")
print(f"  Device Class: 0x{dev.bDeviceClass:02X}")
print(f"  Device Subclass: 0x{dev.bDeviceSubClass:02X}")
print(f"  Device Protocol: 0x{dev.bDeviceProtocol:02X}")
print(f"  Max Packet Size: {dev.bMaxPacketSize0} bytes")
print(f"  Number of Configurations: {dev.bNumConfigurations}")

# Enumerate configurations
print("\n[Step 3] Enumerating configurations and interfaces...")

for cfg_num, cfg in enumerate(dev):
    print(f"\n  Configuration {cfg_num}:")
    print(f"    bConfigurationValue: {cfg.bConfigurationValue}")
    print(f"    Number of Interfaces: {cfg.bNumInterfaces}")

    try:
        cfg_string = usb.util.get_string(dev, cfg.iConfiguration)
        print(f"    Description: {cfg_string}")
    except:
        pass

    # Enumerate interfaces
    for intf_num, intf in enumerate(cfg):
        print(f"\n    Interface {intf_num}:")
        print(f"      bInterfaceNumber: {intf.bInterfaceNumber}")
        print(f"      bAlternateSetting: {intf.bAlternateSetting}")
        print(f"      bInterfaceClass: 0x{intf.bInterfaceClass:02X}", end="")

        # Decode interface class
        class_names = {
            0x01: "Audio",
            0x02: "CDC (Communications)",
            0x03: "HID",
            0x06: "Still Image",
            0x07: "Printer",
            0x08: "Mass Storage",
            0x09: "Hub",
            0x0A: "CDC-Data",
            0x0E: "Video",
            0x0F: "Personal Healthcare",
            0xEF: "Miscellaneous"
        }
        if intf.bInterfaceClass in class_names:
            print(f" ({class_names[intf.bInterfaceClass]})")
        else:
            print()

        print(f"      bInterfaceSubClass: 0x{intf.bInterfaceSubClass:02X}")
        print(f"      bInterfaceProtocol: 0x{intf.bInterfaceProtocol:02X}")
        print(f"      Number of Endpoints: {intf.bNumEndpoints}")

        # Enumerate endpoints
        for ep_num, ep in enumerate(intf):
            print(f"\n      Endpoint {ep_num}:")
            print(f"        bEndpointAddress: 0x{ep.bEndpointAddress:02X}", end="")

            # Decode direction
            direction = "IN" if (ep.bEndpointAddress & 0x80) else "OUT"
            ep_addr = ep.bEndpointAddress & 0x7F
            print(f" (EP{ep_addr} {direction})")

            # Decode transfer type
            transfer_type = ep.bmAttributes & 0x03
            transfer_names = {
                0: "Control",
                1: "Isochronous",
                2: "Bulk",
                3: "Interrupt"
            }
            print(f"        Transfer Type: {transfer_names.get(transfer_type, 'Unknown')}")
            print(f"        Max Packet Size: {ep.wMaxPacketSize} bytes")

            if transfer_type == 1:  # Isochronous
                print(f"        Interval: {ep.bInterval} ms")

print("\n" + "="*70)
print("Device Inspection Complete")
print("="*70)

print("\n[Analysis]")
print("  Look for:")
print("    1. Video interface (class 0x0E)")
print("    2. Bulk IN endpoint (usually 0x81)")
print("    3. Isochronous IN endpoint for video streaming")
print("\n  This information will be used for direct capture implementation.")
print("="*70)
