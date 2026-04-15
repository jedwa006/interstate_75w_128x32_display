# Configuration Guide

The clock can be configured in three ways:

1. **`config.json`** — edit before deploying or via USB while connected
2. **`secrets.py`** — fallback for WiFi credentials (Pimoroni ezwifi compatible)
3. **On-device button menu** — change settings at runtime

Settings are loaded in priority order: defaults -> config.json -> secrets.py (WiFi only) -> button menu overrides. Menu changes are saved back to config.json automatically.

## config.json

Copy `config.json.example` to `config.json` and edit your values:

```json
{
  "wifi_ssid": "YourNetworkName",
  "wifi_password": "YourPassword",
  "ntp_server": "pool.ntp.org",
  "ntp_sync_interval": 3600,
  "utc_offset": -6,
  "dst_enabled": true,
  "dst_rules": "US",
  "color_r": 255,
  "color_g": 255,
  "color_b": 240,
  "brightness": 85,
  "colon_style": "blink",
  "date_format": "iso",
  "transition_mode": "scroll",
  "color_order": "RBG"
}
```

### WiFi Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `wifi_ssid` | string | `""` | Your WiFi network name. **Required.** |
| `wifi_password` | string | `""` | Your WiFi password. **Required.** |

### NTP Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ntp_server` | string | `"pool.ntp.org"` | NTP server hostname. See [Choosing an NTP Server](#choosing-an-ntp-server) below. |
| `ntp_sync_interval` | int (seconds) | `3600` | How often to re-sync with NTP. Default is 1 hour. Minimum recommended: 900 (15 min). |

### Timezone Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `utc_offset` | int | `-6` | Hours offset from UTC. Examples: `-8` (PST), `-7` (MST), `-6` (CST), `-5` (EST), `0` (UTC/GMT), `+1` (CET), `+9` (JST). |
| `dst_enabled` | bool | `true` | Enable automatic Daylight Saving Time adjustment. |
| `dst_rules` | string | `"US"` | Which DST rule set to use. `"US"` or `"EU"`. |

**US DST**: 2nd Sunday of March at 2:00 AM through 1st Sunday of November at 2:00 AM (+1 hour).

**EU DST**: Last Sunday of March at 1:00 UTC through last Sunday of October at 1:00 UTC (+1 hour).

