"""Drawing for the Tomato Crate Timer.

Pure PIL: no hardware here, so every screen can be rendered to a PNG on a laptop.
The screen is the 240x135 MiniPiTFT, drawn in landscape.
"""
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 240, 135
CRATE_SIZE = 25      # tomatoes in a work crate: 1 tomato = 1 minute
BASKET_SIZE = 5      # tomatoes in a break basket

RED = (224, 57, 43)
SHINE = (255, 157, 142)
LEAF = (67, 160, 71)
GOLD = (242, 176, 30)
AMBER = (227, 155, 33)
GREEN = (47, 158, 99)
BLUE = (47, 111, 216)
GRAY = (91, 97, 112)
WOOD = (138, 90, 43)
WOOD_DARK = (59, 42, 27)
SLOT = (90, 68, 49)
CARD = (201, 149, 92)
CARD_DARK = (155, 108, 60)
FLAP = (220, 174, 120)
BAG = (185, 138, 85)
BAG_DARK = (138, 98, 56)
SCREEN = (20, 22, 26)
HDR = (30, 33, 39)
PANEL = (35, 38, 45)
LINE = (58, 61, 69)
WHITE = (255, 255, 255)
TEXT = (213, 216, 222)
MUTED = (154, 160, 170)
TAPE = (239, 224, 184)
LABEL = (244, 239, 230)
ROAD = (58, 61, 68)

_FONT_FILES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        for regular, heavy in _FONT_FILES:
            try:
                _fonts[key] = ImageFont.truetype(heavy if bold else regular, size)
                break
            except OSError:
                continue
        else:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def dim(color, f):
    return tuple(int(c * f) for c in color)


def money_str(amount):
    return f"${amount:.0f}" if abs(amount - round(amount)) < 0.005 else f"${amount:.2f}"


@dataclass
class View:
    """Everything a screen needs to draw itself."""
    mode: str = "work"
    money: float = 0.0
    tomatoes: int = 0            # tomatoes in the crate or basket on screen
    crate_index: int = 1         # which crate of the day this is
    crates_goal: int = 12
    crates_done: int = 0
    boxes_done: int = 0
    boxes_goal: int = 3
    crates_per_box: int = 4
    box_slots: list = field(default_factory=lambda: [0, 0, 0])
    crate_value: float = 3.0
    setup_rows: list = field(default_factory=list)   # (label, value) pairs
    setup_sel: int = 0
    hold: float = 0.0            # 0..1, how far the "hold B" ring has filled
    payout: float = 0.0          # money from a partial crate or a shipment
    boxes_paid: int = 0          # full boxes shipped when a day was ended early
    boxes_pay: float = 0.0
    anim: float = 0.0            # 0..1 progress through an animation
    hours: float = 0.0


def _text(d, xy, s, size, color, bold=False, anchor="la"):
    d.text(xy, s, font=font(size, bold), fill=color, anchor=anchor)


def _tomato(d, cx, cy, r, f=1.0):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=dim(RED, f))
    hr = max(1, r * 0.22)
    hx, hy = cx - r * 0.36, cy - r * 0.36
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=dim(SHINE, f))
    top = cy - r * 0.92
    d.polygon([(cx, top + r * 0.35), (cx - r * 0.75, top - r * 0.25), (cx - r * 0.15, top + r * 0.1)], fill=dim(LEAF, f))
    d.polygon([(cx, top + r * 0.35), (cx + r * 0.75, top - r * 0.25), (cx + r * 0.15, top + r * 0.1)], fill=dim(LEAF, f))
    d.line((cx, top + r * 0.3, cx, top - r * 0.5), fill=dim(LEAF, f), width=1)


def _crate(d, x, y, n, s=19, f=1.0):
    w = h = 5 * s + 8
    d.rectangle((x, y, x + w, y + h), fill=dim(WOOD_DARK, f))
    d.rectangle((x, y, x + 4, y + h), fill=dim(WOOD, f))
    d.rectangle((x + w - 4, y, x + w, y + h), fill=dim(WOOD, f))
    d.rectangle((x, y + h - 4, x + w, y + h), fill=dim(WOOD, f))
    for r in range(1, 5):
        yy = y + 4 + r * s
        d.line((x + 4, yy, x + w - 4, yy), fill=dim((77, 56, 36), f))
    for i in range(CRATE_SIZE):
        row, col = 4 - i // 5, i % 5
        cx = x + 4 + col * s + s / 2
        cy = y + 4 + row * s + s / 2
        if i < n:
            _tomato(d, cx, cy, s * 0.4, f)
        else:
            rr = s * 0.36
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=dim(SLOT, f))


