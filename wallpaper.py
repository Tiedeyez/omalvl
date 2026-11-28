"""OmaLvL wallpaper: your stats drawn as pixel art in the active theme's colours.

`omalvl wallpaper` renders a PNG at the focused monitor's size (1920x1080 if Hyprland isn't
there): the Rice rating as a six-axis hexagon, the six areas with every skill's icon and level,
and your rank. Pure standard library (zlib + struct); nothing is set as your background unless
you run omarchy-theme-bg-set on the file yourself.
"""
import json
import math
import os
import struct
import subprocess
import zlib

import icons
import pixelfont

FALLBACK = {"background": "#1a1b26", "foreground": "#c0caf5", "accent": "#7aa2f7", "red": "#f7768e",
            "orange": "#ff9e64", "yellow": "#e0af68", "green": "#9ece6a", "cyan": "#7dcfff", "blue": "#7aa2f7",
            "magenta": "#bb9af7", "brown": "#a9805b"}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = [[bg] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def rect(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.h, y + h)):
            row = self.px[yy]
            for xx in range(max(0, x), min(self.w, x + w)):
                row[xx] = c

    def text(self, x, y, s, c, scale=1):
        for i, ch in enumerate(str(s).upper()):
            g = pixelfont.GLYPHS.get(ch) or pixelfont.GLYPHS.get("?")
            if not g:
                continue
            for gy in range(7):
                for gx in range(5):
                    if g[gy][gx] == "#":
                        self.rect(x + (i * 6 + gx) * scale, y + gy * scale, scale, scale, c)

    def icon(self, x, y, name, ink, tint, accent, shade, scale=1):
        for iy, row in enumerate(icons.ICONS.get(name, [])):
            for ix, ch in enumerate(row):
                if ch != " ":
                    c = {"#": ink, "a": tint, "b": accent, ".": shade}[ch]
                    self.rect(x + ix * scale, y + iy * scale, scale, scale, c)

    def polygon(self, pts, c):
        ys = [p[1] for p in pts]
        for y in range(max(0, int(min(ys))), min(self.h, int(max(ys)) + 1)):
            xs = []
            for i in range(len(pts)):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
                if (y1 <= y + 0.5 < y2) or (y2 <= y + 0.5 < y1):
                    xs.append(x1 + (y + 0.5 - y1) * (x2 - x1) / (y2 - y1))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(int(math.ceil(a - 0.5)), int(math.floor(b - 0.5)) + 1):
                    self.put(x, y, c)

    def line(self, x0, y0, x1, y1, c):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / float(n)
            self.put(int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)), c)

    def png(self, path, scale):
        raw = bytearray()
        for row in self.px:
            line = b"".join(bytes(c) * scale for c in row)
            for _ in range(scale):
                raw += b"\x00" + line
        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w * scale, self.h * scale, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)


def monitor_size():
    try:
        out = subprocess.run(["/usr/bin/hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=5).stdout
        mons = json.loads(out)
        m = next((m for m in mons if m.get("focused")), mons[0])
        return int(m["width"]), int(m["height"])
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError, StopIteration):
        return 1920, 1080


def render(snap, out=None, size=None):
    w, h = size or monitor_size()
    scale = max(2, min(w, h) // 270)
    gw, gh = -(-w // scale), -(-h // scale)     # round up: the picture always covers the whole screen
    pal = dict(FALLBACK)
    pal.update({k: v for k, v in (snap.get("palette") or {}).items() if isinstance(v, str) and v.startswith("#")})
    bg, fg, accent = _rgb(pal["background"]), _rgb(pal["foreground"]), _rgb(pal["accent"])
    faint, shade = _mix(bg, fg, 0.12), _mix(bg, fg, 0.35)
    cv = Canvas(gw, gh, bg)
    # a quiet dot grid
    for y in range(4, gh, 8):
        for x in range(4, gw, 8):
            cv.put(x, y, faint)
    rice = snap["rice"]
    areas = rice["areas"]
    skills = {s["key"]: s for s in snap["skills"]}
    # title and rank
    cv.text(12, 12, "OMALVL", accent, 2)
    cv.text(12, 32, "RICE %d  %s" % (rice["rating"], rice["rank"]), fg, 1)
    cv.text(12, 42, "TOTAL %d / %d" % (snap["total"], snap["maxTotal"]), shade, 1)
    # the hexagon: rings at 25/50/75/100, the filled shape at each area's level
    cx, cy = int(gw * 0.70), gh // 2
    rad = int(min(gw * 0.22, gh * 0.38))
    def pt(i, f):
        a = -math.pi / 2 + i * math.pi / 3
        return cx + math.cos(a) * rad * f, cy + math.sin(a) * rad * f
    for ring in (0.25, 0.5, 0.75, 1.0):
        ps = [pt(i, ring) for i in range(6)]
        for i in range(6):
            cv.line(ps[i][0], ps[i][1], ps[(i + 1) % 6][0], ps[(i + 1) % 6][1], faint if ring < 1 else shade)
    for i in range(6):
        x, y = pt(i, 1.0)
        cv.line(cx, cy, x, y, faint)
    shape = [pt(i, max(0.04, areas[i]["level"] / 100.0)) for i in range(6)]
    cv.polygon(shape, _mix(bg, accent, 0.55))
    for i in range(6):
        x, y = shape[i]
        x2, y2 = shape[(i + 1) % 6]
        cv.line(x, y, x2, y2, accent)
    for i, a in enumerate(areas):
        tint = _rgb(pal.get(a["tint"], pal["accent"]))
        x, y = pt(i, 1.18)
        label = a["name"].upper()
        cv.text(int(x - len(label) * 3), int(y - 3), label, tint, 1)
        vx, vy = shape[i]
        cv.rect(int(vx) - 1, int(vy) - 1, 3, 3, tint)
    # the areas, as columns of icons with level bars
    col_w, top = 84, 62
    for ai, a in enumerate(areas):
        tint = _rgb(pal.get(a["tint"], pal["accent"]))
        x = 12 + (ai % 2) * col_w
        y = top + (ai // 2) * 62
        cv.text(x, y, a["name"].upper(), tint, 1)
        cv.text(x + 56, y, str(int(a["level"])), shade, 1)
        for si, k in enumerate(a["skills"]):
            s = skills[k]
            st = _rgb(pal.get(s["tint"], pal["accent"]))
            yy = y + 10 + si * 16
            cv.icon(x, yy, k, fg, st, accent, shade)
            cv.text(x + 16, yy + 2, str(s["level"]), fg, 1)
            filled = int(36 * s["level"] / 100.0)
            cv.rect(x + 16, yy + 10, 36, 2, faint)
            cv.rect(x + 16, yy + 10, filled, 2, st)
    if out is None:
        folder = os.path.join(os.path.expanduser("~/Pictures"), "omalvl")
        os.makedirs(folder, exist_ok=True)
        theme = (snap.get("season") or {}).get("theme") or "theme"
        safe = "".join(c for c in theme.lower() if c.isalnum() or c in "-_") or "theme"
        out = os.path.join(folder, "omalvl-%s.png" % safe)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cv.png(out, scale)
    return out
