#!/usr/bin/env python3
"""Test script to detect available COM ports."""
import serial.tools.list_ports

print("="*60)
print("Available COM Ports")
print("="*60)

ports = serial.tools.list_ports.comports()

if not ports:
    print("No COM ports found!")
else:
    for port in ports:
        print(f"\nPort: {port.device}")
        print(f"  Description: {port.description}")
        print(f"  Hardware ID: {port.hwid}")
        print(f"  Manufacturer: {port.manufacturer}")
        print(f"  Product: {port.product}")
        print(f"  Serial Number: {port.serial_number}")

print("\n" + "="*60)
print(f"Total: {len(ports)} port(s) found")
print("="*60)
