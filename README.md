# Interstate 75W 128x32 NTP Clock

A smooth-scrolling NTP clock display for the [Pimoroni Interstate 75W (RP2350)](https://shop.pimoroni.com/products/interstate-75-w) driving two [Waveshare 64x32 P2.5 HUB75 LED matrix panels](https://www.waveshare.com/wiki/RGB-Matrix-P2.5-64x32) arranged side-by-side for a seamless 128x32 pixel display.

## Features

- **24-hour NTP-synced time** with large 10x14 pixel digits
- **Smooth digit transitions** — vertical scroll, crossfade, or snap
- **Date display** above the time in compact format (ISO, short, or day-first)
- **NTP status bar** with sync indicator, offset bar, GMT offset, and stratum
- **Automatic DST** with US and EU rule sets
- **6 color themes** — White, Green, Amber, Red, Blue, Cyan
- **On-device menu** via physical buttons for runtime configuration
- **WiFi auto-reconnect** with exponential backoff
- **Periodic NTP resync** (configurable interval, default 1 hour)
- **RGB LED status** — WiFi/sync state with auto-dim after 30s

## Display Layout

```
 ┌──────────────────────────────────────────────────────────────┐
 │                      2026-04-14                              │  <- date (tiny font)
 │                                                              │
 │              1 9 : 4 3 : 0 2                                 │  <- time (large font)
 │                                                              │
 │ ─────────────────────────────────────────────────────────── │  <- separator
 │ [SYNC]  GMT-6  ····|····  2  [STRAT]                        │  <- NTP status
 └──────────────────────────────────────────────────────────────┘
```

## Hardware

- [Pimoroni Interstate 75W (RP2350)](https://shop.pimoroni.com/products/interstate-75-w) — the WiFi-enabled RP2350 variant
- 2x [Waveshare 64x32 P2.5 RGB LED Matrix](https://www.waveshare.com/wiki/RGB-Matrix-P2.5-64x32) — HUB75 interface
- USB-C power supply (5V, 3A+ recommended for full brightness)

## Quick Start

### 1. Flash Firmware

Download the latest `i75w_rp2350-*-pimoroni-micropython-with-filesystem.uf2` from the [Interstate 75 releases](https://github.com/pimoroni/interstate75/releases).

1. Hold **BOOT** while tapping **RST** on the Interstate 75W
2. Drag the `.uf2` file onto the "RP2350" USB drive that appears
3. Board resets automatically

### 2. Configure

Copy `firmware/config.json.example` to `firmware/config.json` and edit with your settings:

```bash
cp firmware/config.json.example firmware/config.json
```

At minimum, set your WiFi credentials:

```json
{
  "wifi_ssid": "YourNetworkName",
  "wifi_password": "YourPassword",
  "utc_offset": -6
}
```

See [docs/configuration.md](docs/configuration.md) for the full settings reference.

### 3. Deploy

Copy all files from `firmware/` to the device root using [Thonny](https://thonny.org/) or `mpremote`:

```bash
mpremote cp firmware/*.py :
mpremote cp firmware/config.json :
```

### 4. Boot

Power cycle the board. It will:
1. Show "CONNECTING" while joining WiFi (LED blinks blue)
2. Show "SYNCING NTP" while fetching time
3. Show "READY" and begin displaying the clock

## Simulator

Open `simulator.html` in any browser to preview and experiment with the display layout, color themes, transition modes, and NTP indicators — no hardware required.

## Button Controls

| Button | Action |
|--------|--------|
| **A** | Open menu / navigate to next item |
| **B** | Cycle value for current menu item |
| *(wait 5s)* | Menu closes and saves changes |

## Project Structure

```
.
├── simulator.html           # Browser-based display simulator
├── firmware/
│   ├── main.py              # Entry point — boot sequence + main loop
│   ├── config.json.example  # Configuration template
│   ├── secrets.py.example   # WiFi credentials template
│   ├── config_manager.py    # Config loading with secrets.py fallback
│   ├── fonts.py             # 5x7 and 3x5 pixel font bitmaps
│   ├── ntp_manager.py       # WiFi, NTP sync, DST, LED status
│   ├── clock_display.py     # Display rendering engine
│   └── menu.py              # On-screen button menu
└── docs/
    └── configuration.md     # Full settings reference
```

## License

[MIT](LICENSE)
