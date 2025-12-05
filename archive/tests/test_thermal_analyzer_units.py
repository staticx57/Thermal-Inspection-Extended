
import unittest
import numpy as np
from thermal_analyzer import ThermalAnalyzer, TemperatureUnit

class TestThermalAnalyzerUnits(unittest.TestCase):
    def setUp(self):
        self.analyzer = ThermalAnalyzer(config={'radiometric': True})
        # Mock Y16 frame (Kelvin * 100)
        # 300K = 26.85 C = 80.33 F
        # 30000 pixel value
        self.frame = np.full((100, 100), 30000, dtype=np.uint16)
        # Add a hot spot
        self.frame[50, 50] = 31000 # 310K = 36.85 C = 98.33 F

    def test_celsius_default(self):
        self.analyzer.set_temperature_unit('C')
        hot_spots = self.analyzer.detect_hot_spots(self.frame)
        self.assertTrue(len(hot_spots) > 0)
        hs = hot_spots[0]
        self.assertEqual(hs.unit, "°C")
        self.assertAlmostEqual(hs.max_temp, 36.85, places=1)

    def test_fahrenheit_switching(self):
        self.analyzer.set_temperature_unit('F')
        hot_spots = self.analyzer.detect_hot_spots(self.frame)
        self.assertTrue(len(hot_spots) > 0)
        hs = hot_spots[0]
        self.assertEqual(hs.unit, "°F")
        # 310K = 36.85 C -> 98.33 F
        self.assertAlmostEqual(hs.max_temp, 98.33, places=1)

    def test_kelvin_switching(self):
        self.analyzer.set_temperature_unit('K')
        hot_spots = self.analyzer.detect_hot_spots(self.frame)
        self.assertTrue(len(hot_spots) > 0)
        hs = hot_spots[0]
        self.assertEqual(hs.unit, "K")
        self.assertAlmostEqual(hs.max_temp, 310.0, places=1)

    def test_raw_mode(self):
        self.analyzer.set_radiometric_mode(False)
        hot_spots = self.analyzer.detect_hot_spots(self.frame)
        self.assertTrue(len(hot_spots) > 0)
        hs = hot_spots[0]
        self.assertEqual(hs.unit, " (raw)")
        self.assertEqual(hs.max_temp, 31000)

    def test_analyze_frame(self):
        # Set a baseline
        self.analyzer.set_baseline(25.0)
        
        # Test Celsius
        self.analyzer.set_temperature_unit('C')
        stats = self.analyzer.analyze_frame(self.frame)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.unit, "°C")
        # Mean of 30000 (26.85 C) with one hot spot 31000 (36.85 C)
        # Mean will be slightly above 26.85
        self.assertGreater(stats.mean_temp, 26.8)
        self.assertIsNotNone(stats.relative_mean)
        
        # Test Fahrenheit
        self.analyzer.set_temperature_unit('F')
        stats = self.analyzer.analyze_frame(self.frame)
        self.assertEqual(stats.unit, "°F")
        # 26.85 C -> 80.33 F
        self.assertGreater(stats.mean_temp, 80.0)
        self.assertIsNotNone(stats.relative_mean)

if __name__ == '__main__':
    unittest.main()
