#!/usr/bin/env python3
"""
Spot Meter Data Export Utilities
Exports spot meter data to CSV, JSON, and other formats.

Part of Enhancement #12: Spot Meter Management and Data Export
"""

import csv
import json
from datetime import datetime
from typing import List, Dict, Any, TYPE_CHECKING
from pathlib import Path
import logging

if TYPE_CHECKING:
    from spot_meter_panel import SpotMeterData

logger = logging.getLogger(__name__)


class SpotMeterExporter:
    """Export spot meter data to various formats."""
    
    @staticmethod
    def export_to_csv(spots: List['SpotMeterData'], filepath: str) -> bool:
        """Export spot meter data to CSV file.
        
        Args:
            spots: List of SpotMeterData objects
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow([
                    'ID', 'Label', 'X', 'Y', 
                    'Temperature', 'Unit',
                    'Created', 'Last Updated',
                    'Visible', 'Locked', 'Trend'
                ])
                
                # Data rows
                for spot in spots:
                    created_str = datetime.fromtimestamp(spot.created_at).strftime('%Y-%m-%d %H:%M:%S') if spot.created_at else ''
                    updated_str = datetime.fromtimestamp(spot.updated_at).strftime('%Y-%m-%d %H:%M:%S') if spot.updated_at else ''
                    
                    writer.writerow([
                        spot.id,
                        spot.label,
                        spot.x,
                        spot.y,
                        f"{spot.temperature:.2f}" if spot.temperature is not None else '',
                        spot.unit,
                        created_str,
                        updated_str,
                        'Yes' if spot.visible else 'No',
                        'Yes' if spot.locked else 'No',
                        spot.get_trend() if hasattr(spot, 'get_trend') else ''
                    ])
                    
            logger.info(f"Exported {len(spots)} spot meters to CSV: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False
            
    @staticmethod
    def export_to_json(spots: List['SpotMeterData'], filepath: str, 
                       include_history: bool = True) -> bool:
        """Export spot meter data to JSON file.
        
        Args:
            spots: List of SpotMeterData objects
            filepath: Output file path
            include_history: Include temperature history
            
        Returns:
            True if successful
        """
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'export_version': '1.0',
                'spot_count': len(spots),
                'statistics': SpotMeterExporter._calculate_statistics(spots),
                'spots': []
            }
            
            for spot in spots:
                spot_data = {
                    'id': spot.id,
                    'label': spot.label,
                    'coordinates': {'x': spot.x, 'y': spot.y},
                    'temperature': {
                        'value': spot.temperature,
                        'unit': spot.unit,
                        'trend': spot.get_trend() if hasattr(spot, 'get_trend') else 'unknown'
                    },
                    'color': {
                        'r': spot.color[0],
                        'g': spot.color[1],
                        'b': spot.color[2]
                    },
                    'state': {
                        'visible': spot.visible,
                        'locked': spot.locked
                    },
                    'timestamps': {
                        'created': datetime.fromtimestamp(spot.created_at).isoformat() if spot.created_at else None,
                        'updated': datetime.fromtimestamp(spot.updated_at).isoformat() if spot.updated_at else None
                    }
                }
                
                if include_history and spot.history:
                    spot_data['history'] = [
                        {
                            'timestamp': datetime.fromtimestamp(ts).isoformat(),
                            'temperature': temp
                        }
                        for ts, temp in spot.history[-100:]  # Last 100 readings
                    ]
                    spot_data['history_count'] = len(spot.history)
                    
                data['spots'].append(spot_data)
                
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Exported {len(spots)} spot meters to JSON: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False
            
    @staticmethod
    def _calculate_statistics(spots: List['SpotMeterData']) -> Dict[str, Any]:
        """Calculate aggregate statistics for export."""
        temps = [s.temperature for s in spots if s.temperature is not None and s.visible]
        
        if not temps:
            return {
                'visible_count': 0,
                'total_count': len(spots),
                'min': None,
                'max': None,
                'average': None,
                'delta': None
            }
            
        return {
            'visible_count': len(temps),
            'total_count': len(spots),
            'min': min(temps),
            'max': max(temps),
            'average': sum(temps) / len(temps),
            'delta': max(temps) - min(temps),
            'unit': spots[0].unit if spots else '°C'
        }
            
    @staticmethod
    def export_history_to_csv(spots: List['SpotMeterData'], filepath: str) -> bool:
        """Export temperature history to CSV for graphing.
        
        Creates a time-series format with columns for each spot meter.
        Useful for importing into Excel, LibreOffice, or plotting tools.
        
        Args:
            spots: List of SpotMeterData objects with history
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            # Collect all unique timestamps
            all_timestamps = set()
            for spot in spots:
                if spot.history:
                    for ts, _ in spot.history:
                        all_timestamps.add(ts)
                        
            if not all_timestamps:
                logger.warning("No history data to export")
                return False
                    
            all_timestamps = sorted(all_timestamps)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header: Timestamp, Spot1, Spot2, ...
                header = ['Timestamp', 'Elapsed_Seconds'] + [spot.label for spot in spots]
                writer.writerow(header)
                
                # Create lookup for each spot's history
                spot_histories = {}
                for spot in spots:
                    spot_histories[spot.id] = dict(spot.history) if spot.history else {}
                    
                # Base time for elapsed calculation
                base_time = all_timestamps[0] if all_timestamps else 0
                    
                # Data rows
                for ts in all_timestamps:
                    row = [
                        datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                        f"{ts - base_time:.2f}"
                    ]
                    for spot in spots:
                        temp = spot_histories.get(spot.id, {}).get(ts, '')
                        row.append(f"{temp:.2f}" if temp != '' else '')
                    writer.writerow(row)
                    
            logger.info(f"Exported history ({len(all_timestamps)} readings) to: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"History export failed: {e}")
            return False
            
    @staticmethod
    def generate_snapshot_metadata(spots: List['SpotMeterData']) -> Dict[str, Any]:
        """Generate spot meter metadata for snapshot files.
        
        Returns a dictionary suitable for embedding in snapshot metadata.
        
        Args:
            spots: List of SpotMeterData objects
            
        Returns:
            Dictionary with spot meter data
        """
        return {
            'spot_meters': [
                {
                    'label': s.label,
                    'x': s.x,
                    'y': s.y,
                    'temperature': s.temperature,
                    'unit': s.unit,
                    'visible': s.visible
                }
                for s in spots
            ],
            'spot_meter_count': len(spots),
            'spot_meter_stats': SpotMeterExporter._calculate_statistics(spots)
        }


class SpotMeterLogger:
    """Continuous logging of spot meter readings to file.
    
    Usage:
        logger = SpotMeterLogger("spot_log.csv", interval_seconds=1.0)
        logger.start()
        
        # In main loop:
        logger.log(spot_panel.get_all_spots())
        
        # When done:
        logger.stop()
    """
    
    def __init__(self, filepath: str, interval_seconds: float = 1.0):
        """Initialize the logger.
        
        Args:
            filepath: Output CSV file path
            interval_seconds: Minimum time between log entries
        """
        self.filepath = filepath
        self.interval = interval_seconds
        self.running = False
        self.last_log_time = 0
        self._initialized = False
        
    def start(self):
        """Start logging (creates file with header)."""
        if self._initialized:
            return
            
        try:
            with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Elapsed_Seconds', 
                    'Spot_ID', 'Label', 
                    'Temperature', 'Unit'
                ])
            self._initialized = True
            self.running = True
            self._start_time = datetime.now().timestamp()
            logger.info(f"Spot meter logging started: {self.filepath}")
        except Exception as e:
            logger.error(f"Failed to start spot meter logging: {e}")
            
    def stop(self):
        """Stop logging."""
        self.running = False
        logger.info(f"Spot meter logging stopped: {self.filepath}")
            
    def log(self, spots: List['SpotMeterData']):
        """Log current spot meter readings if interval has passed.
        
        Call this from the main processing loop.
        
        Args:
            spots: List of SpotMeterData objects
        """
        if not self.running or not self._initialized:
            return
            
        current_time = datetime.now().timestamp()
        if current_time - self.last_log_time < self.interval:
            return
            
        self.last_log_time = current_time
        elapsed = current_time - self._start_time
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        try:
            with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for spot in spots:
                    if spot.temperature is not None and spot.visible:
                        writer.writerow([
                            timestamp,
                            f"{elapsed:.2f}",
                            spot.id,
                            spot.label,
                            f"{spot.temperature:.2f}",
                            spot.unit
                        ])
        except Exception as e:
            logger.error(f"Spot meter logging error: {e}")
