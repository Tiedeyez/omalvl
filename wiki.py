#!/usr/bin/env python3
"""Build the OmaLvL Wiki: a static, offline wiki in the style of the OmaLvL
OmaLvL Wiki, generated from this game's own data (skills.py + content.py), so it
can never drift from the code. Quests, Contracts, signals, the diary, companions, random
events, Sysop challenges, the XP table and every training rate (skills.RATES)
come straight from the code.

    python3 wiki.py [--open]       (or: omalvl wiki)

Output: ~/.local/share/omalvl/wiki/index.html (sprites and fonts copied
next to it, so it works with no network).
"""
import datetime
import html
import json
import os
import stat
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import skills as S  # noqa: E402
import content as C  # noqa: E402
import glossary as G  # noqa: E402
import icons as I  # noqa: E402
import pixelfont as PF  # noqa: E402
import re  # noqa: E402

OUT = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "omalvl", "wiki")


def _private_write(path, text):
    """Wiki pages carry your activity and machine details: owner-only (0600), never via a symlink.
    O_CREAT keeps an existing file's old mode, so fchmod corrects pages from older builds."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(text)


def _private_dirs():
    """The wiki folder and its app-owned parent are owner-only (0700); older pages get 0600."""
    os.makedirs(OUT, mode=0o700, exist_ok=True)
    for d in (os.path.dirname(OUT), OUT):
        if not os.path.islink(d):
            os.chmod(d, 0o700)
    for name in os.listdir(OUT):
        path = os.path.join(OUT, name)
        st = os.lstat(path)
        if stat.S_ISREG(st.st_mode) and st.st_mode & 0o077:
            os.chmod(path, 0o600)
REPO = HERE   # the plugin folder is its own git repo
e = html.escape

# --------------------------------------------------------------- facts the data doesn't hold

# Plain-English solutions for conditions (signals, quests, diary, challenges).
EVENT_HELP = {
    "keybindings": "open the keybind list (SUPER+K)", "screenshot": "take a screenshot (PRINT)",
    "theme": "change the theme (SUPER+CTRL+SHIFT+SPACE)", "commit": "make a git commit",
    "search": "run a search (rg, fd, grep, find)", "script": "run a script (python, bash, node ...)",
    "cmd": "run shell commands", "ws_switch": "switch workspaces", "win_close": "close windows",
    "movewindow": "move a window to another workspace (SUPER+SHIFT+number)",
    "reminder": "set a reminder", "scratchpad": "send a window to the scratchpad and back",
    "float": "float a window", "fullscreen": "make a window fullscreen", "group": "group two windows",
    "active_min": "minutes at the computer", "game_min": "minutes playing", "visit": "visit web pages",
    "cook": "run builds (make, cargo, npm run ...)", "burn": "clean up (rm, trash, cache purges)",
    "sail": "make remote trips (git push/pull, ssh, rsync)", "toggle:nightlight": "toggle nightlight (SUPER+CTRL+N)",
    "panel:omarchy.clipboard": "open clipboard history (SUPER+CTRL+V)",
    "panel:omarchy.emojis": "open the emoji picker (SUPER+CTRL+E)",
    "window:pop": "pop a window out", "window:transparency": "toggle window transparency",
    "pkg_install": "install packages", "pkg_upgrade": "upgrade packages",
}


def describe_cond(c):
    kind = c[0]
    if kind in ("sum", "distinct"):
        key, n = c[1], c[2]
        what = EVENT_HELP.get(key)
        if not what:
            if key.startswith("cmd2:"):
                what = "run `%s`" % key[5:]
            elif key.startswith("cmd:"):
                what = "run `%s`" % key[4:]
            elif key.startswith("proc:"):
                what = "open %s" % (key[5:] or "a watched program")
            elif key.startswith("agent:"):
                what = "launch an AI agent or local model" + (" (%s)" % key[6:] if key[6:] else "")
            elif key.startswith("local_model:"):
                what = "run a local AI model (llama.cpp, Ollama ...)"
            elif key.startswith("menu:"):
                what = "open the Omarchy %s menu" % (key[5:] or "")
            elif key.startswith("layer:"):
                what = "open Omarchy overlays"
            elif key.startswith("kb:"):
                what = "use Omarchy keybind actions"
            elif key.startswith("toggle:"):
                what = "use Omarchy toggles" + (" (%s)" % key[7:] if key[7:] else "")
            elif key.startswith("panel:"):
                what = "open the %s panel" % key[6:]
            else:
                what = key
        if kind == "distinct":
            return "%s (%d different)" % (what, n) if n > 1 else what
        return what if n <= 1 else "%s ×%s" % (what, "{:,}".format(n) if isinstance(n, int) else n)
    if kind == "quest":
        q = S.QUEST_BY_ID.get(c[1])
        return "complete %s" % (q[1] if q else c[1])
    if kind == "quests":
        return "complete every quest" if c[1] == -1 else "complete %d quests" % c[1]
    if kind == "total":
        return "reach total level %d" % c[1]
    if kind == "level":
        return "get any skill to level %d" % c[1]
    if kind == "contract":
        return "complete %d contracts" % c[1]
    if kind == "signals":
        return "trace %d signals" % c[1]
    if kind == "stamps":
        return "collect %d theme stamp%s" % (c[1], "" if c[1] == 1 else "s")
    if kind == "relics":
        return "unearth %d dotfile relic%s" % (c[1], "" if c[1] == 1 else "s")
    if kind == "rice":
        return "reach a Rice rating of %d" % c[1]
    if kind == "tree":
        return "rank %d keybind action%s to %s" % (c[2], "" if c[2] == 1 else "s", C.TREE_RANKS[c[1] - 1][1].lower())
    return str(c)


# --------------------------------------------------------------- page shell
CSS = r"""
:root{__THEME__}
:root{--page:var(--bg);--box:var(--well);--head:var(--raised);--border:color-mix(in srgb,var(--fg) 22%,transparent);
--text:var(--fg);--muted:color-mix(in srgb,var(--fg) 75%,transparent);--link:var(--accent);--hl:var(--raised);--code:var(--well);
--u:3px;--step:polygon(var(--u) 0,calc(100% - var(--u)) 0,calc(100% - var(--u)) var(--u),100% var(--u),100% calc(100% - var(--u)),
calc(100% - var(--u)) calc(100% - var(--u)),calc(100% - var(--u)) 100%,var(--u) 100%,var(--u) calc(100% - var(--u)),0 calc(100% - var(--u)),
0 var(--u),var(--u) var(--u))}
*{box-sizing:border-box}
body{margin:0;background:var(--well);color:var(--text);font:15px/1.6 ui-monospace,"JetBrainsMono Nerd Font","JetBrains Mono",monospace}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:3px}
svg.px{vertical-align:middle;image-rendering:pixelated}
.step{clip-path:var(--step)}
header{display:flex;align-items:center;gap:14px;padding:10px 18px;background:var(--bg);border-bottom:var(--u) solid var(--accent);
position:sticky;top:0;z-index:5}
header .logo{display:flex;align-items:center;gap:12px;color:var(--fg);white-space:nowrap}
header .logo svg.word{height:21px}
#q{flex:1;max-width:420px;margin-left:auto;padding:8px 10px;border:0;background:var(--well);color:var(--fg);font:inherit;
clip-path:var(--step);outline:none}#q:focus{background:var(--raised)}
#results{position:absolute;top:56px;right:18px;width:min(420px,92vw);background:var(--bg);border:var(--u) solid var(--accent);
display:none;max-height:60vh;overflow:auto;z-index:6}
#results a{display:block;padding:7px 10px;border-bottom:1px solid var(--border)}#results a:hover{background:var(--hl)}
.wrap{display:flex;max-width:1280px;margin:0 auto}
nav{width:220px;flex:none;padding:16px 10px;font-size:14px}
nav h4{margin:16px 0 6px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
nav a{display:block;padding:3px 8px;color:var(--fg)}nav a:hover{background:var(--raised);text-decoration:none;color:var(--accent)}
main{flex:1;min-width:0;background:var(--bg);margin:16px 16px 16px 0;padding:22px 28px 44px;clip-path:var(--step)}
h1{margin:0 0 14px;line-height:0}h1 svg{height:28px}
h2{font-size:15px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:30px 0 10px;padding-bottom:6px;
border-bottom:var(--u) solid var(--border)}
h3{font-size:15px;margin:18px 0 6px}
.crumbs{font-size:13px;color:var(--muted);margin-bottom:12px}
.lead{font-size:16px}
table.wikitable{border-collapse:separate;border-spacing:0 var(--u);margin:8px 0 16px;font-size:14px}
.wikitable th,.wikitable td{padding:7px 11px;vertical-align:middle;background:var(--box)}
.wikitable th{background:var(--head);text-align:left;color:var(--accent);font-weight:600}
.wikitable.center td{text-align:center}
.infobox{float:right;clear:right;width:300px;margin:0 0 14px 22px;border-collapse:collapse;background:var(--box);font-size:14px;clip-path:var(--step)}
.infobox th,.infobox td{border-top:1px solid var(--border);padding:6px 9px;text-align:left;vertical-align:top}
.infobox caption,.infobox .title{padding:10px;background:var(--head);text-align:center;color:var(--accent);font-weight:700;letter-spacing:.06em}
.infobox .pic{text-align:center;padding:16px;background:var(--well)}
.infobox th{width:42%;background:var(--head)}
.navbox{clear:both;margin-top:32px;background:var(--box);font-size:14px;clip-path:var(--step)}
.navbox .nbt{background:var(--head);text-align:center;padding:7px;margin:0;color:var(--accent);letter-spacing:.1em;text-transform:uppercase;font-size:13px}
.navbox .nbb{padding:10px;text-align:center;line-height:2.2}
.navbox .nbb a{white-space:nowrap;margin:0 6px}
a.term{border-bottom:1px dotted var(--link)}a.term:hover{text-decoration:none;border-bottom-style:solid}
.ok{color:var(--green);font-weight:600}.no{color:var(--red);font-weight:600}
code,kbd{background:var(--well);color:var(--accent);padding:1px 6px;font:13px ui-monospace,monospace}
kbd{outline:1px solid var(--border)}
.note{background:var(--well);border-left:var(--u) solid var(--accent);padding:9px 13px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--u);max-width:460px}
.areas{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}.areas h3{margin:6px 0}.areas .slot{margin-bottom:var(--u)}
.slot{display:flex;align-items:center;justify-content:space-between;background:var(--well);padding:6px 10px;height:56px;
color:var(--fg);font-size:22px;font-weight:700;clip-path:var(--step)}
.slot:hover{background:var(--raised);text-decoration:none}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin:12px 0}
.card{background:var(--box);padding:12px 14px;clip-path:var(--step)}
.card h3{margin:0 0 6px;display:flex;align-items:center;gap:10px}
.scroll{background:var(--well);border-left:var(--u) solid var(--accent);padding:12px 16px;max-width:560px}
.qp{color:var(--accent);font-weight:700}
footer{max-width:1280px;margin:0 auto 30px;padding:0 16px;font-size:12px;color:var(--muted)}
@media (max-width:860px){nav{display:none}main{margin:10px}.infobox{float:none;width:100%;margin:0 0 14px}
header .logo span{display:none}}
"""

JS = r"""
const idx = __INDEX__;
const q = document.getElementById('q'), res = document.getElementById('results');
q.addEventListener('input', () => {
  const s = q.value.trim().toLowerCase();
  if (!s) { res.style.display = 'none'; return; }
  const hits = idx.filter(p => (p.t + ' ' + p.k).toLowerCase().includes(s)).slice(0, 14);
  res.innerHTML = hits.map(p => `<a href="${p.u}">${p.t}</a>`).join('') || '<a>No results</a>';
  res.style.display = 'block';
});
q.addEventListener('keydown', ev => { if (ev.key === 'Enter') { const a = res.querySelector('a[href]'); if (a) location = a.href; } });
document.addEventListener('click', ev => { if (!res.contains(ev.target) && ev.target !== q) res.style.display = 'none'; });
"""

PAGES = []      # (title, url, keywords) for search
SIDEBAR = [
    ("Learn", [("Learning path", "learn.html"), ("Glossary", "glossary.html")]),
    ("Navigation", [("Main page", "index.html"), ("Skills", "skills.html"), ("Rice rating", "rice.html"),
                    ("Quests", "quests.html"), ("Journal", "diary.html"), ("Your stats", "stats.html"),
                    ("Updates", "updates.html")]),
    ("Activities", [("Contracts", "contracts.html"), ("Signal hunts", "signals.html"),
                    ("Seasons and stamps", "seasons.html"), ("Keybind tree", "tree.html"),
                    ("Dotfile relics", "relics.html"), ("Random events", "random-events.html"),
                    ("Overclocks", "overclocks.html"), ("Sysop", "sysop.html"),
                    ("Job slots", "job-runs.html"), ("Daily streak", "daily-streak.html")]),
    ("Rewards", [("Tokens", "tokens.html"), ("Companions", "companions.html"), ("Mastery marks", "marks.html"),
                 ("Collection", "collection-log.html")]),
    ("Guides", [("Mechanics", "mechanics.html"), ("Experience", "experience.html"), ("Fair play", "fair-play.html"),
                ("The bar widget", "interface.html"), ("Commands", "commands.html"),
                ("AI agents & local models", "agents.html"), ("Privacy", "mechanics.html#privacy")]),
]


ICON_ALIAS = {"ui/stats.png": "total", "ui/quests.png": "quests", "ui/tasks.png": "tasks", "ui/log.png": "log",
              "ui/diary.png": "diary", "ui/collection-log.png": "collection", "ui/signal.png": "signal"}


def icon(path, size=None, alt=""):
    """A pixel icon as inline SVG in theme colours. `path` is an icon name, or an old sprite
    path (skill/<key>.png, companion/<id>.png, badge/<key>.png, ui/<x>.png)."""
    name, tint = path, "var(--accent)"
    if path.endswith(".png"):
        head, _, file = path.partition("/")
        stem = file[:-4]
        if head == "skill":
            name, tint = stem, "var(--%s)" % S.SKILL_BY_KEY[stem][4]
        elif head == "companion":
            name = stem
            sk = next((c[2] for c in C.COMPANIONS if c[0] == stem), None)
            tint = "var(--%s)" % S.SKILL_BY_KEY[sk][4] if sk else tint
        elif head == "badge":
            key = stem[:-2] if stem.endswith("_t") else stem
            name = "mark"
            tint = "var(--%s)" % S.SKILL_BY_KEY[key][4] if key in S.SKILL_BY_KEY else "var(--accent)"
        elif path.startswith("ui/signal"):
            name = "signal"
        else:
            name = ICON_ALIAS.get(path, "token")
    elif path not in I.ICONS:
        name = "token"
    px = max(1, int((size or 24) / 12))
    svg = I.svg(name, px, "var(--fg)", tint, "var(--accent)")
    label = ' role="img" aria-label="%s"' % e(alt) if alt else ' aria-hidden="true"'
    return svg.replace("<svg ", '<svg class="px"%s ' % label, 1)


def pixel_heading(text, cell=4):
    """A heading in the 5x7 pixel face, as SVG (the text stays in aria-label)."""
    up = text.upper()
    rects = []
    for i, ch in enumerate(up):
        g = PF.GLYPHS.get(ch) or PF.GLYPHS.get("?")
        for y, row in enumerate(g):
            for x, c in enumerate(row):
                if c == "#":
                    rects.append('<rect x="%d" y="%d" width="1" height="1"/>' % (i * 6 + x, y))
    w = max(1, len(up) * 6 - 1)
    return ('<svg class="word" role="img" aria-label="%s" viewBox="0 0 %d 7" width="%d" height="%d" '
            'shape-rendering="crispEdges" fill="currentColor">%s</svg>' % (e(text), w, w * cell, 7 * cell, "".join(rects)))


def skill_icon(k, size=20):
    return icon("skill/%s.png" % k, size, S.SKILL_BY_KEY[k][1])


def slink(k, with_icon=True):
    return '<a href="skill-%s.html">%s%s</a>' % (k, skill_icon(k) + " " if with_icon else "", S.SKILL_BY_KEY[k][1])


def qlink(qid):
    q = S.QUEST_BY_ID[qid]
    return '<a href="quest-%s.html">%s</a>' % (qid, e(q[1]))


def reward_str(reward):
    return ", ".join("%s %s XP" % ("{:,}".format(v), slink(k)) for k, v in reward.items())


def nav_html():
    out = []
    for head, links in SIDEBAR:
        out.append("<h4>%s</h4>" % e(head))
        out += ['<a href="%s">%s</a>' % (u, e(t)) for t, u in links]
    return "\n".join(out)


def skills_navbox():
    links = " ".join('<a href="skill-%s.html">%s%s</a>' % (k, skill_icon(k), e(S.SKILL_BY_KEY[k][1]))
                     for k in S.SKILL_KEYS)
    return '<div class="navbox"><h3 class="nbt">Skills</h3><div class="nbb">%s</div></div>' % links


def write(url, title, body, crumbs=None, keywords="", self_term=None):
    PAGES.append({"t": title, "u": url, "k": keywords})
    body = autolink(body, self_term)
    crumb = ""
    if crumbs:
        crumb = '<div class="crumbs">%s</div>' % " › ".join(
            '<a href="%s">%s</a>' % (u, e(t)) for t, u in crumbs)
    doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s - OmaLvL Wiki</title><link rel="stylesheet" href="wiki.css"><link rel="icon" href="favicon.svg"></head>
<body><header><a class="logo" href="index.html">%s%s</a>
<input id="q" type="search" placeholder="Search the wiki" aria-label="Search the wiki" autocomplete="off">
<div id="results"></div></header>
<div class="wrap"><nav>%s</nav><main>%s<h1>%s</h1>%s</main></div>
<footer>Generated %s from the game's own data · rebuild with <code>omalvl wiki</code> · in your Omarchy theme's colours · offline.</footer>
<script src="search.js"></script></body></html>""" % (
        e(title), icon("total", 24), pixel_heading("OmaLvL", 3), nav_html(), crumb, pixel_heading(title),
        body, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    _private_write(os.path.join(OUT, url), doc)


# --------------------------------------------------------------- data views
def quests_rewarding(k):
    return [q for q in C.QUESTS if k in q[4]]


def sysop_rewarding(k):
    return [w for w in C.SYSOP_CHALLENGES if k in w[4]]


def difficulty(qp):
    return {1: "Novice", 2: "Intermediate", 3: "Experienced"}.get(qp, "Master")


def git_log():
    try:
        out = subprocess.run([S.tool("git"), "-C", REPO, "log", "--date=short", "--pretty=%ad\t%h\t%s", "-n", "60", "--",
                              "."], capture_output=True, text=True, timeout=10).stdout
        return [l.split("\t", 2) for l in out.splitlines() if l.count("\t") >= 2]
    except (OSError, subprocess.SubprocessError):
        return []


# --------------------------------------------------------------- glossary: auto-linking
TERM_BY_ID = {t["id"]: t for t in G.T}
CAT_NAME = dict(G.CATEGORIES)
SKIP_TAGS = {"a", "code", "pre", "script", "style", "h1", "h2", "h3", "kbd", "title", "th", "button"}


# Term names that are also everyday English: link these only through their unambiguous aliases.
NOLINK_NAMES = {"make", "log", "root", "find", "flag", "signal", "kill / pkill", "build", "service", "merge", "bug", "backup"}


def _alias_table():
    """[(alias, id, case_sensitive)], longest first. Short ALL-CAPS acronyms (PATH, CPU, SSH ...)
    only match in capitals so they never link ordinary words."""
    rows = []
    for t in G.T:
        for a in {t["term"].split(" (")[0]} | set(t["aliases"]):
            if len(a) < 2 or a.lower() in NOLINK_NAMES:
                continue
            rows.append((a, t["id"], a.isupper() and len(a) <= 5))
    rows.sort(key=lambda r: -len(r[0]))
    return rows


ALIASES = _alias_table()
_ALIAS_RE = re.compile(r"(?<![\w/.$-])(%s)(?:e?s)?(?![\w/-])" % "|".join(re.escape(a) for a, _, _ in ALIASES), re.I)
_ALIAS_LOOKUP = {}
for _a, _id, _cs in ALIASES:
    _ALIAS_LOOKUP.setdefault(_a.lower(), []).append((_a, _id, _cs))


def autolink(body, self_term=None):
    """Link the first mention of each glossary term in a page's text (not inside links, code,
    headings or buttons), like Wikipedia."""
    done = {self_term} if self_term else set()
    out, depth = [], 0
    for part in re.split(r"(<[^>]+>)", body):
        if part.startswith("<"):
            m = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            if m and m.group(1).lower() in SKIP_TAGS and not part.endswith("/>"):
                depth = max(0, depth + (-1 if part.startswith("</") else 1))
            out.append(part)
            continue
        if depth or not part.strip():
            out.append(part)
            continue

        def sub(m):
            word = m.group(1)
            for alias, tid, cs in _ALIAS_LOOKUP.get(word.lower(), []):
                if cs and word != alias:
                    continue
                if tid in done:
                    return m.group(0)
                done.add(tid)
                return '<a class="term" href="term-%s.html" title="%s">%s</a>' % (
                    tid, e(TERM_BY_ID[tid]["short"]), m.group(0))
            return m.group(0)
        out.append(_ALIAS_RE.sub(sub, part))
    return "".join(out)


def rich(text):
    """Glossary markup: `code`, {skill:key}, {quest:id}, {page:file|text}."""
    text = e(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\{skill:(\w+)\}", lambda m: slink(m.group(1)), text)
    text = re.sub(r"\{quest:(\w+)\}", lambda m: qlink(m.group(1)) if m.group(1) in S.QUEST_BY_ID else m.group(1), text)
    text = re.sub(r"\{page:([\w.#-]+)\|([^}]+)\}", r'<a href="\1">\2</a>', text)
    return text


def _sh(argv, timeout=5):
    try:
        return subprocess.run([S.tool(argv[0])] + list(argv[1:]), capture_output=True, text=True,
                              timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _meminfo(key):
    try:
        for line in open("/proc/meminfo"):
            if line.startswith(key + ":"):
                return int(line.split()[1]) / 1048576
    except OSError:
        pass
    return 0


def machine_facts(tid):
    """Live facts about the computer the wiki was built on, for the 'On this machine' box.
    Detected, never hardcoded, so the wiki fits whoever runs it."""
    f = []
    try:
        if tid in ("cpu", "cpu-time", "load-average"):
            model = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), "?")
            f.append("CPU: %s, %d threads" % (model, os.cpu_count() or 0))
            if tid == "load-average":
                with open("/proc/loadavg") as lf:
                    f.append("Load right now: %s" % " ".join(lf.read().split()[:3]))
        elif tid in ("ram", "swap"):
            f.append("RAM: %.1f GB · swap: %.1f GB" % (_meminfo("MemTotal"), _meminfo("SwapTotal")))
        elif tid == "hdd-ssd":
            for d in _sh(["lsblk", "-dn", "-o", "NAME,ROTA,SIZE,MODEL"]).splitlines():
                parts = d.split(None, 3)
                if len(parts) >= 3 and not parts[0].startswith(("loop", "zram", "sr")):
                    f.append("%s: %s, %s %s" % (parts[0], "spinning HDD" if parts[1] == "1" else "SSD / flash",
                                               parts[2], parts[3] if len(parts) > 3 else ""))
        elif tid == "terminal":
            f.append("Your terminal ($TERMINAL): %s" % (os.environ.get("TERMINAL") or "not set"))
        elif tid in ("shell", "bash"):
            f.append("Your login shell: %s" % os.environ.get("SHELL", "?"))
            if shutil.which("bash"):
                f.append(_sh(["bash", "--version"]).splitlines()[0])
        elif tid in ("kernel", "linux"):
            f.append("Kernel: %s" % os.uname().release)
        elif tid in ("distribution", "arch-linux"):
            pretty = next((l.split("=", 1)[1].strip().strip('"') for l in open("/etc/os-release")
                           if l.startswith("PRETTY_NAME=")), "?")
            f.append("This system: %s" % pretty)
        elif tid in ("package-manager", "pacman", "package") and shutil.which("pacman"):
            f.append("Packages installed: %d" % len(_sh(["pacman", "-Qq"]).splitlines()))
        elif tid == "hyprland" and shutil.which("hyprctl"):
            v = _sh(["hyprctl", "version"])
            if v:
                f.append(v.splitlines()[0])
        elif tid in ("local-model", "llama-cpp", "gguf"):
            md = os.path.expanduser("~/.local/share/models")
            models = sorted(x for x in os.listdir(md) if x.endswith(".gguf")) if os.path.isdir(md) else []
            f.append("Models here: %s" % (", ".join(models) or "none yet"))
            f.append("local-llm: %s" % ("installed" if shutil.which("local-llm") else "not installed"))
        elif tid in ("git", "repository", "commit"):
            f.append("Repos this game watches (~/Work): %d" % len(S.git_repos()))
        elif tid == "encryption":
            f.append("Encrypted volume: %s" % ("yes (LUKS)" if "crypt" in _sh(["lsblk", "-o", "TYPE"]) else "none found"))
        elif tid == "theme" and shutil.which("omarchy-theme-current"):
            f.append("Current theme: %s" % _sh(["omarchy-theme-current"]))
        elif tid == "process":
            f.append("Processes running now: %d" % sum(1 for x in os.listdir("/proc") if x.isdigit()))
    except Exception:
        pass
    return [x for x in f if x]


# Lessons: (title, why, term ids, quest ids, Sysop challenge ids)
LESSONS = [
    ("Meet the terminal", "Everything else builds on typing commands and reading what comes back.",
     ["terminal", "shell", "command-line", "prompt-shell", "argument", "flag", "man-page", "tldr", "tab-completion"],
     ["terminal", "omarchy_cli"], ["man", "tldr", "which"]),
    ("Find your way around files", "Where things live, how to move around, and who may touch what.",
     ["filesystem", "directory", "home-directory", "absolute-path", "hidden-file", "dotfiles", "permissions", "chmod", "symlink"],
     ["shell"], ["chmod", "du", "df"]),
    ("Search and combine", "Small tools plus pipes beat one big tool.",
     ["unix-philosophy", "pipe", "standard-streams", "redirection", "grep", "ripgrep", "fd", "regex", "glob", "fzf", "shell-history"],
     ["shell"], ["fd", "history"]),
    ("The desktop", "Drive Omarchy from the keyboard.",
     ["omarchy", "hyprland", "wayland", "tiling", "workspace", "keybind", "scratchpad", "theme", "notification"],
     ["welcome", "navigation", "top_bar", "hotkeys", "themes", "toggles", "screenshots"], ["keybinds", "theme", "screenshot"]),
    ("Processes and services", "What's running, why, and how to stop it.",
     ["process", "pid", "signal", "kill", "daemon", "systemd", "service", "systemctl", "btop", "cpu", "ram", "load-average"],
     ["tuis_guis", "systemd"], ["btop", "systemctl", "free"]),
    ("When things break", "Logs first, guesses second.",
     ["journal", "log-file", "debugging", "bug", "exit-code", "backup", "kernel"],
     ["troubleshooting", "snapshots_security"], ["journal"]),
    ("Software and packages", "Installing, updating and understanding what's on the system.",
     ["package-manager", "package", "pacman", "aur", "dependency", "library", "arch-linux", "distribution"],
     ["arch_basics", "dotfiles_updates", "arch_wiki"], ["pacman_qi"]),
    ("Networking basics", "Addresses, ports, and talking to other machines safely.",
     ["ip-address", "localhost", "port", "dns", "ping", "ssh", "rsync", "http", "api"],
     [], ["ip", "ping", "rsync"]),
    ("Git and building things", "Save every change, review it, and ship it.",
     ["git", "repository", "commit", "diff", "branch", "merge", "remote", "github", "code-review", "build", "compiler",
      "make", "shell-script"],
     ["dev_tools", "neovim", "ai_builder3"], ["git_log", "git_diff", "tar"]),
    ("Security and the hacker mindset", "Curiosity, care, and least privilege.",
     ["hacker", "least-privilege", "root", "sudo", "encryption", "key-pair", "checksum", "firewall", "telemetry", "ctf",
      "open-source"],
     ["snapshots_security"], []),
    ("AI, agents and local models", "Use AI well: ground it, check it, and run it yourself.",
     ["llm", "ai-agent", "prompt", "token", "context-window", "hallucination", "grounding", "local-model", "llama-cpp",
      "quantization", "inference"],
     ["ai_agents", "ai_builder1", "ai_builder2", "off_grid"], ["local_llm"]),
]


def page_term(t, data):
    tid = t["id"]
    facts = machine_facts(tid)
    box = ('<table class="infobox"><tr><td class="title" colspan="2">%s</td></tr>%s<tr><th>Topic</th><td>'
           '<a href="glossary.html#%s">%s</a></td></tr><tr><th>Also called</th><td>%s</td></tr></table>') % (
        e(t["term"]),
        ('<tr><td class="pic" colspan="2"><b>On this machine</b><br>%s</td></tr>' % "<br>".join(e(x) for x in facts)) if facts else "",
        t["cat"], e(CAT_NAME[t["cat"]]), ", ".join(e(a) for a in t["aliases"]) or "—")
    body = box + '<p class="lead"><b>%s</b>: %s</p>%s' % (
        e(t["term"]), rich(t["short"]), "".join("<p>%s</p>" % rich(p) for p in t["body"]))
    if t["try"]:
        body += ('<h2>Try it</h2><p>Safe to run: nothing here changes your system (except files in /tmp).</p>'
                 '<table class="wikitable"><tr><th>Command</th><th>What you\'ll see</th></tr>%s</table>') % "".join(
            '<tr><td><code>%s</code></td><td>%s</td></tr>' % (e(c), e(w)) for c, w in t["try"])
    if t["irl"]:
        body += "<h2>In this game</h2><p>%s</p>" % rich(t["irl"])
    lessons = [(i, l) for i, l in enumerate(LESSONS, 1) if tid in l[2]]
    if lessons:
        body += "<h2>Learn it in</h2><p>%s</p>" % " · ".join(
            '<a href="learn.html#lesson-%d">Lesson %d: %s</a>' % (i, i, e(l[0])) for i, l in lessons)
    body += "<h2>Related</h2><p>%s</p>" % " · ".join(
        '<a href="term-%s.html">%s</a>' % (r, e(TERM_BY_ID[r]["term"])) for r in t["related"])
    same = [x for x in G.T if x["cat"] == t["cat"]]
    body += '<div class="navbox"><h3 class="nbt">%s</h3><div class="nbb">%s</div></div>' % (
        e(CAT_NAME[t["cat"]]), " ".join('<a href="term-%s.html">%s</a>' % (x["id"], e(x["term"])) for x in same))
    write("term-%s.html" % tid, t["term"], body, [("Main page", "index.html"), ("Glossary", "glossary.html")],
          "term glossary %s %s %s" % (t["short"], " ".join(t["aliases"]), CAT_NAME[t["cat"]]), self_term=tid)


def page_glossary():
    parts = ['<p>%d Linux, developer, hacker and AI terms, each with a plain-English page, commands to try, and where it '
             'shows up in this game. Every wiki page links the first mention of a term to its definition. New here? '
             'Start with the <a href="learn.html">Learning path</a>.</p>' % len(G.T),
             "<p>%s</p>" % " · ".join('<a href="#%s">%s</a>' % (k, e(n)) for k, n in G.CATEGORIES)]
    for key, name in G.CATEGORIES:
        rows = "".join('<tr><td><a href="term-%s.html"><b>%s</b></a></td><td>%s</td></tr>' % (
            t["id"], e(t["term"]), rich(t["short"]))
            for t in sorted((t for t in G.T if t["cat"] == key), key=lambda t: t["term"].lower()))
        parts.append('<h2 id="%s">%s</h2><table class="wikitable"><tr><th>Term</th><th>In one sentence</th></tr>%s</table>'
                     % (key, e(name), rows))
    write("glossary.html", "Glossary", "".join(parts), [("Main page", "index.html")], "glossary terms definitions dictionary")


def page_learn(data):
    parts = ['<p>A path through the glossary and the quests, from first terminal to running your own AI. Each lesson lists '
             'the ideas to read, the quests that make you do them (and pay XP), and Sysop challenges to practise. '
             'Quests complete themselves when the game sees you do the steps.</p>']
    for i, (title, why, terms, quests, woms) in enumerate(LESSONS, 1):
        tl = " · ".join('<a href="term-%s.html">%s</a>' % (t, e(TERM_BY_ID[t]["term"])) for t in terms)
        ql = " · ".join('%s%s' % (qlink(q), ' <span class="ok">✓</span>' if q in data["quests"] else "")
                        for q in quests if q in S.QUEST_BY_ID)
        wl = " · ".join("<code>%s</code>" % e(S.SYSOP_BY_ID[w][2]) for w in woms if w in S.SYSOP_BY_ID)
        parts.append('<h2 id="lesson-%d">Lesson %d: %s</h2><p>%s</p><p><b>Read:</b> %s</p>%s%s' % (
            i, i, e(title), e(why), tl, "<p><b>Quests:</b> %s</p>" % ql if ql else "",
            "<p><b>Practise:</b> %s</p>" % wl if wl else ""))
    write("learn.html", "Learning path", "".join(parts), [("Main page", "index.html")],
          "learn course lessons tutorial beginner")


# --------------------------------------------------------------- pages
def page_index(data, snap):
    by_key = {s["key"]: s for s in snap["skills"]}
    areas = "".join('<div><h3 style="color:var(--%s)">%s <span style="color:var(--muted);font-weight:400">%d</span></h3>%s</div>' % (
        a["tint"], e(a["name"]), int(a["level"]),
        "".join('<a class="slot" href="skill-%s.html" title="%s">%s<span>%d</span></a>' % (
            k, e(by_key[k]["name"]), icon("skill/%s.png" % k), by_key[k]["level"]) for k in a["skills"]))
        for a in snap["rice"]["areas"])
    sysop, surge, season = snap.get("sysopInfo"), snap.get("surgeInfo"), snap.get("season") or {}
    today = []
    if sysop:
        today.append("<b>Sysop:</b> %s — try <code>%s</code> (%s XP)%s" % (
            e(sysop["task"]), e(sysop["hint"]), e(sysop["reward"]), " <span class=ok>done</span>" if sysop["done"] else ""))
    if season.get("areaName"):
        today.append("<b>Season:</b> %s favours %s (+%d%% XP)." % (e(season["theme"]), e(season["areaName"]), season["bonus"]))
    if season.get("updateDay"):
        today.append("<b>Update Day:</b> System XP +%d%% right now." % season["updateDay"]["bonus"])
    if surge:
        today.append("<b>Overclock:</b> %s XP is doubled right now." % slink(surge["skill"]))
    if snap["contractInfo"].get("task"):
        t = snap["contractInfo"]["task"]
        today.append("<b>Contract:</b> %s (%d/%d)" % (e(t["text"]), t["done"], t["n"]))
    if snap.get("signalInfo"):
        today.append("<b>Signal:</b> <i>%s</i>" % e(snap["signalInfo"]["hint"]))
    facts = [
        "Level %d is halfway to level 100 in XP: the last levels are the long climb." % S.HALFWAY,
        "Every Omarchy theme favours one of the six areas. Switching theme changes your season.",
        "Companions hatch at a set level. There are no drop tables in OmaLvL.",
        "The daemon only pays continuous skills while someone is actually at the computer.",
        "Committing your hypr or nvim config to git unearths a dotfile relic.",
        "Nothing in this game leaves your machine: shell history contributes command counts and safe command names only.",
        "Local models train Models; agent CLIs train Agents.",
    ]
    fact = facts[datetime.date.today().toordinal() % len(facts)]
    cards = "".join('<div class="card"><h3>%s<a href="%s">%s</a></h3>%s</div>' % (icon(i), u, e(t), d) for i, t, u, d in [
        ("ui/quests.png", "Learning path", "learn.html", "%d lessons from first terminal to running your own AI." % len(LESSONS)),
        ("ui/log.png", "Glossary", "glossary.html", "%d Linux, dev, hacker and AI terms explained." % len(G.T)),
        ("rice", "Rice rating", "rice.html", "Six areas, one hexagon, eight ranks."),
        ("ui/quests.png", "Quests", "quests.html", "%d quests that teach Omarchy, Linux and AI by doing them." % len(C.QUESTS)),
        ("season", "Seasons and stamps", "seasons.html", "Your theme sets a season; Update Day boosts System."),
        ("tree", "Keybind tree", "tree.html", "Every Omarchy action you use, ranked."),
        ("relic", "Dotfile relics", "relics.html", "Commit your config to unearth them."),
        ("ui/tasks.png", "Contracts", "contracts.html", "A daily task from the Dispatcher; streaks pay points."),
    ])
    body = """<p class="lead"><b>OmaLvL</b> turns using your Omarchy machine into a game: every keybind, command,
build, commit and push trains one of <a href="skills.html">%d skills</a> in six areas, levels 1 to 100 on
<a href="experience.html">its own curve</a>. The areas make your <a href="rice.html">Rice rating</a>, and
<a href="quests.html">quests</a>, <a href="contracts.html">contracts</a>, <a href="signals.html">signals</a> and the
<a href="diary.html">journal</a> teach the system by doing it. This wiki is generated from the game's own code.</p>
<p>Rice rating <b>%d</b> (%s) · total level <b>%d</b> / %d · renown <b>%d</b> / %d · <a href="stats.html">Your stats</a></p>
<div class="areas">%s</div>
<div style="display:flex;gap:28px;flex-wrap:wrap;align-items:flex-start">
<div style="flex:1;min-width:260px"><h2 style="margin-top:6px">Today</h2><ul>%s</ul></div>
<div style="flex:1;min-width:260px"><h2 style="margin-top:6px">Did you know?</h2><p>%s</p></div></div>
<h2>Explore</h2><div class="cards">%s</div>%s""" % (
        len(S.SKILLS), snap["rice"]["rating"], e(snap["rice"]["rank"]), snap["total"], snap["maxTotal"],
        snap["questPoints"], snap["maxQuestPoints"], areas,
        "".join("<li>%s</li>" % t for t in today) or "<li>Nothing waiting. Go and train something.</li>",
        e(fact), cards, skills_navbox())
    write("index.html", "Main page", body, keywords="home welcome")


def page_skills(snap):
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        slink(k), e(S.AREA_BY_ID[S.AREA_OF[k]][1]), e(S.SKILL_BY_KEY[k][3]), "yes" if k in C.SURGE_SKILLS else "")
        for k in S.SKILL_KEYS)
    body = """<p>There are %d skills in six areas. Each levels from 1 to 100 on OmaLvL's
<a href="experience.html">experience curve</a>, so the maximum total level is %d. An area's level is the mean of its
skills, and the six area levels make your <a href="rice.html">Rice rating</a>.</p>
<table class="wikitable"><tr><th>Skill</th><th>Area</th><th>Trained by</th><th>Overclocks</th></tr>%s</table>
<p><b>Passive</b> skills (%s) are paid continuously while you're at the computer, so they don't show
<a href="interface.html">XP drops</a>.</p>%s""" % (
        len(S.SKILLS), S.MAX_TOTAL, rows, ", ".join(S.SKILL_BY_KEY[k][1] for k in S.SKILL_KEYS if k in S.PASSIVE),
        skills_navbox())
    write("skills.html", "Skills", body, [("Main page", "index.html")], "skills list areas")


