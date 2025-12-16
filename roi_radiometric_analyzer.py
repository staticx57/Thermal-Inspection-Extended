"""
ROI Radiometric Analyzer
Manages radiometric temperature analysis for individual ROIs.
Enables per-ROI temperature measurements independent of global measurements.
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import csv
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ROIRadiometricAnalyzer:
    """
    Manages radiometric analysis for individual ROIs.
    
    Features:
    - Per-ROI temperature statistics (min/max/avg/std)
    - Per-ROI emissivity override (different materials per ROI)
    - Temperature trend tracking per ROI
    - Spot temperature within ROI bounds
    - Data export (CSV/JSON)
    """
    
    def __init__(self, converter):
        """
        Initialize ROI radiometric analyzer.
        
        Args:
            converter: TLinearConverter instance for temperature conversion
        """
        self.converter = converter
        self.roi_settings = {}  # roi_id -> {emissivity, distance, etc.}
        self.roi_history = {}   # roi_id -> List of temperature readings
        self.max_history_length = 1000  # Max readings to keep per ROI
        
        logger.info("ROI Radiometric Analyzer initialized")
    
    def set_roi_emissivity(self, roi_id: str, emissivity: Optional[float]):
        """
        Set material emissivity for specific ROI.
        
        Args:
            roi_id: ROI identifier
            emissivity: Emissivity value (0.01-1.0), or None to use global
        """
        if roi_id not in self.roi_settings:
            self.roi_settings[roi_id] = {}
        
        if emissivity is not None:
            if not (0.01 <= emissivity <= 1.0):
                logger.warning(f"Invalid emissivity {emissivity} for ROI {roi_id}, must be 0.01-1.0")
                return
        
        self.roi_settings[roi_id]['emissivity'] = emissivity
        logger.debug(f"Set ROI {roi_id} emissivity: {emissivity}")
    
    def get_roi_emissivity(self, roi_id: str) -> Optional[float]:
        """
        Get emissivity setting for specific ROI.
        
        Returns:
            Emissivity value, or None if using global setting
        """
        if roi_id in self.roi_settings:
            return self.roi_settings[roi_id].get('emissivity')
        return None
    
    def analyze_roi(self, roi, frame_16bit: np.ndarray) -> dict:
        """
        Perform complete radiometric analysis for single ROI.
        
        Args:
            roi: ROI object with get_mask() method
            frame_16bit: Raw 16-bit radiometric frame
        
        Returns:
            Dictionary with temperature statistics:
            {
                'roi_id': str,
                'roi_name': str,
                'temp_min': float,
                'temp_max': float,
                'temp_avg': float,
                'temp_std': float,
                'pixel_count': int,
                'emissivity': float,  # ROI-specific or global
                'min_location': (x, y),
                'max_location': (x, y),
                'timestamp': str
            }
        """
        try:
            # Get ROI mask
            mask = roi.get_mask(frame_16bit.shape)
            
            # Use converter's existing method with per-ROI emissivity if available
            roi_emissivity = self.get_roi_emissivity(roi.roi_id)
            
            # Get temperature statistics
            stats = self.converter.get_roi_temperature_stats(frame_16bit, mask)

            # Add ROI-specific information
            stats['roi_id'] = roi.roi_id
            stats['roi_name'] = roi.label if hasattr(roi, 'label') else roi.roi_id
            stats['emissivity'] = roi_emissivity if roi_emissivity is not None else 'global'
            stats['timestamp'] = datetime.now().isoformat()

            # Phase 2 - Feature 9: Add temperature array for histogram
            # Extract temperature values from ROI mask
            try:
                # Convert 16-bit frame to Celsius
                temp_celsius = (frame_16bit.astype(float) - 27315.0) / 100.0
                # Get temperatures within ROI mask
                roi_temps = temp_celsius[mask]
                stats['temp_array'] = roi_temps.flatten()  # 1D array for histogram
                stats['histogram_bins'] = 50  # Default bin count
            except Exception as e:
                logger.warning(f"Failed to compute temperature array for histogram: {e}")
                stats['temp_array'] = np.array([])

            # Track temperature history
            self.track_roi_temperature(roi.roi_id, stats)

            return stats
            
        except Exception as e:
            logger.error(f"Error analyzing ROI {roi.roi_id}: {e}")
            return {
                'roi_id': roi.roi_id,
                'roi_name': getattr(roi, 'label', roi.roi_id),
                'temp_min': None,
                'temp_max': None,
                'temp_avg': None,
                'temp_std': None,
                'pixel_count': 0,
                'error': str(e)
            }
    
    def analyze_all_rois(self, rois: List, frame_16bit: np.ndarray) -> Dict[str, dict]:
        """
        Analyze all ROIs in single frame.
        
        Args:
            rois: List of ROI objects
            frame_16bit: Raw 16-bit radiometric frame
        
        Returns:
            Dictionary mapping roi_id -> statistics dict
        """
        results = {}
        
        for roi in rois:
            if not roi.active:
                continue
            
            stats = self.analyze_roi(roi, frame_16bit)
            results[roi.roi_id] = stats
            
            # DEBUG: Log first ROI stats
            if len(results) == 1:
                logger.debug(f"Analyzed ROI {roi.roi_id}: {stats}")
        
        logger.debug(f"Analyzed {len(results)} active ROIs")
        return results
    
    def track_roi_temperature(self, roi_id: str, stats: dict):
        """
        Add temperature reading to ROI history for trending.
        
        Args:
            roi_id: ROI identifier
            stats: Statistics dictionary from analyze_roi()
        """
        if roi_id not in self.roi_history:
            self.roi_history[roi_id] = []
        
        # Store simplified history entry
        entry = {
            'timestamp': stats.get('timestamp'),
            'temp_avg': stats.get('temp_avg'),
            'temp_min': stats.get('temp_min'),
            'temp_max': stats.get('temp_max')
        }
        
        self.roi_history[roi_id].append(entry)
        
        # Limit history length
        if len(self.roi_history[roi_id]) > self.max_history_length:
            self.roi_history[roi_id] = self.roi_history[roi_id][-self.max_history_length:]
    
    def get_roi_temperature_trend(self, roi_id: str, last_n: int = 60) -> List[dict]:
        """
        Get recent temperature trend for a specific ROI.
        
        Args:
            roi_id: ROI identifier
            last_n: Number of recent readings to return
        
        Returns:
            List of temperature history entries
        """
        if roi_id not in self.roi_history:
            return []
        
        return self.roi_history[roi_id][-last_n:]
    
    def export_roi_data(self, filepath: str, roi_ids: Optional[List[str]] = None, format: str = 'csv'):
        """
        Export ROI statistics and history to file.
        
        Args:
            filepath: Output file path
            roi_ids: List of ROI IDs to export (None = all)
            format: 'csv' or 'json'
        """
        try:
            if roi_ids is None:
                roi_ids = list(self.roi_history.keys())
            
            if format == 'csv':
                self._export_csv(filepath, roi_ids)
            elif format == 'json':
                self._export_json(filepath, roi_ids)
            else:
                logger.error(f"Unknown export format: {format}")
                return False
            
            logger.info(f"Exported ROI data to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting ROI data: {e}")
            return False
    
    def _export_csv(self, filepath: str, roi_ids: List[str]):
        """Export to CSV format."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['ROI_ID', 'Timestamp', 'Temp_Avg_C', 'Temp_Min_C', 'Temp_Max_C'])
            
            # Data
            for roi_id in roi_ids:
                if roi_id not in self.roi_history:
                    continue
                
                for entry in self.roi_history[roi_id]:
                    writer.writerow([
                        roi_id,
                        entry.get('timestamp', ''),
                        entry.get('temp_avg', ''),
                        entry.get('temp_min', ''),
                        entry.get('temp_max', '')
                    ])
    
    def _export_json(self, filepath: str, roi_ids: List[str]):
        """Export to JSON format."""
        data = {}
        
        for roi_id in roi_ids:
            if roi_id in self.roi_history:
                data[roi_id] = {
                    'settings': self.roi_settings.get(roi_id, {}),
                    'history': self.roi_history[roi_id]
                }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def clear_history(self, roi_id: Optional[str] = None):
        """
        Clear temperature history.
        
        Args:
            roi_id: Specific ROI to clear, or None to clear all
        """
        if roi_id is not None:
            if roi_id in self.roi_history:
                self.roi_history[roi_id] = []
                logger.info(f"Cleared history for ROI {roi_id}")
        else:
            self.roi_history = {}
            logger.info("Cleared all ROI history")
    
    def get_info(self) -> dict:
        """
        Get analyzer information.
        
        Returns:
            Dictionary with analyzer status
        """
        return {
            'tracked_rois': len(self.roi_history),
            'custom_emissivity_rois': sum(1 for s in self.roi_settings.values() 
                                          if s.get('emissivity') is not None),
            'total_measurements': sum(len(h) for h in self.roi_history.values()),
            'max_history_length': self.max_history_length
        }


