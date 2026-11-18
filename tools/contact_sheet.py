#!/usr/bin/env python3
"""Render every icon in a theme's colours to one PNG (needs ImageMagick). Usage: contact_sheet.py colors.toml out.png [tint]"""
import os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import icons
pal = dict(re.findall(r'^(\w+)\s*=\s*"(#[0-9a-fA-F]{6})"', open(sys.argv[1]).read(), re.M))
d = tempfile.mkdtemp()
files = []
for i, n in enumerate(icons.ICONS):
    p = os.path.join(d, "%03d.svg" % i)
    tint = pal.get(sys.argv[3] if len(sys.argv) > 3 else "blue", "#7aa2f7")
    open(p, "w").write(icons.svg(n, 6, pal["foreground"], tint, pal["accent"]))
    files.append(p)
pngs = []
for f in files:
    out = f[:-4] + ".png"
    subprocess.run(["magick", "-background", "none", f, out], check=True)
    pngs.append(out)
subprocess.run(["magick", "montage", *pngs, "-background", pal["background"], "-geometry", "+12+12",
                "-tile", "11x", sys.argv[2]], check=True)
