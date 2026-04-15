import time
import sys
from interstate75 import Interstate75
from config_manager import Config
from ntp_manager import NTPManager
from clock_display import ClockDisplay
from fonts import draw_tiny_centered

# --- Init ---
config = Config()

# Map color order string to Interstate75 constant
_COLOR_ORDERS = {
    "RGB": Interstate75.COLOR_ORDER_RGB,
    "RBG": Interstate75.COLOR_ORDER_RBG,
    "GRB": Interstate75.COLOR_ORDER_GRB,
    "GBR": Interstate75.COLOR_ORDER_GBR,
    "BRG": Interstate75.COLOR_ORDER_BRG,
    "BGR": Interstate75.COLOR_ORDER_BGR,
}
_co = _COLOR_ORDERS.get(config.get("color_order", "RBG"), Interstate75.COLOR_ORDER_RBG)

i75 = Interstate75(display=Interstate75.DISPLAY_INTERSTATE75_128X32, color_order=_co)
graphics = i75.display
ntp = NTPManager(i75, config)
display = ClockDisplay(graphics, config, ntp)
menu = None  # lazy-loaded to save memory


def show_status(text):
    """Show a status message on the display."""
    pen = graphics.create_pen(80, 80, 80)
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    draw_tiny_centered(graphics, text, 14, pen)
    i75.update()


def show_error(text):
    """Show an error message on the display in red."""
    pen = graphics.create_pen(180, 0, 0)
    graphics.set_pen(graphics.create_pen(0, 0, 0))
    graphics.clear()
    draw_tiny_centered(graphics, text, 14, pen)
    i75.update()


def boot_sequence():
    """Connect WiFi and sync NTP at startup."""
    show_status("CONNECTING")
    if ntp.connect_wifi():
        show_status("SYNCING NTP")
        ntp.sync_ntp()
        if ntp.synced:
            show_status("READY")
        else:
            show_status("NTP FAILED")
    else:
        show_status("NO WIFI")
    time.sleep_ms(500)


# --- Menu handling ---
def check_menu():
    """Check buttons and handle menu interaction."""
    global menu

    a_pressed = i75.switch_pressed(0)
    b_pressed = i75.switch_pressed(1)

    if not a_pressed and not b_pressed:
        return False

    # Lazy-load menu module
    if menu is None:
        try:
            from menu import Menu
            menu = Menu(i75, graphics, config, ntp)
        except ImportError:
            return False

    return menu.handle_input(a_pressed, b_pressed)


# --- Main ---
try:
    boot_sequence()
except Exception as e:
    show_error("BOOT FAIL")
    sys.print_exception(e)
    time.sleep(3)

# Main loop
frame_target_ms = 16  # ~60fps

while True:
    try:
        loop_start = time.ticks_ms()

        # Check WiFi + NTP resync
        ntp.check_wifi()
        ntp.check_resync()

        # Update LED
        ntp.update_led()

        # Check buttons / menu
        menu_active = check_menu()

        # Get current local time
        local_time = ntp.get_local_time()

        # Render display
        if menu_active and menu is not None:
            menu.render()
        else:
            display.render(local_time)

        # Push to display
        i75.update()

        # Frame pacing
        elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
        if elapsed < frame_target_ms:
            time.sleep_ms(frame_target_ms - elapsed)

    except Exception as e:
        sys.print_exception(e)
        show_error("ERR CHECK REPL")
        time.sleep(3)
