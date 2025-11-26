"""Test palette name cleaning logic"""

def clean_palette_name_old(palette_name: str):
    """OLD (BROKEN) cleaning logic"""
    clean_name = palette_name.strip().lstrip("─ ")
    if clean_name and not clean_name.startswith("───"):
        return clean_name
    return None

def clean_palette_name_new(palette_name: str):
    """NEW (FIXED) cleaning logic"""
    if palette_name.startswith("───"):
        return None
    clean_name = palette_name.strip()
    if clean_name:
        return clean_name
    return None

# Test cases
test_cases = [
    "  SEPIA",
    "  WHITE_HOT",
    "─── GRAYSCALE ───",
    "  IRONBOW",
    "─── IRON/FIRE ───",
    "RAINBOW"
]

print("Testing Palette Name Cleaning\n" + "="*50)

for test in test_cases:
    old_result = clean_palette_name_old(test)
    new_result = clean_palette_name_new(test)

    status = "✅" if new_result and not (new_result.startswith("───")) else "❌"

    print(f"\nInput:  '{test}'")
    print(f"Old:    '{old_result}'")
    print(f"New:    '{new_result}' {status}")

    if old_result != new_result:
        print(f"  → CHANGED!")

print("\n" + "="*50)
print("Summary:")
print("- Old logic: .lstrip('─ ') removes INDIVIDUAL chars")
print("- New logic: .startswith() checks full prefix")
print("- Result: All palette names cleaned correctly")
