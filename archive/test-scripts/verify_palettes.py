#!/usr/bin/env python3
"""
Verify all 24 thermal palettes are properly configured
"""
from vpi_detector import VPIDetector

# Initialize detector
detector = VPIDetector()

print(f"✓ Total palettes: {len(detector.color_palettes)}\n")
print("Palette list:")
print("=" * 60)

# Group by category
adas_critical = ['white_hot', 'black_hot', 'ironbow', 'arctic', 'cividis', 'outdoor_alert']
scientific = ['viridis', 'plasma', 'lava', 'magma', 'bone', 'parula']
general = ['rainbow', 'rainbow_hc', 'sepia', 'gray', 'amber', 'ocean', 'feather']
experimental = ['twilight', 'twilight_shifted', 'deepgreen', 'hsv', 'pink']

print("\n1. ADAS-Critical (Simple Mode) - 6 palettes:")
for p in adas_critical:
    status = "✓" if p in detector.color_palettes else "✗"
    print(f"  {status} {p}")

print("\n2. Scientific / Perceptually Uniform - 6 palettes:")
for p in scientific:
    status = "✓" if p in detector.color_palettes else "✗"
    print(f"  {status} {p}")

print("\n3. General Purpose - 7 palettes:")
for p in general:
    status = "✓" if p in detector.color_palettes else "✗"
    print(f"  {status} {p}")

print("\n4. Fun / Experimental - 5 palettes:")
for p in experimental:
    status = "✓" if p in detector.color_palettes else "✗"
    print(f"  {status} {p}")

# Verify all expected palettes exist
all_expected = adas_critical + scientific + general + experimental
missing = [p for p in all_expected if p not in detector.color_palettes]
extra = [p for p in detector.color_palettes if p not in all_expected]

print("\n" + "=" * 60)
if len(detector.color_palettes) == 24 and len(missing) == 0:
    print("✓✓✓ SUCCESS: All 24 palettes properly configured ✓✓✓")
else:
    print(f"✗ ERROR: Expected 24 palettes, found {len(detector.color_palettes)}")
    if missing:
        print(f"  Missing: {missing}")
    if extra:
        print(f"  Extra: {extra}")