def page_skill(k, snap):
    key, name, abbr, blurb, accent = S.SKILL_BY_KEY[k]
    me = next(s for s in snap["skills"] if s["key"] == k)
    companion = next((c for c in C.COMPANIONS if c[2] == k), None)
    area = S.AREA_BY_ID[S.AREA_OF[k]]
    info = [("Area", e(area[1])), ("Trained by", e(blurb)),
            ("Passive", "Yes (no XP drops)" if k in S.PASSIVE else "No"),
            ("Overclocks", "Yes" if k in C.SURGE_SKILLS else "No"),
            ("Companion", '%s <a href="companions.html">%s</a> (level %d)' % (icon("companion/%s.png" % companion[0], 24), companion[1], companion[3]) if companion else "None"),
            ("Your level", "%d (%s XP)" % (me["level"], "{:,}".format(me["xp"])))]
    box = '<table class="infobox"><tr><td class="title" colspan="2">%s</td></tr><tr><td class="pic" colspan="2">%s</td></tr>%s</table>' % (
        e(name), icon("skill/%s.png" % k, 75), "".join("<tr><th>%s</th><td>%s</td></tr>" % r for r in info))
    g = S.skill_guide(k, S.load())
    train = "".join("<tr><td>%s</td><td>%s</td></tr>" % (e(t["what"]), e(t["xp"])) for t in g["training"])
    unl = "".join("<tr><td>%d</td><td>%s</td><td>%s</td></tr>" % (
        u["level"], e(u["text"]), '<span class="ok">✓</span>' if u["met"] else "") for u in g["unlocks"])
    qs = quests_rewarding(k)
    quest_rows = "".join("<tr><td>%s</td><td>%s</td></tr>" % (qlink(q[0]), "{:,}".format(q[4][k])) for q in qs)
    womr = sysop_rewarding(k)
    sysop_rows = "".join("<tr><td>%s</td><td><code>%s</code></td><td>%d</td></tr>" % (e(w[1]), e(w[2]), w[4][k]) for w in womr)
    extra = ""
    if k == "agents":
        extra = '<p>Idle agents earn nothing: only CPU time counts. See <a href="agents.html">AI agents</a>.</p>'
    if k == "models":
        extra = '<p>Any local runtime counts (llama.cpp, Ollama, LM Studio ...). See <a href="agents.html">local models</a>.</p>'
    if k == "theming":
        extra = '<p>Theming also pays for <a href="seasons.html">theme stamps</a> and <a href="relics.html">dotfile relics</a>.</p>'
    if k == "shell":
        extra = '<p>Shell also pays for every rank on the <a href="tree.html">keybind tree</a>.</p>'
    body = box + """<p class="lead"><b>%s</b> is a skill in the %s area. It is trained by <b>%s</b>.</p>
<h2>Training</h2><table class="wikitable"><tr><th>Activity</th><th>XP</th></tr>%s</table>%s
<p>Continuous sources are capped at %d XP per 30-second tick, shell-command sources at %d, and the same command again within
%d minutes earns nothing.</p>
<h2>Skill guide</h2><p>What %s levels unlock (in the panel: click the skill).</p>
<table class="wikitable"><tr><th>Level</th><th>Unlock</th><th>You</th></tr>%s</table>
<p>Any skill also gains XP from <a href="tokens.html">tokens</a>, <a href="signals.html">signal caches</a>
and <a href="agents.html">agent awards</a>.</p>
<h2>Quest rewards</h2>%s<h2>Sysop challenges</h2>%s%s""" % (
        e(name), e(area[1]), e(blurb), train, extra,
        S.R["tick_cap"], S.R["cmd_tick_cap"], S.R["repeat_window"] // 60, e(name), unl,
        '<table class="wikitable"><tr><th>Quest</th><th>XP</th></tr>%s</table>' % quest_rows if qs else "<p>None.</p>",
        '<table class="wikitable"><tr><th>Challenge</th><th>Try</th><th>XP</th></tr>%s</table>' % sysop_rows if womr else "<p>None.</p>",
        skills_navbox())
    write("skill-%s.html" % k, name, body, [("Main page", "index.html"), ("Skills", "skills.html")],
          "skill %s %s %s" % (abbr, blurb, area[1]))


