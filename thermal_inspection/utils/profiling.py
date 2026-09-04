"""
Central on/off switch and formatting for this codebase's ad hoc
[PROFILE_*] diagnostic prints (app.py, fusion_3d_panel.py). Each was
added independently by a different performance investigation, with its
own frame_count % N (or update-interval) throttle and its own hand-built
f-string - there was no way to silence one without editing source, and
no way to silence all of them short of grepping every call site.

Set THERMAL_PROFILE=0 in the environment to silence every [PROFILE_*]
line at once; unset (or any other value) keeps the existing default-on
behavior unchanged. Per-callsite throttling is unaffected - that's still
each caller's own job, this only gates whether the line is ever written.
"""
import os

PROFILE_ENABLED = os.environ.get("THERMAL_PROFILE", "1") not in ("0", "false", "False")


def profile_log(tag: str, **fields) -> None:
    """Print '[PROFILE_<tag>] k=v k2=v2 ...' if profiling output is enabled."""
    if not PROFILE_ENABLED:
        return
    kv = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"[PROFILE_{tag}] {kv}", flush=True)
