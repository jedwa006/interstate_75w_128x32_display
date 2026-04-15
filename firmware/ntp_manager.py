import time
import gc
import machine


class NTPManager:
    """Manages WiFi connectivity, NTP synchronization, and RGB LED status."""

    def __init__(self, i75, config):
        self.i75 = i75
        self.config = config

        # WiFi state
        self.wifi_connected = False
        self._wlan = None

        # NTP state
        self.synced = False
        self.last_sync_time = 0       # time.time() of last successful sync
        self.last_sync_ticks = 0      # ticks_ms at last sync
        self.sync_count = 0
        self.fail_count = 0
        self.stratum = 0              # NTP stratum (estimated)
        self.offset_ms = 0            # estimated offset in ms

        # LED state
        self._led_state_time = 0      # ticks_ms when last state change occurred
        self._led_dimmed = False
        self._led_blink_phase = False

        # Reconnect backoff
        self._retry_delay = 15
        self._last_retry_ticks = 0

    def connect_wifi(self):
        """Attempt to connect to WiFi. Returns True on success."""
        ssid = self.config["wifi_ssid"]
        password = self.config["wifi_password"]

        if not ssid:
            self._set_led(80, 0, 0)  # dim red — no credentials
            return False

        self._set_led(0, 0, 60)  # blue — connecting
        self._led_dimmed = False

        # Try ezwifi first (Pimoroni build)
        try:
            import ezwifi
            wifi = ezwifi.EzWiFi()
            wifi.connect(ssid=ssid, password=password, timeout=30, retries=3, verbose=False)
            self.wifi_connected = wifi.isconnected()
        except ImportError:
            # Fall back to raw network module
            try:
                import network
                self._wlan = network.WLAN(network.STA_IF)
                self._wlan.active(True)
                self._wlan.connect(ssid, password)

                max_wait = 30
                while max_wait > 0:
                    if self._wlan.status() >= 3:
                        break
                    if self._wlan.status() < 0:
                        break
                    max_wait -= 1
                    time.sleep(1)

                self.wifi_connected = self._wlan.isconnected()
            except ImportError:
                self.wifi_connected = False

        if self.wifi_connected:
            self._set_led(0, 80, 0)  # green — connected
            self._led_state_time = time.ticks_ms()
            self._retry_delay = 15
        else:
            self._set_led(80, 0, 0)  # red — failed
            self._led_state_time = time.ticks_ms()

        return self.wifi_connected

    def check_wifi(self):
        """Check WiFi connection and attempt reconnect if needed."""
        connected = False
        if self._wlan:
            connected = self._wlan.isconnected()
        else:
            try:
                import ezwifi
                # ezwifi doesn't expose a persistent object easily,
                # check via network module
                import network
                wlan = network.WLAN(network.STA_IF)
                connected = wlan.isconnected()
            except ImportError:
                pass

        if connected and not self.wifi_connected:
            # Just reconnected
            self.wifi_connected = True
            self._set_led(0, 80, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False
        elif not connected and self.wifi_connected:
            # Just lost connection
            self.wifi_connected = False
            self.synced = False
            self._set_led(80, 0, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False

        # Attempt reconnect with backoff
        if not connected:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_retry_ticks) > self._retry_delay * 1000:
                self._last_retry_ticks = now
                self.connect_wifi()
                # Increase backoff: 15 → 30 → 60 → 120s max
                self._retry_delay = min(self._retry_delay * 2, 120)

    def sync_ntp(self):
        """Attempt NTP time sync. Returns True on success."""
        if not self.wifi_connected:
            return False

        gc.collect()

        try:
            import ntptime
            ntptime.host = self.config.get("ntp_server", "pool.ntp.org")

            before_ticks = time.ticks_ms()
            ntptime.settime()
            after_ticks = time.ticks_ms()

            # Estimate round-trip time as rough offset indicator
            rtt = time.ticks_diff(after_ticks, before_ticks)
            self.offset_ms = rtt // 2  # rough estimate

            self.synced = True
            self.last_sync_time = time.time()
            self.last_sync_ticks = after_ticks
            self.sync_count += 1
            self.stratum = 2  # assume stratum 2 (ntptime doesn't expose this)

            # Brief green flash to indicate sync
            self._set_led(0, 80, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False

            return True

        except (OSError, RuntimeError, OverflowError) as e:
            self.fail_count += 1
            return False

    def check_resync(self):
        """Check if it's time to resync NTP."""
        if not self.wifi_connected:
            return
        interval = self.config.get("ntp_sync_interval", 3600)
        if self.last_sync_time == 0 or (time.time() - self.last_sync_time) >= interval:
            self.sync_ntp()

    def get_local_time(self):
        """Get current local time as (year, month, day, hour, minute, second, weekday)."""
        utc_offset = self.config.get("utc_offset", 0)
        dst_offset = 0

        utc_epoch = time.time()
        local_epoch = utc_epoch + utc_offset * 3600

        # Check DST
        if self.config.get("dst_enabled", False):
            lt = time.gmtime(local_epoch)
            dst_offset = _check_dst(lt, self.config.get("dst_rules", "US"))
            local_epoch += dst_offset

        lt = time.gmtime(local_epoch)
        # time.gmtime returns (year, month, mday, hour, minute, second, weekday, yearday)
        return lt[0], lt[1], lt[2], lt[3], lt[4], lt[5], lt[6]

    def get_offset_ms(self):
        """Return estimated NTP offset in ms for display."""
        if not self.synced:
            return 0
        # After initial sync, drift accumulates — estimate based on elapsed time
        # Assume ~30 PPM drift (typical crystal)
        elapsed_s = time.ticks_diff(time.ticks_ms(), self.last_sync_ticks) / 1000
        drift_ms = elapsed_s * 0.03  # 30 PPM = 0.03 ms/s
        return int(self.offset_ms + drift_ms)

    def update_led(self):
        """Update RGB LED — auto-dim after 30s of stable state."""
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._led_state_time)

        if not self._led_dimmed and elapsed > 30000:
            # Fade to off after 30s stable
            self.i75.set_led(0, 0, 0)
            self._led_dimmed = True

        # Blink blue while connecting (not connected, not dimmed)
        if not self.wifi_connected and not self._led_dimmed:
            if (now // 500) % 2:
                self.i75.set_led(0, 0, 60)
            else:
                self.i75.set_led(0, 0, 10)

    def _set_led(self, r, g, b):
        """Set LED color and reset dim timer."""
        self.i75.set_led(r, g, b)
        self._led_dimmed = False
        self._led_state_time = time.ticks_ms()


def _check_dst(lt, rules):
    """Check if DST is active. Returns 3600 if DST, 0 if not.
    lt = (year, month, mday, hour, minute, second, weekday, yearday)
    weekday: 0=Monday in MicroPython's time module
    """
    year, month, mday, hour = lt[0], lt[1], lt[2], lt[3]
    wday = lt[6]  # 0=Monday

    if rules == "US":
        # US: 2nd Sunday of March 2:00 AM → 1st Sunday of November 2:00 AM
        if month < 3 or month > 11:
            return 0
        if month > 3 and month < 11:
            return 3600
        if month == 3:
            # Find 2nd Sunday: day of first Sunday + 7
            # Day 1 weekday → first Sunday = 1 + (6 - wday_of_day1) % 7
            # Simpler: check if we're past the 2nd Sunday
            first_sunday = 1 + (6 - _weekday_of(year, 3, 1)) % 7
            second_sunday = first_sunday + 7
            if mday > second_sunday:
                return 3600
            if mday == second_sunday and hour >= 2:
                return 3600
            return 0
        if month == 11:
            first_sunday = 1 + (6 - _weekday_of(year, 11, 1)) % 7
            if mday < first_sunday:
                return 3600
            if mday == first_sunday and hour < 2:
                return 3600
            return 0

    elif rules == "EU":
        # EU: Last Sunday of March 1:00 UTC → Last Sunday of October 1:00 UTC
        if month < 3 or month > 10:
            return 0
        if month > 3 and month < 10:
            return 3600
        if month == 3:
            last_sunday = 31 - (_weekday_of(year, 3, 31) + 1) % 7
            if mday > last_sunday:
                return 3600
            if mday == last_sunday and hour >= 1:
                return 3600
            return 0
        if month == 10:
            last_sunday = 31 - (_weekday_of(year, 10, 31) + 1) % 7
            if mday < last_sunday:
                return 3600
            if mday == last_sunday and hour < 1:
                return 3600
            return 0

    return 0


def _weekday_of(year, month, day):
    """Return weekday (0=Monday) for a given date using Zeller-like formula."""
    # Tomohiko Sakamoto's algorithm (returns 0=Sunday)
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if month < 3:
        year -= 1
    dow = (year + year // 4 - year // 100 + year // 400 + t[month - 1] + day) % 7
    # Convert: 0=Sunday → 6=Sunday (MicroPython: 0=Monday)
    return (dow - 1) % 7