def page_experience():
    rows = []
    for lvl in range(1, S.MAX_LEVEL + 1):
        xp = S.LEVEL_XP[lvl]
        diff = xp - S.LEVEL_XP[lvl - 1] if lvl > 1 else 0
        style = ' style="font-weight:700"' if lvl in (S.HALFWAY, S.MAX_LEVEL) else ""
        rows.append("<tr%s><td>%d</td><td>%s</td><td>%s</td><td>%.2f%%</td></tr>" % (
            style, lvl, "{:,}".format(xp), "{:,}".format(diff), 100.0 * xp / S.MAX_XP))
    pace = "".join("<tr><td>{:,}</td><td>{:,}</td><td>{:,}</td><td>{:,}</td></tr>".format(
        r, round(S.LEVEL_XP[25] / r), round(S.LEVEL_XP[50] / r), round(S.MAX_XP / r)) for r in (500, 1000, 2500, 5000, 10000))
    body = """<p>OmaLvL's curve is a power curve, not an exponential: the XP to reach level <i>L</i> is
<b>100·(L−1) + 9,990,100·((L−1)/99)<sup>3.5</sup></b>, rounded. Level 2 takes 101 XP, level 100 takes exactly
<b>%s XP</b>, and level <b>%d</b> is the halfway point. Early levels come in minutes; the climb gets steadily longer
instead of suddenly doubling.</p>
<h2>Rules</h2><ul>
<li>Levels stop at <b>100</b>. XP keeps counting after that (up to %s per skill), and level 100 earns the skill's
<a href="marks.html">mastery mark</a>.</li>
<li>Total level is the sum of all %d skills: %d at most.</li>
<li>Some quests, contracts and Sysop challenges need levels; see each <a href="skills.html">skill's guide</a>.</li></ul>
<h2>Pacing</h2><p>Rates are set so a skill you use regularly reaches 100 in roughly 3,000–5,000 active hours (two to
three years of normal use). Hours of activity needed at a steady rate:</p>
<table class="wikitable center"><tr><th>XP per active hour</th><th>Level 25</th><th>Level 50</th><th>Level 100</th></tr>%s</table>
<h2>Experience table</h2><table class="wikitable center"><tr><th>Level</th><th>Experience</th><th>Difference</th><th>Of 100</th></tr>%s</table>""" % (
        "{:,}".format(S.MAX_XP), S.HALFWAY, "{:,}".format(S.XP_CAP), len(S.SKILLS), S.MAX_TOTAL, pace, "".join(rows))
    write("experience.html", "Experience", body, [("Main page", "index.html"), ("Guides", "mechanics.html")],
          "xp table levels curve halfway 100")


