#!/bin/bash
cd "$(dirname "$0")/.."
#
# Thermal Inspection - Linux readiness check and one-step fix for Ubuntu / Debian.
#
#   ./scripts/linux_setup.sh                 report what is missing (changes nothing)
#   ./scripts/linux_setup.sh --fix           also install what is missing (asks for sudo)
#   ./scripts/linux_setup.sh --fix --mm-ignore 1234:abcd
#                                            additionally tell ModemManager to leave the device with this VID:PID
#                                            alone (find it in the "Serial ports" part of the report)
#
# Everything is idempotent: running it twice changes nothing the second time.

FIX=false
MM_IGNORE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --fix) FIX=true ;;
        --mm-ignore) MM_IGNORE="$2"; shift ;;
        -h|--help) sed -n 3,13p "$0"; exit 0 ;;
        *) echo "unknown option: $1"; exit 2 ;;
    esac
    shift
done

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -n "$VIRTUAL_ENV" ] && PY=python

echo "== Report =="
"$PY" thermal_inspection/utils/system_info.py || { echo "(report failed - continuing with the checks below)"; }
echo

PROBLEMS=0
say_fix() { echo "  needs: $1"; PROBLEMS=$((PROBLEMS + 1)); }

# 1. Qt system libraries (pip's PyQt6 needs them; their absence aborts Qt with "could not load the xcb plugin")
QT_PKGS=""
for pair in "libxcb-cursor.so.0:libxcb-cursor0" "libxkbcommon-x11.so.0:libxkbcommon-x11-0" "libGL.so.1:libgl1"; do
    lib="${pair%%:*}"; pkg="${pair##*:}"
    ldconfig -p 2>/dev/null | grep -q "$lib" || QT_PKGS="$QT_PKGS $pkg"
done
[ -n "$QT_PKGS" ] && say_fix "apt packages:$QT_PKGS"
command -v v4l2-ctl >/dev/null 2>&1 || { QT_PKGS="$QT_PKGS v4l-utils"; say_fix "apt package: v4l-utils"; }

# 2. groups (serial ports need dialout, cameras need video)
MISSING_GROUPS=""
for g in dialout video; do
    id -nG "$USER" | tr ' ' '\n' | grep -qx "$g" || MISSING_GROUPS="$MISSING_GROUPS $g"
done
[ -n "$MISSING_GROUPS" ] && say_fix "group membership:$MISSING_GROUPS (takes effect after you log out and in)"

# 3. ModemManager rule for the user's board
RULE=/etc/udev/rules.d/99-thermal-inspection-modemmanager.rules
if [ -n "$MM_IGNORE" ]; then
    VID="${MM_IGNORE%%:*}"; PID="${MM_IGNORE##*:}"
    grep -qs "$VID" "$RULE" 2>/dev/null || say_fix "udev rule telling ModemManager to ignore $MM_IGNORE"
fi

echo
if [ "$PROBLEMS" -eq 0 ]; then
    echo "Nothing to fix."
    exit 0
fi
if [ "$FIX" != true ]; then
    echo "$PROBLEMS item(s) to fix. Re-run with --fix to apply them."
    exit 1
fi

echo "== Applying fixes (sudo) =="
if [ -n "$QT_PKGS" ]; then
    sudo apt-get update && sudo apt-get install -y $QT_PKGS
fi
for g in $MISSING_GROUPS; do
    sudo usermod -aG "$g" "$USER" && echo "added $USER to $g (log out and in for it to apply)"
done
if [ -n "$MM_IGNORE" ]; then
    echo "ACTION==\"add|change\", SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"$VID\", ATTRS{idProduct}==\"$PID\", ENV{ID_MM_DEVICE_IGNORE}=\"1\"" \
        | sudo tee "$RULE" >/dev/null
    sudo udevadm control --reload-rules && sudo udevadm trigger
    echo "ModemManager will now leave $MM_IGNORE alone (unplug and replug the board)"
fi
echo "Done. Re-run without --fix to confirm."