def _basket(d, x, y, n, w=104):
    cx = x + w / 2
    d.arc((x + 6, y - 22, x + w - 6, y + 26), 180, 360, fill=WOOD, width=2)
    for i in range(BASKET_SIZE):
        tx = x + 14 + i * (w - 28) / (BASKET_SIZE - 1)
        if i < n:
            _tomato(d, tx, y, 7)
        else:
            d.ellipse((tx - 6, y - 6, tx + 6, y + 6), outline=(90, 93, 102))
    d.rectangle((x, y + 5, x + w, y + 7), fill=(168, 112, 46))
    d.rectangle((x + 2, y + 7, x + w - 2, y + 24), fill=(199, 138, 63))
    for i in range(12):                                   # woven look
        sx = x + 4 + i * (w - 8) / 12
        top = y + 7 if i % 2 else y + 15
        d.rectangle((sx, top, sx + 4, top + 8), fill=(232, 179, 106))


def _box(d, x, y, w, h, filled=0, per_box=4, closed=False):
    if closed:
        d.rectangle((x, y + 4, x + w, y + h), fill=CARD, outline=CARD_DARK)
        d.rectangle((x - 1, y, x + w + 1, y + 7), fill=FLAP, outline=CARD_DARK)
        d.rectangle((x + w / 2 - 3, y, x + w / 2 + 3, y + 16), fill=TAPE)
        d.rectangle((x + 6, y + 19, x + w - 6, y + 29), fill=LABEL, outline=CARD_DARK)
        d.line((x + 9, y + 23, x + w - 9, y + 23), fill=(138, 131, 120))
        d.line((x + 9, y + 26, x + w - 14, y + 26), fill=(138, 131, 120))
        return
    d.polygon([(x, y + 6), (x - 3, y), (x + w / 2 - 1, y), (x + w / 2 - 1, y + 6)], fill=FLAP, outline=CARD_DARK)
    d.polygon([(x + w / 2 + 1, y + 6), (x + w / 2 + 1, y), (x + w + 3, y), (x + w, y + 6)], fill=FLAP, outline=CARD_DARK)
    d.rectangle((x, y + 6, x + w, y + h), fill=CARD, outline=CARD_DARK)
    cols = 2 if per_box > 1 else 1
    rows = max(1, (per_box + cols - 1) // cols)
    cw, ch = w / cols, (h - 6) / rows
    for c in range(1, cols):
        d.line((x + c * cw, y + 8, x + c * cw, y + h - 2), fill=CARD_DARK)
    for r in range(1, rows):
        d.line((x + 2, y + 6 + r * ch, x + w - 2, y + 6 + r * ch), fill=CARD_DARK)
    for i in range(min(filled, per_box)):                 # crates stack from the bottom
        col, row = i % cols, rows - 1 - i // cols
        d.rectangle((x + 3 + col * cw, y + 9 + row * ch, x + cw - 3 + col * cw, y + ch - 3 + row * ch + 6),
                    fill=RED, outline=(122, 29, 21))


def _coin(d, cx, cy, r=4):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD, outline=(183, 127, 12))


def _truck(d, x, y, boxes=3):
    d.rectangle((x, y, x + 92, y + 52), fill=(16, 18, 22), outline=(217, 220, 225))
    _text(d, (x + 46, y + 4), "TOMATO CO.", 7, RED, bold=True, anchor="ma")
    for i in range(boxes):
        _box(d, x + 6 + i * 27, y + 24, 22, 25, closed=True)
    d.polygon([(x + 92, y + 14), (x + 122, y + 14), (x + 138, y + 32), (x + 138, y + 52), (x + 92, y + 52)], fill=RED)
    d.polygon([(x + 99, y + 18), (x + 119, y + 18), (x + 130, y + 31), (x + 99, y + 31)], fill=(159, 211, 255))
    d.rectangle((x - 4, y + 50, x + 142, y + 54), fill=ROAD)
    for wx in (x + 18, x + 64, x + 118):
        d.ellipse((wx - 7, y + 49, wx + 7, y + 63), fill=(26, 26, 26), outline=(184, 188, 196))
        d.ellipse((wx - 2, y + 54, wx + 2, y + 58), fill=(184, 188, 196))


