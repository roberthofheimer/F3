"""Draw the Shipyard 112 tracker as an 800x480 black-and-white PNG for TRMNL's Image Display plugin."""
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 480
BLACK, WHITE = 0, 255

DISPLAY_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def load(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def display(size):
    return load(DISPLAY_FONTS, size)


def mono(size):
    """Kept for compatibility: the same plain bold face, so every zero is a plain oval."""
    return display(size)


def spaced(draw, xy, text, font, fill, tracking=0, anchor="ls"):
    """Draw text with extra letter spacing. anchor is the vertical part only: 'ls' baseline, 'rs' right-aligned."""
    x, y = xy
    width = sum(font.getlength(c) + tracking for c in text) - tracking
    if anchor.startswith("r"):
        x -= width
    elif anchor.startswith("m"):
        x -= width / 2
    for c in text:
        draw.text((x, y), c, font=font, fill=fill, anchor="ls")
        x += font.getlength(c) + tracking
    return width


def fit_font(make, text, max_width, start, minimum=40):
    size = start
    while size > minimum and make(size).getlength(text) > max_width:
        size -= 2
    return make(size)


def render(feed, path):
    img = Image.new("L", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # Outer frame
    d.rectangle([0, 0, W - 1, H - 1], outline=BLACK, width=4)

    # Header bar: name on the left, month on the right
    d.rectangle([0, 0, W - 1, 51], fill=BLACK)
    title = f"{feed['pax']} 112 Tracker".upper()
    spaced(d, (22, 37), title, display(30), WHITE, tracking=3)
    spaced(d, (W - 22, 37), feed["month_label"], display(30), WHITE, tracking=3, anchor="rs")

    # Two big panels: Posts and Qs
    mid = W // 2
    d.rectangle([mid - 2, 52, mid + 1, 291], fill=BLACK)

    def panel(x0, x1, label, count, goal_n, foot):
        spaced(d, (x0 + 22, 90), label, display(32), BLACK, tracking=3)
        spaced(d, (x1 - 22, 89), f"GOAL {goal_n}", display(24), BLACK, tracking=1, anchor="rs")
        big = fit_font(display, str(count), x1 - x0 - 60, 118)
        d.text(((x0 + x1) / 2, 200), str(count), font=big, fill=BLACK, anchor="ms")
        gx0, gx1, gap = x0 + 22, x1 - 22, 4
        seg = (gx1 - gx0 - gap * (goal_n - 1)) / goal_n
        for i in range(goal_n):
            a = gx0 + i * (seg + gap)
            d.rectangle([round(a), 214, round(a + seg) - 1, 238],
                        fill=BLACK if i < count else WHITE, outline=BLACK, width=3)
        spaced(d, (gx0, 272), foot.upper(), display(22), BLACK, tracking=1)

    posts, pg = feed["posts"], feed["posts_goal"]
    qs, qg = feed["qs"], feed["q_goal"]
    if posts >= pg:
        post_foot = "Goal hit" + (f", +{posts - pg} extra" if posts > pg else "")
    else:
        post_foot = f"{pg - posts} to go"
    if qs >= qg:
        q_foot = "Goal hit" + (f", +{qs - qg} extra" if qs > qg else "")
    else:
        q_foot = "Still need a Q"
    panel(4, mid - 2, "POSTS", posts, pg, post_foot)
    panel(mid + 2, W - 4, "Qs", qs, qg, q_foot)

    # Status bar, full width between the panels and the trend boxes
    d.rectangle([0, 292, W - 1, 331], fill=BLACK)
    status = ("\u2713 " if feed["passed"] else "") + feed["status"].upper()
    size, track = 28, 4
    while size > 20 and sum(display(size).getlength(c) + track for c in status) - track > W - 40:
        size -= 1
        track = 4 if size >= 26 else 2
    baseline = round(311.5 + 0.365 * size)  # keeps the text centred in the bar at any size
    spaced(d, (W / 2, baseline), status, display(size), WHITE, tracking=track, anchor="m")

    # Bottom row: Current streak and Longest streak on the left, next Q on the right
    streak_w = 170
    for i, (lines, value) in enumerate([
        (("CURRENT", "STREAK"), str(feed["streak_current"])),
        (("LONGEST", "STREAK"), str(feed["streak_longest"])),
    ]):
        x = 4 + i * streak_w
        tx = x + 14
        spaced(d, (tx, 354), lines[0], display(20), BLACK, tracking=1)
        spaced(d, (tx, 376), lines[1], display(20), BLACK, tracking=1)
        vf = display(36)
        d.text((tx, 414), value, font=vf, fill=BLACK, anchor="ls")
        d.text((tx + vf.getlength(value) + 4, 414), "mo", font=display(22), fill=BLACK, anchor="ls")
        d.rectangle([x + streak_w - 3, 332, x + streak_w - 1, 423], fill=BLACK)

    q_lines = [t.upper() for t in feed.get("q_box_lines", ["Q schedule unavailable"])]
    qx0, qx1 = 4 + 2 * streak_w + 12, W - 4 - 12
    max_w, box_top, box_bot = qx1 - qx0, 336, 420
    base = 34
    while True:
        sizes = [base] + [round(base * 0.78)] * (len(q_lines) - 1)
        widths = [
            sum(display(sz).getlength(c) + 2 for c in ln) - 2 for ln, sz in zip(q_lines, sizes)
        ]
        height = sum(sz * 1.2 for sz in sizes)
        if (max(widths) <= max_w and height <= box_bot - box_top) or base <= 16:
            break
        base -= 1
    y = (box_top + box_bot) / 2 - height / 2
    for ln, sz in zip(q_lines, sizes):
        lh = sz * 1.2
        spaced(d, ((qx0 + qx1) / 2, round(y + lh / 2 + 0.365 * sz)), ln, display(sz), BLACK,
               tracking=2, anchor="m")
        y += lh

    # Footer
    d.rectangle([0, 424, W - 1, 427], fill=BLACK)
    spaced(d, (22, 459), "F3 SOUTH CARY", display(20), BLACK, tracking=2)
    spaced(d, (W - 22, 459), f"AS OF {feed['as_of']}".upper(), display(20), BLACK, tracking=2, anchor="rs")

    img.save(path, "PNG", optimize=True)
