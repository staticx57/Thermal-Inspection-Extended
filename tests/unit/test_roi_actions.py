"""ROI manager/controller actions behind the ROI Manager panel: lock, visibility, rename, duplicate, delete protection."""
import pytest

from thermal_inspection.core.roi_controller import ROIController
from thermal_inspection.processing.roi_manager import ROIManager, ROIType


@pytest.fixture
def mgr():
    m = ROIManager()
    m.set_resolution(640, 512)
    return m


class TestLockVisibleRename:
    def test_locked_roi_cannot_be_deleted_or_renamed_but_can_be_unlocked(self, mgr):
        r = mgr.create_rectangle_roi(10, 10, 50, 50, label="Fuse box")
        assert mgr.set_locked(r.roi_id, True)
        assert not mgr.delete_roi(r.roi_id) and r.roi_id in mgr.rois          # protected
        assert not mgr.rename_roi(r.roi_id, "New") and r.label == "Fuse box"
        mgr.update_roi(r.roi_id, label="Sneaky")                              # the existing guard still holds
        assert r.label == "Fuse box"
        assert mgr.set_locked(r.roi_id, False)                                # update_roi() could never do this
        assert mgr.rename_roi(r.roi_id, "  New name ") and r.label == "New name"
        assert mgr.delete_roi(r.roi_id) and r.roi_id not in mgr.rois

    def test_force_delete_overrides_lock(self, mgr):
        r = mgr.create_rectangle_roi(0, 0, 5, 5)
        mgr.set_locked(r.roi_id, True)
        assert mgr.delete_roi(r.roi_id, force=True)

    def test_empty_name_refused_and_unknown_ids_are_safe(self, mgr):
        r = mgr.create_rectangle_roi(0, 0, 5, 5, label="Keep")
        assert not mgr.rename_roi(r.roi_id, "   ") and r.label == "Keep"
        assert not mgr.set_locked("nope", True) and not mgr.set_visible("nope", True)
        assert not mgr.rename_roi("nope", "x") and not mgr.delete_roi("nope")

    def test_hidden_roi_is_excluded_from_active_but_still_listed(self, mgr):
        a = mgr.create_rectangle_roi(0, 0, 5, 5)
        b = mgr.create_rectangle_roi(10, 10, 5, 5)
        mgr.set_visible(b.roi_id, False)
        assert [r.roi_id for r in mgr.get_all_rois()] == [a.roi_id]
        assert {r.roi_id for r in mgr.get_all_rois(active_only=False)} == {a.roi_id, b.roi_id}
        mgr.set_visible(b.roi_id, True)
        assert len(mgr.get_all_rois()) == 2


class TestDuplicate:
    def test_copy_is_shifted_manual_unlocked_and_keeps_settings(self, mgr):
        r = mgr.create_rectangle_roi(100, 100, 40, 30, label="Bearing")
        r.custom_palette, r.emissivity = "IRON", 0.9
        mgr.set_locked(r.roi_id, True)
        c = mgr.duplicate_roi(r.roi_id)
        assert c.roi_id != r.roi_id and c.label == "Bearing copy" and not c.locked and c.active
        assert c.points == [(120, 120), (160, 150)]                           # shifted by (20, 20)
        assert (c.custom_palette, c.emissivity, c.roi_type) == ("IRON", 0.9, ROIType.RECTANGLE)
        assert c.normalized_points == [(120 / 640, 120 / 512), (160 / 640, 150 / 512)]
        assert c.roi_id in mgr.rois

    def test_copy_stays_inside_the_frame(self, mgr):
        r = mgr.create_rectangle_roi(600, 480, 39, 31)                        # touching the bottom-right corner
        c = mgr.duplicate_roi(r.roi_id)
        xs = [p[0] for p in c.points]
        ys = [p[1] for p in c.points]
        assert max(xs) <= 639 and max(ys) <= 511 and min(xs) >= 0 and min(ys) >= 0

    def test_duplicate_unknown_is_none(self, mgr):
        assert mgr.duplicate_roi("nope") is None

    def test_area_pixels(self, mgr):
        r = mgr.create_rectangle_roi(0, 0, 10, 10)
        assert 100 <= mgr.area_pixels(r.roi_id) <= 121                        # rectangle fill includes the edge pixels


class TestController:
    def _controller(self, mgr):
        c = ROIController()
        c.set_roi_manager(mgr)
        seen = []
        c.on_rois_changed = lambda data: seen.append(data)
        return c, seen

    def test_actions_notify_and_all_rois_includes_hidden(self, mgr):
        a = mgr.create_rectangle_roi(0, 0, 5, 5, label="A")
        c, seen = self._controller(mgr)
        assert c.set_roi_visible(a.roi_id, False)
        assert seen[-1]["rois"] == [] and [r.roi_id for r in seen[-1]["all_rois"]] == [a.roi_id]
        assert c.rois == [] and [r.roi_id for r in c.all_rois] == [a.roi_id]
        assert c.set_roi_locked(a.roi_id, True) and c.rename_roi(a.roi_id, "B") is False     # locked: no rename
        copy = c.duplicate_roi(a.roi_id)
        assert copy is not None and len(seen) >= 3

    def test_delete_of_locked_roi_is_refused_and_keeps_palette(self, mgr):
        a = mgr.create_rectangle_roi(0, 0, 5, 5)
        mgr.set_locked(a.roi_id, True)
        c, seen = self._controller(mgr)
        cleared = []
        c.palette_manager = type("P", (), {"clear_roi_palette": lambda self, rid: cleared.append(rid)})()
        c.delete_roi(a.roi_id)
        assert a.roi_id in mgr.rois and cleared == [] and seen == []          # nothing changed, nobody told
        mgr.set_locked(a.roi_id, False)
        c.delete_roi(a.roi_id)
        assert a.roi_id not in mgr.rois and cleared == [a.roi_id]