### Display Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `color_r` | int (0-255) | `255` | Red component of digit color. |
| `color_g` | int (0-255) | `255` | Green component of digit color. |
| `color_b` | int (0-255) | `240` | Blue component of digit color. |
| `brightness` | int (10-100) | `85` | Display brightness percentage. |
| `colon_style` | string | `"blink"` | Colon separator behavior: `"blink"`, `"pulse"`, or `"solid"`. |
| `date_format` | string | `"iso"` | Date display format (see below). |
| `transition_mode` | string | `"scroll"` | Digit change animation (see below). |
| `color_order` | string | `"RBG"` | HUB75 panel color order. See [Panel Color Order](#panel-color-order). |

#### Color Presets

These RGB values are available via the button menu, or set manually in config.json:

| Name | R | G | B |
|------|---|---|---|
| White | 255 | 255 | 240 |
| Green | 0 | 255 | 50 |
| Amber | 255 | 160 | 0 |
| Red | 255 | 30 | 10 |
| Blue | 40 | 80 | 255 |
| Cyan | 0 | 230 | 220 |

You can set any custom RGB value in config.json — the presets above are just the ones accessible via the button menu.

#### Date Formats

| Value | Example | Description |
|-------|---------|-------------|
| `"iso"` | `2026-04-14` | ISO 8601 format |
| `"short"` | `MON APR 14` | Day name + month + date |
| `"day"` | `MON 14 APR` | Day name + date + month |
| `"debug"` | `O15ms R24ms S1 42s` | NTP debug info (offset, RTT, stratum, sync age) |

The debug format is useful for monitoring NTP accuracy and diagnosing sync issues. Values shown:
- **O**: Current estimated offset in milliseconds (starts at RTT/2 after sync, grows with crystal drift)
- **R**: Last measured round-trip time to the NTP server in milliseconds
- **S**: NTP stratum of the time source (1 = atomic clock, 2 = one hop away, etc.)
- **Sync age**: Time since last successful NTP sync (seconds/minutes/hours)

#### Transition Modes

| Value | Description |
|-------|-------------|
| `"scroll"` | Digits scroll vertically with eased animation (400ms, cubic ease-out). |
| `"crossfade"` | Old digit fades out while new digit fades in. |
| `"snap"` | Instant change, no animation. |

#### Panel Color Order

HUB75 panels vary in their RGB wiring. If colors appear swapped (e.g., green shows as blue), change the `color_order` setting. To determine your panel's color order, see [Troubleshooting: Wrong Colors](#troubleshooting-wrong-colors).

| Value | Description |
|-------|-------------|
| `"RGB"` | Standard RGB ordering |
| `"RBG"` | Red-Blue-Green (default — correct for Waveshare P2.5 64x32 panels) |
| `"GRB"` | Green-Red-Blue |
| `"GBR"` | Green-Blue-Red |
| `"BRG"` | Blue-Red-Green |
| `"BGR"` | Blue-Green-Red |

## secrets.py

If `wifi_ssid` is empty in config.json, the firmware falls back to `secrets.py` for WiFi credentials. This is compatible with Pimoroni's `ezwifi` convention used in their examples.

Copy `secrets.py.example` to `secrets.py`:

```python
WIFI_SSID = "YourNetworkName"
WIFI_PASSWORD = "YourPassword"
```

Only WiFi credentials are read from this file. All other settings must be in config.json.

**Important**: Both `config.json` and `secrets.py` are gitignored to prevent accidentally publishing your WiFi credentials.

## Button Menu

Press **Button A** or **Button B** on the Interstate 75W to open the on-screen menu. The menu overlays the display and shows color-coded button position indicators aligned with the physical buttons on the back of the board (B in grey, A in orange).

The menu auto-hides after 5 seconds of no input and saves all changes to config.json.

| Button | Action |
|--------|--------|
| **A** (right, looking at display) | Navigate to next menu item |
| **B** (left, looking at display) | Cycle through values for current item |
| *(wait 5s)* | Menu auto-closes and saves all changes to config.json |

Note: Buttons are on the back of the board, so they appear mirrored when looking at the display. The on-screen indicators show the correct physical positions.

### Menu Items

1. **BRIGHT** — Brightness: 10%, 25%, 50%, 75%, 85%, 100%
2. **COLOR** — Theme: White, Green, Amber, Red, Blue, Cyan
3. **COLON** — Colon style: Blink, Pulse, Solid
4. **DATE** — Date format: ISO, Short, Day, Debug
5. **TRANS** — Transition: Scroll, Crossfade, Snap
6. **UTC** — UTC offset: -12 through +14
7. **DST** — DST enabled: ON / OFF
8. **NTP SYNC** — Press B to force an immediate NTP resync
9. **SHOW IP** — Displays the device's current IP address

## Milliseconds Display

The clock shows milliseconds in a small font to the right of the seconds digits (e.g., `.547`). The brightness of the milliseconds automatically reflects the current time accuracy:

| Offset | ms Brightness | Meaning |
|--------|---------------|---------|
| < 10ms | 50% | High confidence — just synced with low RTT |
| 10-30ms | 30% | Moderate — normal operating range |
| 30-100ms | 15% | Low confidence — drift accumulating, resync soon |
| > 100ms | Hidden | Too inaccurate to display meaningfully |

This provides an honest visual indicator: right after a sync to a stratum 1 server like `time.nist.gov`, the milliseconds are bright and accurate. As crystal drift accumulates between syncs, they gracefully fade to acknowledge growing uncertainty.

### How Accurate Are the Milliseconds?

The RP2350's `ticks_ms()` has genuine 1ms resolution for the counter itself. The accuracy depends on:

- **Right after NTP sync**: Accurate to within RTT/2 (typically 10-20ms for internet servers, <5ms for LAN servers)
- **Between syncs**: Crystal drift adds ~0.03ms per second (30 PPM typical), so after 1 hour: ~108ms accumulated drift
- **With `time.nist.gov` (stratum 1, local to Colorado)**: ~12ms RTT gives ~6ms initial uncertainty

The milliseconds are driven by the local crystal oscillator, disciplined by periodic NTP syncs. They're not "NTP-accurate milliseconds" — they're "crystal-interpolated milliseconds anchored to NTP second boundaries."

## Choosing an NTP Server

The default `pool.ntp.org` works well for most setups. However, you can improve accuracy by using a server with lower network latency:

| Server | Use Case |
|--------|----------|
| `pool.ntp.org` | Global pool, good default |
| `us.pool.ntp.org` | US-based pool |
| `time.nist.gov` | NIST Boulder, CO — stratum 1, excellent if you're nearby |
| `time.google.com` | Google's NTP service |
| `time.cloudflare.com` | Cloudflare's NTP service |
| *(local IP)* | Your own NTP server on the LAN for lowest latency |

If you have a local NTP device on your network, pointing to that will give you the best offset (sub-5ms) since you eliminate internet round-trip variability.

### NTP Implementation Details

The firmware implements a custom NTP client (not the basic `ntptime` module) that:

1. Sends a raw NTPv4 UDP packet to the configured server
2. Measures round-trip time using `ticks_ms()` for precise local timing
3. Extracts the **real stratum** from byte 1 of the server response
4. Sets the RTC from the server's transmit timestamp (T3)
5. Records RTT/2 as the initial offset uncertainty
6. Estimates drift between syncs at ~30 PPM (0.03 ms/s)

**Current sync policy:**
- Sync immediately on boot after WiFi connects
- Resync every `ntp_sync_interval` seconds (default: 1 hour)
- Resync when WiFi reconnects after a disconnect
- Manual resync available via the button menu

**Epoch handling:** The firmware auto-detects whether the MicroPython build uses a 1970 (Unix) or 2000 epoch, ensuring correct time regardless of firmware version.

## RGB LED Behavior

The onboard RGB LED indicates WiFi/sync status:

| Color | Meaning |
|-------|---------|
| Blinking blue | Connecting to WiFi |
| Solid green | WiFi connected / NTP synced |
| Solid red | WiFi disconnected or connection failed |
| *(off)* | LED auto-dims to off after 30 seconds of stable connection |

Any status change (disconnect, resync, error) brings the LED back to full brightness, then it dims again after 30 seconds of stability. This prevents the LED from being a constant distraction during normal operation.

## NTP Status Indicators

The bottom of the display shows real-time NTP status:

```
 [SYNC]  GMT-6  ····|····  2  [STRAT]
```

| Indicator | Description |
|-----------|-------------|
| **SYNC box** | Green border + "SYNC" when NTP is synced, red "----" when not |
| **GMT offset** | Your configured UTC offset (e.g., GMT-6), shown between SYNC box and offset bar |
| **Offset bar** | Horizontal bar showing estimated clock offset. Extends left or right from center. Green < 10ms, yellow < 30ms, red >= 30ms. Scale: +-50ms across +-16 pixels |
| **Stratum** | NTP stratum number, shown between offset bar and STRAT box |
| **STRAT box** | Green border + "STRAT" label |
| **Separator line** | Dim horizontal line separating the clock face from the status bar |

### Understanding the Offset Bar

The offset bar is the horizontal indicator in the center of the NTP status area. It shows how far the local clock might be from true time:

- **Center line**: Zero offset (perfect sync)
- **Bar extending right**: Positive offset (clock may be ahead)
- **Bar extending left**: Negative offset (clock may be behind)
- **Color**: Green (< 10ms), yellow (10-30ms), red (>= 30ms)
- **Scale**: Each pixel = ~3.1ms, full range is +-50ms (+-16 pixels)

Right after a sync, the bar shows RTT/2 (your network uncertainty floor). Between syncs, it grows as crystal drift accumulates. After a resync, it snaps back to a small value.

### Understanding Stratum

NTP stratum indicates the hierarchy level of your time source:

| Stratum | Meaning | Example |
|---------|---------|---------|
| 0 | Reference clock (GPS, atomic) | Not directly accessible via NTP |
| 1 | Directly connected to stratum 0 | `time.nist.gov` (NIST atomic clocks) |
| 2 | Syncs from a stratum 1 server | Most `pool.ntp.org` servers |
| 3+ | Each hop adds 1 | Home routers acting as NTP servers |

Lower stratum = closer to an atomic clock = more trustworthy. With `time.nist.gov`, you'll typically see stratum 1.

## Troubleshooting

### Wrong Colors

If colors on your display are swapped (green shows as blue, etc.), your panels use a different color order than the default. To determine the correct order:

1. Connect via Thonny or `mpremote`
2. Stop the running program (Ctrl+C)
3. Run this test:

```python
from interstate75 import Interstate75
i75 = Interstate75(display=Interstate75.DISPLAY_INTERSTATE75_128X32)
g = i75.display
g.set_pen(g.create_pen(0, 0, 0))
g.clear()
g.set_pen(g.create_pen(255, 0, 0)); g.rectangle(5, 5, 10, 10)    # Should be RED
g.set_pen(g.create_pen(0, 255, 0)); g.rectangle(25, 5, 10, 10)   # Should be GREEN
g.set_pen(g.create_pen(0, 0, 255)); g.rectangle(45, 5, 10, 10)   # Should be BLUE
g.set_pen(g.create_pen(100,100,100))
g.text('R', 8, 18, scale=1); g.text('G', 28, 18, scale=1); g.text('B', 48, 18, scale=1)
i75.update()
```

4. Note which actual color appears above each label
5. Map the result to a `color_order` value:
   - R=red, G=green, B=blue → `"RGB"`
   - R=red, G=blue, B=green → `"RBG"` (Waveshare P2.5 64x32)
   - R=green, G=red, B=blue → `"GRB"`
   - etc.

### Display Shows "ERR CHECK REPL"

The main loop caught an exception. Connect via Thonny or `mpremote` to see the error traceback in the serial console. Common causes:
- WiFi credentials incorrect
- NTP server unreachable
- Memory issue (try reducing `ntp_sync_interval`)

### Display Stuck on "CONNECTING"

WiFi is failing to connect. Check:
- SSID and password are correct in `config.json`
- The network is 2.4GHz (the RP2350's WiFi module doesn't support 5GHz)
- The board is within range of the access point

### Year Shows Wrong (e.g., 1996)

This was caused by an epoch mismatch in earlier firmware versions. Update to the latest firmware — it auto-detects the MicroPython epoch (1970 vs 2000).

### Board Doesn't Boot After Flashing UF2

See the [Building Firmware From Source](../README.md#building-firmware-from-source) section. The pre-built v0.0.5 release may not work with all board revisions. Building from the latest source resolves this.