def page_rice(snap):
    r = snap["rice"]
    areas = "".join("<tr><td style=\"color:var(--%s)\"><b>%s</b></td><td>%s</td><td>%.1f</td></tr>" % (
        a["tint"], e(a["name"]), ", ".join(slink(k) for k in a["skills"]), a["level"]) for a in r["areas"])
    ranks = "".join("<tr><td>%d</td><td>%s</td><td>%s</td></tr>" % (
        need, e(name), '<span class="ok">you</span>' if name == r["rank"] else "") for need, name in C.RICE_RANKS)
    skins = "".join("<tr><td>%s</td><td>%d</td><td>%s</td></tr>" % (
        e(name), need, '<span class="ok">unlocked</span>' if r["rating"] >= need else "") for sid, name, need in C.SKINS)
    body = """<p class="lead">Your <b>Rice rating</b> measures how well-rounded your Omarchy use is: ten times the mean of
your six area levels, from 10 on a fresh install to 1000 with every skill at 100. In the panel it is drawn as a hexagon,
one point per area.</p>
<p><b>You:</b> %d · %s%s. Weakest area: %s (train %s).</p>
<h2>Areas</h2><table class="wikitable"><tr><th>Area</th><th>Skills</th><th>Level</th></tr>%s</table>
<h2>Ranks</h2><table class="wikitable"><tr><th>Rating</th><th>Rank</th><th></th></tr>%s</table>
<h2>Skins</h2><p>Panel frames unlocked by your rating. Wear one with <code>omalvl skin &lt;name&gt;</code> or the Rice tab.</p>
<table class="wikitable"><tr><th>Skin</th><th>Rating</th><th></th></tr>%s</table>
<h2>Wallpaper</h2><p><code>omalvl wallpaper</code> draws your hexagon, areas and levels as a pixel-art PNG in your theme's
colours (in <code>~/Pictures/omalvl/</code>). Set it yourself with <code>omarchy-theme-bg-set &lt;file&gt;</code>.</p>""" % (
        r["rating"], e(r["rank"]), (" · next: %s at %d" % (e(r["next"]["rank"]), r["next"]["rating"])) if r["next"] else "",
        e(r["weakest"]["area"]), slink(r["weakest"]["skill"]), areas, ranks, skins)
    write("rice.html", "Rice rating", body, [("Main page", "index.html")], "rice rating rank hexagon area skins wallpaper")


