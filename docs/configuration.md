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
  "transition_mode": "scroll"
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

| Value | Example |
|-------|---------|
| `"iso"` | `2026-04-14` |
| `"short"` | `MON APR 14` |
| `"day"` | `MON 14 APR` |

#### Transition Modes

| Value | Description |
|-------|-------------|
| `"scroll"` | Digits scroll vertically with eased animation (400ms, cubic ease-out). |
| `"crossfade"` | Old digit fades out while new digit fades in. |
| `"snap"` | Instant change, no animation. |

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

Press either physical button to open the on-screen menu. The menu overlays the NTP status area at the bottom of the display.

| Button | Action |
|--------|--------|
| **A** | Navigate to next menu item |
| **B** | Cycle through values for current item |
| *(wait 5s)* | Menu auto-closes and saves all changes to config.json |

### Menu Items

1. **BRIGHT** — Brightness: 10%, 25%, 50%, 75%, 85%, 100%
2. **COLOR** — Theme: White, Green, Amber, Red, Blue, Cyan
3. **COLON** — Colon style: Blink, Pulse, Solid
4. **DATE** — Date format: ISO, Short, Day
5. **TRANS** — Transition: Scroll, Crossfade, Snap
6. **UTC** — UTC offset: -12 through +14
7. **DST** — DST enabled: ON / OFF
8. **NTP SYNC** — Press B to force an immediate NTP resync
9. **SHOW IP** — Displays the device's current IP address

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

## RGB LED Behavior

The onboard RGB LED indicates WiFi/sync status:

| Color | Meaning |
|-------|---------|
| Blinking blue | Connecting to WiFi |
| Solid green | WiFi connected |
| Solid red | WiFi disconnected or connection failed |
| *(off)* | LED auto-dims to off after 30 seconds of stable connection |

Any status change (disconnect, resync, error) brings the LED back to full brightness, then it dims again after 30 seconds of stability.

## NTP Status Indicators

The bottom of the display shows real-time NTP status:

```
 [SYNC]  GMT-6  ····|····  2  [STRAT]
```

| Indicator | Description |
|-----------|-------------|
| **SYNC box** | Green border + "SYNC" when NTP is synced, red "----" when not |
| **GMT offset** | Your configured UTC offset (e.g., GMT-6) |
| **Offset bar** | Horizontal bar showing estimated clock offset from NTP. Green < 10ms, yellow < 30ms, red >= 30ms |
| **Stratum** | NTP stratum level of the time source |
| **STRAT box** | Visual container for stratum indicator |
