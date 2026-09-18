"""
Shared torch GPU-device resolution - CUDA and DirectML (Intel/AMD, via
the torch-directml package) share this single probe, so adding a new
backend here makes it available to every GPU-accelerated code path at
once (fusion_processor.py's feature_weighted/laplacian_pyramid,
fusion_3d_panel.py's relief/normals, parallax_compensator.py's remap)
instead of four separately-maintained copies.

torch-directml is NOT installed in this project's own dev environment
(confirmed 2026-09): its latest published release hard-pins
torch==2.4.1/torchvision==0.19.1, incompatible with this project's
torch 2.9.1+cu126 - installing it here would mean downgrading torch
and risking every CUDA path this codebase already depends on and has
verified against real hardware, on a machine that has no Intel/AMD GPU
to verify DirectML actually works on anyway. Per direct user
instruction ("this would be relevant for another laptop I can have.
leave this machine's configuration intact"), this module's DirectML
branch is deliberately unverified on real hardware here - it's written
to activate automatically the moment a compatible torch_directml
becomes importable, on a different machine or a future compatible
release, not guessed to work. See requirements.txt and the Thermal
Debt Ledger's "No AMD/Intel GPU acceleration path" entry for the full
context.
"""
import logging
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def resolve_torch_gpu_device(device_requested: str, caller_name: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Resolve a real torch GPU device to use, given the caller's own
    requested device string ("cuda", "directml", "cpu", "auto", or ""/
    None treated the same as "auto").

    Returns (device, device_description). device is whatever a torch
    tensor's device= kwarg or .to() accepts - the plain "cuda" string
    (unchanged from before this module existed), or
    torch_directml.device()'s own device object, which every
    .to(device)/torch.tensor(..., device=device) call downstream
    accepts identically. Returns (None, None) if CPU should be used
    instead - either "cpu" was explicitly requested, or no accelerator
    matching what was requested is actually available.

    "auto" (or unset) tries CUDA first, then DirectML - CUDA preferred
    since it's the mature, verified path; DirectML is a fallback for
    machines with an Intel/AMD GPU and no CUDA-capable one at all.

    caller_name is used only for the warning logged when a SPECIFIC
    (non-"auto") device was requested but isn't available - matches
    each call site's own prior "<component>: <device> requested but
    not available" wording.
    """
    if device_requested == "cpu":
        return None, None

    import torch

    if device_requested in ("cuda", "auto", "", None):
        if torch.cuda.is_available():
            return "cuda", torch.cuda.get_device_name(0)
        if device_requested == "cuda":
            logger.warning(f"{caller_name}: CUDA requested but not available, falling back to CPU")

    if device_requested in ("directml", "auto", "", None):
        try:
            import torch_directml
            if torch_directml.is_available():
                device = torch_directml.device()
                try:
                    name = f"DirectML: {torch_directml.device_name(torch_directml.default_device())}"
                except Exception:
                    name = "DirectML"
                return device, name
            elif device_requested == "directml":
                logger.warning(f"{caller_name}: DirectML requested but no DirectML-capable device found")
        except ImportError:
            if device_requested == "directml":
                logger.warning(
                    f"{caller_name}: DirectML requested but torch-directml is not "
                    f"installed (see requirements.txt for the known torch version "
                    f"pin conflict)"
                )
        except Exception as e:
            if device_requested == "directml":
                logger.warning(f"{caller_name}: DirectML device resolution failed: {e}")

    return None, None
