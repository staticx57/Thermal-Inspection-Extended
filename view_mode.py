"""
View mode enumeration for Thermal Fusion Driving Assist
Shared between OpenCV and Qt GUI implementations
"""


class ViewMode:
    """Display view modes for multi-camera fusion"""
    THERMAL_ONLY = "thermal"
    RGB_ONLY = "rgb"
    FUSION = "fusion"
    SIDE_BY_SIDE = "side_by_side"
    PICTURE_IN_PICTURE = "pip"
