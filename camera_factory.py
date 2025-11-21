"""
RGB Camera Factory - Auto-detection and instantiation
Automatically selects the best available RGB camera:
1. FLIR Firefly (global shutter, best quality) - if Spinnaker SDK available
2. Generic UVC webcam (fallback) - works out-of-box

Usage:
    from camera_factory import create_rgb_camera

    # Auto-detect and create camera
    camera = create_rgb_camera(resolution=(640, 480), fps=30)

    if camera.open():
        ret, frame = camera.read()
        # ... use frame
        camera.release()
"""
import logging
from typing import Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import camera classes
try:
    from rgb_camera_firefly import RGBCameraFirefly, detect_firefly_cameras, PYSPIN_AVAILABLE
except ImportError:
    RGBCameraFirefly = None
    detect_firefly_cameras = None
    PYSPIN_AVAILABLE = False
    logger.warning("FLIR Firefly support not available (rgb_camera_firefly.py not found)")

try:
    from rgb_camera_uvc import RGBCameraUVC, detect_uvc_cameras
except ImportError:
    RGBCameraUVC = None
    detect_uvc_cameras = None
    logger.warning("UVC camera support not available (rgb_camera_uvc.py not found)")

# Fallback to original rgb_camera.py if new modules not available
try:
    from rgb_camera import RGBCamera
except ImportError:
    RGBCamera = None
    logger.warning("Fallback RGB camera not available (rgb_camera.py not found)")


def detect_all_rgb_cameras() -> dict:
    """
    Detect all available RGB cameras (Firefly + UVC)

    Returns:
        Dictionary with camera types and their metadata
    """
    cameras = {
        'firefly': [],
        'uvc': [],
        'total_count': 0
    }

    # Detect FLIR Firefly cameras
    if PYSPIN_AVAILABLE and detect_firefly_cameras is not None:
        try:
            firefly_cams = detect_firefly_cameras()
            cameras['firefly'] = firefly_cams
            cameras['total_count'] += len(firefly_cams)
            logger.info(f"Detected {len(firefly_cams)} FLIR Firefly camera(s)")
        except Exception as e:
            logger.warning(f"Firefly detection failed: {e}")

    # Detect UVC cameras
    if detect_uvc_cameras is not None:
        try:
            uvc_cams = detect_uvc_cameras()
            cameras['uvc'] = uvc_cams
            cameras['total_count'] += len(uvc_cams)
            logger.info(f"Detected {len(uvc_cams)} UVC camera(s)")
        except Exception as e:
            logger.warning(f"UVC detection failed: {e}")

    return cameras


def create_rgb_camera(resolution: Tuple[int, int] = (640, 480),
                      fps: int = 30,
                      camera_type: Optional[str] = None,
                      camera_index: int = 0,
                      use_gstreamer: bool = False,
                      thermal_device_id: Optional[int] = None):
    """
    Create RGB camera instance with auto-detection

    Priority order (if camera_type not specified):
    1. FLIR Firefly (global shutter, best for motion)
    2. Generic UVC webcam (fallback)
    3. Original RGBCamera class (legacy fallback)

    Args:
        resolution: Desired resolution (width, height)
        fps: Target frame rate
        camera_type: Force specific camera type ("firefly", "uvc", "auto")
        camera_index: Camera index (0 for first detected, or next available if thermal_device_id provided)
        use_gstreamer: Use GStreamer for CSI cameras (Jetson only)
        thermal_device_id: Device ID of thermal camera to skip (prevents opening same device)

    Returns:
        Camera instance (RGBCameraFirefly, RGBCameraUVC, or RGBCamera)

    Raises:
        RuntimeError: If no cameras are available
    """
    if camera_type is None:
        camera_type = "auto"

    camera_type = camera_type.lower()

    # Skip thermal camera device if provided
    if thermal_device_id is not None and camera_index == thermal_device_id:
        logger.info(f"Skipping thermal camera device {thermal_device_id}, using next available device")
        camera_index = thermal_device_id + 1

    logger.info("="*60)
    logger.info("RGB Camera Factory - Auto-detection")
    logger.info("="*60)

    # Force FLIR Firefly
    if camera_type == "firefly":
        if not PYSPIN_AVAILABLE or RGBCameraFirefly is None:
            raise RuntimeError("FLIR Firefly support not available. Install Spinnaker SDK + PySpin.")

        logger.info("Creating FLIR Firefly camera (forced)")
        return RGBCameraFirefly(
            camera_index=camera_index,
            resolution=resolution,
            fps=fps,
            pixel_format="BGR8"
        )

    # Force UVC webcam
    if camera_type == "uvc":
        if RGBCameraUVC is None:
            raise RuntimeError("UVC camera support not available.")

        logger.info("Creating UVC webcam (forced)")
        return RGBCameraUVC(
            device_id=camera_index,
            resolution=resolution,
            fps=fps,
            use_gstreamer=use_gstreamer
        )

    # Auto-detect (default)
    if camera_type == "auto":
        logger.info("Auto-detecting RGB cameras...")

        # Try FLIR Firefly first (global shutter, best quality)
        if PYSPIN_AVAILABLE and RGBCameraFirefly is not None:
            try:
                firefly_cams = detect_firefly_cameras()
                if firefly_cams and len(firefly_cams) > 0:
                    logger.info(f"[OK] Found {len(firefly_cams)} FLIR Firefly camera(s)")
                    logger.info(f"  Model: {firefly_cams[0]['model']}")
                    logger.info(f"  Serial: {firefly_cams[0]['serial']}")
                    logger.info("  Features: Global shutter, no motion blur")
                    logger.info("Creating FLIR Firefly camera...")
                    return RGBCameraFirefly(
                        camera_index=camera_index,
                        resolution=resolution,
                        fps=fps,
                        pixel_format="BGR8"
                    )
                else:
                    logger.info("[X] No FLIR Firefly cameras detected")
            except Exception as e:
                logger.warning(f"Firefly detection failed: {e}")

        # Fall back to UVC webcam
        if RGBCameraUVC is not None:
            try:
                uvc_cams = detect_uvc_cameras()
                if uvc_cams and len(uvc_cams) > 0:
                    logger.info(f"[OK] Found {len(uvc_cams)} UVC camera(s)")
                    logger.info(f"  Type: {uvc_cams[0]['type']}")
                    logger.info(f"  Resolution: {uvc_cams[0]['resolution']}")
                    logger.info("Creating UVC webcam...")
                    return RGBCameraUVC(
                        device_id=camera_index,
                        resolution=resolution,
                        fps=fps,
                        use_gstreamer=use_gstreamer
                    )
                else:
                    logger.info("[X] No UVC cameras detected")
            except Exception as e:
                logger.warning(f"UVC detection failed: {e}")

        # Final fallback to original RGBCamera class (legacy)
        if RGBCamera is not None:
            logger.warning("Falling back to legacy RGBCamera class")
            return RGBCamera(
                device_id=camera_index,
                resolution=resolution,
                fps=fps,
                use_gstreamer=use_gstreamer
            )

        # No cameras available
        raise RuntimeError("No RGB cameras detected! Check connections and drivers.")

    # Invalid camera type
    raise ValueError(f"Invalid camera_type: {camera_type}. Use 'auto', 'firefly', or 'uvc'.")