def page_seasons(snap):
    si = snap.get("season") or {}
    import zlib  # noqa: F401  (the area per theme is computed in skills.theme_area)
    themes_dir = [os.path.join(S.CONFIG_HOME, "omarchy", "themes"), "/usr/share/omarchy/themes",
                  os.path.join(os.path.expanduser("~"), ".local/share/omarchy/themes")]
    names = set()
    for d in themes_dir:
        try:
            names.update(n for n in os.listdir(d) if not n.startswith("."))
        except OSError:
            pass
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(n), e(S.AREA_BY_ID[S.theme_area(n)][1]), '<span class="ok">stamped</span>' if any(st["theme"] == S._theme_key(n) for st in si.get("stamps", [])) else "")
        for n in sorted(names)[:80])
    body = """<p class="lead">The theme you wear sets a <b>season</b>: one of the six areas earns <b>+%d%%</b> measured XP
while that theme is on. Which area is fixed per theme name, so every theme has its own character.</p>
<p><b>Now:</b> %s</p>
<h2>Theme stamps</h2><p>Wear a theme for <b>%d active minutes</b> to stamp it into your passport (+%d Theming XP).
You have <b>%d</b>: %s.</p>
<h2>Update Day</h2><p>Running <code>omarchy update</code> starts Update Day (once a day): System XP is <b>+%d%%</b> for
%d minutes, and you get an XP token worth %s XP.</p>
<h2>Themes on this machine</h2><table class="wikitable"><tr><th>Theme</th><th>Season favours</th><th></th></tr>%s</table>""" % (
        int(C.SEASON_BONUS * 100),
        ("%s favours %s." % (e(si["theme"]), e(si["areaName"]))) if si.get("areaName") else "no Omarchy theme found.",
        C.STAMP_MINUTES, C.STAMP_XP, len(si.get("stamps", [])), ", ".join(e(st["theme"]) for st in si.get("stamps", [])) or "none yet",
        int(C.UPDATE_DAY_BONUS * 100), C.UPDATE_DAY_MINUTES, "{:,}".format(C.UPDATE_DAY_TOKEN), rows or "<tr><td colspan=3>No themes found.</td></tr>")
    write("seasons.html", "Seasons and stamps", body, [("Main page", "index.html")], "season theme stamp passport update day")


def page_tree(snap):
    parts = []
    for b in snap.get("treeInfo") or []:
        cells = "".join("<tr><td>%s</td><td>%s</td><td>%d</td></tr>" % (e(n["name"]), e(n["title"]), n["uses"]) for n in b["nodes"])
        parts.append("<h2>%s</h2><p>%d found, %d mastered.</p><table class=\"wikitable\"><tr><th>Action</th><th>Rank</th><th>Uses</th></tr>%s</table>" % (
            e(b["name"]), b["found"], b["mastered"], cells))
    ranks = ", ".join("<b>%s</b> at %d use%s (+%d Shell XP)" % (t, n, "" if n == 1 else "s", xp) for n, t, xp in C.TREE_RANKS)
    body = """<p class="lead">Every Omarchy keybind action you use is a node on the <b>keybind tree</b>, grouped into five
branches. Using an action ranks it up: %s. New actions appear as you find them; a few hints are shown before you do.</p>%s""" % (
        ranks, "".join(parts))
    write("tree.html", "Keybind tree", body, [("Main page", "index.html")], "keybind tree branch rank mastered shortcuts")


