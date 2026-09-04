"""
Unit Tests for ROIManager

Tests the ROI (Region of Interest) management including:
- ROI creation and deletion
- ROI types (rectangle, polygon, ellipse, circle)
- ROI queries and retrieval
- Automatic ROI detection
"""

import pytest
import numpy as np
from thermal_inspection.processing.roi_manager import ROIManager, ROI, ROIType, ROISource


class TestROIManagerInit:
    """Tests for ROIManager initialization."""

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test manager initializes with empty ROI list."""
        manager = ROIManager()
        assert manager is not None
        assert len(manager.get_all_rois()) == 0

    @pytest.mark.unit
    def test_initialization_with_config(self):
        """Test manager initializes with configuration."""
        config = {"min_area": 100, "max_rois": 50}
        manager = ROIManager(config=config)
        assert manager is not None
        assert manager.config.get("min_area") == 100


class TestROICreation:
    """Tests for ROI creation."""

    @pytest.mark.unit
    def test_create_rectangle_roi(self):
        """Test creating a rectangular ROI."""
        manager = ROIManager()
        roi = manager.create_rectangle_roi(
            x=100, y=100, w=200, h=150,
            label="Test Rectangle"
        )

        assert roi is not None
        assert roi.roi_id is not None
        assert len(manager.get_all_rois()) == 1

    @pytest.mark.unit
    def test_create_rectangle_roi_with_source(self):
        """Test creating ROI with specific source."""
        manager = ROIManager()
        roi = manager.create_rectangle_roi(
            x=100, y=100, w=200, h=150,
            source=ROISource.AUTO_TEMPERATURE
        )

        assert roi.roi_source == ROISource.AUTO_TEMPERATURE

    @pytest.mark.unit
    def test_create_manual_roi_polygon(self):
        """Test creating a polygon ROI."""
        manager = ROIManager()
        points = [(100, 100), (300, 100), (300, 250), (200, 300), (100, 250)]
        roi = manager.create_manual_roi(
            roi_type=ROIType.POLYGON,
            points=points,
            label="Test Polygon"
        )

        assert roi is not None
        assert roi.roi_type == ROIType.POLYGON
        assert roi.label == "Test Polygon"

    @pytest.mark.unit
    def test_add_roi_object(self):
        """Test adding an ROI object directly."""
        manager = ROIManager()
        roi = ROI(
            roi_id="test_roi_1",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (300, 100), (300, 250), (100, 250)],
            label="Direct Add"
        )

        roi_id = manager.add_roi(roi)
        assert roi_id == "test_roi_1"
        assert len(manager.get_all_rois()) == 1

    @pytest.mark.unit
    def test_roi_unique_ids(self):
        """Test that each ROI gets a unique ID."""
        manager = ROIManager()

        roi1 = manager.create_rectangle_roi(x=10, y=10, w=50, h=50)
        roi2 = manager.create_rectangle_roi(x=100, y=100, w=50, h=50)
        roi3 = manager.create_rectangle_roi(x=200, y=200, w=50, h=50)

        assert roi1.roi_id != roi2.roi_id
        assert roi2.roi_id != roi3.roi_id
        assert roi1.roi_id != roi3.roi_id


class TestROIRetrieval:
    """Tests for ROI retrieval operations."""

    @pytest.mark.unit
    def test_get_roi_by_id(self):
        """Test retrieving ROI by ID."""
        manager = ROIManager()
        created_roi = manager.create_rectangle_roi(x=100, y=100, w=50, h=50)

        roi = manager.get_roi(created_roi.roi_id)
        assert roi is not None
        assert roi.roi_id == created_roi.roi_id

    @pytest.mark.unit
    def test_get_nonexistent_roi(self):
        """Test retrieving non-existent ROI returns None."""
        manager = ROIManager()
        roi = manager.get_roi("nonexistent_id")
        assert roi is None

    @pytest.mark.unit
    def test_get_all_rois(self):
        """Test getting all ROIs."""
        manager = ROIManager()
        manager.create_rectangle_roi(x=10, y=10, w=50, h=50)
        manager.create_rectangle_roi(x=100, y=100, w=50, h=50)
        manager.create_rectangle_roi(x=200, y=200, w=50, h=50)

        rois = manager.get_all_rois()
        assert len(rois) == 3

    @pytest.mark.unit
    def test_get_all_rois_active_only(self):
        """Test getting only active ROIs."""
        manager = ROIManager()
        roi1 = manager.create_rectangle_roi(x=10, y=10, w=50, h=50)
        roi2 = manager.create_rectangle_roi(x=100, y=100, w=50, h=50)

        # Deactivate one ROI
        roi1.active = False

        active_rois = manager.get_all_rois(active_only=True)
        assert len(active_rois) == 1
        assert active_rois[0].roi_id == roi2.roi_id


class TestROIDeletion:
    """Tests for ROI deletion."""

    @pytest.mark.unit
    def test_delete_roi(self):
        """Test deleting a single ROI."""
        manager = ROIManager()
        roi = manager.create_rectangle_roi(x=100, y=100, w=50, h=50)

        manager.delete_roi(roi.roi_id)
        assert len(manager.get_all_rois()) == 0

    @pytest.mark.unit
    def test_delete_nonexistent_roi(self):
        """Test deleting non-existent ROI doesn't crash."""
        manager = ROIManager()
        # Should not raise exception
        manager.delete_roi("nonexistent_id")

    @pytest.mark.unit
    def test_clear_all_rois(self):
        """Test clearing all ROIs."""
        manager = ROIManager()
        manager.create_rectangle_roi(x=10, y=10, w=50, h=50)
        manager.create_rectangle_roi(x=100, y=100, w=50, h=50)

        manager.clear_all_rois()
        assert len(manager.get_all_rois()) == 0

    @pytest.mark.unit
    def test_delete_rois_by_source(self):
        """Test deleting ROIs by source."""
        manager = ROIManager()
        manager.create_rectangle_roi(x=10, y=10, w=50, h=50, source=ROISource.MANUAL)
        manager.create_rectangle_roi(x=100, y=100, w=50, h=50, source=ROISource.AUTO_TEMPERATURE)
        manager.create_rectangle_roi(x=200, y=200, w=50, h=50, source=ROISource.AUTO_TEMPERATURE)

        manager.delete_rois_by_source(ROISource.AUTO_TEMPERATURE)

        remaining = manager.get_all_rois()
        assert len(remaining) == 1
        assert remaining[0].roi_source == ROISource.MANUAL


