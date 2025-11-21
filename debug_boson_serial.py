#!/usr/bin/env python3
"""
Debug script for Boson serial communication.
Shows raw bytes to diagnose protocol issues.
"""

import serial
import serial.tools.list_ports
import time
import sys

def find_boson():
    """Find Boson COM port."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if port.vid == 0x09CB or 'FLIR' in port.description.upper():
            return port.device
    return None

def hex_dump(data, prefix=""):
    """Pretty print hex dump of bytes."""
    if not data:
        print(f"{prefix}(empty)")
        return

    hex_str = ' '.join(f'{b:02X}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"{prefix}{hex_str}  |{ascii_str}|")

def test_simple_command(ser):
    """Test a simple command and show raw response."""
    print("\n" + "="*80)
    print("TEST: Simple FFC Trigger")
    print("="*80)

    # Try different baud rates
    for baud in [921600, 460800, 115200]:
        print(f"\nTrying baud rate: {baud}")
        ser.baudrate = baud
        time.sleep(0.1)

        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Simple FFC command (CCI Module 0x05, Function 0x02)
        # Packet: [START=0x8E][PROCESS=0x00][STATUS=0x00][CMD][LEN_MSB][LEN_LSB][CRC_MSB][CRC_LSB]
        cmd_byte = (0x05 << 2) | (0x02 & 0x03)  # Module 5, Function 2

        packet = bytes([
            0x8E,  # Start byte
            0x00,  # Process ID
            0x00,  # Status
            cmd_byte,  # Command byte
            0x00,  # Length MSB (no data)
            0x00,  # Length LSB
            0x00,  # CRC MSB (simplified)
            0x00   # CRC LSB
        ])

        print(f"\nSending command:")
        hex_dump(packet, "  TX: ")

        ser.write(packet)
        ser.flush()

        # Wait for response
        time.sleep(0.2)

        # Read what we get
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"\nReceived {len(response)} bytes:")
            hex_dump(response, "  RX: ")

            if len(response) > 0:
                print(f"\n  First byte: 0x{response[0]:02X} (expected: 0x8E)")
                if response[0] == 0x8E:
                    print("  ✓ Valid start byte!")
                    return True
        else:
            print("  No response received")

    return False

def test_raw_communication(ser):
    """Test raw serial communication."""
    print("\n" + "="*80)
    print("TEST: Raw Serial Communication")
    print("="*80)

    # Clear buffers
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Send a simple byte pattern
    test_bytes = bytes([0x8E, 0x00, 0x00, 0x14, 0x00, 0x00, 0x00, 0x00])

    print("\nSending test pattern:")
    hex_dump(test_bytes, "  TX: ")

    ser.write(test_bytes)
    ser.flush()

    time.sleep(0.3)

    if ser.in_waiting > 0:
        response = ser.read(ser.in_waiting)
        print(f"\nReceived {len(response)} bytes:")
        hex_dump(response, "  RX: ")
        return True
    else:
        print("\nNo response received")
        return False

def main():
    """Main debug script."""
    print("="*80)
    print("Boson Serial Communication Debug Tool")
    print("="*80)

    # Find port
    port = find_boson()
    if not port:
        print("\nERROR: No Boson found!")
        return 1

    print(f"\nFound Boson on: {port}")

    try:
        # Open serial port
        ser = serial.Serial(
            port=port,
            baudrate=921600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )

        print(f"Port opened: {port} @ {ser.baudrate} baud")
        print(f"Settings: {ser.bytesize}{ser.parity}{ser.stopbits}")

        # Test 1: Raw communication
        test_raw_communication(ser)

        # Test 2: Try FFC command
        test_simple_command(ser)

        print("\n" + "="*80)
        print("Debug Analysis:")
        print("="*80)
        print("\nIf you see responses but wrong start byte:")
        print("  → Camera might be using different protocol")
        print("  → May need different command structure")
        print("\nIf you see no responses:")
        print("  → Try different baud rate")
        print("  → Check if camera needs initialization")
        print("  → Verify COM port is correct")

        ser.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
