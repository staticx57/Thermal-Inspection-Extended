#!/usr/bin/env python3
"""
Utility script to reverse all palette gradient definitions.
This fixes the issue where palettes are inverted (white hot showing black as hot).
"""

import re

def reverse_palette_colors(palette_str):
    """Reverse the order of colors in a palette definition."""
    # Extract all (R, G, B) tuples from the palette
    color_pattern = r'\((\d+),\s*(\d+),\s*(\d+)\)'
    colors = re.findall(color_pattern, palette_str)

    if not colors:
        return palette_str

    # Reverse the order of colors
    colors_reversed = list(reversed(colors))

    # Replace colors in the original string one by one
    def replacer(match):
        if not colors_reversed:
            return match.group(0)
        r, g, b = colors_reversed.pop(0)
        return f'({r}, {g}, {b})'

    # Reset for actual replacement
    colors_reversed = list(reversed(colors))
    result = re.sub(color_pattern, replacer, palette_str)

    return result

# Read the file
with open('palette_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and reverse each palette definition
# Pattern to match: self.palette_cache[PaletteType.XXX] = self._create_gradient_palette([
palette_pattern = r'(self\.palette_cache\[PaletteType\.\w+\]\s*=\s*self\._create_gradient_palette\(\[)(.*?)(\]\))'

def process_palette(match):
    """Process a single palette definition."""
    prefix = match.group(1)
    colors_section = match.group(2)
    suffix = match.group(3)

    # Reverse the colors
    reversed_colors = reverse_palette_colors(colors_section)

    return prefix + reversed_colors + suffix

# Apply the reversal to all palettes
content_reversed = re.sub(palette_pattern, process_palette, content, flags=re.DOTALL)

# Write the result
with open('palette_manager.py', 'w', encoding='utf-8') as f:
    f.write(content_reversed)

print("All palettes have been reversed!")
print("Cold temperatures (index 0) now map to cold colors")
print("Hot temperatures (index 255) now map to hot colors")