class TestROI:
    """Tests for ROI dataclass."""

    @pytest.mark.unit
    def test_roi_get_bbox(self):
        """Test ROI bounding box calculation."""
        roi = ROI(
            roi_id="test",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (300, 100), (300, 250), (100, 250)]
        )

        bbox = roi.get_bbox()
        assert bbox[0] == 100  # x
        assert bbox[1] == 100  # y
        assert bbox[2] == 200  # width
        assert bbox[3] == 150  # height

    @pytest.mark.unit
    def test_roi_get_mask(self):
        """Test ROI mask generation."""
        roi = ROI(
            roi_id="test",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (200, 100), (200, 200), (100, 200)]
        )

        mask = roi.get_mask((512, 640))
        assert mask is not None
        assert mask.shape == (512, 640)
        assert mask.dtype == np.uint8
        assert np.sum(mask) > 0  # Non-empty mask

    @pytest.mark.unit
    def test_roi_get_centroid(self):
        """Test ROI centroid calculation."""
        roi = ROI(
            roi_id="test",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (200, 100), (200, 200), (100, 200)]
        )

        centroid = roi.get_centroid()
        assert centroid is not None
        assert centroid[0] == 150  # x center
        assert centroid[1] == 150  # y center

    @pytest.mark.unit
    def test_roi_contains_point(self):
        """Test ROI point containment."""
        roi = ROI(
            roi_id="test",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (200, 100), (200, 200), (100, 200)]
        )

        assert roi.contains_point((150, 150)) is True  # Inside
        assert roi.contains_point((50, 50)) is False   # Outside

    @pytest.mark.unit
    def test_roi_to_dict(self):
        """Test ROI serialization to dict."""
        roi = ROI(
            roi_id="test",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (200, 200)],
            label="Test ROI"
        )

        data = roi.to_dict()
        assert data["roi_id"] == "test"
        assert data["label"] == "Test ROI"

    @pytest.mark.unit
    def test_roi_from_dict(self):
        """Test ROI deserialization from dict."""
        data = {
            "roi_id": "test",
            "roi_type": "rectangle",
            "roi_source": "manual",
            "points": [[100, 100], [200, 200]],
            "label": "Test ROI"
        }

        roi = ROI.from_dict(data)
        assert roi.roi_id == "test"
        assert roi.roi_type == ROIType.RECTANGLE
        assert roi.label == "Test ROI"

    @pytest.mark.unit
    def test_to_dict_from_dict_round_trip_preserves_every_field(self):
        """Regression test for a general-audit finding (2026-09-03):
        to_dict() only serialized 10 of the dataclass's ~18 fields,
        silently dropping selected/custom_palette/the temp_* fields/
        emissivity/temp_history/normalized_points/source_resolution on
        every save -> load round trip (a session restart). Every field
        gets a non-default value here so a dropped one is caught."""
        roi = ROI(
            roi_id="test",
            roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.MANUAL,
            points=[(100, 100), (200, 200)],
            label="Test ROI",
            color=(10, 20, 30),
            active=False,
            locked=True,
            selected=True,
            custom_palette="ironbow",
            metadata={"note": "hi"},
            temp_min=10.0,
            temp_max=90.0,
            temp_avg=50.0,
            temp_std=5.0,
            emissivity=0.95,
            temp_history=[48.0, 49.0, 50.0],
            normalized_points=[(0.1, 0.1), (0.2, 0.2)],
            source_resolution=(1280, 800),
        )

        restored = ROI.from_dict(roi.to_dict())

        for field_name in (
            "roi_id", "roi_type", "roi_source", "points", "label", "color",
            "active", "locked", "selected", "custom_palette", "metadata",
            "temp_min", "temp_max", "temp_avg", "temp_std", "emissivity",
            "temp_history", "normalized_points", "source_resolution",
        ):
            assert getattr(restored, field_name) == getattr(roi, field_name), (
                f"field '{field_name}' did not survive a to_dict/from_dict round trip"
            )


