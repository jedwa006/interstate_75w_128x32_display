import time
import math
from fonts import (
    FONT, FONT_W, FONT_H, TINY, TINY_W, TINY_H,
    draw_char, draw_string, string_width,
    draw_tiny, draw_tiny_str, tiny_str_width, draw_tiny_centered,
)

COLS = 128
ROWS = 32


def _day_of_year(year, month, day):
    """Return 1-based day of year."""
    days_in_month = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    doy = sum(days_in_month[1:month]) + day
    if month > 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        doy += 1
    return doy


def _dow_mon(year, month, day):
    """Day of week, 0=Mon..6=Sun (ISO 8601)."""
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    y = year - (1 if month < 3 else 0)
    dow_sun = (y + y // 4 - y // 100 + y // 400 + t[month - 1] + day) % 7
    return (dow_sun + 6) % 7


def _iso_week(year, month, day):
    """Calculate ISO 8601 week number (1-53).
    Week 1 contains the year's first Thursday."""
    doy = _day_of_year(year, month, day)
    dow = _dow_mon(year, month, day)  # 0=Mon..6=Sun

    # Find DOY of the Thursday in the current week
    thu_doy = doy + (3 - dow)

    # Thursday in previous year → last week of prev year
    if thu_doy < 1:
        return _iso_week(year - 1, 12, 31)

    # Thursday in next year → week 1 of next year
    year_days = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
    if thu_doy > year_days:
        return 1

    # First Thursday of the year
    jan1_dow = _dow_mon(year, 1, 1)
    first_thu_doy = 1 + (3 - jan1_dow) % 7

    return (thu_doy - first_thu_doy) // 7 + 1

MONTHS = ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
          'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC')
DAYS = ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')

ANIM_DURATION = 400  # ms for digit transitions


