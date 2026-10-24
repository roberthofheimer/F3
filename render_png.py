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

    # Header bar
    d.rectangle([0, 0, W - 1, 67], fill=BLACK)
    title = f"{feed['pax']} · 112 Tracker".upper()
    spaced(d, (24, 45), title, display(32), WHITE, tracking=3)
    spaced(d, (W - 24, 44), feed["month_label"], mono(20), WHITE, tracking=1, anchor="rs")

    # Left column: verdict
    col_right = 300
    d.rectangle([col_right, 68, col_right + 3, 343], fill=BLACK)
    spaced(d, (22, 96), "THIS MONTH", mono(15), BLACK, tracking=2)
    big = fit_font(display, "112", col_right - 40, 170)
    cx = (4 + col_right) / 2
    d.text((cx, 262), "112", font=big, fill=BLACK, anchor="ms")
    status = feed["status"].upper()
    if feed["passed"]:
        status = "✓ " + status
    size = 26
    while size > 12 and display(size).getlength(status) + 3 * (len(status) - 1) > col_right - 4 - 22 - 28 - 14:
        size -= 1
    sf = display(size)
    sw = sf.getlength(status) + 3 * (len(status) - 1)
    d.rectangle([22, 288, 22 + sw + 28, 326], fill=BLACK)
    spaced(d, (36, 316), status, sf, WHITE, tracking=3)

    # Right column: goals
    gx0, gx1 = col_right + 4 + 24, W - 4 - 24
    def goal(y, name, count, goal_n, foot):
        spaced(d, (gx0, y + 30), name.upper(), display(30), BLACK, tracking=2)
        small = mono(18)
        unit = f" / {goal_n}"
        d.text((gx1, y + 30), unit, font=small, fill=BLACK, anchor="rs")
        d.text((gx1 - small.getlength(unit), y + 34), str(count), font=mono(46), fill=BLACK, anchor="rs")
        by = y + 46
        gap, bar_h = 5, 34
        seg_w = (gx1 - gx0 - gap * (goal_n - 1)) / goal_n
        for i in range(goal_n):
            x0 = gx0 + i * (seg_w + gap)
            box = [round(x0), by, round(x0 + seg_w) - 1, by + bar_h - 1]
            d.rectangle(box, fill=BLACK if i < count else WHITE, outline=BLACK, width=3)
        spaced(d, (gx0, by + bar_h + 22), foot.upper(), mono(14), BLACK, tracking=1)

    posts, goal_posts = feed["posts"], feed["posts_goal"]
    if posts >= goal_posts:
        foot = "Goal hit" + (f", +{feed['posts_over']} extra" if feed["posts_over"] else "")
    else:
        foot = f"{feed['days_left']} days left in month"
    goal(80, f"{goal_posts} Posts", posts, goal_posts, foot)
    goal(212, f"{feed['q_goal']} Q", feed["qs"], feed["q_goal"],
         "Goal hit" if feed["qs"] >= feed["q_goal"] else "Still need a Q")

    # Streak strip
    d.rectangle([0, 344, W - 1, 347], fill=BLACK)
    cells = [
        ("112 months", str(feed["months_112"]), ""),
        ("Current streak", str(feed["streak_current"]), " mo"),
        ("Longest streak", str(feed["streak_longest"]), " mo"),
        ("Hit 12 posts", str(feed["months_hit_posts"]), " mo"),
        ("Hit 1 Q", str(feed["months_hit_q"]), " mo"),
    ]
    cw = (W - 8) / 5
    for i, (label, value, unit) in enumerate(cells):
        x = 4 + i * cw
        if i:
            d.rectangle([round(x), 348, round(x) + 2, 439], fill=BLACK)
        tx = x + 14
        spaced(d, (tx, 372), label.upper(), mono(12), BLACK, tracking=1)
        vf = mono(34)
        d.text((tx, 414), value, font=vf, fill=BLACK, anchor="ls")
        if unit:
            d.text((tx + vf.getlength(value), 414), unit, font=mono(13), fill=BLACK, anchor="ls")

    # Footer
    d.rectangle([0, 440, W - 1, 443], fill=BLACK)
    spaced(d, (24, 464), "F3 SOUTH CARY", mono(13), BLACK, tracking=1)
    spaced(d, (W - 24, 464), f"AS OF {feed['as_of']}".upper(), mono(13), BLACK, tracking=1, anchor="rs")

    img.save(path, "PNG", optimize=True)
