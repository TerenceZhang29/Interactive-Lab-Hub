"""Tomato Crate Timer, stage 1: a new tomato lands in the crate every minute.

Run on the Pi (stop the boot screen first so it doesn't fight over the display):
    sudo systemctl stop piscreen.service
    ~/venv/bin/python tomato_clock.py                          # 1 tomato / 60 s
    ~/venv/bin/python tomato_clock.py --seconds-per-tomato 2   # fast demo

Preview a frame without the Pi (e.g. on a laptop):
    python tomato_clock.py --png preview.png --tomatoes 12
"""
import argparse
import time

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 240, 135  # MiniPiTFT in landscape
CRATE_SIZE = 25           # 5 x 5 grid, 1 tomato = 1 minute
GRID = 5
CELL = 23
FULL_HOLD_SECONDS = 4     # how long "Crate full!" stays up before the crate empties

BG = (20, 24, 28)
WOOD = (150, 95, 45)
WOOD_DARK = (95, 58, 25)
TOMATO = (225, 45, 35)
TOMATO_SHINE = (255, 140, 120)
LEAF = (60, 170, 60)
TEXT = (255, 255, 255)
MUTED = (150, 160, 170)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


FONT_SMALL = load_font(FONT_PATH, 12)
FONT_BIG = load_font(FONT_BOLD_PATH, 30)
FONT_MSG = load_font(FONT_BOLD_PATH, 16)


def draw_tomato(draw, cx, cy, r=9):
    draw.ellipse((cx - r, cy - r + 1, cx + r, cy + r), fill=TOMATO)
    draw.ellipse((cx - r + 3, cy - r + 4, cx - r + 7, cy - r + 7), fill=TOMATO_SHINE)
    # stem and two leaves
    draw.line((cx, cy - r + 1, cx, cy - r - 2), fill=LEAF, width=2)
    draw.polygon([(cx, cy - r + 2), (cx - 5, cy - r - 1), (cx - 2, cy - r + 3)], fill=LEAF)
    draw.polygon([(cx, cy - r + 2), (cx + 5, cy - r - 1), (cx + 2, cy - r + 3)], fill=LEAF)


def draw_crate(draw, x0, y0, tomatoes):
    inner = GRID * CELL
    x1, y1 = x0 + inner + 8, y0 + inner + 8
    draw.rectangle((x0, y0, x1, y1), fill=WOOD_DARK)
    # wooden slats behind the tomatoes
    for row in range(GRID):
        sy = y0 + 4 + row * CELL
        draw.rectangle((x0 + 4, sy + 1, x1 - 4, sy + CELL - 2), fill=WOOD)
    draw.rectangle((x0, y0, x1, y1), outline=WOOD_DARK, width=3)

    # fill bottom-up, left to right
    for i in range(tomatoes):
        row = GRID - 1 - i // GRID
        col = i % GRID
        cx = x0 + 4 + col * CELL + CELL // 2
        cy = y0 + 4 + row * CELL + CELL // 2
        draw_tomato(draw, cx, cy)


def render(tomatoes, seconds_to_next):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    draw_crate(draw, 4, 1, tomatoes)

    px = 142
    draw.text((px, 4), "TOMATOES", font=FONT_SMALL, fill=MUTED)
    draw.text((px, 20), f"{tomatoes}", font=FONT_BIG, fill=TEXT)
    draw.text((px, 56), f"of {CRATE_SIZE}", font=FONT_SMALL, fill=MUTED)

    if tomatoes >= CRATE_SIZE:
        draw.text((px, 90), "Crate", font=FONT_MSG, fill=TOMATO)
        draw.text((px, 108), "full!", font=FONT_MSG, fill=TOMATO)
    else:
        mins, secs = divmod(int(seconds_to_next + 0.999), 60)
        draw.text((px, 90), "next tomato", font=FONT_SMALL, fill=MUTED)
        draw.text((px, 106), f"{mins}:{secs:02d}", font=FONT_MSG, fill=TEXT)
    return image


def crate_state(elapsed, seconds_per_tomato):
    """Tomatoes in the crate and seconds until the next one, given time since the crate was emptied."""
    tomatoes = min(CRATE_SIZE, int(elapsed // seconds_per_tomato))
    seconds_to_next = (tomatoes + 1) * seconds_per_tomato - elapsed
    return tomatoes, seconds_to_next


def setup_display():
    import board
    import digitalio
    import adafruit_rgb_display.st7789 as st7789

    disp = st7789.ST7789(
        board.SPI(),
        cs=digitalio.DigitalInOut(board.D5),
        dc=digitalio.DigitalInOut(board.D25),
        rst=None,
        baudrate=64000000,
        width=135,
        height=240,
        x_offset=53,
        y_offset=40,
    )
    backlight = digitalio.DigitalInOut(board.D22)
    backlight.switch_to_output()
    backlight.value = True
    return disp


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds-per-tomato", type=float, default=60)
    parser.add_argument("--png", help="render one frame to this file instead of the screen")
    parser.add_argument("--tomatoes", type=int, default=0, help="tomato count for --png")
    args = parser.parse_args()

    if args.png:
        render(args.tomatoes, args.seconds_per_tomato).save(args.png)
        return

    disp = setup_display()
    rotation = 90
    cycle = CRATE_SIZE * args.seconds_per_tomato + FULL_HOLD_SECONDS
    tick = min(1.0, args.seconds_per_tomato / 4)
    # time-based rather than counting loop iterations, so the timer doesn't drift
    start = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= cycle:
                start += cycle
                elapsed -= cycle
            disp.image(render(*crate_state(elapsed, args.seconds_per_tomato)), rotation)
            time.sleep(tick)
    except KeyboardInterrupt:
        disp.image(Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)), rotation)


if __name__ == "__main__":
    main()
