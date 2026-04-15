import json

DEFAULTS = {
    "wifi_ssid": "",
    "wifi_password": "",
    "ntp_server": "pool.ntp.org",
    "ntp_sync_interval": 3600,
    "utc_offset": -6,
    "dst_enabled": True,
    "dst_rules": "US",
    "color_r": 255,
    "color_g": 255,
    "color_b": 240,
    "brightness": 85,
    "colon_style": "blink",
    "date_format": "iso",
    "transition_mode": "scroll",
    "color_order": "RBG",
}

CONFIG_PATH = "config.json"


class Config:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        # Try config.json first
        try:
            with open(CONFIG_PATH, "r") as f:
                stored = json.load(f)
            for k, v in stored.items():
                if k in DEFAULTS:
                    self._data[k] = v
        except (OSError, ValueError):
            pass

        # Fall back to secrets.py for WiFi if not set in JSON
        if not self._data["wifi_ssid"]:
            try:
                import secrets
                if hasattr(secrets, "WIFI_SSID") and secrets.WIFI_SSID:
                    self._data["wifi_ssid"] = secrets.WIFI_SSID
                if hasattr(secrets, "WIFI_PASSWORD") and secrets.WIFI_PASSWORD:
                    self._data["wifi_password"] = secrets.WIFI_PASSWORD
            except ImportError:
                pass

    def save(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self._data, f)
        except OSError:
            pass

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def color(self):
        return (self._data["color_r"], self._data["color_g"], self._data["color_b"])

    def brightness_frac(self):
        return self._data["brightness"] / 100.0