class ClockDisplay:
    """Renders the clock face: date, time, and NTP indicators."""

    def __init__(self, graphics, config, ntp):
        self.g = graphics
        self.config = config
        self.ntp = ntp

        # Pre-create pens (will be recreated on color change)
        self._update_pens()

        # Per-digit transition state
        self._digit_slots = {}  # {position: (prev_ch, new_ch, start_ticks)}

    def _update_pens(self):
        """Create drawing pens from current config."""
        r, g, b = self.config.color()
        br = self.config.brightness_frac()
        self.pen_main = self.g.create_pen(int(r * br), int(g * br), int(b * br))
        self.pen_dim = self.g.create_pen(int(r * br * 0.4), int(g * br * 0.4), int(b * br * 0.4))
        self.pen_black = self.g.create_pen(0, 0, 0)
        self.pen_sep = self.g.create_pen(int(38 * br), int(38 * br), int(38 * br))

        # NTP indicator pens
        self.pen_sync_ok = self.g.create_pen(0, int(180 * br), 0)
        self.pen_sync_ok_dim = self.g.create_pen(0, int(108 * br), 0)
        self.pen_sync_fail = self.g.create_pen(int(180 * br), 0, 0)
        self.pen_sync_fail_dim = self.g.create_pen(int(108 * br), 0, 0)
        self.pen_strat = self.g.create_pen(0, int(128 * br), 0)
        self.pen_strat_dim = self.g.create_pen(0, int(64 * br), 0)
        self.pen_grey = self.g.create_pen(int(77 * br), int(77 * br), int(89 * br))
        self.pen_bar_green = self.g.create_pen(0, int(166 * br), 0)
        self.pen_bar_yellow = self.g.create_pen(int(166 * br), int(140 * br), 0)
        self.pen_bar_red = self.g.create_pen(int(180 * br), 0, 0)
        self.pen_tick = self.g.create_pen(int(30 * br), int(30 * br), int(30 * br))
        self.pen_center = self.g.create_pen(int(77 * br), int(77 * br), int(77 * br))

    def render(self, local_time):
        """Render a full frame. local_time = (year, month, day, hour, min, sec, weekday)."""
        self.g.set_pen(self.pen_black)
        self.g.clear()

        year, month, day, hour, minute, second, weekday = local_time
        now_ticks = time.ticks_ms()

        # Top line: date, debug, or both (tiny font, row 0)
        fmt = self.config.get("date_format", "iso")
        if fmt == "debug":
            # Date + week left-aligned, debug right-aligned
            wk = _iso_week(year, month, day)
            date_short = "{:02d}-{:02d}-{:02d} W{:02d}".format(month, day, year % 100, wk)
            debug_str = self._format_debug()
            draw_tiny_str(self.g, date_short, 1, 0, self.pen_dim)
            debug_w = tiny_str_width(debug_str)
            draw_tiny_str(self.g, debug_str, COLS - debug_w - 1, 0, self.pen_dim)
        else:
            top_str = self._format_date(year, month, day, weekday)
            draw_tiny_centered(self.g, top_str, 0, self.pen_dim)

        # Time (large font, row 7)
        time_str = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
        time_y = 7
        self._render_time(time_str, time_y, now_ticks)

        # Milliseconds (tiny font, bottom-right of time digits)
        ms = now_ticks % 1000
        ms_str = ".{:03d}".format(ms)
        scale = 2
        char_h = FONT_H * scale  # 14
        time_w = string_width(time_str, scale)
        time_x = (COLS - time_w) // 2
        ms_x = time_x + time_w + 1
        ms_y = time_y + char_h - TINY_H  # align to bottom of big digits

        # Dim the ms based on offset — less trustworthy = dimmer
        offset = abs(self.ntp.get_offset_ms())
        if offset < 10:
            ms_alpha = 0.5    # high confidence
        elif offset < 30:
            ms_alpha = 0.3    # moderate
        elif offset < 100:
            ms_alpha = 0.15   # low confidence
        else:
            ms_alpha = 0.0    # don't show — too inaccurate

        if ms_alpha > 0:
            r, g, b = self.config.color()
            br = self.config.brightness_frac()
            ms_pen = self.g.create_pen(
                int(r * br * ms_alpha),
                int(g * br * ms_alpha),
                int(b * br * ms_alpha),
            )
            draw_tiny_str(self.g, ms_str, ms_x, ms_y, ms_pen)

        # NTP indicators (row 22+)
        self._render_ntp(22)

    def _format_date(self, year, month, day, weekday):
        fmt = self.config.get("date_format", "iso")
        if fmt == "iso":
            return "{:04d}-{:02d}-{:02d}".format(year, month, day)
        day_name = DAYS[weekday] if weekday < 7 else "???"
        month_name = MONTHS[month - 1] if 1 <= month <= 12 else "???"
        if fmt == "short":
            return "{} {} {:02d}".format(day_name, month_name, day)
        # "day" format
        return "{} {:02d} {}".format(day_name, day, month_name)

    def _format_debug(self):
        """Format debug line: offset, RTT, stratum, sync age, next sync."""
        off = self.ntp.get_offset_ms()
        rtt = self.ntp.rtt_ms
        strat = self.ntp.stratum

        # Time since last sync
        if self.ntp.last_sync_time > 0:
            age_s = time.time() - self.ntp.last_sync_time
            if age_s < 60:
                age_str = '{}s'.format(age_s)
            elif age_s < 3600:
                age_str = '{}m'.format(age_s // 60)
            else:
                age_str = '{}h'.format(age_s // 3600)

            # Time until next sync
            remaining = max(0, self.ntp._next_sync_interval - age_s)
            if remaining < 60:
                nxt = '{}s'.format(int(remaining))
            elif remaining < 3600:
                nxt = '{}m'.format(int(remaining // 60))
            else:
                nxt = '{}h'.format(int(remaining // 3600))
            age_str = '{}/{}'.format(age_str, nxt)
        else:
            age_str = '--'

        return 'O{}ms S{} {}'.format(off, strat, age_str)

    def _render_time(self, time_str, start_y, now_ticks):
        """Render HH:MM:SS with transitions."""
        scale = 2
        char_w = FONT_W * scale
        char_h = FONT_H * scale
        gap = 2
        total_w = string_width(time_str, scale)
        start_x = (COLS - total_w) // 2
        spacing = char_w + gap

        frac_ms = now_ticks % 1000
        frac = frac_ms / 1000.0

        for i, ch in enumerate(time_str):
            x = start_x + i * spacing

            if ch == ':':
                alpha = self._colon_alpha(frac)
                if alpha > 0:
                    pen = self._alpha_pen(alpha)
                    draw_char(self.g, ':', x, start_y, pen, scale)
                continue

            # Transition animation
            slot = self._digit_slots.get(i)
            if slot is None:
                self._digit_slots[i] = (ch, ch, 0)
                draw_char(self.g, ch, x, start_y, self.pen_main, scale)
                continue

            prev_ch, cur_ch, start_t = slot
            if ch != cur_ch:
                # Digit changed
                self._digit_slots[i] = (cur_ch, ch, now_ticks)
                prev_ch, cur_ch, start_t = cur_ch, ch, now_ticks

            if start_t == 0 or prev_ch == cur_ch:
                draw_char(self.g, ch, x, start_y, self.pen_main, scale)
                continue

            elapsed = time.ticks_diff(now_ticks, start_t)
            progress = min(1.0, elapsed / ANIM_DURATION)

            if progress >= 1.0:
                draw_char(self.g, ch, x, start_y, self.pen_main, scale)
                continue

            # Cubic ease-out
            eased = 1.0 - (1.0 - progress) ** 3
            mode = self.config.get("transition_mode", "scroll")

            if mode == "scroll":
                offset = int(eased * (char_h + 2))
                old_alpha = 1.0 - eased
                new_alpha = eased
                if old_alpha > 0.05:
                    pen_old = self._alpha_pen(old_alpha)
                    self._draw_char_clipped(prev_ch, x, start_y - offset, scale, pen_old)
                if new_alpha > 0.05:
                    pen_new = self._alpha_pen(new_alpha)
                    self._draw_char_clipped(cur_ch, x, start_y + char_h + 2 - offset, scale, pen_new)
            elif mode == "crossfade":
                if eased < 1.0:
                    pen_old = self._alpha_pen(1.0 - eased)
                    draw_char(self.g, prev_ch, x, start_y, pen_old, scale)
                pen_new = self._alpha_pen(eased)
                draw_char(self.g, cur_ch, x, start_y, pen_new, scale)
            else:
                # snap
                draw_char(self.g, ch, x, start_y, self.pen_main, scale)

    def _colon_alpha(self, frac):
        """Calculate colon visibility based on style."""
        style = self.config.get("colon_style", "blink")
        if style == "solid":
            return 1.0
        if style == "blink":
            return 1.0 if frac < 0.5 else 0.0
        # pulse
        return 0.3 + 0.7 * (0.5 + 0.5 * math.cos(frac * 2 * math.pi))

    def _alpha_pen(self, alpha):
        """Create a pen with the main color scaled by alpha."""
        r, g, b = self.config.color()
        br = self.config.brightness_frac()
        return self.g.create_pen(
            int(r * br * alpha),
            int(g * br * alpha),
            int(b * br * alpha),
        )

    def _draw_char_clipped(self, ch, ox, oy, scale, pen):
        """Draw a character clipped to display bounds."""
        bitmap = FONT.get(ch)
        if not bitmap:
            return
        self.g.set_pen(pen)
        for row in range(FONT_H):
            for col in range(FONT_W):
                if bitmap[row] & (1 << (FONT_W - 1 - col)):
                    for sy in range(scale):
                        for sx in range(scale):
                            px = ox + col * scale + sx
                            py = oy + row * scale + sy
                            if 0 <= px < COLS and 0 <= py < ROWS:
                                self.g.pixel(px, py)

    def _render_ntp(self, y_base):
        """Render the NTP status bar."""
        # Separator line
        self.g.set_pen(self.pen_sep)
        for x in range(COLS):
            self.g.pixel(x, y_base)

        synced = self.ntp.synced
        sync_pen = self.pen_sync_ok if synced else self.pen_sync_fail
        sync_dim_pen = self.pen_sync_ok_dim if synced else self.pen_sync_fail_dim

        # === LEFT: SYNC box ===
        box_l, box_r = 1, 21
        box_t, box_b = y_base + 2, y_base + 8
        self._draw_rect(box_l, box_t, box_r, box_b, sync_dim_pen)

        if synced:
            draw_tiny_str(self.g, 'SYNC', box_l + 3, box_t + 1, sync_pen)
        else:
            # Draw "----"
            self.g.set_pen(sync_pen)
            for dx in range(4):
                lx = box_l + 3 + dx * 4
                ly = box_t + 3
                for px in range(3):
                    self.g.pixel(lx + px, ly)

        # === RIGHT: STRAT box ===
        s_box_l, s_box_r = COLS - 25, COLS - 2
        s_box_t, s_box_b = y_base + 2, y_base + 8
        strat_pen = self.pen_strat if synced else self.pen_grey
        strat_dim_pen = self.pen_strat_dim if synced else self.pen_tick
        self._draw_rect(s_box_l, s_box_t, s_box_r, s_box_b, strat_dim_pen)
        draw_tiny_str(self.g, 'STRAT', s_box_l + 2, s_box_t + 1, strat_pen)

        # === GMT + Stratum readouts in gaps ===
        utc_offset = self.config.get("utc_offset", 0)
        sign = '+' if utc_offset >= 0 else '-'
        gmt_str = 'GMT{}{}'.format(sign, abs(utc_offset))
        gmt_x = box_r + 3
        gmt_vy = box_t + ((box_b - box_t - TINY_H) // 2) + 1
        draw_tiny_str(self.g, gmt_str, gmt_x, gmt_vy, self.pen_grey)

        strat_str = str(self.ntp.stratum) if self.ntp.stratum > 0 else '-'
        strat_w = tiny_str_width(strat_str)
        strat_x = s_box_l - strat_w - 3
        draw_tiny_str(self.g, strat_str, strat_x, gmt_vy, self.pen_grey)

        # === CENTER: Offset bar ===
        bar_center = 64
        bar_y = y_base + 3
        bar_h = 3
        max_bar_px = 16
        offset_ms = self.ntp.get_offset_ms()
        offset_px = max(-max_bar_px, min(max_bar_px, int((offset_ms / 50) * max_bar_px)))

        # Color by magnitude
        abs_off = abs(offset_ms)
        bar_pen = (self.pen_bar_green if abs_off < 10
                   else self.pen_bar_yellow if abs_off < 30
                   else self.pen_bar_red)

        # Scale ticks
        for tick in range(-50, 51, 10):
            if tick == 0:
                continue
            tx = bar_center + (tick * max_bar_px) // 50
            self.g.set_pen(self.pen_tick)
            self.g.pixel(tx, bar_y)
            self.g.pixel(tx, bar_y + bar_h - 1)

        # Center reference line
        self.g.set_pen(self.pen_center)
        for by in range(bar_h):
            self.g.pixel(bar_center, bar_y + by)

        # Offset bar
        if offset_px != 0:
            d = 1 if offset_px > 0 else -1
            self.g.set_pen(bar_pen)
            for i in range(1, abs(offset_px) + 1):
                bx = bar_center + d * i
                for by in range(bar_h):
                    self.g.pixel(bx, bar_y + by)

    def _draw_rect(self, x1, y1, x2, y2, pen):
        """Draw a 1px outline rectangle."""
        self.g.set_pen(pen)
        for x in range(x1, x2 + 1):
            self.g.pixel(x, y1)
            self.g.pixel(x, y2)
        for y in range(y1 + 1, y2):
            self.g.pixel(x1, y)
            self.g.pixel(x2, y)
