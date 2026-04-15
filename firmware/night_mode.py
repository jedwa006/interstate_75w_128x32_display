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

        # Green flash tracking (only fire once per sunset)
        self._green_flash_pending = False
        self._green_flash_fired = False
        self._i75_ref = None  # set during boot or first render

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

    def render_animation(self, graphics, y_base, i75=None):
        """Render the horizon sun animation during transitions.
        y_base: bottom of display area (typically 31).
        Call this after main display rendering."""
        if i75:
            self._i75_ref = i75

        if not self._in_transition:
            # Check if sunset just ended — fire green flash once
            if self._green_flash_pending and not self._green_flash_fired:
                self._green_flash_fired = True
                self._green_flash_pending = False
                if self._i75_ref:
                    self._green_flash(self._i75_ref, graphics, y_base)
            return

        self._draw_sun(graphics, y_base, self._transition_progress, self._transition_type)

        # Track when sunset is near completion to trigger green flash
        if self._transition_type == 'sunset' and self._transition_progress > 0.95:
            self._green_flash_pending = True
            self._green_flash_fired = False

    def play_boot_animation(self, i75, graphics):
        """Play a quick sunrise→sunset sequence on boot for visual effect."""
        import time as t

        # Quick sunrise (1.5s)
        for step in range(30):
            p = step / 29.0
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            self._draw_sun(graphics, 31, p, 'sunrise')
            i75.update()
            t.sleep_ms(50)

        t.sleep_ms(300)

        # Quick sunset (1.5s)
        for step in range(30):
            p = step / 29.0
            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()
            self._draw_sun(graphics, 31, p, 'sunset')
            i75.update()
            t.sleep_ms(50)

        # Green flash
        self._green_flash(i75, graphics, 31)

        t.sleep_ms(200)

    def _green_flash(self, i75, graphics, y_base):
        """The green flash — an initial sea-green burst from the sun's last
        position that seeds a brief Game of Life evolution, spreading across
        the display in sea-green before dying off naturally."""
        import time as t

        sun_cx = 64
        sun_cy = y_base
        W = 128
        H = 32

        # --- Phase 1: Initial flash burst (3 frames) ---
        for step in range(3):
            p = step / 2.0
            radius = int(2 + p * 4)
            alpha = 0.8 - p * 0.2

            gr = int(20 * alpha)
            gg = int(200 * alpha)
            gb = int(120 * alpha)

            graphics.set_pen(graphics.create_pen(0, 0, 0))
            graphics.clear()

            pen = graphics.create_pen(gr, gg, gb)
            graphics.set_pen(pen)
            for dy in range(-radius, 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius:
                        px, py = sun_cx + dx, sun_cy + dy
                        if 0 <= py < H and 0 <= px < W:
                            graphics.pixel(px, py)
            i75.update()
            t.sleep_ms(50)

        # --- Phase 2: GOL with aging cells and wide expanding wave ---
        # Grid stores cell age: 0=dead, 1+=alive (age in generations)
        # Cells die after MAX_AGE — prevents oscillators
        grid = bytearray(W * H)
        buf = bytearray(W * H)

        MAX_AGE = 5        # cells die after this many gens
        MAX_GENS = 80      # generous cap (~30s at 30ms/frame + evolution time)
        WAVE_SPEED = 10    # pixels of wave expansion per gen (wider sweep)
        SEED_GENS = 7      # how many gens to keep seeding
        STALE_CHECK_GEN = 30  # start checking for oscillators after this gen
        STALE_WINDOW = 4      # compare population over this many gens

        # Pre-compute color LUT
        age_pens = [None] * (MAX_AGE + 1)
        # Wave front bloom pen (brighter leading edge)
        bloom_pen = None

        # Population history for oscillator detection
        pop_history = []

        for gen in range(MAX_GENS):
            fade = 1.0 - (gen / MAX_GENS) * 0.75

            # Build pen LUT for this generation
            for a in range(1, MAX_AGE + 1):
                life = 1.0 - ((a - 1) / MAX_AGE)
                v = life * fade
                age_pens[a] = graphics.create_pen(int(15 * v), int(200 * v), int(110 * v))
            black = graphics.create_pen(0, 0, 0)
            # Bloom: bright leading edge for newborn cells during wave phase
            bv = fade * 0.9
            bloom_pen = graphics.create_pen(int(40 * bv), int(255 * bv), int(160 * bv))

            # --- Seed wave front with bloom ---
            if gen < SEED_GENS:
                wave_r = 4 + gen * WAVE_SPEED
                inner_r = max(0, wave_r - 3)
                inner_sq = inner_r * inner_r
                outer_sq = wave_r * wave_r
                for dy in range(-min(wave_r, sun_cy), 1):
                    py = sun_cy + dy
                    if py < 0 or py >= H:
                        continue
                    dy_sq = dy * dy
                    if dy_sq > outer_sq:
                        continue
                    max_dx = int(math.sqrt(outer_sq - dy_sq))
                    min_dx = int(math.sqrt(inner_sq - dy_sq)) if dy_sq < inner_sq else 0
                    for dx in range(-max_dx, max_dx + 1):
                        adx = abs(dx)
                        if adx < min_dx:
                            continue
                        px = sun_cx + dx
                        if 0 <= px < W:
                            if ((px * 7 + py * 13 + gen * 11) % 10) < 3:
                                idx = py * W + px
                                if grid[idx] == 0:
                                    grid[idx] = 1

            # --- Render ---
            graphics.set_pen(black)
            graphics.clear()

            live_count = 0
            seeding = gen < SEED_GENS
            for y in range(H):
                row = y * W
                for x in range(W):
                    a = grid[row + x]
                    if a > 0:
                        live_count += 1
                        # Newborn cells (age 1) during wave phase get bloom color
                        if seeding and a == 1:
                            graphics.set_pen(bloom_pen)
                        else:
                            pen = age_pens[a]
                            if pen is not None:
                                graphics.set_pen(pen)
                            else:
                                continue
                        graphics.pixel(x, y)

            i75.update()

            # Track population for oscillator detection
            pop_history.append(live_count)

            # --- Exit conditions ---
            # 1. All dead after seeding phase
            if live_count == 0 and gen >= SEED_GENS:
                break

            # 2. Oscillator detection: if population repeats over STALE_WINDOW
            if gen >= STALE_CHECK_GEN and len(pop_history) >= STALE_WINDOW * 2:
                recent = pop_history[-STALE_WINDOW:]
                older = pop_history[-STALE_WINDOW * 2:-STALE_WINDOW]
                # Check if population is cycling (period 1 or 2)
                if recent == older:
                    break
                # Also check period-2: [a,b,a,b] pattern
                if STALE_WINDOW >= 4:
                    r = recent
                    if r[0] == r[2] and r[1] == r[3] and r[0] != r[1]:
                        break

            # --- Evolve ---
            for y in range(H):
                row = y * W
                y0 = max(0, y - 1)
                y1 = min(H - 1, y + 1)
                for x in range(W):
                    x0 = max(0, x - 1)
                    x1 = min(W - 1, x + 1)
                    n = 0
                    r0 = y0 * W
                    r1 = y * W
                    r2 = y1 * W
                    for nx in range(x0, x1 + 1):
                        if grid[r0 + nx] > 0:
                            n += 1
                        if grid[r2 + nx] > 0:
                            n += 1
                    if grid[r1 + x0] > 0:
                        n += 1
                    if grid[r1 + x1] > 0:
                        n += 1

                    age = grid[row + x]
                    if age > 0:
                        buf[row + x] = (age + 1) if (2 <= n <= 3 and age < MAX_AGE) else 0
                    else:
                        buf[row + x] = 1 if n == 3 else 0

            grid, buf = buf, grid
            for i in range(W * H):
                buf[i] = 0

            t.sleep_ms(30)

        # Clean exit
        graphics.set_pen(graphics.create_pen(0, 0, 0))
        graphics.clear()
        i75.update()
        t.sleep_ms(100)

    def _draw_sun(self, graphics, y_base, p, transition_type):
        """Draw the sun sprite with bloom effect at a given progress (0-1)."""
        if transition_type == 'sunset':
            sun_y = int((y_base - 5) + p * 5)
            colors = SUN_COLORS_SUNSET
        else:
            sun_y = int(y_base - p * 5)
            colors = SUN_COLORS_SUNRISE

        # Interpolate sun color
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

        # Ray brightness
        if transition_type == 'sunset':
            ray_alpha = 1.0 - p
        else:
            ray_alpha = p

        sun_x = 62
        sun_cx = sun_x + 2  # center of 5px sprite
        sun_cy = sun_y + 2

        # --- Bloom effect ---
        # Bloom appears at sunrise start (p < 0.2) and sunset end (p > 0.8)
        bloom = 0.0
        if transition_type == 'sunrise' and p < 0.25:
            bloom = 1.0 - (p / 0.25)  # fades out as sun rises
        elif transition_type == 'sunset' and p > 0.75:
            bloom = (p - 0.75) / 0.25  # grows as sun sets

        if bloom > 0.05:
            # Draw expanding glow ring around sun center
            bloom_radius = int(3 + bloom * 5)  # 3-8 px radius
            bloom_alpha = bloom * 0.3
            bloom_pen = graphics.create_pen(
                int(cr * bloom_alpha),
                int(cg * bloom_alpha),
                int(cb * bloom_alpha * 0.5),  # less blue for warm glow
            )
            graphics.set_pen(bloom_pen)
            for by in range(-bloom_radius, bloom_radius + 1):
                for bx in range(-bloom_radius, bloom_radius + 1):
                    dist_sq = bx * bx + by * by
                    if dist_sq <= bloom_radius * bloom_radius:
                        px = sun_cx + bx
                        py = sun_cy + by
                        if 0 <= py < 32 and 0 <= px < 128:
                            # Fade with distance
                            dist = math.sqrt(dist_sq)
                            if dist > bloom_radius * 0.5:
                                fade_pen = graphics.create_pen(
                                    int(cr * bloom_alpha * (1 - dist / bloom_radius)),
                                    int(cg * bloom_alpha * (1 - dist / bloom_radius)),
                                    int(cb * bloom_alpha * 0.5 * (1 - dist / bloom_radius)),
                                )
                                graphics.set_pen(fade_pen)
                            else:
                                graphics.set_pen(bloom_pen)
                            graphics.pixel(px, py)

        # --- Sun sprite ---
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