class TestROITypes:
    """Tests for ROI type enumeration."""

    @pytest.mark.unit
    def test_roi_types_exist(self):
        """Test that all ROI types are defined."""
        assert ROIType.RECTANGLE is not None
        assert ROIType.POLYGON is not None
        assert ROIType.ELLIPSE is not None
        assert ROIType.CIRCLE is not None

    @pytest.mark.unit
    def test_roi_sources_exist(self):
        """Test that all ROI sources are defined."""
        assert ROISource.MANUAL is not None
        assert ROISource.AUTO_TEMPERATURE is not None
        assert ROISource.AUTO_GRADIENT is not None
        assert ROISource.AUTO_MOTION is not None
        assert ROISource.AUTO_EDGE is not None


class TestAutoROIDetection:
    """Tests for automatic ROI detection."""

    @pytest.mark.unit
    def test_detect_temperature_rois(self, thermal_frame_8bit):
        """Test auto-detection by temperature threshold."""
        manager = ROIManager()
        manager.set_resolution(640, 512)

        rois = manager.detect_temperature_rois(thermal_frame_8bit)

        assert isinstance(rois, list)
        # Detection may or may not find ROIs depending on threshold

    @pytest.mark.unit
    def test_detect_gradient_rois(self, thermal_frame_8bit):
        """Test auto-detection by gradient."""
        manager = ROIManager()
        manager.set_resolution(640, 512)

        rois = manager.detect_gradient_rois(thermal_frame_8bit)

        assert isinstance(rois, list)


