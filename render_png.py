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
MONO_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
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
    return load(MONO_FONTS, size)


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
    spaced(d, (22, 36), title, display(28), WHITE, tracking=3)
    spaced(d, (W - 22, 36), feed["month_label"], display(28), WHITE, tracking=3, anchor="rs")

    # Two big panels: Posts and Qs
    mid = W // 2
    d.rectangle([mid - 2, 52, mid + 1, 339], fill=BLACK)

    def panel(x0, x1, label, count, goal_n, foot):
        spaced(d, (x0 + 22, 92), label, display(30), BLACK, tracking=3)
        spaced(d, (x1 - 22, 90), f"GOAL {goal_n}", mono(16), BLACK, tracking=1, anchor="rs")
        big = fit_font(mono, str(count), x1 - x0 - 60, 165)
        d.text(((x0 + x1) / 2, 240), str(count), font=big, fill=BLACK, anchor="ms")
        gx0, gx1, gap = x0 + 22, x1 - 22, 4
        seg = (gx1 - gx0 - gap * (goal_n - 1)) / goal_n
        for i in range(goal_n):
            a = gx0 + i * (seg + gap)
            d.rectangle([round(a), 258, round(a + seg) - 1, 284],
                        fill=BLACK if i < count else WHITE, outline=BLACK, width=3)
        spaced(d, (gx0, 318), foot.upper(), mono(15), BLACK, tracking=1)

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
    d.rectangle([0, 340, W - 1, 375], fill=BLACK)
    status = ("\u2713 " if feed["passed"] else "") + feed["status"].upper()
    size = 24
    while size > 12 and sum(display(size).getlength(c) + 4 for c in status) - 4 > W - 80:
        size -= 1
    spaced(d, (W / 2, 366), status, display(size), WHITE, tracking=4, anchor="m")

    # Trend boxes
    cells = [
        ("112 months", str(feed["months_112"]), ""),
        ("Current streak", str(feed["streak_current"]), " mo"),
        ("Longest streak", str(feed["streak_longest"]), " mo"),
        (f"Hit {pg} posts", str(feed["months_hit_posts"]), " mo"),
        (f"Hit {qg} Q", str(feed["months_hit_q"]), " mo"),
    ]
    cw = (W - 8) / 5
    for i, (label, value, unit) in enumerate(cells):
        x = 4 + i * cw
        if i:
            d.rectangle([round(x), 376, round(x) + 2, 439], fill=BLACK)
        tx = x + 14
        spaced(d, (tx, 395), label.upper(), mono(12), BLACK, tracking=1)
        vf = mono(30)
        d.text((tx, 428), value, font=vf, fill=BLACK, anchor="ls")
        if unit:
            d.text((tx + vf.getlength(value), 428), unit, font=mono(13), fill=BLACK, anchor="ls")

    # Footer
    d.rectangle([0, 440, W - 1, 443], fill=BLACK)
    spaced(d, (22, 464), "F3 SOUTH CARY", mono(13), BLACK, tracking=1)
    spaced(d, (W - 22, 464), f"AS OF {feed['as_of']}".upper(), mono(13), BLACK, tracking=1, anchor="rs")

    img.save(path, "PNG", optimize=True)
