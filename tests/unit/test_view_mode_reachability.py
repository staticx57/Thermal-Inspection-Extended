"""
C1: ViewMode.THREE_D_MAPPING was unreachable in the running app - neither
cycle_view_mode() (thermal_inspection/app.py) nor FusionController.set_view_mode
(thermal_inspection/core/fusion_controller.py) included it, and
cycle_view_mode()'s modes.index(self.view_mode) raised ValueError for it
(silently resetting to THERMAL_ONLY) since it was never in the modes list
in the first place - the new THREE_D_MAPPING dispatch branch in app.py's
frame loop could only ever be reached by tests assigning app.view_mode
directly, never by a real user action.

These tests call ThermalInspectionApp.cycle_view_mode unbound against a
lightweight stand-in (following test_mapping_fusion_wiring.py's own
established pattern for exactly this kind of thing), and exercise the real
FusionController - no full ThermalInspectionApp/QApplication construction
needed for either.
"""
from unittest.mock import MagicMock

from thermal_inspection.app import ThermalInspectionApp
from thermal_inspection.core import ViewMode
from thermal_inspection.core.fusion_controller import FusionController


class _CycleStandIn:
    """Bare stand-in exposing only what cycle_view_mode() touches."""

    def __init__(self, view_mode):
        self.view_mode = view_mode
        self.fusion_controller = MagicMock()


class TestCycleViewModeReachesThreeDMapping:
    def test_three_d_mapping_is_in_the_cycle_right_after_three_d(self):
        stand_in = _CycleStandIn(ViewMode.THREE_D)

        ThermalInspectionApp.cycle_view_mode(stand_in)  # must not raise ValueError

        assert stand_in.view_mode == ViewMode.THREE_D_MAPPING
        stand_in.fusion_controller.set_view_mode.assert_called_once_with("3d mapping")

    def test_cycling_from_three_d_mapping_wraps_to_thermal_only_without_raising(self):
        """The actual C1 regression: modes.index(self.view_mode) used to
        raise ValueError here (THREE_D_MAPPING was never in the modes
        list), silently resetting to THERMAL_ONLY via the except branch
        rather than cycling forward normally."""
        stand_in = _CycleStandIn(ViewMode.THREE_D_MAPPING)

        ThermalInspectionApp.cycle_view_mode(stand_in)  # must not raise

        assert stand_in.view_mode == ViewMode.THERMAL_ONLY
        stand_in.fusion_controller.set_view_mode.assert_called_once_with("thermal only")

    def test_full_cycle_visits_every_view_mode_exactly_once(self):
        stand_in = _CycleStandIn(ViewMode.THERMAL_ONLY)
        seen = [stand_in.view_mode]
        for _ in range(7):
            ThermalInspectionApp.cycle_view_mode(stand_in)
            seen.append(stand_in.view_mode)

        assert seen[-1] == ViewMode.THERMAL_ONLY  # wrapped all the way around
        assert seen[:-1] == [
            ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION,
            ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE,
            ViewMode.THREE_D, ViewMode.THREE_D_MAPPING,
        ]


class TestFusionControllerSetViewModeThreeDMapping:
    def test_set_view_mode_accepts_3d_mapping(self):
        controller = FusionController()
        received = []
        controller.on_view_mode_change = lambda vm, overlay: received.append((vm, overlay))

        ok = controller.set_view_mode("3d mapping")

        assert ok is True
        assert controller.state.view_mode == ViewMode.THREE_D_MAPPING
        # Overlay mode falls back to "thermal" - 3D (Mapping or otherwise)
        # has no 2D overlay of its own, same as ViewMode.THREE_D.
        assert received == [(ViewMode.THREE_D_MAPPING, "thermal")]

    def test_set_view_mode_is_case_insensitive(self):
        controller = FusionController()
        assert controller.set_view_mode("3D MAPPING") is True
        assert controller.state.view_mode == ViewMode.THREE_D_MAPPING