class TestROIProperties:
    """Tests for ROI property access and modification."""

    @pytest.mark.unit
    def test_roi_label(self):
        """Test ROI label property."""
        manager = ROIManager()
        roi = manager.create_rectangle_roi(
            x=100, y=100, w=50, h=50,
            label="My ROI"
        )

        assert roi.label == "My ROI"

    @pytest.mark.unit
    def test_update_roi(self):
        """Test updating ROI properties."""
        manager = ROIManager()
        roi = manager.create_rectangle_roi(
            x=100, y=100, w=50, h=50,
            label="Original"
        )

        manager.update_roi(roi.roi_id, label="Updated")

        updated_roi = manager.get_roi(roi.roi_id)
        assert updated_roi.label == "Updated"

    @pytest.mark.unit
    def test_roi_color(self):
        """Test ROI color property."""
        manager = ROIManager()
        roi = manager.create_manual_roi(
            roi_type=ROIType.RECTANGLE,
            points=[(100, 100), (150, 100), (150, 150), (100, 150)],
            color=(255, 0, 0)  # Red
        )

        assert roi.color == (255, 0, 0)


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.unit
    def test_empty_roi_list(self):
        """Test operations on empty ROI list."""
        manager = ROIManager()

        assert len(manager.get_all_rois()) == 0
        assert manager.get_roi("any_id") is None

    @pytest.mark.unit
    def test_roi_with_default_color(self):
        """Test ROI with default color."""
        manager = ROIManager()
        roi = manager.create_rectangle_roi(x=100, y=100, w=50, h=50)

        # Should have default color (0, 255, 0) - green
        assert roi.color == (0, 255, 0)


class TestCalculateIou:
    """
    Regression tests for a general-audit finding (2026-09-03):
    calculate_iou() had no zero-guard on its union-area denominator,
    unlike cleanup_overlapping_rois' own containment calc three lines
    below its call site. A zero-area box (e.g. a manual rectangle ROI
    created by a click without drag) reaching this function used to
    raise ZeroDivisionError.
    """

    @pytest.mark.unit
    def test_zero_area_boxes_do_not_raise(self):
        manager = ROIManager()
        # Two degenerate (zero-area) boxes at the same position - the
        # exact case that used to make the union-area denominator 0.
        assert manager.calculate_iou((10, 10, 0, 0), (10, 10, 0, 0)) == 0.0

    @pytest.mark.unit
    def test_identical_boxes_have_iou_one(self):
        manager = ROIManager()
        assert manager.calculate_iou((0, 0, 100, 100), (0, 0, 100, 100)) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_non_overlapping_boxes_have_iou_zero(self):
        manager = ROIManager()
        assert manager.calculate_iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0

    @pytest.mark.unit
    def test_cleanup_overlapping_rois_does_not_raise_with_a_zero_area_manual_roi(self):
        """The realistic path this bug was reachable from: a manual
        rectangle ROI with zero area (a click without drag) coexisting
        with an auto-detected ROI when cleanup runs."""
        manager = ROIManager()
        manager.create_manual_roi(
            roi_type=ROIType.RECTANGLE, points=[(50, 50), (50, 50)],
        )
        auto_roi = ROI(
            roi_id="auto1", roi_type=ROIType.RECTANGLE,
            roi_source=ROISource.AUTO_TEMPERATURE,
            points=[(10, 10), (60, 60)],
        )
        manager.rois[auto_roi.roi_id] = auto_roi

        manager.cleanup_overlapping_rois()  # must not raise