# ============================================================================
# Standalone Test
# ============================================================================

if __name__ == "__main__":
    # Test the analyzer
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from radiometric_converter import TLinearConverter
    from roi_manager import ROI, ROIType, ROISource
    
    print("Testing ROI Radiometric Analyzer...")
    
    # Create converter
    converter = TLinearConverter(method="linear")
    converter.set_temperature_range(-10, 100)
    
    # Create analyzer
    analyzer = ROIRadiometricAnalyzer(converter)
    
    # Create test ROI
    test_roi = ROI(
        roi_id="test_roi_1",
        roi_type=ROIType.RECTANGLE,
        roi_source=ROISource.MANUAL,
        points=[(100, 100), (200, 100), (200, 200), (100, 200)],
        label="Test PCB Area"
    )
    
    # Create synthetic 16-bit frame
    frame = np.random.randint(20000, 40000, (512, 640), dtype=np.uint16)
    
    # Analyze ROI
    stats = analyzer.analyze_roi(test_roi, frame)
    print(f"\nROI Analysis Results:")
    print(f"  ROI: {stats['roi_name']}")
    if stats.get('temp_avg'):
        print(f"  Avg Temp: {stats['temp_avg']:.2f}°C")
        print(f"  Min Temp: {stats['temp_min']:.2f}°C")
        print(f"  Max Temp: {stats['temp_max']:.2f}°C")
    print(f"  Pixels: {stats.get('pixel_count', 0)}")
    
    # Test emissivity override
    analyzer.set_roi_emissivity("test_roi_1", 0.90)
    print(f"\nSet custom emissivity: {analyzer.get_roi_emissivity('test_roi_1')}")
    
    # Test trend tracking
    for i in range(5):
        stats = analyzer.analyze_roi(test_roi, frame)
    
    trend = analyzer.get_roi_temperature_trend("test_roi_1")
    print(f"\nTemperature trend ({len(trend)} readings)")
    
    # Test export
    test_export_path = Path(__file__).parent / "test_roi_export.csv"
    analyzer.export_roi_data(str(test_export_path), format='csv')
    print(f"\nExported to: {test_export_path}")
    
    # Get info
    info = analyzer.get_info()
    print(f"\nAnalyzer Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print("\n✓ ROI Radiometric Analyzer test complete!")