def page_relics(data):
    rows = "".join("<tr><td>%s %s</td><td><code>%s</code></td><td>%s</td></tr>" % (
        icon("relic", 22), e(name), e(rx), '<span class="ok">found</span>' if rid in data["relics"] else "")
        for rid, name, rx in C.RELICS)
    body = """<p class="lead">Keep your config in git. A commit that touches a config path, in any repo the game watches
(config <code>repos</code>), unearths that path's <b>dotfile relic</b>, once: %s.</p>
<table class="wikitable"><tr><th>Relic</th><th>Path pattern</th><th>You</th></tr>%s</table>
<p>Only file paths of the newest commit are read, never contents.</p>""" % (
        ", ".join("+%d %s XP" % (v, S.SKILL_BY_KEY[k][1]) for k, v in C.RELIC_XP.items()), rows)
    write("relics.html", "Dotfile relics", body, [("Main page", "index.html")], "relic dotfiles config git commit")


def page_quests(data):
    rows = []
    for qid, name, qp, desc, reward, auto, steps in C.QUESTS:
        done = qid in data["quests"]
        rows.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            qlink(qid), difficulty(qp), qp, "Auto" if auto else "Manual",
            ", ".join("%d %s" % (v, slink(k)) for k, v in C.QUEST_REQS.get(qid, {}).items()) or "—", reward_str(reward),
            '<span class="ok">Complete</span>' if done else '<span class="no">Not started</span>'))
    body = """<p>Quests teach Omarchy, Linux and AI by doing them. Most <b>auto-complete</b> when the daemon sees you do
the steps; the rest you tick off yourself in the <a href="interface.html">Quests tab</a> or with <code>omalvl quest &lt;id&gt;</code>.
There are %d quests worth %d renown.</p>
<table class="wikitable"><tr><th>Quest</th><th>Difficulty</th><th>Renown</th><th>Completion</th><th>Requirements</th><th>Rewards</th><th>You</th></tr>%s</table>""" % (
        len(C.QUESTS), S.MAX_QP, "".join(rows))
    write("quests.html", "Quests", body, [("Main page", "index.html")], "quest list renown")


def page_quest(q, data):
    qid, name, qp, desc, reward, auto, steps = q
    done = data["quests"].get(qid)
    info = [("Difficulty", difficulty(qp)), ("Renown", qp), ("Completion", "Automatic" if auto else "By hand"),
            ("Status", '<span class="ok">Complete</span>' if done else '<span class="no">Not started</span>'),
            ("Requirements", ", ".join("%d %s" % (v, slink(k)) for k, v in C.QUEST_REQS.get(qid, {}).items()) or "None"),
            ("ID", "<code>%s</code>" % qid)]
    box = '<table class="infobox"><tr><td class="title" colspan="2">%s</td></tr><tr><td class="pic" colspan="2">%s</td></tr>%s</table>' % (
        e(name), icon("ui/quests.png", 54), "".join("<tr><th>%s</th><td>%s</td></tr>" % r for r in info))
    walk = "".join("<li>%s%s</li>" % (e(t), "" if c is None else ' <span style="color:var(--muted)">(tracked: %s)</span>' % e(describe_cond(c)))
                   for t, c in steps)
    autos = "".join("<li>%s</li>" % e(describe_cond(c)) for c in auto)
    body = box + """<p class="lead"><b>%s</b> is a %s quest. %s.</p>
<h2>Walkthrough</h2><ol>%s</ol>%s
<h2>Rewards</h2><div class="scroll">%d renown<br>%s</div>""" % (
        e(name), difficulty(qp).lower(), e(desc), walk,
        "<p>The quest completes itself when you: </p><ul>%s</ul>" % autos if auto else
        "<p>Mark it complete in the Quests tab (two clicks) or run <code>omalvl quest %s</code>.</p>" % qid,
        qp, "<br>".join("%s %s XP" % ("{:,}".format(v), S.SKILL_BY_KEY[k][1]) for k, v in reward.items()))
    write("quest-%s.html" % qid, name, body, [("Main page", "index.html"), ("Quests", "quests.html")],
          "quest " + desc)


def page_contracts(snap):
    m = S.R["contract_task_mult"]
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%d</td><td>%d–%d</td><td>%s–%s</td></tr>" % (
        e(text.format(n="N")), slink(pays), C.CONTRACT_REQS.get(tid, 0), lo, hi,
        "{:,}".format(lo * unit * m), "{:,}".format(hi * unit * m))
        for tid, text, key, (lo, hi), unit, pays in C.CONTRACT_TASKS)
    sl = snap["contractInfo"]
    body = """<p>The Dispatcher gives you one contract a day automatically, and you can ask for up to %d a day.
Finishing one pays XP in the skill it trains, plus contract points: <b>10</b> per contract, <b>50</b> for every 10th in a row.
Skipping one resets your streak. A finished contract has a 25%% chance to come with an easy or medium
<a href="signals.html">signal</a> if you don't already have one.</p>
<p><b>You:</b> streak %d · %d points · %d done%s.</p>
<h2>Contracts</h2><table class="wikitable"><tr><th>Contract</th><th>Pays</th><th>Total level</th><th>Amount</th><th>XP</th></tr>%s</table>
<p>Commands: <code>omalvl contract</code>, <code>omalvl contract new</code>, <code>omalvl contract skip</code>.</p>""" % (
        C.CONTRACT_PER_DAY, sl["streak"], sl["points"], sl["completed"],
        " · current: " + e(sl["task"]["text"]) if sl.get("task") else "", rows)
    write("contracts.html", "Contracts", body, [("Main page", "index.html")], "contract dispatcher points streak")


def page_clues():
    tiers = "".join("<tr><td>%s %s</td><td>%d</td><td>%s–%s XP</td><td>%d%%</td></tr>" % (
        icon("ui/signal-%s.png" % t, 22), t.title(), steps, "{:,}".format(lo), "{:,}".format(hi), int(token * 100))
        for t, (steps, (lo, hi), token) in C.SIGNAL_TIERS.items())
    steps = "".join("<tr><td><i>%s</i></td><td>%s</td></tr>" % (e(hint), e(describe_cond(cond)).capitalize())
                    for cid, hint, cond in C.SIGNAL_STEPS)
    body = """<p>Signals come from <a href="random-events.html">the Sysop's notes</a> and finished
<a href="contracts.html">contracts</a>. Each step is a riddle about something to do on the desktop; it solves itself
when you do it. The last step decrypts a <b>cache</b>: XP spread over three random skills, sometimes with a
<a href="tokens.html">token</a>.</p>
<h2>Tiers</h2><table class="wikitable"><tr><th>Tier</th><th>Steps</th><th>Cache</th><th>Token chance</th></tr>%s</table>
<h2>Signal steps</h2><p>Spoilers below.</p><table class="wikitable"><tr><th>Signal</th><th>Solution</th></tr>%s</table>""" % (tiers, steps)
    write("signals.html", "Signal hunts", body, [("Main page", "index.html")], "signal cache riddle")


def page_diary(data):
    parts = []
    for tier, title, tasks, token in C.DIARIES:
        done = tier in data["diary"]
        rows = "".join("<tr><td>%s</td><td>%s</td></tr>" % (
            e(t), '<span class="ok">✓</span>' if S.cond_met(data, c) else "") for t, c in tasks)
        parts.append("<h2>%s %s</h2><p>Reward: an XP token worth <b>%s XP</b>.</p><table class=\"wikitable\"><tr><th>Entry</th><th>Done</th></tr>%s</table>" % (
            e(title), '<span class="ok">(complete)</span>' if done else "", "{:,}".format(token), rows))
    body = """<p>The Omarchy journal has four tiers, named for how deep into the machine you've gone: Boot, Login, Root and
Kernel. Every entry is checked automatically; finishing a tier gives an XP token you can redeem on any skill
(<code>omalvl token &lt;skill&gt;</code>).</p>""" + "".join(parts)
    write("diary.html", "Journal", body, [("Main page", "index.html")], "journal boot login root kernel token")


