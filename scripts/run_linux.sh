#!/bin/bash
cd "$(dirname "$0")/.."
#
# Start Thermal Inspection on Linux. Uses the project's .venv when there is one, picks a Qt platform that works under
# Wayland, and lets the app's own start-up check explain anything that is missing (it never crashes with a traceback).
# Extra arguments are passed to the app:   ./scripts/run_linux.sh --log-level INFO --log-file debug.log
#
if [ -z "$VIRTUAL_ENV" ] && [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    . .venv/bin/activate
fi

# Qt under a Wayland session: the xcb plugin (via XWayland) is the one the pip wheels reliably ship with
if [ "$XDG_SESSION_TYPE" = "wayland" ] && [ -z "$QT_QPA_PLATFORM" ] && [ -n "$DISPLAY" ]; then
    export QT_QPA_PLATFORM=xcb
fi

PY=python3
command -v python >/dev/null 2>&1 && [ -n "$VIRTUAL_ENV" ] && PY=python

if ! "$PY" -m thermal_inspection "$@"; then
    code=$?
    echo
    echo "The app exited with code $code. To see what this machine is missing:"
    echo "    ./scripts/linux_setup.sh        (report)     ./scripts/linux_setup.sh --fix   (install what is missing)"
    exit $code
fi
