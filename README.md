# Interstate 75W 128x32 NTP Clock

A smooth-scrolling NTP clock display for the [Pimoroni Interstate 75W (RP2350)](https://shop.pimoroni.com/products/interstate-75-w) driving two [Waveshare 64x32 P2.5 HUB75 LED matrix panels](https://www.waveshare.com/wiki/RGB-Matrix-P2.5-64x32) arranged side-by-side for a seamless 128x32 pixel display.

## Features

- **24-hour NTP-synced time** with large 10x14 pixel digits
- **Milliseconds display** with confidence-based dimming (fades as accuracy decreases)
- **Smooth digit transitions** — vertical scroll, crossfade, or snap
- **Date display** above the time in compact format (ISO, short, day-first, or debug)
- **Debug mode** — shows NTP offset, RTT, stratum, sync age, and ISO week number
- **NTP status bar** with sync indicator, offset bar, GMT offset, and stratum
- **Custom NTP client** — real stratum from server response, RTT-based offset measurement
- **Adaptive NTP sync** — learns crystal drift rate over first 3 syncs, then calculates optimal resync interval to stay under 20ms offset
- **Automatic DST** with US and EU rule sets
- **Night mode** — auto-dims and shifts to warm amber between sunset and sunrise
  - Astronomical sunrise/sunset calculation (NOAA algorithm) with IP geolocation
  - Fallback to configurable fixed hours
  - Pixel-art sun horizon animation during transitions
  - "Green flash" effect: sea-green bloom wave seeds a Game of Life that evolves and fades
  - Boot animation: sunrise → sunset → green flash sequence on power-up
- **6 color themes** — White, Green, Amber, Red, Blue, Cyan
- **Configurable panel color order** — supports RGB, RBG, GRB, GBR, BRG, BGR
- **On-device menu** via physical buttons with position indicators for blind navigation
- **WiFi auto-reconnect** with exponential backoff
- **RGB LED status** — WiFi/sync state with auto-dim after 30s

## Display Layout

```
 ┌──────────────────────────────────────────────────────────────┐
 │ 04-15-26 W16              O12ms S1 2m/3m                    │  <- date + debug info
 │                                                              │
 │              1 9 : 4 3 : 0 2 .547                           │  <- time + ms
 │                                                              │
 │ ─────────────────────────────────────────────────────────── │  <- separator
 │ [SYNC]  GMT-6  ····|····  2  [STRAT]                        │  <- NTP status
 └──────────────────────────────────────────────────────────────┘
```
The top line cycles between date formats via the menu (ISO, short, day, debug).
Milliseconds dim as NTP confidence decreases between syncs.

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

## Building Firmware From Source

If the pre-built UF2 from [Pimoroni's releases](https://github.com/pimoroni/interstate75/releases) doesn't work for your board (or you want the latest MicroPython + PSRAM support + fixes not yet in a release), you can build from source:

### Prerequisites

**macOS:**
```bash
brew install cmake arm-none-eabi-gcc ccache python3
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install cmake gcc-arm-none-eabi build-essential ccache python3 python3-pip
```

### Build

```bash
./build.sh              # Full build (clone repos + compile) — first run takes ~10-15 min
./build.sh rebuild      # Rebuild only (after code changes)
./build.sh clean        # Remove build artifacts
```

Output UF2 files appear in `output/`:
- `i75w_rp2350-micropython.uf2` — standard firmware
- `i75w_rp2350-micropython-with-filesystem.uf2` — with writable filesystem (use this one)

### What's different from the v0.0.5 release?

The build script tracks Pimoroni's latest `main` branch, which includes:
- MicroPython master (latest upstream)
- GCC 14.2 toolchain
- PicoVector2 + layers support
- Bluetooth (BTStack + CYW43)
- All bug fixes since January 2025

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
├── build.sh                 # Firmware build script (from source)
├── firmware/
│   ├── main.py              # Entry point — boot sequence + main loop
│   ├── config.json.example  # Configuration template
│   ├── secrets.py.example   # WiFi credentials template
│   ├── config_manager.py    # Config loading with secrets.py fallback
│   ├── fonts.py             # 5x7 and 3x5 pixel font bitmaps
│   ├── ntp_manager.py       # WiFi, NTP sync, DST, LED status
│   ├── clock_display.py     # Display rendering engine
│   ├── night_mode.py        # Sunset/sunrise, night dimming, animations
│   └── menu.py              # On-screen button menu
└── docs/
    └── configuration.md     # Full settings reference
```

## License

[MIT](LICENSE)
