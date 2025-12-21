"""
Camera Manager Dialog for managing camera assignments.
"""

import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QSpinBox, QMessageBox
)

logger = logging.getLogger(__name__)


class CameraManagerDialog(QDialog):
    """Dialog to manage camera assignments."""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Camera Management")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Camera Status Group
        status_group = QGroupBox("Current Assignment")
        status_layout = QGridLayout()

        status_layout.addWidget(QLabel("Thermal Camera:"), 0, 0)
        args_obj = getattr(self.app, 'args', None)
        thermal_dev = getattr(args_obj, 'thermal_device', 0) if args_obj is not None else 0
        if thermal_dev is None:
            thermal_dev = 0
        self.thermal_label = QLabel(f"Device {thermal_dev}")
        status_layout.addWidget(self.thermal_label, 0, 1)

        status_layout.addWidget(QLabel("RGB Camera:"), 1, 0)
        rgb_dev = getattr(args_obj, 'rgb_device', None) if args_obj is not None else None
        self.rgb_label = QLabel(f"Device {rgb_dev if rgb_dev is not None else 'Auto'}")
        status_layout.addWidget(self.rgb_label, 1, 1)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Actions
        btn_layout = QHBoxLayout()

        self.redetect_btn = QPushButton("Re-Detect Cameras")
        self.redetect_btn.clicked.connect(self._on_redetect)
        self.redetect_btn.setToolTip("Stop capture and re-detect available cameras")
        btn_layout.addWidget(self.redetect_btn)

        self.swap_btn = QPushButton("Swap Cameras")
        self.swap_btn.clicked.connect(self._on_swap)
        self.swap_btn.setToolTip("Swap Thermal and RGB camera sources")
        btn_layout.addWidget(self.swap_btn)

        layout.addLayout(btn_layout)

        # Manual Assignment Group
        manual_group = QGroupBox("Manual Assignment")
        manual_layout = QGridLayout()

        manual_layout.addWidget(QLabel("Thermal Device ID:"), 0, 0)
        self.thermal_spin = QSpinBox()
        self.thermal_spin.setRange(0, 10)
        args_obj = getattr(self.app, 'args', None)
        thermal_dev = getattr(args_obj, 'thermal_device', 0) if args_obj is not None else 0
        if thermal_dev is None:
            thermal_dev = 0
        self.thermal_spin.setValue(thermal_dev)
        manual_layout.addWidget(self.thermal_spin, 0, 1)

        manual_layout.addWidget(QLabel("RGB Device ID:"), 1, 0)
        self.rgb_spin = QSpinBox()
        self.rgb_spin.setRange(0, 10)
        val = getattr(args_obj, 'rgb_device', 0) if args_obj is not None else 0
        if val is None:
            val = 0
        self.rgb_spin.setValue(val)
        manual_layout.addWidget(self.rgb_spin, 1, 1)

        self.apply_btn = QPushButton("Apply Assignment")
        self.apply_btn.clicked.connect(self._on_apply)
        manual_layout.addWidget(self.apply_btn, 2, 0, 1, 2)

        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)

        # Close
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _on_swap(self):
        if QMessageBox.question(
            self, "Confirm Swap",
            "This will stop capture, swap cameras, and restart.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.app.swap_cameras()
            self._update_labels()
            QMessageBox.information(self, "Success", "Cameras swapped successfully.")

    def _on_redetect(self):
        """Re-detect cameras and reassign."""
        if QMessageBox.question(
            self, "Confirm Re-Detection",
            "This will stop capture, detect cameras, and restart.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                from thermal_inspection.cameras.camera_factory import autodetect_camera_types

                logger.info("Re-detecting cameras...")
                t_id, r_id = autodetect_camera_types()

                if t_id is None and r_id is None:
                    QMessageBox.warning(
                        self, "Detection Failed",
                        "No cameras detected. Please check connections."
                    )
                    return

                thermal_id = t_id if t_id is not None else 1
                rgb_id = r_id if r_id is not None else 0

                logger.info(f"Re-detection results: Thermal={thermal_id}, RGB={rgb_id}")

                self.app.reassign_cameras(thermal_id, rgb_id)

                self.thermal_spin.setValue(thermal_id)
                self.rgb_spin.setValue(rgb_id)

                self._update_labels()
                QMessageBox.information(
                    self, "Success",
                    f"Cameras re-detected and assigned:\nThermal: Device {thermal_id}\nRGB: Device {rgb_id}"
                )

            except Exception as e:
                logger.error(f"Re-detection failed: {e}")
                QMessageBox.critical(self, "Error", f"Re-detection failed: {e}")

    def _on_apply(self):
        t_id = self.thermal_spin.value()
        r_id = self.rgb_spin.value()

        if t_id == r_id:
            QMessageBox.warning(
                self, "Invalid Assignment",
                "Thermal and RGB cameras cannot share the same device ID."
            )
            return

        if QMessageBox.question(
            self, "Confirm Assignment",
            f"Reassign cameras?\nThermal: {t_id}\nRGB: {r_id}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.app.reassign_cameras(t_id, r_id)
            self._update_labels()
            QMessageBox.information(self, "Success", "Cameras reassigned successfully.")

    def _update_labels(self):
        args_obj = getattr(self.app, 'args', None)
        thermal_dev = getattr(args_obj, 'thermal_device', 0) if args_obj is not None else 0
        if thermal_dev is None:
            thermal_dev = 0
        self.thermal_label.setText(f"Device {thermal_dev}")
        rgb_dev = getattr(args_obj, 'rgb_device', None) if args_obj is not None else None
        self.rgb_label.setText(f"Device {rgb_dev if rgb_dev is not None else 'Auto'}")
        self.thermal_spin.setValue(thermal_dev)
        val = rgb_dev if rgb_dev is not None else 0
        self.rgb_spin.setValue(val)
