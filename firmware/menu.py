import time
from fonts import draw_tiny, draw_tiny_str, draw_tiny_centered, tiny_str_width

COLS = 128
AUTO_HIDE_MS = 5000  # hide menu after 5s of no input

MENU_ITEMS = (
    ("BRIGHT", "brightness", (10, 25, 50, 75, 85, 100)),
    ("COLOR", "color_preset", ("WHITE", "GREEN", "AMBER", "RED", "BLUE", "CYAN")),
    ("COLON", "colon_style", ("blink", "pulse", "solid")),
    ("DATE", "date_format", ("iso", "short", "day", "debug")),
    ("TRANS", "transition_mode", ("scroll", "crossfade", "snap")),
    ("UTC", "utc_offset", tuple(range(-12, 15))),
    ("DST", "dst_enabled", (True, False)),
    ("NIGHT", "night_mode_enabled", (True, False)),
    ("NTP SYNC", "_action_sync", None),
    ("SHOW IP", "_action_ip", None),
)

COLOR_PRESETS = {
    "WHITE": (255, 255, 240),
    "GREEN": (0, 255, 50),
    "AMBER": (255, 160, 0),
    "RED": (255, 30, 10),
    "BLUE": (40, 80, 255),
    "CYAN": (0, 230, 220),
}


class Menu:
    """On-screen menu system for button-based configuration."""

    def __init__(self, i75, graphics, config, ntp):
        self.i75 = i75
        self.g = graphics
        self.config = config
        self.ntp = ntp

        self.active = False
        self.cursor = 0
        self.last_input_ticks = 0

        # Debounce: track previous state + minimum time between actions
        self._last_a = False
        self._last_b = False
        self._last_action_ticks = 0
        self._debounce_ms = 200  # minimum ms between button actions

        # Pens
        self.pen_bg = self.g.create_pen(0, 0, 0)
        self.pen_label = self.g.create_pen(100, 100, 100)
        self.pen_value = self.g.create_pen(200, 200, 200)
        self.pen_highlight = self.g.create_pen(255, 180, 0)

    def handle_input(self, a_pressed, b_pressed):
        """Process button input. Returns True if menu is active."""
        now = time.ticks_ms()

        # Edge detection (press, not hold)
        a_edge = a_pressed and not self._last_a
        b_edge = b_pressed and not self._last_b
        self._last_a = a_pressed
        self._last_b = b_pressed

        if not a_edge and not b_edge:
            # Check auto-hide
            if self.active and time.ticks_diff(now, self.last_input_ticks) > AUTO_HIDE_MS:
                self._deactivate()
            return self.active

        # Debounce: ignore edges that come too fast
        if time.ticks_diff(now, self._last_action_ticks) < self._debounce_ms:
            return self.active

        self._last_action_ticks = now
        self.last_input_ticks = now

        if not self.active:
            # Any button press activates menu
            self.active = True
            return True

        if a_edge:
            # Navigate to next item
            self.cursor = (self.cursor + 1) % len(MENU_ITEMS)

        if b_edge:
            # Change value or execute action
            self._select_current()

        return True

    def _select_current(self):
        """Handle selection of current menu item."""
        name, key, values = MENU_ITEMS[self.cursor]

        if key == "_action_sync":
            self.ntp.sync_ntp()
            return

        if key == "_action_ip":
            # IP display is handled in render
            return

        if values is None:
            return

        if key == "color_preset":
            # Cycle through color presets
            current = self._get_current_preset()
            idx = 0
            for i, v in enumerate(values):
                if v == current:
                    idx = i
                    break
            idx = (idx + 1) % len(values)
            preset = values[idx]
            r, g, b = COLOR_PRESETS.get(preset, (255, 255, 240))
            self.config["color_r"] = r
            self.config["color_g"] = g
            self.config["color_b"] = b
            return

        # Cycle through values
        current = self.config.get(key)
        idx = 0
        for i, v in enumerate(values):
            if v == current:
                idx = i
                break
        idx = (idx + 1) % len(values)
        self.config[key] = values[idx]

    def _get_current_preset(self):
        """Find which color preset matches current config."""
        r, g, b = self.config.color()
        for name, (pr, pg, pb) in COLOR_PRESETS.items():
            if r == pr and g == pg and b == pb:
                return name
        return "WHITE"

    def _deactivate(self):
        """Leave menu and save config."""
        self.active = False
        self.config.save()

    def render(self):
        """Render the menu overlay on the display."""
        if not self.active:
            return

        # Clear display
        self.g.set_pen(self.pen_bg)
        self.g.clear()

        name, key, values = MENU_ITEMS[self.cursor]

        # Title
        draw_tiny_centered(self.g, name, 2, self.pen_highlight)

        # Current value
        val_str = self._get_value_str(key, values)
        draw_tiny_centered(self.g, val_str, 12, self.pen_value)

        # Navigation hint
        draw_tiny_centered(self.g, "A=NEXT  B=SET", 24, self.pen_label)

        # Button position indicators on right edge
        # Physical buttons are on the back, so mirrored from front view:
        # Looking at display: B is left, A is right
        # Indicators: 2px wide, 4px tall, spaced 2px apart
        # Starting ~32px from right edge = x=96
        btn_x = 108
        btn_w = 2
        btn_h = 4
        btn_gap = 2
        btn_y = 0  # top edge

        # B indicator (left)
        self.g.set_pen(self.pen_label)
        self.g.rectangle(btn_x, btn_y, btn_w, btn_h)
        # A indicator (right of B)
        self.g.set_pen(self.pen_highlight)
        self.g.rectangle(btn_x + btn_w + btn_gap, btn_y, btn_w, btn_h)

        # Tiny labels
        draw_tiny(self.g, 'B', btn_x - 4, btn_y, self.pen_label)
        draw_tiny(self.g, 'A', btn_x + btn_w + btn_gap + btn_w + 1, btn_y, self.pen_highlight)

    def _get_value_str(self, key, values):
        """Get display string for current value."""
        if key == "_action_sync":
            return "SYNCED" if self.ntp.synced else "PRESS B"

        if key == "_action_ip":
            try:
                import network
                wlan = network.WLAN(network.STA_IF)
                if wlan.isconnected():
                    return wlan.ifconfig()[0]
            except Exception:
                pass
            return "NO WIFI"

        if key == "color_preset":
            return self._get_current_preset()

        val = self.config.get(key)

        if isinstance(val, bool):
            return "ON" if val else "OFF"

        return str(val).upper()
