import math
from datetime import datetime, timedelta

from models import BrandingConfig
from utils.constants import (BLOOD_BANK_LAT, BLOOD_BANK_LNG,
                              GEOFENCE_RADIUS_M,
                              WORK_START_HOUR, WORK_START_MINUTE,
                              LATE_GRACE_MINUTES)


class ClockService:

    @staticmethod
    def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Great-circle distance in meters between two GPS coordinates."""
        R = 6371000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lng2 - lng1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return round(2 * R * math.asin(math.sqrt(a)))

    @staticmethod
    def _geofence_center() -> tuple:
        """Return (lat, lng, radius_m) from BrandingConfig or fallback constants."""
        cfg = BrandingConfig.query.first()
        if cfg and cfg.company_lat and cfg.company_lng:
            return cfg.company_lat, cfg.company_lng, cfg.allowed_radius_meters or GEOFENCE_RADIUS_M
        return BLOOD_BANK_LAT, BLOOD_BANK_LNG, GEOFENCE_RADIUS_M

    @staticmethod
    def check_geofence(lat: float, lng: float) -> tuple:
        """
        Validate a GPS coordinate against the company geofence.
        Returns (inside: bool, distance_meters: float).
        """
        clat, clng, radius = ClockService._geofence_center()
        dist = ClockService.haversine(float(lat), float(lng), clat, clng)
        return dist <= radius, dist

    @staticmethod
    def calc_late_minutes(clock_in_dt: datetime) -> int:
        """
        Calculate how many minutes late a clock-in is.
        Returns 0 if on time or within grace period.
        """
        start = clock_in_dt.replace(
            hour=WORK_START_HOUR, minute=WORK_START_MINUTE,
            second=0, microsecond=0
        )
        grace = start + timedelta(minutes=LATE_GRACE_MINUTES)
        if clock_in_dt > grace:
            return int((clock_in_dt - start).total_seconds() / 60)
        return 0