def _road(d):
    for x in range(0, WIDTH, 14):
        d.line((x, 129, x + 8, 129), fill=ROAD, width=2)


def _spark(d, x, y, s=3, color=GOLD):
    d.polygon([(x, y - s), (x + s * .3, y - s * .3), (x + s, y), (x + s * .3, y + s * .3),
               (x, y + s), (x - s * .3, y + s * .3), (x - s, y), (x - s * .3, y - s * .3)], fill=color)


def _header(d, tag, color, sub, money, sub_color=MUTED):
    d.rectangle((0, 0, WIDTH, 18), fill=HDR)
    tw = d.textlength(tag, font=font(8, True))
    d.rounded_rectangle((4, 4, 4 + tw + 12, 15), radius=6, fill=color)
    _text(d, (4 + (tw + 12) / 2, 9.5), tag, 8, WHITE, bold=True, anchor="mm")
    if sub:
        _text(d, (4 + tw + 18, 9.5), sub, 8, sub_color, bold=sub_color is not MUTED, anchor="lm")
    text = money_str(money)
    _text(d, (236, 9.5), text, 9, WHITE, bold=True, anchor="rm")
    _coin(d, 236 - d.textlength(text, font=font(9, True)) - 8, 9.5)


def _today(d, v):
    _text(d, (236, 23), "TODAY", 7, MUTED, anchor="ra")
    for i in range(min(v.boxes_goal, 3)):
        filled = v.box_slots[i] if i < len(v.box_slots) else 0
        _box(d, 126 + i * 37, 32, 33, 38, filled, v.crates_per_box, closed=filled >= v.crates_per_box)
    _text(d, (126, 99), "crates", 8, MUTED)
    _text(d, (236, 99), f"{v.crates_done}/{v.crates_goal}", 9, WHITE, bold=True, anchor="ra")
    _text(d, (126, 113), "boxes", 8, MUTED)
    _text(d, (236, 113), f"{v.boxes_done}/{v.boxes_goal}", 9, WHITE, bold=True, anchor="ra")


def _hold_bar(d, x, y, w, progress, label):
    d.rounded_rectangle((x, y, x + w, y + 9), radius=4, fill=(45, 48, 56))
    if progress > 0:
        d.rounded_rectangle((x, y, x + max(6, w * progress), y + 9), radius=4, fill=AMBER)
    _text(d, (x + w / 2, y + 4.5), label, 7, WHITE, bold=True, anchor="mm")


# --- screens ---------------------------------------------------------------

def _screen_setup(d, v):
    _header(d, "SETUP", BLUE, "", v.money)
    for i, (label, value) in enumerate(v.setup_rows):
        y = 22 + i * 19
        selected = i == v.setup_sel
        start_row = i == len(v.setup_rows) - 1        # the last row starts the day
        outline = (GREEN if start_row else GOLD) if selected else None
        d.rounded_rectangle((6, y, 114, y + 16), radius=3, fill=PANEL if selected else (26, 28, 33), outline=outline)
        _text(d, (12, y + 8), label, 8, GOLD if start_row else TEXT, bold=start_row, anchor="lm")
        _text(d, (108, y + 8), value, 9 if start_row else 11, GREEN if start_row else WHITE, bold=True, anchor="rm")
    _text(d, (8, 101), f"= {v.crates_goal} crates · about {v.hours:.0f} h", 8, MUTED)
    _text(d, (8, 112), f"1 crate = {money_str(v.crate_value)}", 8, MUTED)
    _text(d, (8, 124), "A +1", 8, GOLD, bold=True)
    _text(d, (44, 124), "B next", 8, GOLD, bold=True)
    _today(d, v)


def _screen_work(d, v):
    _header(d, "WORK", RED, f"crate {v.crate_index} of {v.crates_goal}", v.money)
    _crate(d, 6, 22, v.tomatoes)
    _today(d, v)


