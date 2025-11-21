#!/usr/bin/env python3
"""
Utility script to convert palette definitions from RGB to BGR format.
Run this to convert palette_manager.py palettes from RGB to BGR.
"""

import re

def rgb_to_bgr(rgb_tuple_str):
    """Convert (R, G, B) string to (B, G, R) string."""
    # Extract numbers from tuple string like "(255, 128, 0)"
    match = re.match(r'\((\d+),\s*(\d+),\s*(\d+)\)', rgb_tuple_str)
    if match:
        r, g, b = match.groups()
        return f"({b}, {g}, {r})"
    return rgb_tuple_str

def convert_palette_line(line):
    """Convert a palette definition line from RGB to BGR."""
    # Find all (R, G, B) tuples in the line
    def replacer(match):
        return rgb_to_bgr(match.group(0))

    # Pattern to match (num, num, num) tuples
    pattern = r'\(\d+,\s*\d+,\s*\d+\)'
    return re.sub(pattern, replacer, line)

# Read the file
with open('palette_manager.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Convert all lines
converted_lines = []
in_palette_section = False

for line in lines:
    # Detect palette cache assignment lines
    if 'self.palette_cache[' in line and '_create_gradient_palette' in line:
        in_palette_section = True
    elif in_palette_section and '])' in line:
        in_palette_section = False

    # Convert the line if we're in a palette section
    if in_palette_section or (converted_lines and in_palette_section):
        converted_line = convert_palette_line(line)
        # Add BGR comment if it's a color tuple line
        if re.search(r'\(\d+,\s*\d+,\s*\d+\)', line) and '# ' in line:
            # Replace existing comment with (BGR) suffix
            converted_line = re.sub(r'#\s*(.+?)(\s*\(BGR\))?$', r'# \1 (BGR)', converted_line)
        converted_lines.append(converted_line)
    else:
        converted_lines.append(line)

# Write the converted file
with open('palette_manager.py', 'w', encoding='utf-8') as f:
    f.writelines(converted_lines)

print("Palette conversion complete!")
print("All RGB values have been converted to BGR format.")
