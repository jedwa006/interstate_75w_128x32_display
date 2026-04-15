import math
import time

# Amber night color target
AMBER = (255, 140, 20)

# Transition duration in minutes
TRANSITION_MINS = 5

# Sun pixel art (5x5, 1=core, 2=ray)
SUN_SPRITE = (
    (0, 0, 2, 0, 0),
    (0, 1, 1, 1, 0),
    (2, 1, 1, 1, 2),
    (0, 1, 1, 1, 0),
    (0, 0, 2, 0, 0),
)

SUN_COLORS_SUNSET = (
    (255, 200, 50),   # start: bright yellow
    (255, 160, 30),   # mid: orange
    (200, 80, 10),    # end: deep orange
)

SUN_COLORS_SUNRISE = (
    (200, 80, 10),    # start: deep orange
    (255, 160, 30),   # mid: orange
    (255, 200, 50),   # end: bright yellow
)


class NightMode:
    """Manages day/night display mode with sunset/sunrise timing."""

    def __init__(self, config):
        self.config = config
        self.enabled = config.get("night_mode_enabled", True)

        # Cached sun times (recalculated daily)
        self._sunrise_h = config.get("sunrise_hour", 7)  # decimal hours
        self._sunset_h = config.get("sunset_hour", 20)
        self._last_calc_day = -1

        # Current state
        self._brightness_mult = 1.0
        self._amber_blend = 0.0
        self._in_transition = False
        self._transition_type = None  # 'sunset' or 'sunrise'
        self._transition_progress = 0.0  # 0-1

        # Location (0 = not set, will try geolocation)
        self._lat = config.get("lat", 0)
        self._lon = config.get("lon", 0)
        self._geo_attempted = False

    def try_geolocate(self):
        """Attempt IP geolocation if lat/lon not configured. Call after WiFi connects."""
        if self._lat != 0 and self._lon != 0:
            return  # already have coordinates
        if self._geo_attempted:
            return  # don't retry

        self._geo_attempted = True
        try:
            import urequests
            resp = urequests.get('http://ip-api.com/json/')
            data = resp.json()
            resp.close()
            if data.get('status') == 'success':
                self._lat = data['lat']
                self._lon = data['lon']
                # Save to config so we don't need network next boot
                self.config["lat"] = self._lat
                self.config["lon"] = self._lon
                self.config.save()
        except Exception:
            # Fall back to Denver defaults
            self._lat = 39.74
            self._lon = -104.98

    def update(self, hour, minute, day_of_year, year):
        """Update night mode state. Call once per frame (only does real work per minute)."""
        if not self.enabled:
            self._brightness_mult = 1.0
            self._amber_blend = 0.0
            self._in_transition = False
            return

        # Recalculate sun times once per day
        if day_of_year != self._last_calc_day:
            self._calc_sun_times(day_of_year, year)
            self._last_calc_day = day_of_year

        # Current time as decimal hours
        now_h = hour + minute / 60.0

        # Transition window in decimal hours
        trans_h = TRANSITION_MINS / 60.0

        # Sunset transition: sunset_h to sunset_h + trans_h
        sunset_start = self._sunset_h
        sunset_end = sunset_start + trans_h

        # Sunrise transition: sunrise_h to sunrise_h + trans_h
        sunrise_start = self._sunrise_h
        sunrise_end = sunrise_start + trans_h

        night_brightness = self.config.get("night_brightness_pct", 50) / 100.0

        if sunrise_start <= now_h < sunrise_end:
            # Sunrise transition: night → day
            p = (now_h - sunrise_start) / trans_h
            self._brightness_mult = night_brightness + (1.0 - night_brightness) * p
            self._amber_blend = 1.0 - p
            self._in_transition = True
            self._transition_type = 'sunrise'
            self._transition_progress = p

        elif sunset_start <= now_h < sunset_end:
            # Sunset transition: day → night
            p = (now_h - sunset_start) / trans_h
            self._brightness_mult = 1.0 - (1.0 - night_brightness) * p
            self._amber_blend = p
            self._in_transition = True
            self._transition_type = 'sunset'
            self._transition_progress = p

        elif sunrise_end <= now_h < sunset_start:
            # Daytime
            self._brightness_mult = 1.0
            self._amber_blend = 0.0
            self._in_transition = False

        else:
            # Nighttime
            self._brightness_mult = night_brightness
            self._amber_blend = 1.0
            self._in_transition = False

    def apply_color(self, r, g, b, brightness_pct):
        """Apply night mode adjustments to color and brightness.
        Returns (r, g, b, brightness_frac) with night mode applied."""
        # Blend toward amber
        blend = self._amber_blend
        nr = int(r * (1 - blend) + AMBER[0] * blend)
        ng = int(g * (1 - blend) + AMBER[1] * blend)
        nb = int(b * (1 - blend) + AMBER[2] * blend)

        # Apply brightness multiplier
        br = (brightness_pct / 100.0) * self._brightness_mult

        return nr, ng, nb, br

    def render_animation(self, graphics, y_base):
        """Render the horizon sun animation during transitions.
        y_base: bottom of display area (typically 31).
        Call this after main display rendering."""
        if not self._in_transition:
            return

        p = self._transition_progress  # 0-1

        if self._transition_type == 'sunset':
            # Sun descends: starts at y_base-5, ends at y_base
            sun_y = int((y_base - 5) + p * 5)
            colors = SUN_COLORS_SUNSET
        else:
            # Sun ascends: starts at y_base, ends at y_base-5
            sun_y = int(y_base - p * 5)
            colors = SUN_COLORS_SUNRISE

        # Interpolate sun color based on progress
        if p < 0.5:
            t = p * 2
            cr = int(colors[0][0] * (1 - t) + colors[1][0] * t)
            cg = int(colors[0][1] * (1 - t) + colors[1][1] * t)
            cb = int(colors[0][2] * (1 - t) + colors[1][2] * t)
        else:
            t = (p - 0.5) * 2
            cr = int(colors[1][0] * (1 - t) + colors[2][0] * t)
            cg = int(colors[1][1] * (1 - t) + colors[2][1] * t)
            cb = int(colors[1][2] * (1 - t) + colors[2][2] * t)

        # Ray brightness fades during sunset, grows during sunrise
        if self._transition_type == 'sunset':
            ray_alpha = 1.0 - p
        else:
            ray_alpha = p

        sun_x = 62  # centered on display

        core_pen = graphics.create_pen(cr, cg, cb)
        ray_pen = graphics.create_pen(
            int(cr * ray_alpha * 0.6),
            int(cg * ray_alpha * 0.6),
            int(cb * ray_alpha * 0.6),
        )

        for sy in range(5):
            for sx in range(5):
                px = sun_x + sx
                py = sun_y + sy
                if 0 <= py < 32 and 0 <= px < 128:
                    cell = SUN_SPRITE[sy][sx]
                    if cell == 1:
                        graphics.set_pen(core_pen)
                        graphics.pixel(px, py)
                    elif cell == 2 and ray_alpha > 0.05:
                        graphics.set_pen(ray_pen)
                        graphics.pixel(px, py)

    @property
    def brightness_mult(self):
        return self._brightness_mult

    @property
    def amber_blend(self):
        return self._amber_blend

    @property
    def in_transition(self):
        return self._in_transition

    def _calc_sun_times(self, day_of_year, year):
        """Calculate sunrise/sunset using simplified NOAA algorithm.
        Sets self._sunrise_h and self._sunset_h as decimal hours (local time)."""
        lat = self._lat
        lon = self._lon

        if lat == 0 and lon == 0:
            # No coordinates — use config fixed hours
            self._sunrise_h = self.config.get("sunrise_hour", 7)
            self._sunset_h = self.config.get("sunset_hour", 20)
            return

        utc_offset = self.config.get("utc_offset", 0)
        # Add DST if enabled
        if self.config.get("dst_enabled", False):
            # Simple check: assume DST is active if we're between Mar-Nov (US)
            # Full DST check is in ntp_manager, but we just need approximate here
            rules = self.config.get("dst_rules", "US")
            if rules == "US":
                # Rough: DOY 70-310 ≈ Mar 11 - Nov 6
                if 70 <= day_of_year <= 310:
                    utc_offset += 1
            elif rules == "EU":
                if 85 <= day_of_year <= 300:
                    utc_offset += 1

        try:
            self._sunrise_h = self._calc_sun_hour(lat, lon, day_of_year, utc_offset, True)
            self._sunset_h = self._calc_sun_hour(lat, lon, day_of_year, utc_offset, False)
        except (ValueError, ZeroDivisionError):
            # Polar regions or math error — fall back to config
            self._sunrise_h = self.config.get("sunrise_hour", 7)
            self._sunset_h = self.config.get("sunset_hour", 20)

    def _calc_sun_hour(self, lat, lon, doy, utc_offset, is_sunrise):
        """NOAA simplified sunrise/sunset for a given day.
        Returns decimal hour in local time."""
        RAD = math.pi / 180
        DEG = 180 / math.pi

        lng_hour = lon / 15.0

        if is_sunrise:
            t = doy + ((6 - lng_hour) / 24)
        else:
            t = doy + ((18 - lng_hour) / 24)

        # Sun's mean anomaly
        M = (0.9856 * t) - 3.289

        # Sun's true longitude
        L = M + (1.916 * math.sin(M * RAD)) + (0.020 * math.sin(2 * M * RAD)) + 282.634
        L = L % 360

        # Right ascension
        RA = math.atan(0.91764 * math.tan(L * RAD)) * DEG
        RA = RA % 360

        # RA in same quadrant as L
        L_quad = (int(L / 90)) * 90
        RA_quad = (int(RA / 90)) * 90
        RA = RA + (L_quad - RA_quad)

        # RA to hours
        RA = RA / 15

        # Sun's declination
        sin_dec = 0.39782 * math.sin(L * RAD)
        cos_dec = math.cos(math.asin(sin_dec))

        # Hour angle
        # -0.833 degrees = standard refraction correction
        cos_H = (-0.01454 - (math.sin(lat * RAD) * sin_dec)) / (math.cos(lat * RAD) * cos_dec)

        if cos_H > 1:
            raise ValueError("No sunrise")  # sun never rises
        if cos_H < -1:
            raise ValueError("No sunset")   # sun never sets

        if is_sunrise:
            H = 360 - math.acos(cos_H) * DEG
        else:
            H = math.acos(cos_H) * DEG

        H = H / 15  # to hours

        # Local mean time
        T = H + RA - (0.06571 * t) - 6.622

        # UTC
        UT = T - lng_hour
        UT = UT % 24

        # Local time
        local = UT + utc_offset
        local = local % 24

        return local