def print_camera_summary():
    """
    Print summary of all detected cameras
    """
    print("="*60)
    print("RGB Camera Detection Summary")
    print("="*60)

    cameras = detect_all_rgb_cameras()

    print(f"\nTotal cameras detected: {cameras['total_count']}")

    if cameras['firefly']:
        print(f"\nFLIR Firefly Cameras ({len(cameras['firefly'])}):")
        for i, cam in enumerate(cameras['firefly']):
            print(f"  [{i}] {cam['model']}")
            print(f"      Serial: {cam['serial']}")
            print(f"      Features: Global shutter, no motion blur")

    if cameras['uvc']:
        print(f"\nUVC Webcams ({len(cameras['uvc'])}):")
        for i, cam in enumerate(cameras['uvc']):
            print(f"  [{i}] {cam['type']} Camera")
            print(f"      Resolution: {cam['resolution'][0]}x{cam['resolution'][1]}")

    if cameras['total_count'] == 0:
        print("\n⚠ No RGB cameras detected!")
        print("\nTroubleshooting:")
        print("  1. Check USB connections")
        print("  2. For FLIR Firefly: Install Spinnaker SDK")
        print("     https://www.flir.com/products/spinnaker-sdk/")
        print("  3. For UVC webcams: Check device manager")
        print("  4. Run with sudo (Linux) if permission issues")

    print("="*60)


if __name__ == "__main__":
    """Test camera factory"""
    import sys

    # Print camera summary
    print_camera_summary()

    print("\n" + "="*60)
    print("Testing Camera Creation (Auto-detect)")
    print("="*60)

    try:
        # Create camera with auto-detection
        camera = create_rgb_camera(resolution=(640, 480), fps=30, camera_type="auto")

        print(f"\nCamera created: {camera.camera_type}")
        print("Attempting to open camera...")

        if camera.open():
            print("[OK] Camera opened successfully!")
            print(f"  Resolution: {camera.get_actual_resolution()}")

            # Test frame capture
            print("\nTesting frame capture...")
            for i in range(10):
                ret, frame = camera.read()
                if ret:
                    print(f"  Frame {i+1}: {frame.shape} ({frame.dtype})")
                else:
                    print(f"  Frame {i+1}: Failed")

            print("\nTest with live display (press 'q' to quit)...")

            try:
                import cv2
                import time

                frame_count = 0
                start_time = time.time()

                while True:
                    ret, frame = camera.read()

                    if not ret:
                        print("Failed to read frame")
                        break

                    frame_count += 1

                    # Calculate FPS
                    if frame_count % 30 == 0:
                        elapsed = time.time() - start_time
                        fps = frame_count / elapsed
                        print(f"FPS: {fps:.1f}")

                    # Draw camera type on frame
                    cv2.putText(frame, f"{camera.camera_type}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Display frame
                    cv2.imshow("Camera Factory Test", frame)

                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break

                cv2.destroyAllWindows()

            except ImportError:
                print("OpenCV not available for display test. Camera is working!")

            # Release camera
            camera.release()
            print("\n[OK] Camera released")

        else:
            print("[X] Failed to open camera")
            sys.exit(1)

    except RuntimeError as e:
        print(f"\n[X] Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        try:
            camera.release()
        except:
            pass
        sys.exit(0)

    print("\n" + "="*60)
    print("Camera Factory Test Complete!")
    print("="*60)
