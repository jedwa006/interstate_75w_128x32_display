import time
import gc
import struct
import socket
import machine


# NTP epoch is 1900-01-01, MicroPython epoch is 2000-01-01
# Difference in seconds: 70 years worth (including leap years)
NTP_DELTA = 3155673600


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
        self.stratum = 0              # real NTP stratum from server response
        self.offset_ms = 0            # measured clock offset in ms
        self.rtt_ms = 0               # round-trip time in ms

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

        self._set_led(0, 0, 60)  # blue — connecting
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
        """Perform proper NTP sync with offset and stratum calculation.

        NTP offset formula:
            offset = ((T2 - T1) + (T3 - T4)) / 2
        Where:
            T1 = client send time (our clock, before request)
            T2 = server receive time (from NTP response)
            T3 = server transmit time (from NTP response)
            T4 = client receive time (our clock, after response)

        Round-trip delay:
            rtt = (T4 - T1) - (T3 - T2)

        Stratum: read directly from byte 1 of the NTP response.
        """
        if not self.wifi_connected:
            return False

        gc.collect()
        host = self.config.get("ntp_server", "pool.ntp.org")

        try:
            # Resolve host
            addr = socket.getaddrinfo(host, 123)[0][-1]

            # Build NTP request packet (48 bytes)
            # Byte 0: LI=0, Version=4, Mode=3 (client) = 0x23
            pkt = bytearray(48)
            pkt[0] = 0x23

            # Record T1 using ticks_ms for precise relative timing
            t1_ticks = time.ticks_ms()

            # Send request
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(5)
            s.sendto(pkt, addr)

            # Receive response
            resp = s.recv(48)
            t4_ticks = time.ticks_ms()
            s.close()

            if len(resp) < 48:
                self.fail_count += 1
                return False

            # Parse response
            self.stratum = resp[1]

            # RTT from local ticks (most reliable measurement)
            self.rtt_ms = time.ticks_diff(t4_ticks, t1_ticks)

            # Extract T3 (server transmit timestamp) for setting the clock
            t3_secs = struct.unpack_from("!I", resp, 40)[0]
            t3_frac = struct.unpack_from("!I", resp, 44)[0]
            ntp_secs = t3_secs - NTP_DELTA

            # Convert T3 fractional to ms: shift down to avoid overflow
            t3_ms = (t3_frac >> 22) * 1000 >> 10

            # Best estimate of true time: T3 + half RTT
            # The offset is how far our clock was off before correction
            # After we set the clock, offset should be ~RTT/2 (network asymmetry)
            half_rtt = self.rtt_ms // 2

            # Offset after sync: our best-case accuracy is limited by RTT/2
            # (network asymmetry). We can't measure true offset with integer-second
            # time.time(), so we use half-RTT as the uncertainty bound.
            # This represents "we're accurate to within ±half_rtt ms"
            self.offset_ms = half_rtt

            # Set the RTC to server time
            rtc = machine.RTC()
            tm = time.gmtime(ntp_secs)
            rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))

            self.synced = True
            self.last_sync_time = time.time()
            self.last_sync_ticks = t4_ticks
            self.sync_count += 1

            self._set_led(0, 80, 0)
            self._led_state_time = time.ticks_ms()
            self._led_dimmed = False

            return True

        except Exception as e:
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

        if self.config.get("dst_enabled", False):
            lt = time.gmtime(local_epoch)
            dst_offset = _check_dst(lt, self.config.get("dst_rules", "US"))
            local_epoch += dst_offset

        lt = time.gmtime(local_epoch)
        return lt[0], lt[1], lt[2], lt[3], lt[4], lt[5], lt[6]

    def get_offset_ms(self):
        """Return estimated current clock uncertainty in ms.

        Immediately after sync: RTT/2 (network uncertainty).
        Between syncs: adds crystal drift (~30 PPM = 0.03 ms/s).
        So after 1 hour with no resync: RTT/2 + ~108ms drift.
        """
        if not self.synced:
            return 0
        elapsed_s = time.ticks_diff(time.ticks_ms(), self.last_sync_ticks) / 1000
        drift_ms = elapsed_s * 0.03  # 30 PPM = 0.03 ms/s
        return int(self.offset_ms + drift_ms)

    def get_rtt_ms(self):
        """Return last measured round-trip time in ms."""
        return self.rtt_ms

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
