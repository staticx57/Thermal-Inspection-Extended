"""
Placeholder Frames for Disconnected Cameras
Generates user-friendly placeholder frames when camera feeds are unavailable
"""
import cv2
import numpy as np
from enum import Enum
from typing import Optional


class CameraStatus(Enum):
    """Camera connection status"""
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    RETRYING = "Retrying..."
    ERROR = "Error"
    NOT_CONFIGURED = "Not Configured"


def create_placeholder_frame(width: int, height: int,
                            camera_name: str,
                            status: CameraStatus = CameraStatus.DISCONNECTED,
                            message: str = "") -> np.ndarray:
    """
    Create placeholder frame for disconnected camera

    Args:
        width: Frame width
        height: Frame height
        camera_name: Name of camera ("Thermal", "RGB", "LiDAR")
        status: Camera status
        message: Additional message to display

    Returns:
        Placeholder frame (BGR image)
    """
    # Create dark gray background
    frame = np.full((height, width, 3), 40, dtype=np.uint8)

    # Colors based on status
    colors = {
        CameraStatus.CONNECTED: (0, 255, 0),        # Green
        CameraStatus.DISCONNECTED: (128, 128, 128), # Gray
        CameraStatus.RETRYING: (0, 255, 255),       # Yellow
        CameraStatus.ERROR: (0, 0, 255),            # Red
        CameraStatus.NOT_CONFIGURED: (100, 100, 100), # Dark Gray
    }
    color = colors.get(status, (128, 128, 128))

    # Draw border
    border_thickness = max(2, min(width, height) // 200)
    cv2.rectangle(frame, (10, 10), (width-10, height-10), color, border_thickness)

    # Add camera icon (simple circle with lens)
    center_x, center_y = width // 2, height // 2 - 50
    icon_radius = min(40, min(width, height) // 10)
    cv2.circle(frame, (center_x, center_y), icon_radius, color, -1)
    cv2.circle(frame, (center_x, center_y), icon_radius // 2, (40, 40, 40), -1)

    # Add small lens flare
    flare_offset = icon_radius // 3
    cv2.circle(frame, (center_x - flare_offset, center_y - flare_offset),
               icon_radius // 6, (200, 200, 200), -1)

    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Camera name
    title = f"{camera_name} Camera"
    title_size = min(1.2, width / 400)
    text_size = cv2.getTextSize(title, font, title_size, 2)[0]
    text_x = (width - text_size[0]) // 2
    text_y = center_y + icon_radius + 60
    cv2.putText(frame, title, (text_x, text_y),
               font, title_size, (255, 255, 255), 2, cv2.LINE_AA)

    # Feed unavailable message
    unavailable_text = "FEED UNAVAILABLE"
    unavailable_size = min(0.9, width / 500)
    text_size = cv2.getTextSize(unavailable_text, font, unavailable_size, 2)[0]
    text_x = (width - text_size[0]) // 2
    text_y = text_y + 50
    cv2.putText(frame, unavailable_text, (text_x, text_y),
               font, unavailable_size, color, 2, cv2.LINE_AA)

    # Status
    status_text = status.value
    status_size = min(0.7, width / 600)
    text_size = cv2.getTextSize(status_text, font, status_size, 2)[0]
    text_x = (width - text_size[0]) // 2
    text_y = text_y + 40
    cv2.putText(frame, status_text, (text_x, text_y),
               font, status_size, color, 2, cv2.LINE_AA)

    # Additional message
    if message:
        msg_size = min(0.5, width / 800)
        lines = message.split('\n')
        y_offset = text_y + 35
        for line in lines:
            text_size = cv2.getTextSize(line, font, msg_size, 1)[0]
            text_x = (width - text_size[0]) // 2
            cv2.putText(frame, line, (text_x, y_offset),
                       font, msg_size, (200, 200, 200), 1, cv2.LINE_AA)
            y_offset += 25

    return frame


def create_feed_unavailable_frame(width: int = 640, height: int = 480,
                                  camera_name: str = "Camera") -> np.ndarray:
    """
    Create a simple "Feed Unavailable" placeholder frame

    Args:
        width: Frame width
        height: Frame height
        camera_name: Name of camera

    Returns:
        Placeholder frame
    """
    return create_placeholder_frame(
        width, height, camera_name,
        CameraStatus.DISCONNECTED,
        "Press 'Retry Sensors' in Developer Panel"
    )


def create_thermal_placeholder(width: int = 640, height: int = 512) -> np.ndarray:
    """Create placeholder for thermal camera (default FLIR Boson resolution)"""
    return create_feed_unavailable_frame(width, height, "Thermal")


def create_rgb_placeholder(width: int = 640, height: int = 480) -> np.ndarray:
    """Create placeholder for RGB camera"""
    return create_feed_unavailable_frame(width, height, "RGB")


def create_lidar_placeholder(width: int = 640, height: int = 480) -> np.ndarray:
    """Create placeholder for LiDAR sensor"""
    return create_placeholder_frame(
        width, height, "LiDAR",
        CameraStatus.NOT_CONFIGURED,
        "LiDAR support not configured"
    )


if __name__ == "__main__":
    """Test placeholder frame generation"""
    print("="*60)
    print("Placeholder Frame Generator Test")
    print("="*60)

    # Test all status types
    statuses = [
        (CameraStatus.DISCONNECTED, "Thermal camera not detected"),
        (CameraStatus.RETRYING, "Attempting to reconnect..."),
        (CameraStatus.ERROR, "Camera initialization failed"),
        (CameraStatus.NOT_CONFIGURED, "Camera not configured"),
    ]

    print("\nGenerating test frames...")

    for i, (status, msg) in enumerate(statuses):
        frame = create_placeholder_frame(
            640, 480, "Test Camera",
            status, msg
        )
        filename = f"test_placeholder_{status.value.lower().replace(' ', '_')}.png"
        cv2.imwrite(filename, frame)
        print(f"  {i+1}. Created: {filename} ({status.value})")

    # Test convenience functions
    print("\nTesting convenience functions...")
    thermal_frame = create_thermal_placeholder()
    cv2.imwrite("test_thermal_placeholder.png", thermal_frame)
    print("  Created: test_thermal_placeholder.png")

    rgb_frame = create_rgb_placeholder()
    cv2.imwrite("test_rgb_placeholder.png", rgb_frame)
    print("  Created: test_rgb_placeholder.png")

    lidar_frame = create_lidar_placeholder()
    cv2.imwrite("test_lidar_placeholder.png", lidar_frame)
    print("  Created: test_lidar_placeholder.png")

    print("\n" + "="*60)
    print("Test complete! Check generated PNG files.")
    print("="*60)
