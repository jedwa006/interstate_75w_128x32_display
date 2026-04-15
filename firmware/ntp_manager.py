import time
import gc
import struct
import socket
import machine


# NTP epoch is 1900-01-01. MicroPython epoch varies by build:
# Detect at import time:
import time as _time
_NTP_TO_UNIX = 2208988800
_NTP_TO_2000 = 3155673600
NTP_DELTA = _NTP_TO_UNIX if _time.gmtime(0)[0] == 1970 else _NTP_TO_2000

# Adaptive sync constants
DRIFT_LEARN_SYNCS = 3       # how many syncs before trusting drift estimate
DRIFT_LEARN_INTERVAL = 300  # 5 min between learning syncs
DRIFT_THRESHOLD_MS = 20     # resync when estimated offset exceeds this
MIN_SYNC_INTERVAL = 300     # never sync more often than 5 min
DEFAULT_PPM = 30.0          # assumed drift before learning (conservative)


class NTPManager:
    """Manages WiFi, NTP synchronization with adaptive drift-learning."""

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
        self.stratum = 0
        self.offset_ms = 0            # measured offset at last sync (RTT/2)
        self.rtt_ms = 0

        # Drift learning state
        self._drift_ppm = DEFAULT_PPM       # estimated crystal drift in PPM
        self._drift_samples = []            # list of (elapsed_s, measured_offset_ms)
        self._drift_stable = False          # True once we trust our PPM estimate
        self._next_sync_interval = DRIFT_LEARN_INTERVAL  # seconds until next sync
        self._last_pre_sync_offset = 0      # offset measured just before last sync

        # Consecutive failure tracking
        self._consec_fails = 0

        # LED state
        self._led_state_time = 0
        self._led_dimmed = False

        # Reconnect backoff
        self._retry_delay = 15
        self._last_retry_ticks = 0

    def connect_wifi(self):
        """Attempt to connect to WiFi. Returns True on success."""
        ssid = self.config["wifi_ssid"]
        password = self.config["wifi_password"]

        if not ssid:
            self._set_led(80, 0, 0)
            return False

        self._set_led(0, 0, 60)
        self._led_dimmed = False

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
        except Exception:
            self.wifi_connected = False

        if self.wifi_connected:
            self._set_led(0, 80, 0)
            self._led_state_time = time.ticks_ms()
            self._retry_delay = 15
        else:
            self._set_led(80, 0, 0)
            self._led_state_time = time.ticks_ms()

        return self.wifi_connected

    def check_wifi(self):
        """Check WiFi connection and attempt reconnect if needed."""
        connected = False
        if self._wlan:
            connected = self._wlan.isconnected()

        if connected and not self.wifi_connected:
            self.wifi_connected = True
            self._set_led(0, 80, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False
        elif not connected and self.wifi_connected:
            self.wifi_connected = False
            self.synced = False
            self._set_led(80, 0, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False

        if not connected:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_retry_ticks) > self._retry_delay * 1000:
                self._last_retry_ticks = now
                self.connect_wifi()
                self._retry_delay = min(self._retry_delay * 2, 120)

    def sync_ntp(self):
        """Perform NTP sync with real stratum and offset measurement."""
        if not self.wifi_connected:
            return False

        gc.collect()
        host = self.config.get("ntp_server", "pool.ntp.org")

        try:
            addr = socket.getaddrinfo(host, 123)[0][-1]

            pkt = bytearray(48)
            pkt[0] = 0x23

            t1_ticks = time.ticks_ms()

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(5)
            s.sendto(pkt, addr)

            resp = s.recv(48)
            t4_ticks = time.ticks_ms()
            s.close()

            if len(resp) < 48:
                self._on_sync_fail()
                return False

            self.stratum = resp[1]
            self.rtt_ms = time.ticks_diff(t4_ticks, t1_ticks)
            half_rtt = self.rtt_ms // 2

            t3_secs = struct.unpack_from("!I", resp, 40)[0]
            ntp_secs = t3_secs - NTP_DELTA

            # Record pre-sync offset for drift learning
            pre_sync_offset = self.get_offset_ms() if self.synced else 0

            # Set the RTC
            self.offset_ms = half_rtt
            rtc = machine.RTC()
            tm = time.gmtime(ntp_secs)
            rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))

            # Drift learning: if we had a previous sync, measure actual drift
            if self.synced and self.last_sync_ticks > 0:
                elapsed_s = time.ticks_diff(t4_ticks, self.last_sync_ticks) / 1000
                if elapsed_s > 60:  # only learn from intervals > 1 min
                    self._learn_drift(elapsed_s, pre_sync_offset)

            self.synced = True
            self.last_sync_time = time.time()
            self.last_sync_ticks = t4_ticks
            self.sync_count += 1
            self._consec_fails = 0
            self._last_pre_sync_offset = pre_sync_offset

            # Calculate next sync interval
            self._update_sync_interval()

            self._set_led(0, 80, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False

            return True

        except Exception:
            self._on_sync_fail()
            return False

    def _on_sync_fail(self):
        """Handle a failed sync attempt."""
        self.fail_count += 1
        self._consec_fails += 1

        if self._consec_fails >= 3:
            # Multiple failures — something is wrong
            # Tighten sync interval to retry sooner
            self._next_sync_interval = MIN_SYNC_INTERVAL
            # Reset drift learning since we can't trust timing anymore
            self._drift_stable = False
            self._drift_samples = []
            self._drift_ppm = DEFAULT_PPM

    def _learn_drift(self, elapsed_s, pre_sync_offset_ms):
        """Learn crystal drift rate from observed offset between syncs.

        Args:
            elapsed_s: seconds between this sync and the last
            pre_sync_offset_ms: estimated offset just before this sync
        """
        # pre_sync_offset = RTT/2 from last sync + accumulated drift
        # The drift portion is: pre_sync_offset - last_sync_rtt/2
        # But since offset_ms is set to half_rtt at sync, get_offset_ms()
        # already includes the drift accumulation. So pre_sync_offset
        # IS the total offset including initial uncertainty.

        # Store the sample
        self._drift_samples.append((elapsed_s, abs(pre_sync_offset_ms)))

        # Keep last 10 samples
        if len(self._drift_samples) > 10:
            self._drift_samples = self._drift_samples[-10:]

        # Need at least DRIFT_LEARN_SYNCS to estimate
        if len(self._drift_samples) >= DRIFT_LEARN_SYNCS:
            # Calculate average drift rate in PPM
            # offset_ms / elapsed_s gives ms/s, multiply by 1000 for PPM
            total_drift = 0
            total_time = 0
            for es, off_ms in self._drift_samples:
                total_drift += off_ms
                total_time += es

            if total_time > 0:
                avg_ms_per_s = total_drift / total_time
                measured_ppm = avg_ms_per_s * 1000
                # Sanity check: drift should be 1-200 PPM for any reasonable crystal
                if 0.5 < measured_ppm < 200:
                    self._drift_ppm = measured_ppm
                    self._drift_stable = True
                else:
                    # Measurement seems off — could be network jitter
                    # Stay with default but keep learning
                    self._drift_stable = False

    def _update_sync_interval(self):
        """Calculate optimal interval until next sync based on drift rate."""
        max_interval = self.config.get("ntp_sync_interval", 3600)

        if not self._drift_stable:
            # Still learning — use short intervals
            if self.sync_count <= DRIFT_LEARN_SYNCS:
                self._next_sync_interval = DRIFT_LEARN_INTERVAL
            else:
                # Learning phase done but drift is unstable — moderate interval
                self._next_sync_interval = min(900, max_interval)  # 15 min
            return

        # Calculate: how many seconds until drift exceeds threshold?
        # drift_ms = elapsed_s * drift_ppm / 1000
        # threshold = elapsed_s * drift_ppm / 1000 + rtt/2
        # Solve for elapsed_s:
        # elapsed_s = (threshold - rtt/2) * 1000 / drift_ppm
        available_ms = DRIFT_THRESHOLD_MS - (self.rtt_ms // 2)
        if available_ms <= 0:
            # RTT alone exceeds threshold — sync as often as allowed
            self._next_sync_interval = MIN_SYNC_INTERVAL
            return

        if self._drift_ppm > 0:
            optimal_s = int((available_ms * 1000) / self._drift_ppm)
        else:
            optimal_s = max_interval

        # Clamp to min/max
        self._next_sync_interval = max(MIN_SYNC_INTERVAL,
                                       min(optimal_s, max_interval))

    def check_resync(self):
        """Check if it's time to resync NTP, using adaptive interval."""
        if not self.wifi_connected:
            return

        # First sync
        if self.last_sync_time == 0:
            self.sync_ntp()
            return

        elapsed = time.time() - self.last_sync_time
        if elapsed >= self._next_sync_interval:
            self.sync_ntp()

    def get_local_time(self):
        """Get current local time as (year, month, day, hour, minute, second, weekday)."""
        utc_offset = self.config.get("utc_offset", 0)
        dst_offset = 0

        utc_epoch = time.time()
        local_epoch = utc_epoch + utc_offset * 3600

        if self.config.get("dst_enabled", False):
            lt = time.gmtime(local_epoch)
            dst_offset = _check_dst(lt, self.config.get("dst_rules", "US"))
            local_epoch += dst_offset

        lt = time.gmtime(local_epoch)
        return lt[0], lt[1], lt[2], lt[3], lt[4], lt[5], lt[6]

    def get_offset_ms(self):
        """Return estimated current clock uncertainty in ms.

        Immediately after sync: RTT/2 (network uncertainty).
        Between syncs: adds estimated crystal drift.
        """
        if not self.synced:
            return 0
        elapsed_s = time.ticks_diff(time.ticks_ms(), self.last_sync_ticks) / 1000
        drift_ms = elapsed_s * self._drift_ppm / 1000
        return int(self.offset_ms + drift_ms)

    def get_rtt_ms(self):
        """Return last measured round-trip time in ms."""
        return self.rtt_ms

    def get_sync_info(self):
        """Return dict of sync diagnostics for debug display."""
        return {
            'drift_ppm': self._drift_ppm,
            'drift_stable': self._drift_stable,
            'drift_samples': len(self._drift_samples),
            'next_sync_s': self._next_sync_interval,
            'consec_fails': self._consec_fails,
        }

    def update_led(self):
        """Update RGB LED — auto-dim after 30s of stable state."""
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._led_state_time)

        if not self._led_dimmed and elapsed > 30000:
            self.i75.set_led(0, 0, 0)
            self._led_dimmed = True

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
    """Check if DST is active. Returns 3600 if DST, 0 if not."""
    year, month, mday, hour = lt[0], lt[1], lt[2], lt[3]

    if rules == "US":
        if month < 3 or month > 11:
            return 0
        if month > 3 and month < 11:
            return 3600
        if month == 3:
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
    """Return weekday (0=Monday) for a given date."""
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if month < 3:
        year -= 1
    dow = (year + year // 4 - year // 100 + year // 400 + t[month - 1] + day) % 7
    return (dow - 1) % 7