def _screen_paused(d, v):
    _header(d, "PAUSED", GRAY, f"crate {v.crate_index} of {v.crates_goal}", v.money)
    _crate(d, 6, 22, v.tomatoes, f=0.42)
    cx, cy = 57, 70
    d.ellipse((cx - 17, cy - 17, cx + 17, cy + 17), fill=(0, 0, 0), outline=WHITE, width=2)
    d.rounded_rectangle((cx - 7, cy - 8, cx - 2, cy + 8), radius=1, fill=WHITE)
    d.rounded_rectangle((cx + 2, cy - 8, cx + 7, cy + 8), radius=1, fill=WHITE)
    _hold_bar(d, 6, 123, 104, 0, "hold B · end early")
    _today(d, v)


def _screen_end_early(d, v):
    _header(d, "END EARLY?", AMBER, f"crate {v.crate_index}", v.money)
    _crate(d, 6, 22, v.tomatoes, f=0.3)
    d.rounded_rectangle((10, 30, 116, 112), radius=5, fill=PANEL, outline=AMBER)
    _text(d, (63, 38), "End crate early?", 9, WHITE, bold=True, anchor="ma")
    _text(d, (63, 54), f"{v.tomatoes} / {CRATE_SIZE} tomatoes", 8, MUTED, anchor="ma")
    _text(d, (63, 68), f"pays {money_str(v.payout)}", 11, GOLD, bold=True, anchor="ma")
    _text(d, (63, 84), f"instead of {money_str(v.crate_value)}", 7, MUTED, anchor="ma")
    _text(d, (63, 98), "A · resume", 8, TEXT, bold=True, anchor="ma")
    _hold_bar(d, 10, 116, 106, v.hold, "keep holding")
    _today(d, v)


def _screen_partial(d, v):
    _header(d, "PARTIAL", AMBER, "sold loose", v.money)
    _text(d, (8, 24), f"+{money_str(v.payout)}", 24, GOLD, bold=True)
    for i in range(CRATE_SIZE):
        x = 8 + i * 4.4
        filled = i < v.tomatoes
        d.rectangle((x, 52, x + 3.2, 61), fill=RED if filled else None, outline=RED if filled else (74, 77, 85))
    pct = round(100 * v.tomatoes / CRATE_SIZE)
    _text(d, (8, 67), f"{v.tomatoes} / {CRATE_SIZE} tomatoes = {pct}%", 8, TEXT)
    d.polygon([(12, 90), (40, 90), (37, 126), (15, 126)], fill=BAG, outline=BAG_DARK)
    d.polygon([(12, 90), (15, 86), (37, 86), (40, 90)], fill=(202, 160, 109), outline=BAG_DARK)
    _tomato(d, 20, 87, 6)
    _tomato(d, 32, 86, 6)
    _tomato(d, 26, 81, 5.5)
    _text(d, (48, 88), "crate not packed", 8, MUTED)
    if v.boxes_paid:                                   # full boxes still get shipped and paid
        _text(d, (48, 100), f"{v.boxes_paid} box shipped", 8, MUTED)
        _text(d, (48, 112), f"+{money_str(v.boxes_pay)}", 8, GOLD, bold=True)
    else:
        _text(d, (48, 100), "day ends here", 8, MUTED)
        _text(d, (48, 112), "back to settings", 8, MUTED)
    _text(d, (48, 125), "press any button", 7, GOLD, bold=True)
    _today(d, v)


def _screen_crate_done(d, v):
    _header(d, "WORK", RED, "+1 crate!", v.money, sub_color=GOLD)
    _crate(d, 6, 22, CRATE_SIZE)
    for x, y, s in ((8, 24, 3), (64, 20, 2.5), (120, 60, 2.5)):
        _spark(d, x, y, s)
    d.line((104, 28, 124, 34), fill=GOLD, width=1)
    d.polygon([(126, 30), (126, 40), (133, 35)], fill=GOLD)
    _today(d, v)


def _screen_break(d, v):
    _header(d, "BREAK", GREEN, f"after crate {v.crates_done}", v.money)
    _text(d, (58, 32), "stretch · sip water", 8, MUTED, anchor="ma")
    _basket(d, 6, 78, v.tomatoes)
    _today(d, v)


