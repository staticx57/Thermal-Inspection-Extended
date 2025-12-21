
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from thermal_inspection.app import ThermalInspectionApp

class TestAppWiring(unittest.TestCase):
    def setUp(self):
        self.app = ThermalInspectionApp(qt_app=None)
        
        # Mock the internal processors
        self.app.fusion_processor = MagicMock()
        self.app.thermal_analyzer = MagicMock()
        self.app.thermal_processor = MagicMock()
        self.app.radiometric_controller = MagicMock()

    def test_fusion_delegates(self):
        """Verify fusion settings are delegated to fusion_processor."""
        # Strength -> set_intensity
        self.app.set_fusion_strength(0.75)
        self.app.fusion_processor.set_intensity.assert_called_with(0.75)

        # Fuzziness -> set_edge_blur
        self.app.set_fusion_fuzziness(0.5)
        self.app.fusion_processor.set_edge_blur.assert_called()
        
        # Edge Strength -> set_edge_strength (inverted logic)
        self.app.set_edge_strength(0.8)
        self.app.fusion_processor.set_edge_strength.assert_called()

        # Edge Color
        self.app.set_edge_color('red')
        self.app.fusion_processor.set_edge_color.assert_called_with((0, 0, 255))

    def test_detail_delegates(self):
        """Verify detail settings are delegated."""
        self.app.set_detail_strength(1.5)
        # Check attribute set
        self.assertEqual(self.app.fusion_processor.detail_strength, 1.5)
        
        self.app.set_detail_quality('high')
        self.assertEqual(self.app.fusion_processor.detail_quality, 1.0)

    def test_environmental_delegates(self):
        """Verify environmental settings are delegated to thermal_analyzer."""
        self.app.set_emissivity(0.95)
        self.app.thermal_analyzer.set_emissivity.assert_called_with(0.95)

        self.app.set_atmospheric_temperature(300.0)
        self.app.thermal_analyzer.set_atmospheric_temperature.assert_called_with(300.0)

        self.app.set_atmospheric_transmission(0.99)
        self.app.thermal_analyzer.set_atmospheric_transmission.assert_called_with(0.99)

if __name__ == '__main__':
    unittest.main()
