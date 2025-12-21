#!/usr/bin/env python3
"""
Command-line interface for Thermal Inspection Fusion Tool.

This module provides argument parsing and the main entry point.
"""

import sys
import argparse
import logging

logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Thermal + RGB Fusion Inspection Tool'
    )

    # Camera settings
    parser.add_argument('--thermal-device', type=int, default=None,
                       help='Thermal camera device ID (default: auto-detect)')
    parser.add_argument('--rgb-device', type=int, default=None,
                       help='RGB camera device ID (default: auto-detect)')
    parser.add_argument('--auto-detect-cameras', action='store_true', default=True,
                       help='Auto-detect camera types (default: True)')
    parser.add_argument('--width', type=int, default=640,
                       help='Thermal camera width (default: 640)')
    parser.add_argument('--height', type=int, default=512,
                       help='Thermal camera height (default: 512)')
    parser.add_argument('--disable-rgb', action='store_true',
                       help='Disable RGB camera')

    # Boson SDK settings
    parser.add_argument('--enable-boson-sdk', action='store_true',
                       help='Enable FLIR Boson SDK for serial control (FFC, gain, temperature)')
    parser.add_argument('--boson-com-port', type=str, default='COM7',
                       help='Boson COM port for SDK control (default: COM7)')

    # Thermal backend selection
    parser.add_argument('--thermal-backend', type=str, choices=['opencv', 'flirpy'], default='opencv',
                       help='Thermal camera backend: opencv (8-bit AGC) or flirpy (16-bit Y16 radiometric) (default: opencv)')

    # Processing settings
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda',
                       help='Processing device (default: cuda)')
    parser.add_argument('--palette', type=str, default='ironbow',
                      help='Thermal palette name (default: ironbow)')
    parser.add_argument('--radiometric', action='store_true',
                      help='Enable radiometric temperature measurement (default: False)')

    # Fusion settings
    parser.add_argument('--fusion-mode', type=str, default='thermal_overlay',
                       choices=['alpha_blend', 'detail_inject', 'relief_fusion',
                               'edge_enhanced', 'thermal_overlay',
                               'side_by_side', 'picture_in_picture', 'max_intensity',
                               'feature_weighted'],
                       help='Fusion mode (default: thermal_overlay)')
    parser.add_argument('--fusion-alpha', type=float, default=0.5,
                       help='Fusion alpha for alpha_blend mode (default: 0.5)')
    parser.add_argument('--calibration-file', type=str,
                       help='Camera calibration file for alignment')

    # Inspection settings
    parser.add_argument('--mode', choices=['realtime', 'playback'], default='realtime',
                       help='Inspection mode (default: realtime)')
    parser.add_argument('--playback-file', type=str,
                       help='Video file to play back (required for playback mode)')
    parser.add_argument('--auto-roi', action='store_true',
                       help='Enable automatic ROI detection')

    # GUI settings
    parser.add_argument('--gui', type=str, choices=['qt', 'opencv', 'headless'], default='qt',
                       help='GUI type (default: qt)')
    parser.add_argument('--use-opencv-gui', action='store_true',
                       help='Use simple OpenCV GUI instead of Qt')
    parser.add_argument('--headless', action='store_true',
                       help='Run without GUI')

    # Performance optimization settings
    parser.add_argument('--enable_parallel', type=lambda x: x.lower() == 'true', default=True,
                       help='Enable parallel processing (default: True)')
    parser.add_argument('--max_workers', type=int, default=5,
                       help='Maximum number of worker threads for parallel detection (default: 5)')

    return parser.parse_args()


def main():
    """Main entry point for the Thermal Inspection application."""
    args = parse_arguments()

    logger.info("=" * 80)
    logger.info("Thermal Inspection Fusion Tool")
    logger.info("Transformed from ThermalFusionDrivingAssist")
    logger.info("=" * 80)

    # Initialize Qt app if not using OpenCV GUI
    qt_app = None
    if not args.use_opencv_gui and not args.headless:
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            import signal
            
            qt_app = QApplication(sys.argv)
            logger.info("Qt GUI enabled")
            
            # Enable Ctrl+C to work with Qt event loop
            # Qt blocks SIGINT by default - this timer allows Python to process signals
            def handle_sigint(*args):
                logger.info("Ctrl+C received, shutting down...")
                QApplication.quit()
            
            signal.signal(signal.SIGINT, handle_sigint)
            # Timer allows signal handling during Qt event loop
            timer = QTimer()
            timer.timeout.connect(lambda: None)  # Empty callback to allow signal processing
            timer.start(100)
            
        except ImportError:
            logger.warning("PyQt6 not available, falling back to OpenCV GUI")
            args.use_opencv_gui = True

    # Import the new modular app coordinator
    from .app import ThermalInspectionApp, AppConfig

    # Create config from args and run application
    config = AppConfig.from_args(args)
    app = ThermalInspectionApp(config, qt_app)

    if not app.initialize():
        logger.error("Initialization failed")
        return 1

    app.run()

    return 0


if __name__ == '__main__':
    sys.exit(main())
