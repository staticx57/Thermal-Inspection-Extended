#!/usr/bin/env python3
"""
Auto Day/Night Detection Module
Automatically determines optimal theme (light/dark) based on:
1. Time of day (simple hour-based)
2. Ambient light from RGB camera (when available)
3. Sunrise/sunset calculations (astronomical)
"""
import logging
import time
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Tuple
import math
import numpy as np

logger = logging.getLogger(__name__)


class AutoDayNightDetector:
    """
    Intelligent day/night detection with multiple methods:
    - Time-based: Simple hour check (7am-7pm = day)
    - Ambient light: RGB camera brightness analysis
    - Astronomical: Sunrise/sunset calculations based on location and date

    Priority: Ambient light > Astronomical > Time-based
    """

    def __init__(self,
                 latitude: float = 37.7749,  # Default: San Francisco
                 longitude: float = -122.4194,
                 ambient_threshold: int = 80,  # Brightness threshold 0-255
                 time_day_start: int = 7,      # 7 AM
                 time_night_start: int = 19):  # 7 PM
        """
        Args:
            latitude: Location latitude for sun calculations (-90 to 90)
            longitude: Location longitude for sun calculations (-180 to 180)
            ambient_threshold: RGB brightness threshold (0-255), below = night
            time_day_start: Hour when day starts (0-23)
            time_night_start: Hour when night starts (0-23)
        """
        self.latitude = latitude
        self.longitude = longitude
        self.ambient_threshold = ambient_threshold
        self.time_day_start = time_day_start
        self.time_night_start = time_night_start

        # State
        self.last_ambient_brightness = None
        self.last_check_time = 0
        self.check_interval = 10.0  # Check every 10 seconds to avoid thrashing

        logger.info(f"AutoDayNightDetector initialized: lat={latitude}, lon={longitude}, "
                   f"ambient_threshold={ambient_threshold}, time={time_day_start}-{time_night_start}")

    def detect_theme(self, rgb_frame: Optional[np.ndarray] = None) -> Tuple[str, str]:
        """
        Detect optimal theme (light/dark) using available methods

        Args:
            rgb_frame: Optional RGB frame for ambient light detection

        Returns:
            Tuple of (theme, method) where:
                theme: 'light' or 'dark'
                method: 'ambient', 'astronomical', or 'time'
        """
        # Rate limiting: only check every N seconds
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval:
            # Return cached result
            if self.last_ambient_brightness is not None:
                theme = 'light' if self.last_ambient_brightness >= self.ambient_threshold else 'dark'
                return theme, 'ambient (cached)'

        self.last_check_time = current_time

        # Priority 1: Ambient light (most accurate, real-time)
        if rgb_frame is not None:
            theme, brightness = self._detect_from_ambient_light(rgb_frame)
            self.last_ambient_brightness = brightness
            return theme, 'ambient'

        # Priority 2: Astronomical calculations (accurate, location-aware)
        theme = self._detect_from_sun_position()
        if theme is not None:
            return theme, 'astronomical'

        # Priority 3: Simple time-based (fallback, always works)
        theme = self._detect_from_time_of_day()
        return theme, 'time'

    def _detect_from_ambient_light(self, rgb_frame: np.ndarray) -> Tuple[str, float]:
        """
        Detect theme from RGB camera brightness

        Method: Average brightness of entire frame
        - Day (bright): Mean brightness > threshold (default 80/255)
        - Night (dark): Mean brightness <= threshold

        Args:
            rgb_frame: RGB image (H x W x 3), dtype=uint8

        Returns:
            Tuple of (theme, brightness)
        """
        # Convert to grayscale for brightness
        if len(rgb_frame.shape) == 3:
            # RGB to grayscale: 0.299*R + 0.587*G + 0.114*B
            gray = np.dot(rgb_frame[..., :3], [0.299, 0.587, 0.114])
        else:
            gray = rgb_frame

        # Calculate mean brightness (0-255)
        brightness = float(np.mean(gray))

        # Determine theme
        if brightness >= self.ambient_threshold:
            theme = 'light'  # Bright environment = day theme
        else:
            theme = 'dark'   # Dark environment = night theme

        logger.debug(f"Ambient light detection: brightness={brightness:.1f}, "
                    f"threshold={self.ambient_threshold}, theme={theme}")

        return theme, brightness

    def _detect_from_sun_position(self) -> Optional[str]:
        """
        Detect theme from astronomical sunrise/sunset

        Uses simplified sunrise/sunset calculation based on:
        - Current date and time
        - Geographic location (latitude/longitude)
        - Solar noon and day length formulas

        Returns:
            'light' if sun is up, 'dark' if sun is down, None if calculation fails
        """
        try:
            now = datetime.now()
            sunrise, sunset = self._calculate_sunrise_sunset(now)

            if sunrise is None or sunset is None:
                return None

            # Check if current time is between sunrise and sunset
            current_time = now.time()

            if sunrise <= current_time <= sunset:
                theme = 'light'  # Sun is up
            else:
                theme = 'dark'   # Sun is down

            logger.debug(f"Astronomical detection: sunrise={sunrise}, sunset={sunset}, "
                        f"current={current_time}, theme={theme}")

            return theme

        except Exception as e:
            logger.warning(f"Astronomical calculation failed: {e}")
            return None

    def _calculate_sunrise_sunset(self, date: datetime) -> Tuple[Optional[dt_time], Optional[dt_time]]:
        """
        Calculate sunrise and sunset times for given date and location

        Uses simplified astronomical formula (accurate to ~15 minutes):
        - Solar declination based on day of year
        - Hour angle calculation
        - Local solar time conversion

        Args:
            date: Date to calculate for

        Returns:
            Tuple of (sunrise_time, sunset_time) or (None, None) if error
        """
        try:
            # Day of year (1-365/366)
            day_of_year = date.timetuple().tm_yday

            # Solar declination (angle of sun relative to equator)
            # Simplified formula: varies between -23.45° (winter solstice) and +23.45° (summer solstice)
            declination_rad = math.radians(23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81))))

            # Latitude in radians
            lat_rad = math.radians(self.latitude)

            # Hour angle (angle of sun at sunrise/sunset)
            # cos(hour_angle) = -tan(lat) * tan(declination)
            cos_hour_angle = -math.tan(lat_rad) * math.tan(declination_rad)

            # Check for polar day/night (sun never sets/rises)
            if cos_hour_angle > 1:
                # Polar night (sun never rises)
                logger.debug("Polar night detected (sun never rises)")
                return dt_time(23, 59), dt_time(0, 0)
            elif cos_hour_angle < -1:
                # Polar day (sun never sets)
                logger.debug("Polar day detected (sun never sets)")
                return dt_time(0, 0), dt_time(23, 59)

            # Hour angle in degrees
            hour_angle_deg = math.degrees(math.acos(cos_hour_angle))

            # Solar noon (time when sun is highest, depends on longitude)
            # Simplified: assume solar noon = 12:00 + longitude_correction
            longitude_correction_hours = -self.longitude / 15.0  # 15° per hour
            solar_noon_hours = 12.0 + longitude_correction_hours

            # Sunrise and sunset times (hours from midnight)
            sunrise_hours = solar_noon_hours - (hour_angle_deg / 15.0)
            sunset_hours = solar_noon_hours + (hour_angle_deg / 15.0)

            # Convert to time objects
            sunrise_time = self._hours_to_time(sunrise_hours)
            sunset_time = self._hours_to_time(sunset_hours)

            logger.debug(f"Calculated sunrise/sunset for day {day_of_year}: "
                        f"sunrise={sunrise_time}, sunset={sunset_time}")

            return sunrise_time, sunset_time

        except Exception as e:
            logger.warning(f"Sunrise/sunset calculation error: {e}")
            return None, None

    def _hours_to_time(self, hours: float) -> dt_time:
        """
        Convert decimal hours (0-24) to time object

        Args:
            hours: Hours since midnight (e.g., 6.5 = 6:30 AM)

        Returns:
            datetime.time object
        """
        # Clamp to 0-24 range
        hours = max(0, min(24, hours))

        # Extract hours and minutes
        hour = int(hours)
        minute = int((hours - hour) * 60)

        # Handle hour=24 edge case
        if hour == 24:
            hour = 23
            minute = 59

        return dt_time(hour, minute)

    def _detect_from_time_of_day(self) -> str:
        """
        Detect theme from simple hour-based rule

        Simple heuristic:
        - Day: time_day_start to time_night_start (e.g., 7am-7pm)
        - Night: time_night_start to time_day_start (e.g., 7pm-7am)

        Returns:
            'light' or 'dark'
        """
        current_hour = datetime.now().hour

        # Check if current hour is in day range
        if self.time_day_start <= current_hour < self.time_night_start:
            theme = 'light'
        else:
            theme = 'dark'

        logger.debug(f"Time-based detection: hour={current_hour}, "
                    f"day_hours={self.time_day_start}-{self.time_night_start}, theme={theme}")

        return theme

    def set_location(self, latitude: float, longitude: float):
        """
        Update geographic location for sun calculations

        Args:
            latitude: Latitude in degrees (-90 to 90)
            longitude: Longitude in degrees (-180 to 180)
        """
        self.latitude = latitude
        self.longitude = longitude
        logger.info(f"Location updated: lat={latitude}, lon={longitude}")

    def set_ambient_threshold(self, threshold: int):
        """
        Update ambient light threshold

        Args:
            threshold: Brightness threshold (0-255)
        """
        self.ambient_threshold = max(0, min(255, threshold))
        logger.info(f"Ambient threshold updated: {self.ambient_threshold}")

    def get_status(self) -> dict:
        """
        Get current detector status

        Returns:
            Dictionary with status info
        """
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'ambient_threshold': self.ambient_threshold,
            'time_day_start': self.time_day_start,
            'time_night_start': self.time_night_start,
            'last_ambient_brightness': self.last_ambient_brightness,
            'check_interval': self.check_interval
        }


# Global instance (singleton pattern)
_detector_instance = None


def get_detector() -> AutoDayNightDetector:
    """
    Get global AutoDayNightDetector instance (singleton)

    Returns:
        AutoDayNightDetector instance
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AutoDayNightDetector()
        logger.info("Created global AutoDayNightDetector instance")
    return _detector_instance
