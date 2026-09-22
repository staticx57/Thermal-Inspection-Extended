"""
Lazy-import gate for Open3D, this app's optional dependency for 3D Mapping
Fusion (PoseTracker/WorldPointCloud/WorldMapper - see world_mapper.py).
Same pattern as fusion_3d_panel.py's _TORCH_SPEC_AVAILABLE/GL_AVAILABLE -
importing Open3D eagerly at module load would slow every app startup (and
fail entirely on a machine that never installs it) for a feature most
users won't touch.
"""
import importlib.util

OPEN3D_AVAILABLE = importlib.util.find_spec("open3d") is not None


def get_open3d():
    """Import and return the open3d module, or raise a clear ImportError."""
    if not OPEN3D_AVAILABLE:
        raise ImportError(
            "open3d is not installed. 3D Mapping Fusion needs it - "
            "install with: pip install open3d"
        )
    import open3d as o3d
    return o3d