def page_random_events():
    total = sum(ev[4] for ev in C.RANDOM_EVENTS)
    effect = {"token": "a courier token (10× a skill's level in XP)", "signal": "a signal (or a token if you have one)",
              "xp_random": "XP in a random skill (5× its level + 20)", "xp_focus": "Focus XP (10× its level + 50)"}
    rows = "".join("<tr><td>%s</td><td><i>%s</i></td><td>%s</td><td>%d%%</td></tr>" % (
        e(t), e(m), effect[kind], round(100 * w / total)) for eid, t, m, kind, w in C.RANDOM_EVENTS)
    body = """<p>While you're at the computer, a random event can appear at most once every %d minutes; after that each
active 30-second tick has a 1 in %d chance. They arrive as a notification.</p>
<table class="wikitable"><tr><th>Event</th><th>Message</th><th>Gives</th><th>Share</th></tr>%s</table>""" % (
        C.RANDOM_COOLDOWN // 60, round(1 / C.RANDOM_CHANCE), rows)
    write("random-events.html", "Random events", body, [("Main page", "index.html")], "courier sysop note gremlin coffee")


def page_pets(data):
    rows = "".join("<tr><td>%s</td><td><b>%s</b></td><td>%s</td><td>%d</td><td>%s</td></tr>" % (
        icon("companion/%s.png" % pid, 40), e(name), slink(skill), lvl,
        '<span class="ok">Hatched</span>' if pid in data["companions"] else "")
        for pid, name, skill, lvl in C.COMPANIONS)
    body = """<p>Nine pixel companions. Each one hatches, for certain, the moment its skill reaches the level below. There is
no luck involved: train the skill and it comes.</p>
<table class="wikitable"><tr><th></th><th>Companion</th><th>Skill</th><th>Level</th><th>You</th></tr>%s</table>""" % rows
    write("companions.html", "Companions", body, [("Main page", "index.html"), ("Rewards", "collection-log.html")], "companion hatch")


def page_stars():
    body = """<p>A few times a day, while you're at the computer, an <b>overclock</b> starts. For <b>%d minutes</b> the XP you
earn from activity in one skill is <b>doubled</b>. Tokens, caches and agent awards are not doubled. After one ends, the next
can't come for %d hours; then each active tick has a 1 in %d chance.</p>
<p>Skills an overclock can land on: %s.</p>
<p>While one is on, the bar shows a yellow pip and the skill gets a gold edge. Check with <code>omalvl overclock</code>.</p>""" % (
        C.SURGE_MINUTES, C.SURGE_COOLDOWN // 3600, round(1 / C.SURGE_CHANCE), ", ".join(slink(k) for k in C.SURGE_SKILLS))
    write("overclocks.html", "Overclocks", body, [("Main page", "index.html")], "overclock double xp")


def page_wom(snap):
    rows = "".join("<tr><td>%s</td><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
        e(task), ("%d %s" % (C.SYSOP_REQS[cid][1], slink(C.SYSOP_REQS[cid][0]))) if cid in C.SYSOP_REQS else "Beginner", e(hint), reward_str(reward), ("<code>%s</code> %s" % (e(req), '<span class="ok">✓</span>' if shutil.which(req) else '<span class="no">missing</span>')) if req else "—")
        for cid, task, hint, cond, reward, req in C.SYSOP_CHALLENGES)
    w = snap.get("sysopInfo")
    body = """%s<p>The Sysop sets one small "learn this" challenge a day. It is picked by date from the challenges whose
command is installed, checked automatically, and pays XP once. These are written by hand, so every hint is correct.</p>
<p><b>Today:</b> %s</p>
<h2>Ask the local AI</h2><p>The Tasks tab's <b>Explain it (local AI)</b> button (or <code>omalvl sysop explain</code>) has your
<a href="agents.html">local model</a> explain today's command. It is grounded in the command's own documentation (its
<code>tldr</code> page, else <code>--help</code>, else the man page) and told not to guess. The panel labels the answer as the
AI's, because small models can still be wrong. The challenge itself stays hand-written.</p>
<h2>All challenges</h2><p>Beginner challenges are open to everyone; the rest join the rotation once you have the level.</p>
<table class="wikitable"><tr><th>Challenge</th><th>Level</th><th>Try</th><th>Reward</th><th>Needs</th></tr>%s</table>""" % (
        '<p style="float:right">%s</p>' % icon("sysop", 120),
        ("%s — <code>%s</code>%s" % (e(w["task"]), e(w["hint"]), " <span class=ok>done</span>" if w["done"] else "")) if w else "not set yet",
        rows)
    write("sysop.html", "Sysop", body, [("Main page", "index.html")], "daily challenge learn command")


def page_farming_runs(snap):
    jobs = snap.get("jobInfo") or []
    rows = []
    for name in C.JOB_SLOTS:
        p = next((x for x in jobs if x["slot"] == name), None)
        state = "empty" if not p else (("failed (+%d XP)" % p["xp"] if p["dead"] else "done (+%d XP)" % p["xp"]) if p["done"] else "running")
        rows.append("<tr><td>%s %s</td><td>%s</td><td>%s</td></tr>" % (
            icon("job_dead" if p and p["dead"] else ("job_done" if p and p["done"] else ("job_growing" if p else "job_empty")), 22),
            e(name), e(state), "<code>%s</code>" % e(p["cmd"]) if p else ""))
    body = """<p>Queue a long job (a build, a big download, a local-AI run) in one of four job slots. When it finishes, the
daemon tells you, and you <b>collect</b> it for %s XP: <b>%d + %d per minute</b> it ran, up to %s. A job that fails
(non-zero exit) pays %d%%.</p>
<pre><code>omalvl run make -j2                   # run and watch a command
omalvl run --pid 12345 "big download"  # watch something already running
omalvl jobs                           # see the four slots
omalvl collect                        # collect everything that's done
omalvl drop alpha                     # free a slot without collecting (the program keeps running)</code></pre>
<h2>Your slots</h2><table class="wikitable"><tr><th>Slot</th><th>State</th><th>Job</th></tr>%s</table>
<p>Output of queued commands is kept in <code>~/.local/state/omalvl/jobs/</code>.</p>""" % (
        slink("workload"), C.HARVEST_BASE, C.HARVEST_PER_MIN, "{:,}".format(C.HARVEST_MAX), int(C.DEAD_SHARE * 100), "".join(rows))
    write("job-runs.html", "Job slots", body, [("Main page", "index.html"), ("Skills", "skills.html")], "jobs run collect slot")


def page_streak(data):
    st = data.get("streak") or {}
    tokens = "".join("<li>%d days: an XP token worth %s XP</li>" % (d, "{:,}".format(x)) for d, x in sorted(C.STREAK_TOKENS.items()))
    pool = [k for k in S.SKILL_KEYS if k not in S.PASSIVE]
    body = """<p>The first active minute of each day continues your streak (or starts a new one if you missed a day) and pays
<b>%d XP × streak</b> (counting up to %d days) to <b>today's skill</b>, which rotates daily through the %d non-passive skills.</p>
<ul>%s</ul><p><b>You:</b> %d day(s), best %d. Check with <code>omalvl streak</code>.</p>""" % (
        C.STREAK_XP, C.STREAK_CAP_DAYS, len(pool), tokens, st.get("count", 0), st.get("best", 0))
    write("daily-streak.html", "Daily streak", body, [("Main page", "index.html")], "streak daily bonus")


def page_capes(data):
    marks = data.get("badges") or {}
    row = " ".join(icon("badge/%s.png" % k, 48) if k in marks else '<span style="opacity:.2">%s</span>' % icon("badge/%s.png" % k, 48)
                   for k in S.SKILL_KEYS)
    body = """<p>Reaching <b>level 100</b> in a skill earns its <b>mastery mark</b>, in the skill's colour. Completing every
quest earns the <b>Questmaster</b> mark, and every skill at 100 earns <b>Omarchist</b>.</p>
<p>%s</p><p><b>You:</b> %d / %d marks.</p>
<h2>Total level milestones</h2><p>Every 100 total levels (up to %d) is announced and logged: %s.</p>""" % (
        row, len([c for c in marks if c in S.SKILL_BY_KEY]), len(S.SKILLS), S.MAX_TOTAL,
        ", ".join(str(m) for m in C.TOTAL_MILESTONES[:6]) + " … " + str(C.TOTAL_MILESTONES[-1]))
    write("marks.html", "Mastery marks", body, [("Main page", "index.html"), ("Rewards", "collection-log.html")], "mastery mark 100 milestone")


def page_lamps():
    diaries = "".join("<li>%s tier: %s XP</li>" % (e(t), "{:,}".format(l)) for _, t, _, l in C.DIARIES)
    body = """<p>A token gives XP to a skill of your choice: open the skill's guide in the panel and redeem it there, or run
<code>omalvl token &lt;skill&gt;</code>. <code>omalvl token</code> lists the ones you have.</p>
<ul><li><b>Courier token</b> (the courier <a href="random-events.html">random event</a>, some signal caches): 10 × the skill's level.</li>
<li><b>XP tokens</b>: fixed XP, from the <a href="diary.html">journal</a><ul>%s</ul>
from <a href="seasons.html">Update Day</a> (%s XP) and from long <a href="daily-streak.html">streaks</a>.</li></ul>""" % (
        diaries, "{:,}".format(C.UPDATE_DAY_TOKEN))
    write("tokens.html", "Tokens", body, [("Main page", "index.html"), ("Rewards", "collection-log.html")], "courier XP token")


def page_collection(data):
    col = data["collection"]
    companions = " ".join(icon("companion/%s.png" % p[0], 36) if p[0] in data["companions"] else
                          '<span style="opacity:.25">%s</span>' % icon("companion/%s.png" % p[0], 36) for p in C.COMPANIONS)
    body = """<p>Everything you've collected. Open it in the Collection tab or with <code>omalvl collection</code>.</p>
<h2>Yours</h2><p>%s</p><ul>
<li>Companions: %d / %d (<a href="companions.html">hatch levels</a>)</li>
<li>Mastery marks: %d / %d · theme stamps: %d · dotfile relics: %d / %d</li>
<li>Signal caches: easy %d · medium %d · hard %d</li>
<li>Random events: %s</li><li>Overclocks: %d · Update Days: %d · Sysop challenges: %d</li></ul>""" % (
        companions, len(data["companions"]), len(C.COMPANIONS),
        len([k for k in data["badges"] if k in S.SKILL_BY_KEY]), len(S.SKILLS), len(data["stamps"]), len(data["relics"]), len(C.RELICS),
        col.get("cache:easy", 0), col.get("cache:medium", 0), col.get("cache:hard", 0),
        " · ".join("%s %d" % (e(ev[1]), col.get("random:" + ev[0], 0)) for ev in C.RANDOM_EVENTS),
        col.get("surge", 0), col.get("update_day", 0), col.get("sysop", 0))
    write("collection-log.html", "Collection", body, [("Main page", "index.html")], "collection companions caches marks")


def page_commands():
    doc = S.__doc__.split("Commands:", 1)[1].strip() if "Commands:" in S.__doc__ else ""
    rows = []
    for line in doc.splitlines():
        if line.startswith("  ") and len(line.strip()) > 0:
            cmd, _, desc = line.strip().partition("  ")
            rows.append("<tr><td><code>omalvl %s</code></td><td>%s</td></tr>" % (e(cmd.strip()), e(desc.strip())))
    body = """<p><code>omalvl</code> is the command-line side of the game.</p>
<table class="wikitable"><tr><th>Command</th><th>What it does</th></tr>%s</table>""" % "".join(rows)
    write("commands.html", "Commands", body, [("Main page", "index.html"), ("Guides", "mechanics.html")], "cli commands")


def page_mechanics():
    body = """<h2>Ticks and activity</h2><p>The daemon samples every <b>%d seconds</b>. A tick counts as <i>at the computer</i> when the
keyboard/touchpad raised at least %d interrupts or the pointer moved. Continuous skills (Focus, Workload, and the data part of
Downloads) are only paid on those ticks, and each is capped at <b>%d XP per tick</b>.</p>
<h2>Boosts</h2><p>Measured XP (not tokens, caches or awards) can be boosted by your theme's <a href="seasons.html">season</a>
(+%d%% to one area), <a href="seasons.html">Update Day</a> (+%d%% to System) and an <a href="overclocks.html">overclock</a>
(double one skill).</p>
<h2>Saving</h2><p>Routine XP is saved at most every %d seconds; anything notable (an action, a quest, a level) is saved at once.
Every save is atomic, a daily copy is kept for two weeks, and a save that would lose more than a tenth of your XP is refused.</p>
<h2>Keybind detection</h2><p>Hyprland's event socket reports window and workspace events, and a 6 Hz scan of new processes
catches the short-lived <code>omarchy-*</code> commands that keybinds run.</p>
<h2 id="privacy">Privacy</h2><p>Everything stays on this machine. The daemon reads only local sources: <code>/proc</code>
and <code>/sys</code> (CPU, disk, network counters, processes), Hyprland's socket, your shell history file, file times in
a few config folders, git repos in your configured folders, the pacman log, the Chromium history count (opt-in) and
<code>~/Downloads</code> size. Shell history contributes command counts plus allowlisted names and fixed safe pairs; arguments are discarded.
It makes no network calls. State: <code>~/.local/state/omalvl/state.json</code>.</p>""" % (
        S.TICK, S.ACTIVE_IRQS, S.R["tick_cap"], int(C.SEASON_BONUS * 100), int(C.UPDATE_DAY_BONUS * 100), S.FLUSH)
    write("mechanics.html", "Mechanics", body, [("Main page", "index.html")], "tick activity privacy saving boosts")


def page_interface():
    body = """<p>The bar shows the OmaLvL icon and your total level. An accent pip means a token, signal or finished job is
waiting; a yellow one means an overclock is on. Hover for a summary; click to open the panel.</p>
<table class="wikitable"><tr><th>Tab</th><th>Contents</th></tr>
<tr><td>%s Skills</td><td>Six area cards, the Rice hexagon, hover detail and each skill's guide (click a skill)</td></tr>
<tr><td>%s Rice</td><td>Area levels, season and stamps, the keybind tree, dotfile relics and skins</td></tr>
<tr><td>%s Quests</td><td>Quest list with a quest helper (click a quest)</td></tr>
<tr><td>%s Tasks</td><td>Contract, signal, tokens, the Sysop (+ local-AI explanation), bonuses, job slots</td></tr>
<tr><td>%s Journal</td><td>Boot, Login, Root and Kernel tiers</td></tr>
<tr><td>%s Collection</td><td>Companions, mastery marks and finds</td></tr>
<tr><td>%s Log</td><td>Fair play, and what earned XP, and why</td></tr></table>
<p>Scriptable: <code>omarchy-shell omalvl.ui tab quests</code>, <code>omarchy-shell omalvl.ui quest navigation</code>.</p>""" % tuple(
        icon(i, 20) for i in ("total", "rice", "quests", "tasks", "diary", "collection", "log"))
    write("interface.html", "The bar widget", body, [("Main page", "index.html"), ("Guides", "mechanics.html")], "panel tabs bar widget")


def page_agents():
    body = """<h2>Agent awards</h2><p>AI agents you work with (Claude Code, OpenCode, Codex …) award XP for finished, verified work
with <code>omalvl agent &lt;skill&gt; &lt;tier&gt; "&lt;what was done&gt;"</code>. It is sized by how hard the work was; each
tier is about 3× the one before. <a href="fair-play.html">Fair play</a> voids awards that recent activity doesn't back up.</p>
<table class="wikitable"><tr><th>Tier</th><th>XP</th><th>Kind of work</th></tr>%s</table>
<p>A plain number also works, for anything that doesn't fit a tier.</p>
<h2>Agents and Models</h2><p>{skill:agents} grows from the CPU time of agent CLIs (%s); {skill:models} from local
model runtimes (%s). Node/Python agents are found by script name. Running a local model completes the
<a href="quest-off_grid.html">Off the Grid</a> quest.</p>""" % (
        "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (t, "{:,}".format(xp), d) for t, xp, d in (
            ("trivial", S.AGENT_TIERS["trivial"], "a one-liner, a lookup, one config value"),
            ("easy", S.AGENT_TIERS["easy"], "a small fix or tweak, minutes of work"),
            ("medium", S.AGENT_TIERS["medium"], "a real bug fix or small feature, about an hour for a person"),
            ("hard", S.AGENT_TIERS["hard"], "multi-file feature, tricky root cause, several hours"),
            ("expert", S.AGENT_TIERS["expert"], "a new subsystem or a deep investigation, a day or more"),
            ("master", S.AGENT_TIERS["master"], "a whole project end to end, days to weeks"))),
        ", ".join(sorted(S.AGENT_NAMES - S.LOCAL_RUNTIMES)),
        ", ".join(sorted(S.LOCAL_RUNTIMES)) + ", llama.cpp (llama-*), vLLM")
    body = body.replace("{skill:agents}", slink("agents")).replace("{skill:models}", slink("models"))
    write("agents.html", "AI agents & local models", body, [("Main page", "index.html"), ("Guides", "mechanics.html")], "agent ai local model llama")