def _screen_box_packed(d, v):
    _header(d, "PACKED", AMBER, f"box {v.boxes_done} of {v.boxes_goal}", v.money)
    _box(d, 30, 26, 62, 62, closed=True)
    for x, y, s in ((18, 34, 3), (102, 32, 3), (20, 80, 2.4), (100, 84, 2.4)):
        _spark(d, x, y, s)
    _text(d, (60, 100), f"BOX {v.boxes_done} PACKED", 11, GOLD, bold=True, anchor="ma")
    _text(d, (60, 116), "next crates go to the next box", 7, MUTED, anchor="ma")
    _today(d, v)


def _screen_ship(d, v):
    _header(d, "SHIP", AMBER, "goal met!", v.money, sub_color=GOLD)
    _text(d, (8, 26), f"loading {v.boxes_goal} boxes", 8, TEXT)
    _text(d, (8, 38), f"{money_str(v.crate_value * v.crates_per_box)} each", 8, TEXT)
    _road(d)
    loaded = min(v.boxes_goal, int(v.anim * (v.boxes_goal + 1)))
    _truck(d, 88, 60, loaded)
    d.line((44, 122, 86, 108), fill=MUTED, width=2)
    if loaded < v.boxes_goal:                              # one box still climbing the ramp
        t = (v.anim * (v.boxes_goal + 1)) % 1
        _box(d, 46 + t * 36, 96 - t * 12, 22, 22, closed=True)
    _text(d, (56, 84), "›››", 10, GOLD, bold=True)


def _screen_shipped(d, v):
    _header(d, "SHIPPED", AMBER, "", v.money)
    _text(d, (8, 24), f"+{money_str(v.payout)}", 24, GOLD, bold=True)
    _text(d, (8, 56), "bank", 8, MUTED)
    _text(d, (8, 66), money_str(v.money), 14, WHITE, bold=True)
    for i in range(4):
        d.ellipse((10, 110 - i * 5, 34, 118 - i * 5), fill=GOLD, outline=(183, 127, 12))
    _text(d, (42, 100), f"{v.crates_done} crates", 8, MUTED)
    _text(d, (42, 113), f"{v.hours:.1f} h focused", 8, MUTED)
    _road(d)
    _truck(d, int(146 + v.anim * 40), 60, v.boxes_goal)


def _screen_ready(d, v):
    _header(d, "READY", GREEN, f"crate {v.crate_index} of {v.crates_goal}", v.money)
    _crate(d, 6, 22, 0, f=0.55)
    d.rounded_rectangle((10, 52, 112, 96), radius=5, fill=PANEL, outline=GREEN)
    _text(d, (61, 60), f"crate {v.crate_index}", 9, WHITE, bold=True, anchor="ma")
    _text(d, (61, 74), "B · start", 11, GOLD, bold=True, anchor="ma")
    _today(d, v)


def _screen_day_done(d, v):
    _header(d, "DONE", GREEN, "goal met", v.money)
    _text(d, (8, 26), "Day packed up", 12, WHITE, bold=True)
    _text(d, (8, 46), f"{v.crates_done} crates · {v.hours:.1f} h focused", 8, TEXT)
    _text(d, (8, 60), f"bank {money_str(v.money)}", 8, GOLD, bold=True)
    for i in range(v.boxes_goal):
        _box(d, 8 + i * 30, 76, 26, 32, closed=True)
    _text(d, (8, 120), "press any button · new day", 8, MUTED)


_SCREENS = {
    "setup": _screen_setup,
    "work": _screen_work,
    "paused": _screen_paused,
    "end_early": _screen_end_early,
    "partial": _screen_partial,
    "crate_done": _screen_crate_done,
    "break": _screen_break,
    "box_packed": _screen_box_packed,
    "ship": _screen_ship,
    "shipped": _screen_shipped,
    "ready": _screen_ready,
    "day_done": _screen_day_done,
}


def render(view):
    image = Image.new("RGB", (WIDTH, HEIGHT), SCREEN)
    d = ImageDraw.Draw(image)
    _SCREENS[view.mode](d, view)
    return image
