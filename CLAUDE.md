# Project: Interstate 75W 128x32 NTP Clock

Repo: https://github.com/jedwa006/interstate_75w_128x32_display

## Hardware

- Pimoroni Interstate 75W (RP2350 A0A2 stepping), 4MB flash confirmed good
- Two Waveshare 64x32 P2.5 HUB75 LED panels (128x32 total)
- Panel color order is **RBG** (not RGB) — set in config.json `color_order`
- Board connects at `/dev/tty.usbmodem1101`
- Deploy: `python3 -m mpremote connect /dev/tty.usbmodem1101 cp firmware/*.py : + reset`

## Firmware Build

- MicroPython built from source (latest Pimoroni interstate75 main branch, not v0.0.5 release)
- `build.sh` clones all deps and produces UF2s in `output/`
- MicroPython epoch is **1970 (Unix)** on this build, not 2000 — NTP_DELTA auto-detected at runtime

## API Gotchas (learned the hard way)

- Button API uses **integer indices** `0`=A/GP14, `1`=B/GP15 — `SWITCH_A`/`SWITCH_B` constants don't exist
- `network.WLAN` works directly — `ezwifi` API is unreliable on this build (wrong kwarg signatures)
- `alpha || 1` bug: use `alpha != null ? alpha : 1` — zero is falsy in JS (simulator) and needs explicit check
- `setPixel` must floor x,y to integers (`x | 0`) — fractional coords from scroll transitions cause crashes
- `time.time()` is integer seconds only — can't measure sub-second NTP offsets from it
- `create_pen()` is expensive — use lookup tables, don't call per-pixel

## User Context

- Located in Denver, CO (UTC-6 MDT)
- Near NIST Boulder — `time.nist.gov` gives stratum 1 at ~20ms RTT
- Button position indicators at x=108 on display align with physical buttons on the back of the board

## Architecture

- `simulator.html` — standalone browser LED matrix simulator (no server needed), open directly
- `firmware/` — MicroPython files deployed to the board:
  - `main.py` — entry point, boot sequence, main loop
  - `config_manager.py` — loads config.json with secrets.py fallback
  - `ntp_manager.py` — custom NTP client (real stratum/RTT), adaptive drift-learning sync, WiFi, DST
  - `clock_display.py` — rendering: date, time, ms, NTP status bar, transitions
  - `night_mode.py` — sunset/sunrise (NOAA algo), IP geolocation, amber tint, animations (bloom, GOL green flash)
  - `fonts.py` — 5x7 and 3x5 pixel font bitmaps
  - `menu.py` — on-screen button menu with position indicators

## Features Working on Hardware

- Clock: date, HH:MM:SS, confidence-dimmed milliseconds
- Custom NTP client with real stratum and RTT measurement
- Adaptive drift-learning sync (learns crystal PPM, auto-calculates optimal resync interval, 20ms threshold)
- Night mode: astronomical sunrise/sunset, IP geolocation fallback, amber color shift, 50% brightness
- Sunset animation: sun descends with bloom, green flash bloom wave seeds GOL with age-dimming and dithered glow halos
- Boot animation: sunrise, sunset, green flash GOL sequence
- Debug display mode: offset, RTT, stratum, sync age/next countdown, date (MM-DD-YY), ISO week number
- Button menu with physical position color-coded indicators (B=grey left, A=orange right)
- WiFi auto-reconnect with exponential backoff
- RGB LED: blue=connecting, green=connected, red=failed, auto-dims to off after 30s

## Pending / Future Work

- Bloom wave leading edge could be smoother (currently seeds well but arc front isn't as visually smooth as the sun bloom effect)
- Sunset/sunrise animation: bloom/travel polish at start/end of cycles
- Update simulator.html to match all firmware features
- Consider more robust NTP library (micropython-ntp) for proper T1-T4 offset calculation if integer-second `time.time()` limitation needs to be overcome