def page_fair():
    import anticheat as A
    body = """<p class="lead">There is no cap on how fast you can level by using the machine. What fair play stops is XP
that real use doesn't back up.</p><ul>
<li>Awards from agents and by hand share a budget of <b>%s XP</b> plus <b>%d per worked minute</b> in the last 24 hours, and
any single award is capped at %s XP. A worked minute is one where you were at the keyboard or an AI agent or local model was
measurably working for you (its CPU time), so work you wait on counts. Each hour counts at most 60 worked minutes.</li>
<li>Awards to more than %d different skills within %d minutes are void (sweeping every skill is the botting pattern).</li>
<li>The same reason again within 7 days is void.</li>
<li>More than %d hours of keyboard activity in 24 holds measured XP (that's a bot, or a stuck sensor). Agents working
overnight don't count towards this.</li>
<li>Every XP change is tallied by source; if a skill's XP stops matching its tally (a hand edit), the account shows as
<b>unverified</b>.</li></ul>
<p>So "max all my stats" to an agent is void, while a real build, a real commit or a real fix is paid. Check with
<code>omalvl fair</code>.</p>
<h2>Local history</h2><p>The public OmaLvL release has no admin grant command. Existing owner grants from the maintainer's
local-only override remain recorded with their reason and shown on that local fair-play card.</p>""" % (
        "{:,}".format(A.BASE), A.PER_ACTIVE_MIN, "{:,}".format(A.MAX_SINGLE), A.BURST_SKILLS, A.BURST_WINDOW // 60, A.ACTIVE_DAY_MAX // 60)
    write("fair-play.html", "Fair play", body, [("Main page", "index.html"), ("Guides", "mechanics.html")], "fair play cheat bot void")


def page_hiscores(data, snap):
    rows = "".join("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>" % (
        slink(s["key"]), e(S.AREA_BY_ID[s["area"]][1]), s["level"], "{:,}".format(s["xp"]), "{:,}".format(s["rate"]) + "/h" if s["rate"] else "")
        for s in snap["skills"])
    body = """<p>Your account, as of this build. Rice rating <b>%d</b> (%s) · total level <b>%d</b> · total XP <b>%s</b> ·
renown <b>%d</b> · contract points %d · companions %d/%d.</p>
<table class="wikitable"><tr><th>Skill</th><th>Area</th><th>Level</th><th>XP</th><th>Rate</th></tr>%s
<tr><th>Overall</th><th></th><th>%d</th><th>%s</th><th></th></tr></table>""" % (
        snap["rice"]["rating"], e(snap["rice"]["rank"]), snap["total"], "{:,}".format(sum(s["xp"] for s in snap["skills"])),
        snap["questPoints"], snap["contractInfo"]["points"], len(data["companions"]), len(C.COMPANIONS), rows, snap["total"],
        "{:,}".format(sum(s["xp"] for s in snap["skills"])))
    write("stats.html", "Your stats", body, [("Main page", "index.html")], "stats account")


def page_updates():
    rows = "".join("<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>" % (e(d), e(h), e(s)) for d, h, s in git_log())
    body = """<p>Updates, from OmaLvL's git history.</p>
<table class="wikitable"><tr><th>Date</th><th>Commit</th><th>Update</th></tr>%s</table>""" % (rows or "<tr><td colspan=3>No history found.</td></tr>")
    write("updates.html", "Updates", body, [("Main page", "index.html")], "updates changelog news")


# --------------------------------------------------------------- build
def theme_vars():
    pal = S.theme_palette()
    d = {"bg": pal.get("background", "#1a1b26"), "fg": pal.get("foreground", "#c0caf5"), "accent": pal.get("accent", "#7aa2f7"),
         "well": pal.get("dark_background", "#16161e"), "raised": pal.get("lighter_background", "#24283b")}
    for k in ("red", "orange", "yellow", "green", "cyan", "blue", "magenta", "brown"):
        d[k] = pal.get(k, d["accent"])
    return "".join("--%s:%s;" % kv for kv in d.items())


def copy_assets():
    _private_write(os.path.join(OUT, "favicon.svg"), I.svg("total", 4, "#e0e0e0", "#7aa2f7", "#e0af68"))


def build():
    _private_dirs()
    copy_assets()
    data = S.load()
    snap = S.snapshot(data)
    PAGES.clear()
    page_index(data, snap)
    page_skills(snap)
    for k in S.SKILL_KEYS:
        page_skill(k, snap)
    page_experience()
    page_quests(data)
    for q in C.QUESTS:
        page_quest(q, data)
    page_contracts(snap)
    page_clues()
    page_diary(data)
    page_random_events()
    page_pets(data)
    page_stars()
    page_rice(snap)
    page_seasons(snap)
    page_tree(snap)
    page_relics(data)
    page_fair()
    page_wom(snap)
    page_lamps()
    page_farming_runs(snap)
    page_streak(data)
    page_capes(data)
    page_collection(data)
    page_commands()
    page_mechanics()
    page_interface()
    page_agents()
    page_hiscores(data, snap)
    page_updates()
    page_glossary()
    page_learn(data)
    for t in G.T:
        page_term(t, data)
    _private_write(os.path.join(OUT, "wiki.css"), CSS.replace("__THEME__", theme_vars()))
    _private_write(os.path.join(OUT, "search.js"), JS.replace("__INDEX__", json.dumps(PAGES)))
    return os.path.join(OUT, "index.html"), len(PAGES)


def main():
    path, n = build()
    print("OmaLvL Wiki: %d pages -> %s" % (n, path))
    if "--open" in sys.argv:
        subprocess.Popen([S.tool("xdg-open"), path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
