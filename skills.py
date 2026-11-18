#!/usr/bin/env python3
"""OmaLvL: level up by using your Omarchy machine.

17 skills in six areas (Terminal, Desktop, Code, System, Web, AI), levels 1-100 on OmaLvL's own
curve, a Rice rating built from the six areas, quests that teach Omarchy / Linux / AI by doing them,
daily contracts, signals, theme seasons and stamps, Update Day, dotfile relics, the keybind tree,
panel skins and a pixel wallpaper of your stats. The daemon watches cheap signals (/proc, /sys,
Hyprland's event socket, shell history, git, pacman) and pays the continuous skills only while
you are actually at the computer. Content lives in content.py.

State: ~/.local/state/omalvl/state.json  (weekly reports: weekly/)   Config: ~/.config/omalvl/config.json

Commands:
  list | stats              every skill by area: level, xp, xp/hr  (the default)
  rice                      your Rice rating, rank, area levels and what raises it next
  quests                    the quest log;  quest <id>  completes one by hand
  contract [new|skip]       your contract from the Dispatcher (one new task a day is automatic)
  signal                    your current signal
  token [<skill>]           list tokens / redeem the oldest one on a skill
  journal                   the Omarchy journal (Boot, Login, Root, Kernel)
  season                    this theme's season, your theme stamps and Update Day
  relics                    dotfile relics: commit your config to unearth them
  tree                      the keybind tree: every Omarchy action you use, ranked
  skin [<name>]             list panel skins / wear one (unlocked by Rice rating)
  wallpaper [--out <png>]   draw your stats as a pixel wallpaper in your theme's colours
  log                       what earned XP recently, and why
  week                      this week's report
  backup                    save a copy now and list backups (daily + off-machine copies are automatic)
  fair                      fair play: verified books, voided awards, award budget
  restore <file>|latest     put a backup back (the current state is saved first)
  sysop | challenge         the Sysop's daily challenge;  sysop explain  asks your local AI about it
  overclock                 is an overclock on (double XP on one skill)?
  collection | companions   companions, mastery marks and rare finds
  wiki [--no-open]          build the offline OmaLvL wiki from the game data and open it
  guide <skill> [--json]    the skill guide: XP, pace, how to train it, what each level unlocks
  run <command...>          queue a long job in a job slot (or: run --pid N)
  collect [slot] | jobs     collect finished jobs for Workload XP / list the four slots
  streak                    your daily streak (the first active minute of each day continues it)
  add <skill> <xp>          grant XP by hand (fair play applies)
  admin grant <skill> <xp|tier> <why>  the owner's override: no fair-play checks, logged and shown openly
  agent <skill> <tier> <why>  an AI agent awards work XP, sized by difficulty:
                            trivial 100, easy 300, medium 1k, hard 3k, expert 10k, master 30k (or a number)
  task <name> [xp]          a named daily task (commit, write, tidy, ...)
  get <skill> | total | state | reset [skill]
  daemon                    the activity sampler (the bar widget launches it)
"""
import collections
import datetime
import fcntl
import glob
import json
import os
import random
import re
import urllib.request as urllib_request
import shutil
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import anticheat  # noqa: E402
from content import (QUESTS, CONTRACT_TASKS, CONTRACT_PER_DAY, SIGNAL_STEPS, SIGNAL_TIERS,  # noqa: E402
                     DIARIES, RANDOM_EVENTS, RANDOM_COOLDOWN, RANDOM_CHANCE,
                     COMPANIONS, SURGE_SKILLS, SURGE_MINUTES, SURGE_COOLDOWN, SURGE_CHANCE,
                     SEASON_BONUS, UPDATE_DAY_BONUS, UPDATE_DAY_MINUTES, UPDATE_DAY_TOKEN,
                     STAMP_MINUTES, STAMP_XP, RELICS, RELIC_XP, TREE_BRANCHES, TREE_RANKS,
                     RICE_RANKS, SKINS, SYSOP_CHALLENGES,
                     JOB_SLOTS, HARVEST_BASE, HARVEST_PER_MIN, HARVEST_MAX, DEAD_SHARE,
                     STREAK_XP, STREAK_CAP_DAYS, STREAK_TOKENS, TOTAL_MILESTONES,
                     QUEST_REQS, CONTRACT_REQS, SYSOP_REQS)

STATE_HOME = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
STATE = os.path.join(STATE_HOME, "omalvl", "state.json")
CONFIG = os.path.join(CONFIG_HOME, "omalvl", "config.json")
# Where commits are counted: every git repo directly inside these folders (config "repos").
DEFAULT_REPO_GLOBS = ["~/Work/*", "~/Projects/*", "~/projects/*", "~/src/*", "~/code/*", "~/dev/*", "~/git/*"]


def tool(name):
    """A helper program by absolute path: /usr/bin first, then the user's PATH once (cached)."""
    if name not in _TOOLS:
        p = "/usr/bin/" + name
        resolved = shutil.which(name)
        _TOOLS[name] = p if os.access(p, os.X_OK) else (os.path.abspath(resolved) if resolved else p)
    return _TOOLS[name]


_TOOLS = {}


def config():
    """~/.config/omalvl/config.json, read with a size cap; every key is optional."""
    try:
        with open(CONFIG, "rb") as f:
            raw = f.read(65537)
        if len(raw) > 65536:
            return {}
        c = json.loads(raw.decode("utf-8", "replace"))
        return c if isinstance(c, dict) else {}
    except (OSError, ValueError):
        return {}
LOCK = STATE + ".lock"
HOME = os.path.expanduser("~")
RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"

# key, name, abbr, blurb (how it levels), tint: a colour name from the Omarchy theme's
# colors.toml (red, orange, yellow, green, cyan, blue, magenta, brown), so every theme recolours it.
# Listed area by area; AREAS below groups them.
SKILLS = [
    ("shell",     "Shell",     "SH",  "shell commands + Omarchy keybind actions", "magenta"),
    ("scripting", "Scripting", "SCR", "scripts invoked", "magenta"),
    ("searching", "Searching", "SRC", "searches run", "yellow"),
    ("tiling",    "Tiling",    "TIL", "workspace + window moves, windows closed", "blue"),
    ("theming",   "Theming",   "THM", "themes, backgrounds and config edits", "cyan"),
    ("focus",     "Focus",     "FOC", "time at the computer (and with a game on)", "blue"),
    ("commits",   "Commits",   "GIT", "git commits in your repos", "orange"),
    ("editing",   "Editing",   "EDT", "files added, changed and removed in commits", "yellow"),
    ("building",  "Building",  "BLD", "builds and compiles (make, cargo, npm, gcc ...)", "orange"),
    ("packages",  "Packages",  "PKG", "packages installed and upgraded", "brown"),
    ("cleanup",   "Cleanup",   "CLN", "clean-ups: rm, trash, cache and log purges", "red"),
    ("workload",  "Workload",  "WRK", "CPU worked and disk written while you're on", "red"),
    ("browsing",  "Browsing",  "WEB", "web pages visited", "green"),
    ("downloads", "Downloads", "DL",  "files collected and data received", "green"),
    ("remote",    "Remote",    "RMT", "git push/pull/clone, ssh, rsync", "cyan"),
    ("agents",    "Agents",    "AI",  "AI agent CLIs working (their CPU time)", "green"),
    ("models",    "Models",    "LLM", "local models running on this machine (their CPU time)", "magenta"),
]
SKILL_KEYS = [s[0] for s in SKILLS]
SKILL_BY_KEY = {s[0]: s for s in SKILLS}
# The six areas: id, name, skills, tint. The Rice rating is built from them.
AREAS = [
    ("terminal", "Terminal", ("shell", "scripting", "searching"), "magenta"),
    ("desktop", "Desktop", ("tiling", "theming", "focus"), "blue"),
    ("code", "Code", ("commits", "editing", "building"), "orange"),
    ("system", "System", ("packages", "cleanup", "workload"), "red"),
    ("web", "Web", ("browsing", "downloads", "remote"), "green"),
    ("ai", "AI", ("agents", "models"), "cyan"),
]
AREA_BY_ID = {a[0]: a for a in AREAS}
AREA_OF = {k: a[0] for a in AREAS for k in a[2]}
# Continuous skills: paid every tick while you're here, so XP drops skip them.
PASSIVE = {"focus", "workload", "agents", "models"}

TASKS = {
    "commit": ("commits", 500), "write": ("editing", 150), "download": ("downloads", 120),
    "tidy": ("editing", 120), "search": ("searching", 60), "script": ("scripting", 150),
    "install": ("packages", 400), "update": ("packages", 300), "theme": ("theming", 150),
    "browse": ("browsing", 90), "game": ("focus", 300), "build": ("building", 150),
    "clean": ("cleanup", 120), "agent": ("agents", 150), "push": ("remote", 150),
}
TASK_ALIASES = {
    "pkg": "install", "upgrade": "update", "grep": "search", "run": "script", "play": "game",
    "surf": "browse", "compile": "build", "delete": "clean", "purge": "clean", "ssh": "push",
    "rice": "theme",
}
# Agent awards are uncapped work XP, sized by how hard the finished work was. Tiers rise ~3x and are
# anchored to RATES' pacing (a commit is 500; a regularly used skill earns ~3,000 XP per active hour),
# so a tier is roughly "what that much skilled human work would be worth".
AGENT_TIERS = {
    "trivial": 100,      # a one-liner, a lookup, one config value
    "easy": 300,         # a small fix or tweak, minutes of work
    "medium": 1000,      # a real bug fix or small feature, about an hour for a person
    "hard": 3000,        # multi-file feature, tricky root cause, several hours
    "expert": 10000,     # a new subsystem or a deep investigation, a day or more
    "master": 30000,     # a whole project end to end (design, build, tests, docs), days to weeks
}

# Every activity rate in one place (the daemon and the wiki both read it). Paced so a skill you use
# regularly reaches 100 in roughly 3,000-5,000 active hours (two to three years of normal use).
# "tick" = one 30-second sample while you're active.
RATES = {
    "focus_tick": 25,            # being at the computer
    "focus_game_min": 30,        # + per minute with a game focused
    "workload_cpu_s": 3,         # per CPU-second used
    "workload_mb": 8,            # per MB written to disk
    "downloads_net_mb": 12,      # per MB received
    "downloads_mb": 15,          # per MB collected in ~/Downloads
    "shell_kb": 15,              # per Omarchy keybind action
    "shell_cmd": 20,             # per ordinary shell command
    "tiling_ws": 4,              # per workspace switch
    "tiling_focus": 2,           # per window focus change
    "tiling_close": 20,          # per window closed
    "contract_task_mult": 4,     # contract XP = size x unit x this
    "browsing_visit": 40,        # per page visited
    "searching_search": 40,      # per search command
    "scripting_script": 60,      # per script run
    "building_build": 80,        # per build command
    "building_tick": 30,         # per tick a compiler is running
    "cleanup_burn": 50,          # per clean-up command
    "remote_trip": 90,           # per remote trip (push/pull/ssh/rsync)
    "agents_cpu_s": 6,           # per CPU-second of AI agent CLIs
    "models_cpu_s": 4,           # per CPU-second of local model runtimes
    "theming_theme": 150,        # per theme switch
    "theming_bg": 40,            # per background change
    "theming_edit": 30,          # per config file saved under ~/.config (hypr, omarchy, terminals ...)
    "packages_pkg": 250, "packages_max": 5000,     # per package installed (cap per update)
    "packages_upg": 60, "packages_upg_max": 6000,  # per package upgraded
    "commits_commit": 500,       # per git commit
    "editing_added": 40,         # per file added in a commit
    "editing_file": 25,          # per file changed
    "editing_removed": 30,       # per file deleted
    "file_max": 600,             # cap per commit
    "tick_cap": 120,             # cap per tick for each continuous skill
    "cmd_tick_cap": 400,         # cap per tick for each shell-command skill (anti-spam)
    "repeat_window": 300,        # the same command again within 5 min earns nothing
}
R = RATES

QUEST_BY_ID = {q[0]: q for q in QUESTS}
MAX_QP = sum(q[2] for q in QUESTS)
CONTRACT_BY_ID = {t[0]: t for t in CONTRACT_TASKS}
SIGNAL_BY_ID = {c[0]: c for c in SIGNAL_STEPS}
COMPANION_BY_ID = {p[0]: p for p in COMPANIONS}
SYSOP_BY_ID = {w[0]: w for w in SYSOP_CHALLENGES}


# --------------------------------------------------------------- XP curve
# OmaLvL's own curve: XP to reach level L is 100*(L-1) + 9,990,100 * ((L-1)/99) ** 3.5, so level 2 is
# 101 XP, level 10 about 3,200, level 50 about 851,000 and level 100 exactly 10,000,000. Early levels
# come fast; the last fifth of the climb is half the XP. XP keeps counting after 100.
MAX_LEVEL = 100


def _build_curve():
    table = [0, 0]
    for lvl in range(2, MAX_LEVEL + 1):
        n = lvl - 1
        table.append(int(round(100 * n + 9_990_100 * (n / 99.0) ** 3.5)))
    return table


LEVEL_XP = _build_curve()
MAX_XP = LEVEL_XP[MAX_LEVEL]          # 10,000,000
XP_CAP = 100_000_000                  # per-skill ceiling, far past mastery
MAX_TOTAL = MAX_LEVEL * len(SKILLS)   # 1700
HALFWAY = next(l for l in range(1, MAX_LEVEL + 1) if LEVEL_XP[l] >= MAX_XP // 2)


def level_for_xp(xp, cap=MAX_LEVEL):
    """Level 1-100."""
    if xp >= LEVEL_XP[cap]:
        return cap
    lo, hi = 1, cap
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if LEVEL_XP[mid] <= xp:
            lo = mid
        else:
            hi = mid - 1
    return lo


def xp_to_next(xp):
    lvl = level_for_xp(xp)
    if lvl >= MAX_LEVEL:
        return 0, 0
    return LEVEL_XP[lvl + 1] - xp, LEVEL_XP[lvl + 1] - LEVEL_XP[lvl]


def today(t=None):
    return time.strftime("%Y-%m-%d", time.localtime(t))


# --------------------------------------------------------------- state io
STATE_KEYS = {  # key: default factory
    "xp": lambda: {k: 0 for k in SKILL_KEYS}, "quests": dict, "log": list, "stats": dict,
    "contract": lambda: {"task": None, "streak": 0, "points": 0, "completed": 0,
                       "day": "", "taken": 0},
    "signal": lambda: None, "signals": dict, "tokens": list, "diary": dict, "days": dict,
    "rates": dict, "drop": lambda: None, "meta": lambda: {"created": int(time.time()), "version": 3},
    # v6: surge, companions, collection log counters, Sysop's daily challenge
    "surge": lambda: None, "companions": dict, "collection": dict, "sysop": lambda: None,
    # v8: job slots, daily streak, mastery marks (key "badges"), total-level milestones
    "jobs": list, "streak": lambda: {"day": "", "count": 0, "best": 0}, "badges": dict,
    # v10 (OmaLvL): theme stamps, relics, keybind tree ranks, Update Day, chosen skin
    "stamps": dict, "relics": dict, "tree": dict, "updateDay": lambda: None, "skin": lambda: "plain",
    # fair play (anticheat.py): activity per hour, unmeasured awards, XP tallied by source
    "fair": lambda: anticheat.blank(),
}


def _blank():
    d = {k: f() for k, f in STATE_KEYS.items()}
    d["meta"]["version"] = 10
    anticheat.set_baseline(d["fair"], d["xp"])
    return d


BACKUP = STATE + ".bak"
BACKUP_DIR = os.path.join(os.path.dirname(STATE), "backups")
BACKUP_DAYS = 14
# Off-machine copy: a folder synced to another machine (Syncthing, Dropbox, a mounted
# drive...): config "offsite", or OMALVL_OFFSITE. Off by default.
OFFSITE = os.path.expanduser(os.environ.get("OMALVL_OFFSITE", str(config().get("offsite") or "")))
OFFSITE_DAYS = 60
DROP_GUARD = 0.9   # a save that loses >10% of total xp is refused unless allow_drop


def _offsite_dir():
    # off unless configured; the folder's parent must exist (a synced or mounted folder)
    if not OFFSITE or not os.path.isdir(os.path.dirname(OFFSITE.rstrip("/")) or "/"):
        return None
    return os.path.join(OFFSITE, socket.gethostname())


def _total_xp(data):
    return sum(v for v in (data.get("xp") or {}).values() if isinstance(v, (int, float)))


def _read_state(path):
    data = json.loads(read_capped(path, 4 * 1024 * 1024))
    if not isinstance(data, dict) or not isinstance(data.get("xp"), dict):
        raise ValueError("not a skills state")
    return data


def _recover():
    """The main file is missing or corrupt (e.g. a hard power-off mid-write).
    Never silently start from zero: try the .bak, then the newest daily copy.
    A corrupt file is kept aside so nothing is lost."""
    if os.path.exists(STATE):
        try:
            os.replace(STATE, "%s.corrupt-%d" % (STATE, int(time.time())))
        except OSError:
            pass
    daily = sorted(glob.glob(os.path.join(BACKUP_DIR, "skills-2*.json")), reverse=True)
    off = _offsite_dir()
    if off:
        daily += sorted(glob.glob(os.path.join(off, "skills-2*.json")), reverse=True)
    for path in [BACKUP] + daily:
        try:
            data = _read_state(path)
        except (OSError, ValueError):
            continue
        sys.stderr.write("omalvl: state restored from %s\n" % path)
        return data
    return None


def load():
    try:
        data = _read_state(STATE)
    except (OSError, ValueError):
        data = _recover()
        if data is None:
            return _blank()
    if not isinstance(data.get("fair"), dict):
        data["fair"] = anticheat.blank()            # an older save: books start below, at its own XP
    blank = _blank()
    for k, v in blank.items():
        if k not in data or (v is not None and not isinstance(data[k], type(v))):
            data[k] = v
    for k in SKILL_KEYS:
        data["xp"].setdefault(k, 0)
    for k in [k for k in data["xp"] if k not in SKILL_BY_KEY]:
        del data["xp"][k]
    for k, v in blank["contract"].items():
        data["contract"].setdefault(k, v)
    for k, v in anticheat.blank().items():
        data["fair"].setdefault(k, v)
    if data["fair"]["baseline"] is None:          # an account from before fair play: start the books now
        anticheat.set_baseline(data["fair"], data["xp"])
    return data


def save(data, allow_drop=False):
    # Persist the enriched view (skills, questLog, diary, ...) alongside the raw
    # state so the shell widget renders straight from the file.
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    payload = {k: data[k] for k in STATE_KEYS}
    payload.update(snapshot(data))
    text = json.dumps(payload)
    if not allow_drop:
        try:
            on_disk = _total_xp(_read_state(STATE))
        except (OSError, ValueError):
            on_disk = 0
        if on_disk and _total_xp(payload) < on_disk * DROP_GUARD:
            # Something is about to wipe progress (a bad load, a bug): keep the file.
            _atomic_write(STATE + ".rejected", text)
            sys.stderr.write("omalvl: refused a save that drops total xp %d -> %d "
                             "(kept the old file; new data in %s.rejected)\n"
                             % (on_disk, _total_xp(payload), STATE))
            return
    # fsync before rename: without it a freeze/power-off can leave an empty file
    # (this wiped the account on 2026-11-17). The .bak is written the same way.
    for path in (BACKUP, STATE):
        _atomic_write(path, text)
    day = time.strftime("%Y-%m-%d")
    daily = os.path.join(BACKUP_DIR, "skills-%s.json" % day)
    if not os.path.exists(daily):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        _atomic_write(daily, text)
        _prune(BACKUP_DIR, BACKUP_DAYS)
    off = _offsite_dir()
    if off and not os.path.exists(os.path.join(off, "skills-%s.json" % day)):
        try:
            os.makedirs(off, exist_ok=True)
            _atomic_write(os.path.join(off, "skills-%s.json" % day), text)
            _prune(off, OFFSITE_DAYS)
        except OSError:
            pass


def _prune(folder, keep):
    for old in sorted(glob.glob(os.path.join(folder, "skills-2*.json")))[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass


def snapshot_file(tag):
    """Copy the current state to backups/skills-<tag>-<time>.json (kept, never pruned)."""
    if not os.path.exists(STATE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = os.path.join(BACKUP_DIR, "skills-%s-%s.json" % (tag, time.strftime("%Y%m%d-%H%M%S")))
    with open(STATE) as f:
        _atomic_write(out, f.read())
    return out


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


class _Lock:
    def __enter__(self):
        os.makedirs(os.path.dirname(LOCK), exist_ok=True)
        self.f = open(LOCK, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# --------------------------------------------------------------- conditions
def stat_sum(data, prefix):
    return sum(v for k, v in data["stats"].items() if k.startswith(prefix))


def stat_distinct(data, prefix):
    return sum(1 for k, v in data["stats"].items() if k.startswith(prefix) and v > 0)


def total_level(data):
    return sum(level_for_xp(data["xp"][k]) for k in SKILL_KEYS)


def cond_progress(data, cond):
    """(have, need) for a content.py condition."""
    kind = cond[0]
    if kind == "sum":
        return stat_sum(data, cond[1]), cond[2]
    if kind == "distinct":
        return stat_distinct(data, cond[1]), cond[2]
    if kind == "quest":
        return int(cond[1] in data["quests"]), 1
    if kind == "quests":
        need = len(QUESTS) if cond[1] < 0 else cond[1]
        return len(data["quests"]), need
    if kind == "total":
        return total_level(data), cond[1]
    if kind == "level":
        return max(level_for_xp(v) for v in data["xp"].values()), cond[1]
    if kind == "contract":
        return data["contract"]["completed"], cond[1]
    if kind == "signals":
        return sum(data["signals"].values()), cond[1]
    if kind == "stamps":
        return len(data.get("stamps") or {}), cond[1]
    if kind == "relics":
        return len(data.get("relics") or {}), cond[1]
    if kind == "rice":
        return rice_info(data)["rating"], cond[1]
    if kind == "tree":
        return sum(1 for r in (data.get("tree") or {}).values() if r >= cond[1]), cond[2]
    return 0, 1


def cond_met(data, cond):
    have, need = cond_progress(data, cond)
    return have >= need


def events_match(events, prefix):
    return sum(v for k, v in events.items() if k.startswith(prefix))


# --------------------------------------------------------------- game rules
class Result:
    def __init__(self):
        self.ups, self.quests, self.notes = [], [], []   # notes: (title, message)
        self.milestone = 0
        self.voided = ""
        self.gains = collections.Counter()

    def __iter__(self):            # old (ups, done) unpacking still works
        return iter((self.ups, self.quests))


def _add(data, amounts, res):
    for k, xp in amounts.items():
        xp = int(xp)
        if k not in SKILL_BY_KEY or xp <= 0:
            continue
        before = level_for_xp(data["xp"][k])
        data["xp"][k] = min(XP_CAP, data["xp"][k] + xp)
        res.gains[k] += xp
        after = level_for_xp(data["xp"][k])
        if after > before:
            res.ups.append((k, before, after))


def _complete_quest(data, qid, res):
    if qid in QUEST_BY_ID and qid not in data["quests"]:
        data["quests"][qid] = int(time.time())
        _add(data, QUEST_BY_ID[qid][4], res)
        res.quests.append(qid)


def _new_contract_task(data, rng=random):
    sl = data["contract"]
    if sl["day"] != today():
        sl["day"], sl["taken"] = today(), 0
    if sl["taken"] >= CONTRACT_PER_DAY:
        return None
    lvl = total_level(data)
    tid, text, key, (lo, hi), unit, _ = rng.choice([t for t in CONTRACT_TASKS if CONTRACT_REQS.get(t[0], 0) <= lvl])
    n = rng.randint(lo, hi)
    sl["task"] = {"id": tid, "n": n, "done": 0, "assigned": int(time.time())}
    sl["taken"] += 1
    return text.format(n=n)


def _contract_progress(data, events, res):
    sl = data["contract"]
    task = sl["task"]
    if not task or task.get("done", 0) >= task["n"] or task["id"] not in CONTRACT_BY_ID:
        return
    _, text, key, _, unit, pays = CONTRACT_BY_ID[task["id"]]
    task["done"] = min(task["n"], task["done"] + events_match(events, key))
    if task["done"] >= task["n"]:
        sl["completed"] += 1
        sl["streak"] += 1
        pts = 50 if sl["streak"] % 10 == 0 else 10   # every 10th task in a row pays 5x
        sl["points"] += pts
        _add(data, {pays: task["n"] * unit * R["contract_task_mult"]}, res)
        sl["task"] = None
        bonus = ""
        if not data["signal"] and random.random() < 0.25:
            tier = random.choice(["easy", "easy", "medium"])
            _start_clue(data, tier)
            bonus = " A %s signal came with it." % tier
        res.notes.append(("Contract done",
                          "%d contracts in a row (+%d contract points, +%s %s XP). "
                          "The Dispatcher has more: omalvl contract new.%s"
                          % (sl["streak"], pts, format(task["n"] * unit * R["contract_task_mult"], ","),
                             SKILL_BY_KEY[pays][1], bonus)))


def _start_clue(data, tier):
    steps = random.sample([c[0] for c in SIGNAL_STEPS], SIGNAL_TIERS[tier][0])
    data["signal"] = {"tier": tier, "steps": steps, "at": 0,
                    "base": stat_sum(data, SIGNAL_BY_ID[steps[0]][2][1]), "started": int(time.time())}


def _signal_progress(data, res):
    signal = data["signal"]
    while signal:
        step = SIGNAL_BY_ID.get(signal["steps"][signal["at"]])
        if not step:
            data["signal"] = None
            return
        prefix, need = step[2][1], step[2][2]
        if stat_sum(data, prefix) - signal["base"] < need:
            return
        signal["at"] += 1
        if signal["at"] < len(signal["steps"]):
            nxt = SIGNAL_BY_ID[signal["steps"][signal["at"]]]
            signal["base"] = stat_sum(data, nxt[2][1])
            res.notes.append(("Signal: next step", nxt[1]))
            continue
        tier = signal["tier"]
        _, (lo, hi), lamp_chance = SIGNAL_TIERS[tier]
        total = random.randint(lo, hi)
        picks = random.sample(SKILL_KEYS, 3)
        cuts = sorted(random.sample(range(1, total), 2))
        _add(data, dict(zip(picks, (cuts[0], cuts[1] - cuts[0], total - cuts[1]))), res)
        data["signals"][tier] = data["signals"].get(tier, 0) + 1
        collect(data, "cache:" + tier)
        extra = ""
        if random.random() < lamp_chance:
            data["tokens"].append({"kind": "courier", "from": "%s cache" % tier, "t": int(time.time())})
            extra = " An XP token was in the cache too."
        res.notes.append(("Signal traced",
                          "The %s cache decrypts: %d XP across %s.%s" %
                          (tier, total, ", ".join(SKILL_BY_KEY[k][1] for k in picks), extra)))
        data["signal"] = None
        return


def _diary_progress(data, res):
    for tier, title, tasks, lamp_xp in DIARIES:
        if tier in data["diary"]:
            continue
        if all(cond_met(data, c) for _, c in tasks):
            data["diary"][tier] = int(time.time())
            data["tokens"].append({"kind": "fixed", "xp": lamp_xp, "from": "%s journal tier" % title,
                                  "t": int(time.time())})
            res.notes.append(("Journal: %s tier" % title,
                              "Every %s entry is done. Here is an XP token worth %s XP "
                              "(omalvl token <skill>)." % (title, format(lamp_xp, ","))))


def reqs_met(data, reqs):
    """{skill: level} requirements, quest and content requirements."""
    return all(level_for_xp(data["xp"][k]) >= lvl for k, lvl in (reqs or {}).items())


def reqs_text(reqs):
    return ", ".join("%d %s" % (lvl, SKILL_BY_KEY[k][1]) for k, lvl in (reqs or {}).items())


def _auto_quests(data, res):
    for qid, _, _, _, _, auto, _ in QUESTS:
        if auto and qid not in data["quests"] and reqs_met(data, QUEST_REQS.get(qid)) \
                and all(cond_met(data, c) for c in auto):
            _complete_quest(data, qid, res)


def _log(data, why, res):
    if not res.gains and not res.quests and not res.voided:
        return
    now = int(time.time())
    log = data["log"]
    gained = dict(res.gains)
    if log and not res.quests and not log[-1].get("quests") and log[-1]["why"] == why \
            and now - log[-1]["t"] < 600:
        for k, v in gained.items():
            log[-1]["xp"][k] = log[-1]["xp"].get(k, 0) + v
        log[-1]["t"] = now
        log[-1]["n"] = log[-1].get("n", 1) + 1
    else:
        log.append({"t": now, "why": why, "xp": gained, "quests": list(res.quests)})
    del log[:-40]


def _days(data, res):
    day = data["days"].setdefault(today(), {})
    for k, v in res.gains.items():
        day[k] = day.get(k, 0) + v
    day["_total"] = total_level(data)
    for old in sorted(data["days"])[:-21]:
        del data["days"][old]


def surge_active(data, now=None):
    st = data.get("surge")
    return st if st and st.get("until", 0) > (now or time.time()) else None


def collect(data, key, n=1):
    """Collection counter (caches, random events, overclocks, challenges, milestones ...)."""
    data["collection"][key] = data["collection"].get(key, 0) + n


# --------------------------------------------------------------- rice rating
# An area's level is the mean of its skills' levels; the Rice rating is ten times the mean of the six
# area levels, rounded: 10 on a fresh install, 1000 with everything at 100.
def area_levels(data):
    return {a[0]: sum(level_for_xp(data["xp"][k]) for k in a[2]) / float(len(a[2])) for a in AREAS}


def rice_rank(rating):
    title = RICE_RANKS[0][1]
    for need, name in RICE_RANKS:
        if rating >= need:
            title = name
    nxt = next(((need, name) for need, name in RICE_RANKS if need > rating), None)
    return title, nxt


def rice_info(data):
    al = area_levels(data)
    rating = int(round(10 * sum(al.values()) / len(al)))
    title, nxt = rice_rank(rating)
    weakest = min(AREAS, key=lambda a: (al[a[0]], AREAS.index(a)))
    low = min(weakest[2], key=lambda k: (data["xp"][k], weakest[2].index(k)))
    return {"rating": rating, "rank": title, "next": {"rating": nxt[0], "rank": nxt[1]} if nxt else None,
            "areas": [{"id": a[0], "name": a[1], "tint": a[3], "level": round(al[a[0]], 2),
                       "skills": list(a[2])} for a in AREAS],
            "weakest": {"area": weakest[1], "skill": low, "name": SKILL_BY_KEY[low][1]}}


def cmd_rice(argv):
    """omalvl rice   Rice rating, rank, the six areas and what raises it next"""
    r = rice_info(load())
    if "--json" in argv:
        print(json.dumps(r))
        return 0
    print("Rice rating %d  ·  %s%s" % (r["rating"], r["rank"],
          "  ·  next rank %s at %d" % (r["next"]["rank"], r["next"]["rating"]) if r["next"] else ""))
    for a in r["areas"]:
        bar = "#" * int(a["level"] / 5) + "." * (20 - int(a["level"] / 5))
        print("  %-9s %6.1f  %s  %s" % (a["name"], a["level"], bar,
              ", ".join(SKILL_BY_KEY[k][1] for k in a["skills"])))
    print("Weakest area: %s. Train %s to lift it." % (r["weakest"]["area"], r["weakest"]["name"]))
    return 0


def _marks_and_milestones(data, res, total_before, rice_before=None):
    """Level 100 earns that skill's mastery mark; companions hatch at their level; a total-level
    milestone or a new Rice rank is announced, and skins unlock with the rating."""
    for k, lo, hi in res.ups:
        if hi >= MAX_LEVEL and k not in data["badges"]:
            data["badges"][k] = int(time.time())
            collect(data, "mark")
    for pid, name, skill, lvl in COMPANIONS:
        if pid not in data["companions"] and level_for_xp(data["xp"][skill]) >= lvl:
            data["companions"][pid] = int(time.time())
            res.notes.append(("A companion hatched",
                              "%s hatched at %s level %d and joins you (omalvl collection)."
                              % (name, SKILL_BY_KEY[skill][1], lvl)))
    if all(q[0] in data["quests"] for q in QUESTS) and "questmaster" not in data["badges"]:
        data["badges"]["questmaster"] = int(time.time())
        collect(data, "mark")
        res.notes.append(("Questmaster", "Every quest is done. The Questmaster mark is yours."))
    if all(level_for_xp(data["xp"][k]) >= MAX_LEVEL for k in SKILL_KEYS) and "max" not in data["badges"]:
        data["badges"]["max"] = int(time.time())
        res.notes.append(("Omarchist", "Every skill is at 100. Nothing left to learn here, only to share."))
    if rice_before is not None:
        r = rice_info(data)["rating"]
        if rice_rank(r)[0] != rice_rank(rice_before)[0]:
            res.notes.append(("Rice rank: %s" % rice_rank(r)[0], "Your Rice rating is now %d." % r))
        for sid, sname, need in SKINS:
            if rice_before < need <= r:
                res.notes.append(("Skin unlocked: %s" % sname, "Wear it with: omalvl skin %s" % sid))
    after = total_level(data)
    crossed = [m for m in TOTAL_MILESTONES if total_before < m <= after]
    if crossed:
        m = crossed[-1]
        res.milestone = m
        collect(data, "milestone:%d" % m)
        res.notes.append(("Total level %d" % m, "Your total level reached %d%s." % (
            m, ": every skill at 100" if m >= MAX_TOTAL else "")))


def _tree_progress(data, res):
    """Rank up every keybind node whose use count crossed a threshold; each rank pays Shell XP."""
    for key, uses in data["stats"].items():
        if not key.startswith("kb:"):
            continue
        node = key[3:]
        if not tree_branch(node):
            continue
        rank = sum(1 for need, _, _ in TREE_RANKS if uses >= need)
        had = data["tree"].get(node, 0)
        if rank > had:
            data["tree"][node] = rank
            xp = sum(TREE_RANKS[i][2] for i in range(had, rank))
            _add(data, {"shell": xp}, res)
            if rank >= 2:
                res.notes.append(("Keybind tree: %s" % TREE_RANKS[rank - 1][1],
                                  "%s is %s (%d uses): +%d Shell XP." % (node_name(node), TREE_RANKS[rank - 1][1].lower(),
                                                                         int(uses), xp)))


def tree_branch(node):
    for bid, name, prefixes, _ in TREE_BRANCHES:
        if any(node == p or (p.endswith(":") and node.startswith(p)) for p in prefixes):
            return bid
    return None


def node_name(node):
    kind, _, word = node.partition(":")
    word = (word or kind).replace("omarchy.", "").replace("-", " ")
    fmt = {"menu": "%s menu", "toggle": "Toggle %s", "window": "Window %s", "capture": "Capture %s",
           "panel": "%s panel"}.get(kind if word != kind else "", "%s")
    if word == "root":
        word = "Omarchy"
    text = fmt % word
    return text[:1].upper() + text[1:]


def tree_info(data):
    out = []
    for bid, name, prefixes, hints in TREE_BRANCHES:
        nodes = {}
        for key, uses in data["stats"].items():
            if key.startswith("kb:") and tree_branch(key[3:]) == bid:
                nodes[key[3:]] = uses
        for h in hints:
            nodes.setdefault(h, 0)
        rows = [{"id": n, "name": node_name(n), "uses": int(u), "rank": data["tree"].get(n, 0),
                 "title": TREE_RANKS[data["tree"][n] - 1][1] if data["tree"].get(n) else "Unfound"}
                for n, u in sorted(nodes.items(), key=lambda kv: (-kv[1], kv[0]))]
        out.append({"id": bid, "name": name, "nodes": rows[:12],
                    "mastered": sum(1 for r in rows if r["rank"] >= 3), "found": sum(1 for r in rows if r["rank"])})
    return out


def cmd_tree(argv):
    """omalvl tree   the keybind tree"""
    t = tree_info(load())
    if "--json" in argv:
        print(json.dumps(t))
        return 0
    for b in t:
        print("%s  (%d found, %d mastered)" % (b["name"], b["found"], b["mastered"]))
        for n in b["nodes"]:
            print("  %-26s %-9s %d use%s" % (n["name"], n["title"], n["uses"], "" if n["uses"] == 1 else "s"))
    print("Ranks: " + ", ".join("%s at %d use%s (+%d Shell XP)" % (t_, n, "" if n == 1 else "s", xp)
                                for n, t_, xp in TREE_RANKS))
    return 0


# --------------------------------------------------------------- seasons, stamps, Update Day
def theme_area(theme):
    """The area a theme's season favours: fixed per theme name."""
    import zlib
    return AREAS[zlib.crc32((theme or "").strip().lower().encode("utf-8")) % len(AREAS)][0] if theme else None


def update_day_active(data, now=None):
    u = data.get("updateDay")
    return u if u and u.get("until", 0) > (now or time.time()) else None


def season_info(data, theme=None):
    theme = theme if theme is not None else theme_name()
    area = theme_area(theme)
    ud = update_day_active(data)
    mins = {k[10:]: v for k, v in data["stats"].items() if k.startswith("theme_min:")}
    return {"theme": theme, "area": area, "areaName": AREA_BY_ID[area][1] if area else "",
            "bonus": int(SEASON_BONUS * 100),
            "updateDay": {"until": ud["until"], "bonus": int(UPDATE_DAY_BONUS * 100)} if ud else None,
            "stamps": [{"theme": t, "at": at} for t, at in sorted((data.get("stamps") or {}).items(), key=lambda kv: kv[1])],
            "wearing": round(mins.get(_theme_key(theme), 0)), "stampMinutes": STAMP_MINUTES}


def _theme_key(theme):
    return re.sub(r"[^a-z0-9 _.-]", "", (theme or "").lower())[:40]


def _boosts(data, amounts):
    """Theme season (+25% to one area) and Update Day (+50% to System) on measured XP."""
    theme = theme_name()
    area = theme_area(theme)
    ud = update_day_active(data)
    out = {}
    for k, v in amounts.items():
        mult = 1.0
        if area and AREA_OF.get(k) == area:
            mult += SEASON_BONUS
        if ud and AREA_OF.get(k) == "system":
            mult += UPDATE_DAY_BONUS
        out[k] = v * mult
    return out


def _stamps_and_relics(data, events, res):
    for key in [k for k in events if k.startswith("theme_min:")]:
        t = key[10:]
        if t and t not in data["stamps"] and data["stats"].get(key, 0) >= STAMP_MINUTES:
            data["stamps"][t] = int(time.time())
            _add(data, {"theming": STAMP_XP}, res)
            res.notes.append(("Theme stamp: %s" % t, "%d minutes in %s: stamped (+%d Theming XP). "
                              "%d stamp%s so far." % (STAMP_MINUTES, t, STAMP_XP, len(data["stamps"]),
                                                      "" if len(data["stamps"]) == 1 else "s")))
    for key in [k for k in events if k.startswith("relic:")]:
        rid = key[6:]
        relic = next((r for r in RELICS if r[0] == rid), None)
        if relic and rid not in data["relics"]:
            data["relics"][rid] = int(time.time())
            _add(data, RELIC_XP, res)
            res.notes.append(("Relic unearthed: %s" % relic[1], "Your config is in version control. "
                              + ", ".join("+%d %s XP" % (v, SKILL_BY_KEY[k][1]) for k, v in RELIC_XP.items())))
    if events.get("update") and not update_day_active(data) and \
            (data.get("updateDay") or {}).get("day") != today():
        data["updateDay"] = {"day": today(), "until": int(time.time()) + UPDATE_DAY_MINUTES * 60}
        data["tokens"].append({"kind": "fixed", "xp": UPDATE_DAY_TOKEN, "from": "Update Day", "t": int(time.time())})
        collect(data, "update_day")
        res.notes.append(("Update Day", "You ran omarchy update. System XP is +%d%% for %d minutes, and here "
                          "is an XP token worth %s XP." % (int(UPDATE_DAY_BONUS * 100), UPDATE_DAY_MINUTES,
                                                          format(UPDATE_DAY_TOKEN, ","))))


def cmd_season(argv):
    data = load()
    si = season_info(data)
    if "--json" in argv:
        print(json.dumps(si))
        return 0
    if si["theme"]:
        print("Season: %s favours %s (+%d%% XP while you wear it)." % (si["theme"], si["areaName"], si["bonus"]))
        if si["theme"] not in data["stamps"]:
            print("  %d of %d minutes towards its stamp." % (si["wearing"], STAMP_MINUTES))
    else:
        print("No Omarchy theme found, so no season.")
    if si["updateDay"]:
        print("Update Day: System XP +%d%% for %s more." % (si["updateDay"]["bonus"], fmt_dur(si["updateDay"]["until"] - time.time())))
    print("Theme stamps (%d): %s" % (len(si["stamps"]), ", ".join(s_["theme"] for s_ in si["stamps"]) or "none yet"))
    return 0


def cmd_relics(argv):
    data = load()
    print("Dotfile relics %d / %d  (commit your config in a watched repo)" % (len(data["relics"]), len(RELICS)))
    for rid, name, _ in RELICS:
        print("  [%s] %s" % ("x" if rid in data["relics"] else " ", name))
    return 0


def relic_paths(paths):
    found = set()
    for path in paths:
        for rid, _, rx in RELICS:
            if re.search(rx, path):
                found.add(rid)
    return found


# --------------------------------------------------------------- skins
def skins_info(data):
    r = rice_info(data)["rating"]
    return [{"id": sid, "name": name, "need": need, "unlocked": r >= need, "worn": data.get("skin") == sid}
            for sid, name, need in SKINS]


def cmd_skin(argv):
    data = load()
    if not argv:
        for s_ in skins_info(data):
            print("  %s %-9s %s" % ("*" if s_["worn"] else " ", s_["name"],
                  "unlocked" if s_["unlocked"] else "Rice rating %d" % s_["need"]))
        return 0
    want = argv[0].lower()
    row = next((s_ for s_ in skins_info(data) if s_["id"] == want), None)
    if not row:
        print("unknown skin: %s (%s)" % (want, ", ".join(s_[0] for s_ in SKINS)), file=sys.stderr)
        return 2
    if not row["unlocked"]:
        print("%s unlocks at Rice rating %d." % (row["name"], row["need"]))
        return 1
    with _Lock():
        data = load()
        data["skin"] = want
        save(data)
    print("Wearing the %s skin." % row["name"])
    return 0


def sysop_today(data):
    """Pick (and remember) today's Sysop challenge: by date, from installed commands."""
    w = data.get("sysop")
    if w and w.get("day") == today() and w.get("id") in SYSOP_BY_ID:
        return w
    pool = [c for c in SYSOP_CHALLENGES if (not c[5] or shutil.which(c[5]))
            and level_for_xp(data["xp"][SYSOP_REQS[c[0]][0]]) >= SYSOP_REQS[c[0]][1] if c[0] in SYSOP_REQS] + \
           [c for c in SYSOP_CHALLENGES if c[0] not in SYSOP_REQS and (not c[5] or shutil.which(c[5]))]
    day = datetime.date.today().toordinal()
    cid = pool[(day * 7) % len(pool)][0]          # deterministic, cycles through the pool
    cond = SYSOP_BY_ID[cid][3]
    data["sysop"] = {"day": today(), "id": cid, "base": stat_sum(data, cond[1]), "done": 0}
    return data["sysop"]


def _sysop_progress(data, res):
    w = data.get("sysop")
    if not w or w.get("done") or w.get("day") != today() or w.get("id") not in SYSOP_BY_ID:
        return
    cid, task, hint, cond, reward, _ = SYSOP_BY_ID[w["id"]]
    if stat_sum(data, cond[1]) - w["base"] < cond[2]:
        return
    w["done"] = int(time.time())
    collect(data, "sysop")
    _add(data, reward, res)
    res.notes.append(("The Sysop nods.", "\"Not bad, not bad at all.\" %s: done. %s"
                      % (task, ", ".join("+%d %s XP" % (v, SKILL_BY_KEY[k][1]) for k, v in reward.items()))))


def grant(amounts=None, quests=(), why="by hand", events=None, rates=None, token_drop=False,
          boost=False, source="game"):
    """The one place state changes. Adds xp, counts events into lifetime stats,
    advances quests / contract / signals / diary, logs it. Returns a Result."""
    res = Result()
    with _Lock():
        data = load()
        total_before = total_level(data)
        rice_before = rice_info(data)["rating"]
        events = {k: v for k, v in (events or {}).items() if v}
        for k, v in events.items():
            data["stats"][k] = round(data["stats"].get(k, 0) + v, 2)
        amounts = dict(amounts or {})
        fair = data["fair"]
        now = time.time()
        if events.get("active_min"):
            anticheat.note_active(fair, events["active_min"], now)
        if events.get("agent_work_min"):
            anticheat.note_work(fair, events["agent_work_min"], now)
        if events and amounts and not anticheat.measured_ok(fair, now):
            res.voided = "activity around the clock (more than %d h of the last 24)" % (anticheat.ACTIVE_DAY_MAX // 60)
            fair["voided"] += 1
            fair["voidedXp"] += int(sum(amounts.values()))
            why = "voided (%s): %s" % (res.voided, why)
            amounts = {}
        if source == "admin" and amounts:
            for k, xp in amounts.items():
                anticheat.record_award(fair, k, int(xp), why, "admin", True, "", now)
        if source in ("agent", "manual") and amounts:
            for k, xp in list(amounts.items()):
                ok, why_not = anticheat.check_award(fair, k, int(xp), why, source, now)
                anticheat.record_award(fair, k, int(xp), why, source, ok, why_not, now)
                if not ok:
                    res.voided = why_not
                    del amounts[k]
            if res.voided:
                why = "voided (%s): %s" % (res.voided, why)
        if boost and amounts:
            amounts = _boosts(data, amounts)          # theme season and Update Day: measured XP only
        surge = surge_active(data)
        if boost and surge and amounts.get(surge["skill"], 0) > 0:
            extra = int(amounts[surge["skill"]])        # the surge doubles measured activity only
            amounts[surge["skill"]] += extra
            surge["xp"] = surge.get("xp", 0) + extra
        _add(data, amounts, res)
        for qid in quests:
            _complete_quest(data, qid, res)
        if events:
            _contract_progress(data, events, res)
        _signal_progress(data, res)
        _sysop_progress(data, res)
        _auto_quests(data, res)
        if events:
            _stamps_and_relics(data, events, res)
            _tree_progress(data, res)
        _diary_progress(data, res)
        _marks_and_milestones(data, res, total_before, rice_before)
        anticheat.tally(fair, res.gains, "measured" if events else source)
        _log(data, why, res)
        _days(data, res)
        if rates is not None:
            data["rates"] = rates
        drops = [{"skill": k, "xp": v} for k, v in res.gains.most_common()
                 if k not in PASSIVE or res.quests or token_drop]
        if drops or res.ups:
            data["drop"] = {"t": time.time(), "gains": drops[:4],
                            "ups": [[k, hi] for k, lo, hi in res.ups],
                            "milestone": res.milestone}
        save(data)
    return res


def snapshot(data=None):
    data = data if data is not None else load()
    out, total = [], 0
    for key, name, abbr, blurb, tint in SKILLS:
        xp = data["xp"][key]
        lvl = level_for_xp(xp)
        total += lvl
        need, span = xp_to_next(xp)
        rate = int(data.get("rates", {}).get(key, 0))
        out.append({"key": key, "name": name, "abbr": abbr, "blurb": blurb, "area": AREA_OF[key],
                    "mastered": lvl >= MAX_LEVEL,
                    "tint": tint, "xp": xp, "level": lvl, "toNext": need, "span": span,
                    "rate": rate, "eta": int(need / rate * 3600) if rate > 0 and need else 0})
    qlog, qp = [], 0
    for qid, name, points, desc, reward, auto, steps in QUESTS:
        when = data["quests"].get(qid)
        if when:
            qp += points
        rq = QUEST_REQS.get(qid, {})
        qlog.append({"id": qid, "name": name, "qp": points, "desc": desc,
                     "reqs": [{"skill": k, "name": SKILL_BY_KEY[k][1], "level": v,
                               "met": level_for_xp(data["xp"][k]) >= v} for k, v in rq.items()],
                     "locked": not reqs_met(data, rq),
                     "done": bool(when), "doneAt": when or 0, "auto": bool(auto),
                     "reward": ", ".join("%d %s" % (v, SKILL_BY_KEY[k][1]) for k, v in reward.items()),
                     "steps": [{"text": t, "done": bool(when) or (c is not None and cond_met(data, c)),
                                "tracked": c is not None} for t, c in steps]})
    diary = []
    for tier, title, tasks, lamp_xp in DIARIES:
        diary.append({"tier": tier, "title": title, "done": tier in data["diary"], "token": lamp_xp,
                      "tasks": [{"text": t, "done": cond_met(data, c),
                                 "have": min(*cond_progress(data, c)), "need": cond_progress(data, c)[1]}
                                for t, c in tasks]})
    sl = data["contract"]
    task = sl.get("task")
    contract = {"streak": sl["streak"], "points": sl["points"], "completed": sl["completed"],
              "task": None, "canNew": sl["day"] != today() or sl["taken"] < CONTRACT_PER_DAY}
    if task and task["id"] in CONTRACT_BY_ID:
        contract["task"] = {"text": CONTRACT_BY_ID[task["id"]][1].format(n=task["n"]),
                          "done": int(task["done"]), "n": task["n"]}
    signal = None
    if data["signal"]:
        c = data["signal"]
        signal = {"tier": c["tier"], "step": c["at"] + 1, "steps": len(c["steps"]),
                "hint": SIGNAL_BY_ID[c["steps"][c["at"]]][1]}
    activity = []
    for e in reversed(data["log"]):
        gains = sorted(e["xp"].items(), key=lambda kv: -kv[1])
        activity.append({"t": e["t"], "why": e["why"], "n": e.get("n", 1),
                         "quests": [QUEST_BY_ID[q][1] for q in e.get("quests", []) if q in QUEST_BY_ID],
                         "gains": "  ".join("+%d %s" % (v, SKILL_BY_KEY[k][1]) for k, v in gains)})
    rice = rice_info(data)
    return {"name": "OmaLvL", "skills": out, "total": total, "maxTotal": MAX_TOTAL, "maxXp": MAX_XP,
            "maxLevel": MAX_LEVEL, "rice": rice, "season": season_info(data), "treeInfo": tree_info(data),
            "relicInfo": [{"id": rid, "name": name, "found": rid in data["relics"]} for rid, name, _ in RELICS],
            "skins": skins_info(data), "skin": data.get("skin") or "plain", "palette": theme_palette(),
            "settings": {"reduceMotion": bool(config().get("reduceMotion"))},
            "fairPlay": fair_info(data),
            "questLog": qlog, "questPoints": qp, "maxQuestPoints": MAX_QP,
            "activity": activity, "diaryLog": diary, "contractInfo": contract, "signalInfo": signal,
            "tokenCount": len(data["tokens"]), "xpRate": sum(data.get("rates", {}).values()),
            "dropInfo": data.get("drop"), "surgeInfo": _surge_info(data),
            "sysopInfo": _sysop_info(data), "companionLog": _companion_log(data), "collectionLog": data["collection"],
            "jobInfo": [{"slot": p["slot"], "cmd": p["cmd"], "planted": p["planted"], "done": p["done"] or 0,
                           "dead": bool(p.get("exit")), "xp": job_xp(p) if p["done"] else 0}
                          for p in data["jobs"]],
            "streakInfo": data["streak"], "marks": data["badges"]}


def cmd_panel_state(argv):
    """Emit the bounded, display-ready state the panel needs; never pass the save file to QML."""
    data = load()
    view = snapshot(data)
    view["activity"] = view["activity"][:80]
    print(json.dumps(view, separators=(",", ":")))
    return 0


def _surge_info(data):
    st = surge_active(data)
    if not st:
        return None
    return {"skill": st["skill"], "name": SKILL_BY_KEY[st["skill"]][1], "until": st["until"],
            "xp": st.get("xp", 0)}


def _sysop_info(data):
    w = data.get("sysop")
    if not w or w.get("day") != today() or w.get("id") not in SYSOP_BY_ID:
        return None
    cid, task, hint, cond, reward, _ = SYSOP_BY_ID[w["id"]]
    return {"id": cid, "task": task, "hint": hint, "done": bool(w.get("done")),
            "explain": w.get("explain", ""), "explainSource": w.get("explainSource", ""),
            "reward": ", ".join("%d %s" % (v, SKILL_BY_KEY[k][1]) for k, v in reward.items())}


def _companion_log(data):
    return [{"id": pid, "name": name, "skill": skill, "skillName": SKILL_BY_KEY[skill][1], "level": lvl,
             "owned": pid in data["companions"], "t": data["companions"].get(pid, 0)}
            for pid, name, skill, lvl in COMPANIONS]


# --------------------------------------------------------------- output
def notify(title, msg):
    try:
        subprocess.Popen([tool("notify-send"), "-a", "OmaLvL", "-i", "input-gaming", title, msg])
    except OSError:
        pass


def announce(res):
    for qid in res.quests:
        _, name, points, _, reward, _, _ = QUEST_BY_ID[qid]
        notify("Quest done: %s" % name, "+%d renown · %s"
               % (points,
                  ", ".join("%d %s xp" % (v, SKILL_BY_KEY[k][1]) for k, v in reward.items())))
        print("QUEST %s" % qid)
    for title, msg in res.notes:
        notify(title, msg)
        print("%s %s" % (title.upper(), msg))
    for key, lo, hi in res.ups:
        name = SKILL_BY_KEY[key][1]
        notify("%s %d" % (name, hi), "%s is now level %d." % (name, hi))
        if hi == MAX_LEVEL:
            notify("Mastery: %s" % name, "%s reached 100. Its mastery mark is in your collection." % name)
        print("LEVELUP %s %d" % (key, hi))


# Skill names from the 0.x prototype, so scripts and agents written against them keep working.
RENAMED = {"presence": "focus", "play": "focus", "stamina": "focus", "charging": "focus",
           "compute": "workload", "storage": "workload", "network": "downloads", "contracts": "editing",
           "creating": "editing", "pruning": "editing", "upgrading": "packages"}


def skill_key(word):
    word = (word or "").lower()
    if word in SKILL_BY_KEY:
        return word
    if word in RENAMED:
        return RENAMED[word]
    hit = next((k for k, s in SKILL_BY_KEY.items() if s[1].lower() == word or s[2].lower() == word), None)
    if hit:
        return hit
    try:
        import migrate                              # optional, local: names from an older save format
    except ImportError:
        return None
    old = migrate.SKILL_KEYS.get(word)
    return RENAMED.get(old, old) if old else None


def fmt_dur(sec):
    if sec <= 0:
        return "-"
    h, m = divmod(int(sec) // 60, 60)
    return "%dh %02dm" % (h, m) if h else "%dm" % m


# --------------------------------------------------------------- commands
def cmd_list(argv):
    snap = snapshot()
    by_key = {x["key"]: x for x in snap["skills"]}
    for a in snap["rice"]["areas"]:
        print("%s  (area level %.1f)" % (a["name"].upper(), a["level"]))
        for k in a["skills"]:
            s_ = by_key[k]
            rate = ("%6d xp/hr  next in %s" % (s_["rate"], fmt_dur(s_["eta"]))) if s_["rate"] else ""
            print("  %-11s %3d  %12s xp  (+%s to next)  %s" % (s_["name"], s_["level"], "{:,}".format(s_["xp"]),
                                                              "{:,}".format(s_["toNext"]), rate))
    print("TOTAL %d / %d   ·   RICE %d (%s)   ·   RENOWN %d / %d   ·   %d xp/hr" %
          (snap["total"], snap["maxTotal"], snap["rice"]["rating"], snap["rice"]["rank"],
           snap["questPoints"], snap["maxQuestPoints"], snap["xpRate"]))
    sl = snap["contractInfo"]
    if sl["task"]:
        print("CONTRACT %s (%d/%d)" % (sl["task"]["text"], sl["task"]["done"], sl["task"]["n"]))
    if snap["signalInfo"]:
        print("SIGNAL (%s, step %d/%d) %s" % (snap["signalInfo"]["tier"], snap["signalInfo"]["step"],
                                            snap["signalInfo"]["steps"], snap["signalInfo"]["hint"]))
    if snap["tokenCount"]:
        print("TOKENS %d unused  (omalvl token <skill>)" % snap["tokenCount"])


def cmd_add(argv, agent=False):
    if len(argv) < 2:
        print("usage: %s <skill> %s" % ("agent" if agent else "add",
              "<tier|xp> <why>   tiers: " + ", ".join("%s %d" % t for t in AGENT_TIERS.items()) if agent else "<xp>"),
              file=sys.stderr)
        return 2
    key = skill_key(argv[0])
    if not key:
        print("unknown skill: %s (%s)" % (argv[0], ", ".join(SKILL_KEYS)), file=sys.stderr)
        return 2
    tier = argv[1].lower() if agent and argv[1].lower() in AGENT_TIERS else None
    try:
        xp = AGENT_TIERS[tier] if tier else int(float(argv[1]))
    except ValueError:
        print("not a tier or a number: %s (tiers: %s)" % (argv[1], ", ".join(AGENT_TIERS)), file=sys.stderr)
        return 2
    if xp <= 0:
        print("xp must be positive", file=sys.stderr)
        return 2
    why = "omalvl add"
    if agent:
        reason = " ".join(argv[2:]).strip()
        if not reason:
            print("agent awards need a reason: omalvl agent <skill> <tier> <what was done>", file=sys.stderr)
            return 2
        why = "agent%s: %s" % (" [%s]" % tier if tier else "", reason)
    res = grant({key: xp}, why=why, source="agent" if agent else "manual")
    if res.voided:
        print("voided: %s. No XP was given; see `omalvl fair`." % res.voided, file=sys.stderr)
        return 1
    if agent:
        with _Lock():
            data = load()
            day = data["days"].setdefault(today(), {})
            day["_agent"] = day.get("_agent", 0) + xp
            save(data)
    announce(res)
    print("ok %s +%d%s" % (key, xp, " (%s)" % tier if tier else ""))


def cmd_admin(argv):
    """omalvl admin grant <skill> <xp|tier> <reason>   the owner's override: XP with no fair-play checks"""
    if len(argv) < 4 or argv[0] != "grant":
        print("usage: omalvl admin grant <skill> <xp|tier> <reason>\n"
              "  Grants XP with no fair-play budget. Every grant is logged with its reason and shown\n"
              "  on the fair-play card (omalvl fair), and the account stays verified.", file=sys.stderr)
        return 2
    key = skill_key(argv[1])
    if not key:
        print("unknown skill: %s (%s)" % (argv[1], ", ".join(SKILL_KEYS)), file=sys.stderr)
        return 2
    tier = argv[2].lower()
    try:
        xp = AGENT_TIERS[tier] if tier in AGENT_TIERS else int(float(tier))
    except ValueError:
        print("not a tier or a number: %s" % argv[2], file=sys.stderr)
        return 2
    reason = " ".join(argv[3:]).strip()
    if xp <= 0 or len(reason) < 4:
        print("xp must be positive and the reason must say what it is for", file=sys.stderr)
        return 2
    res = grant({key: xp}, why="admin: " + reason, source="admin", token_drop=True)
    announce(res)
    print("ok admin %s +%s" % (key, format(xp, ",")))
    return 0


def cmd_task(argv):
    if not argv:
        print("tasks: %s" % ", ".join(sorted(TASKS)), file=sys.stderr)
        return 2
    name = TASK_ALIASES.get(argv[0].lower(), argv[0].lower())
    if name not in TASKS:
        print("unknown task: %s (%s)" % (name, ", ".join(sorted(TASKS))), file=sys.stderr)
        return 2
    key, xp = TASKS[name]
    if len(argv) > 1:
        xp = int(float(argv[1]))
    res = grant({key: xp}, why="task: " + name, source="manual")
    announce(res)
    if res.voided:
        print("voided: %s" % res.voided, file=sys.stderr)
        return 1
    print("ok task %s -> %s +%d" % (name, key, xp))


def cmd_get(argv):
    key = skill_key(argv[0]) if argv else None
    if not key:
        print("usage: get <skill>", file=sys.stderr)
        return 2
    xp = load()["xp"][key]
    print("%s level %d  xp %d  (next in %d)" % (key, level_for_xp(xp), xp, xp_to_next(xp)[0]))


def cmd_quests(argv):
    snap = snapshot()
    for q in snap["questLog"]:
        mark = "done" if q["done"] else ("auto" if q["auto"] else "    ")
        print("[%s] %-20s %-30s %d renown  %s" % (mark, q["id"], q["name"], q["qp"], q["desc"]))
    print("RENOWN %d / %d   (omalvl quest <id> to see steps or complete one)" %
          (snap["questPoints"], snap["maxQuestPoints"]))


def cmd_quest(argv):
    qid = argv[0].lower() if argv else ""
    if qid not in QUEST_BY_ID:
        print("unknown quest: %s  (see: omalvl quests)" % qid, file=sys.stderr)
        return 2
    if len(argv) > 1 and argv[1] == "steps" or load()["quests"].get(qid):
        q = next(q for q in snapshot()["questLog"] if q["id"] == qid)
        print("%s — %s\nReward: %s" % (q["name"], q["desc"], q["reward"]))
        for s in q["steps"]:
            print("  [%s] %s" % ("x" if s["done"] else " ", s["text"]))
        if q["done"]:
            print("(complete)")
        return 0
    if not reqs_met(load(), QUEST_REQS.get(qid)):
        print("You need %s to start this quest." % reqs_text(QUEST_REQS[qid]))
        return 1
    res = grant({}, [qid], why="quest")
    announce(res)


def cmd_contract(argv):
    if argv and argv[0] in ("new", "skip"):
        with _Lock():
            data = load()
            if argv[0] == "skip" and data["contract"]["task"]:
                data["contract"]["streak"] = 0
                data["contract"]["task"] = None
                print("Task cancelled. Your streak is reset.")
            elif argv[0] == "new" and data["contract"]["task"]:
                print("You already have a contract. (omalvl contract skip resets your streak)")
                save(data)
                return 0
            text = _new_contract_task(data)
            save(data)
        print(("New contract: %s." % text) if text
              else "No more contracts today (%d a day). Come back tomorrow." % CONTRACT_PER_DAY)
        return 0
    sl = snapshot()["contractInfo"]
    if sl["task"]:
        print("Task: %s  (%d/%d)" % (sl["task"]["text"], sl["task"]["done"], sl["task"]["n"]))
    else:
        print("No task. %s" % ("Get one: omalvl contract new" if sl["canNew"] else "Back tomorrow."))
    print("Streak %d · points %d · completed %d" % (sl["streak"], sl["points"], sl["completed"]))


def cmd_signal(argv):
    c = snapshot()["signalInfo"]
    print(("Signal (%s), step %d of %d:\n  %s" % (c["tier"], c["step"], c["steps"], c["hint"]))
          if c else "You have no signal. Random events and Contracts give them.")


def cmd_token(argv):
    if not argv:
        tokens = load()["tokens"]
        if not tokens:
            print("You have no tokens.")
        for l in tokens:
            print("- %s token from %s" % ("Courier (10× level)" if l["kind"] == "courier" else "%d XP" % l["xp"],
                                         l.get("from", "?")))
        return 0
    key = skill_key(argv[0])
    if not key:
        print("unknown skill: %s" % argv[0], file=sys.stderr)
        return 2
    with _Lock():
        data = load()
        if not data["tokens"]:
            print("You have no tokens.")
            return 0
        token = data["tokens"].pop(0)
        save(data)
    xp = token.get("xp") or 10 * level_for_xp(load()["xp"][key])
    res = grant({key: xp}, why="token (%s)" % token.get("from", "?"), token_drop=True)
    announce(res)
    print("Token redeemed: +%d %s XP" % (xp, SKILL_BY_KEY[key][1]))


def cmd_diary(argv):
    for d in snapshot()["diaryLog"]:
        print("%s tier%s  (reward: %d XP token)" % (d["title"], "  COMPLETE" if d["done"] else "", d["token"]))
        for t in d["tasks"]:
            print("  [%s] %s%s" % ("x" if t["done"] else " ", t["text"],
                                   "" if t["done"] or t["need"] <= 1 else "  (%d/%d)" % (t["have"], t["need"])))


def cmd_log(argv):
    for e in reversed(snapshot()["activity"]):
        stamp = time.strftime("%a %H:%M", time.localtime(e["t"]))
        extra = ("  [quest: %s]" % ", ".join(e["quests"])) if e["quests"] else ""
        print("%s  %-34s %s%s" % (stamp, e["why"][:34], e["gains"], extra))


def week_report(data=None):
    data = data or load()
    end = datetime.date.today()
    days = [(end - datetime.timedelta(d)).isoformat() for d in range(6, -1, -1)]
    gains = collections.Counter()
    for d in days:
        for k, v in data["days"].get(d, {}).items():
            if not k.startswith("_"):
                gains[k] += v
    start_total = next((data["days"][d]["_total"] for d in sorted(data["days"])
                        if d < days[0] and "_total" in data["days"][d]), None)
    start_total = start_total or next((data["days"][d].get("_total") for d in days
                                       if data["days"].get(d, {}).get("_total")), total_level(data))
    t0 = time.mktime(time.strptime(days[0], "%Y-%m-%d"))
    quests = [QUEST_BY_ID[q][1] for q, t in data["quests"].items() if t >= t0 and q in QUEST_BY_ID]
    active = [d for d in days if any(not k.startswith("_") for k in data["days"].get(d, {}))]
    lines = ["OmaLvL — week ending %s" % end.strftime("%a %d %b"),
             "Total XP: %d   ·   total level %d (+%d)   ·   active %d/7 days" %
             (sum(gains.values()), total_level(data), total_level(data) - start_total, len(active))]
    if gains:
        lines.append("Top skills: " + ", ".join("%s %d" % (SKILL_BY_KEY[k][1], v)
                                                for k, v in gains.most_common(3)))
    if quests:
        lines.append("Quests: " + ", ".join(quests))
    sl = data["contract"]
    lines.append("Rice rating %d (%s)   ·   contracts: streak %d, %d done   ·   signals traced: %d   ·   stamps %d, relics %d"
                 % (rice_info(data)["rating"], rice_info(data)["rank"], sl["streak"], sl["completed"],
                    sum(data["signals"].values()), len(data["stamps"]), len(data["relics"])))
    return "\n".join(lines)


def cmd_week(argv):
    print(week_report())


def cmd_reset(argv):
    with _Lock():
        snap = snapshot_file("before-reset")
        if snap:
            print("saved a copy first: %s  (undo: omalvl restore %s)" % (snap, snap))
        if argv:
            key = skill_key(argv[0])
            if not key:
                print("unknown skill: %s" % argv[0], file=sys.stderr)
                return 2
            data = load()
            data["xp"][key] = 0
            anticheat.set_baseline(data["fair"], data["xp"])
            save(data, allow_drop=True)
        else:
            save(_blank(), allow_drop=True)
    print("reset")


def _backup_list():
    paths = glob.glob(os.path.join(BACKUP_DIR, "skills-*.json")) + [BACKUP]
    off = _offsite_dir()
    if off:
        paths += glob.glob(os.path.join(off, "skills-*.json"))
    rows = []
    for p in paths:
        try:
            d = _read_state(p)
        except (OSError, ValueError):
            continue
        rows.append((os.path.getmtime(p), p, total_level(_fill(d)), _total_xp(d)))
    return sorted(rows, reverse=True)


def _fill(d):
    for k in SKILL_KEYS:
        d["xp"].setdefault(k, 0)
    return d


def cmd_backup(argv):
    """omalvl backup        save a copy now and list every backup"""
    with _Lock():
        snap = snapshot_file("manual")
    print("saved %s" % snap)
    print("off-machine copies: %s" % (_offsite_dir() or "off (set \"offsite\" in the config)"))
    for t, p, lvl, xp in _backup_list()[:20]:
        print("%s  level %4d  %11s xp  %s" % (time.strftime("%Y-%m-%d %H:%M", time.localtime(t)),
                                             lvl, format(int(xp), ","), p))


def cmd_restore(argv):
    """omalvl restore [file|latest]   put a backup back (the current state is saved first)"""
    rows = _backup_list()
    if not argv:
        print("usage: omalvl restore <file> | latest   (omalvl backup lists them)")
        return 2
    if argv[0] == "latest":
        rows = [r for r in rows if r[1] != BACKUP]
        if not rows:
            print("no backups found", file=sys.stderr)
            return 1
        path = max(rows, key=lambda r: r[3])[1] if "--best" in argv else rows[0][1]
    else:
        path = os.path.expanduser(argv[0])
    try:
        data = _read_state(path)
    except (OSError, ValueError) as e:
        print("can't read %s: %s" % (path, e), file=sys.stderr)
        return 1
    with _Lock():
        snap = snapshot_file("before-restore")
        blank = _blank()
        for k, v in blank.items():
            data.setdefault(k, v)
        if not isinstance(data.get("fair"), dict) or data["fair"].get("baseline") is None:
            data["fair"] = anticheat.blank()
            anticheat.set_baseline(data["fair"], data["xp"])
        save(data, allow_drop=True)
    print("restored %s (level %d)  ·  previous state kept in %s"
          % (path, total_level(_fill(data)), snap))


def cmd_import(argv):
    """omalvl import <state.json>   bring over a save from the prototype (local builds only)"""
    if not argv:
        print("usage: omalvl import <path to an older save>", file=sys.stderr)
        return 2
    try:
        import migrate
    except ImportError:
        print("legacy save import is not included in this public build", file=sys.stderr)
        return 2
    try:
        old = _read_state(os.path.expanduser(argv[0]))
    except (OSError, ValueError) as e:
        print("can't read %s: %s" % (argv[0], e), file=sys.stderr)
        return 1
    data = migrate.convert(old)
    blank = _blank()
    for k, v in blank.items():
        if k not in data or (v is not None and not isinstance(data[k], type(v))):
            data[k] = v
    for k in SKILL_KEYS:
        data["xp"].setdefault(k, 0)
    data["fair"] = anticheat.blank()                  # an imported save starts the books at its XP
    anticheat.set_baseline(data["fair"], data["xp"])
    data["meta"]["imported"] = int(time.time())
    with _Lock():
        snap = snapshot_file("before-import")
        save(data, allow_drop=True)
    print("imported %s: total level %d, Rice rating %d%s" % (argv[0], total_level(data), rice_info(data)["rating"],
          ("  ·  previous state kept in %s" % snap) if snap else ""))
    return 0


# --------------------------------------------------------------- theme
THEME_COLOURS = [os.path.join(STATE_HOME, "omarchy/current/theme/colors.toml"),
                 os.path.join(CONFIG_HOME, "omarchy/current/theme/colors.toml")]
PALETTE_KEYS = ("background", "foreground", "accent", "muted", "selection", "red", "orange", "yellow", "green",
                "cyan", "blue", "magenta", "brown", "dark_background", "lighter_background", "dark_foreground")


def read_capped(path, limit=65536):
    """Read a small regular file: one open (no symlink follow), fstat that descriptor, cap the size."""
    import stat as _stat
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not _stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        chunks, left = [], limit + 1
        while left > 0:
            b = os.read(fd, left)
            if not b:
                break
            chunks.append(b)
            left -= len(b)
        raw = b"".join(chunks)
        if len(raw) > limit:
            raise OSError("too large")
        return raw.decode("utf-8", "replace")
    finally:
        os.close(fd)


def theme_palette():
    """The active Omarchy theme's named colours (colors.toml), for the panel's pixel art."""
    for path in THEME_COLOURS:
        real = os.path.realpath(path)        # the theme dir is a symlink by design; the file itself must not be
        try:
            text = read_capped(real)
        except OSError:
            continue
        pal = {}
        for k, v in re.findall(r'^\s*([a-z_]+)\s*=\s*"(#[0-9a-fA-F]{6})"', text, re.M):
            if k in PALETTE_KEYS:
                pal[k] = v.lower()
        if pal:
            return pal
    return {}


def fair_info(data):
    f = data["fair"]
    bad = anticheat.verify(f, data["xp"], XP_CAP)
    voids = [a for a in f["awards"] if not a["ok"]][-5:]
    return {"verified": not bad, "unverified": [SKILL_BY_KEY[k][1] for k in bad if k in SKILL_BY_KEY],
            "voided": f["voided"], "voidedXp": f["voidedXp"], "hold": bool(f.get("measuredHold")),
            "active24h": round(anticheat.active_minutes(f)), "imported": bool(data["meta"].get("imported")),
            "worked24h": round(anticheat.worked_minutes(f)),
            "adminXp": sum(v.get("admin", 0) for v in f["sources"].values()),
            "adminGrants": sum(1 for a in f["awards"] if a.get("kind") == "admin"),
            "budgetLeft": max(0, int(anticheat.budget(f)
                                     - sum(a["xp"] for a in f["awards"] if a["ok"] and a.get("kind") != "admin"
                                           and time.time() - a["t"] < anticheat.DAY))),
            "recentVoids": [{"t": a["t"], "skill": a["skill"], "xp": a["xp"], "why": a["void"]} for a in voids]}


def cmd_fair(argv):
    """omalvl fair   fair-play status: verified books, voided awards, today's award budget"""
    fp = fair_info(load())
    if "--json" in argv:
        print(json.dumps(fp))
        return 0
    print("Fair play: %s" % ("verified" if fp["verified"] else "UNVERIFIED (edited by hand: %s)" % ", ".join(fp["unverified"])))
    print("Last 24 h: %d min at the keyboard, %d worked min (incl. agents)  ·  award budget left: %s XP"
          % (fp["active24h"], fp["worked24h"], format(fp["budgetLeft"], ",")))
    if fp["adminGrants"]:
        print("Admin grants: %d, %s XP (shown openly; they skip fair play)" % (fp["adminGrants"], format(fp["adminXp"], ",")))
    print("Voided: %d award(s), %s XP%s" % (fp["voided"], format(fp["voidedXp"], ","),
          "  ·  measured XP on hold (activity around the clock)" if fp["hold"] else ""))
    for v in fp["recentVoids"]:
        print("  %s  %s +%s: %s" % (time.strftime("%m-%d %H:%M", time.localtime(v["t"])), SKILL_BY_KEY[v["skill"]][1]
              if v["skill"] in SKILL_BY_KEY else v["skill"], format(v["xp"], ","), v["why"]))
    return 0


def cmd_icons(argv):
    """omalvl icons --json   the pixel icons, for the panel"""
    import icons
    import pixelfont
    print(json.dumps({"size": icons.SIZE, "icons": icons.ICONS, "font": pixelfont.GLYPHS}))
    return 0


# --------------------------------------------------------------- sampler
def read(path, default=""):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return default


def input_irqs():
    """Keyboard + touchpad interrupts (i8042): counts, never contents."""
    n = 0
    for line in read("/proc/interrupts").splitlines():
        if line.rstrip().endswith("i8042"):
            n += sum(int(x) for x in line.split()[1:] if x.isdigit())
    return n


def cpu_busy_ticks():
    for line in read("/proc/stat").splitlines():
        if line.startswith("cpu "):
            f = [int(x) for x in line.split()[1:]]
            return sum(f) - f[3] - (f[4] if len(f) > 4 else 0)
    return 0


def on_ac_power():
    for p in glob.glob("/sys/class/power_supply/A*"):
        if read(p + "/online").strip() == "1":
            return True
    for p in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        if read(p + "/status").strip() in ("Charging", "Full"):
            return True
    return not glob.glob("/sys/class/power_supply/BAT*")


# Window classes that count as a game (config "games" adds more, e.g. a game client you use).
GAMES = ("retroarch", "flycast", "duckstation", "pcsx2", "steam", "dolphin-emu", "ppsspp", "mupen64",
         "rpcs3", "es-de", "lutris", "heroic", "minecraft", "prismlauncher")


def games():
    extra = config().get("games")
    return GAMES + tuple(g.lower() for g in extra if isinstance(g, str)) if isinstance(extra, list) else GAMES
WATCH_PROCS = ("claude", "opencode", "codex", "crush", "nvim", "btop", "lazygit", "lazydocker", "yazi")


COOK_PROCS = {"cc1", "cc1plus", "rustc", "javac", "ld", "ld.lld", "mold", "ninja", "esbuild", "tsc", "go", "zig"}
# AI that counts for Agents / Models and the AI quests: agent CLIs (cloud or local) train Agents,
# local-model runtimes train Models. Matched on the process name, or for agents that run under
# an interpreter (node/python/bun), on the script name in argv.
AGENT_NAMES = {
    # agent CLIs; most can also drive a local model (opencode, crush, codex --oss, aider, goose ...)
    "claude", "opencode", "codex", "crush", "gemini", "qwen", "aider", "goose", "llm",
    "interpreter", "cline", "amp", "kilo", "cursor-agent", "continue", "plandex", "mods",
    # local-model runtimes and apps
    "ollama", "llamafile", "koboldcpp", "lms", "lm studio", "lm-studio", "jan", "localai",
    "local-ai", "gpt4all", "tabby", "mistralrs-server", "mlc_llm", "tgi", "sglang",
}
AGENT_PREFIXES = ("ollama", "llama-", "llama.cpp", "vllm", "koboldcpp", "whisper-", "text-generation")
# The subset that runs the model itself, on this machine (the Off the Grid quest).
LOCAL_RUNTIMES = {"ollama", "llamafile", "koboldcpp", "lms", "lm studio", "lm-studio", "jan", "localai",
                  "local-ai", "gpt4all", "tabby", "mistralrs-server", "mlc_llm", "tgi", "sglang"}
LOCAL_PREFIXES = ("ollama", "llama-", "llama.cpp", "vllm", "koboldcpp", "whisper-", "text-generation")
INTERPRETERS = {"node", "python", "python3", "bun", "deno"}


def agent_name(comm, pid=None):
    """The agent/model name a process belongs to, or None."""
    c = comm.lower()
    if c in AGENT_NAMES or c.startswith(AGENT_PREFIXES):
        return c.split("_")[0] if c.startswith("ollama") else c
    # newer Node names its main thread "node-MainThread"; python may be python3.14
    if pid is not None and (c in INTERPRETERS or c.startswith(("node-", "python3.", "bun-"))):
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                argv = f.read().split(b"\0")
        except OSError:
            return None
        for a in argv[1:3]:   # `node /path/gemini`, `python -m aider`, `python3 /usr/bin/aider`
            b = os.path.basename(a.decode("utf-8", "replace")).lower()
            for suffix in (".js", ".mjs", ".py"):
                b = b[:-len(suffix)] if b.endswith(suffix) else b
            if b in AGENT_NAMES or b.startswith(AGENT_PREFIXES):
                return b
    return None


def is_local_runtime(name):
    return name in LOCAL_RUNTIMES or name.startswith(LOCAL_PREFIXES)


def agent_scan():
    """({running agent/model names}, CPU ticks of agent CLIs, CPU ticks of local model runtimes)."""
    names, total, local = set(), 0, 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % pid) as f:
                st = f.read()
        except OSError:
            continue
        name = agent_name(st[st.find("(") + 1:st.rfind(")")], pid)
        if name:
            names.add(name)
            parts = st[st.rfind(")") + 2:].split()
            ticks = int(parts[11]) + int(parts[12])
            if is_local_runtime(name):
                local += ticks
            else:
                total += ticks
    return names, total, local


def processes():
    try:
        out = subprocess.run([tool("ps"), "-eo", "comm="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {l.strip().lower() for l in out.splitlines()}


def hyprctl_json(*args):
    try:
        return json.loads(subprocess.run([tool("hyprctl"), *args, "-j"], capture_output=True,
                                         text=True, timeout=5).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def focus_state():
    """(focused window class lowercase, cursor position)."""
    aw = hyprctl_json("activewindow")
    cur = hyprctl_json("cursorpos")
    return (str(aw.get("class", "")).lower() if isinstance(aw, dict) else "",
            (cur.get("x"), cur.get("y")) if isinstance(cur, dict) else None)


def disk_written_bytes():
    total = 0
    for line in read("/proc/diskstats").splitlines():
        f = line.split()
        if len(f) >= 10 and not f[2].startswith(("loop", "dm-", "ram", "zram", "sr")):
            total += int(f[9]) * 512
    return total


def net_received_bytes():
    total = 0
    for line in read("/proc/net/dev").splitlines():
        if ":" in line and line.split(":")[0].strip() != "lo":
            total += int(line.split(":")[1].split()[0])
    return total


def dir_size(path):
    total = 0
    try:
        for e in os.scandir(path):
            try:
                total += e.stat().st_size if e.is_file() else dir_size(e.path)
            except OSError:
                pass
    except OSError:
        pass
    return total


def git_repos():
    globs = config().get("repos") or DEFAULT_REPO_GLOBS
    found = set()
    for pattern in globs if isinstance(globs, list) else []:
        if isinstance(pattern, str):
            for g in glob.glob(os.path.join(os.path.expanduser(pattern), ".git")):
                found.add(os.path.dirname(g))
    return sorted(found)


def mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0


def git_commit_count(repo):
    try:
        out = subprocess.run([tool("git"), "-C", repo, "rev-list", "--count", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def git_head_numstat(repo):
    """(added, modified, deleted, paths) for the HEAD commit (paths: the first 500 file paths)."""
    try:
        out = subprocess.run([tool("git"), "-C", repo, "show", "--numstat", "--format=", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return 0, 0, 0, []
    a = m = d = 0
    paths = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and len(paths) < 500:
            paths.append(parts[2])
        if len(parts) != 3 or parts[0] == "-" or parts[1] == "-":
            continue
        add, dele = int(parts[0]), int(parts[1])
        if dele > 0 and add == 0:
            d += 1
        elif add > 0 and dele == 0:
            a += 1
        else:
            m += 1
    return a, m, d, paths


HISTORY = [os.path.join(HOME, p) for p in
           (".bash_history", ".zsh_history", ".local/share/fish/fish_history")]


class HistoryTail:
    """New lines appended to the shell history files since the last call.
    Bash writes history on exit unless PROMPT_COMMAND runs `history -a`."""
    def __init__(self):
        self.pos = {p: self._size(p) for p in HISTORY}

    @staticmethod
    def _size(p):
        try:
            return os.path.getsize(p)
        except OSError:
            return 0

    def new_commands(self):
        cmds = []
        if config().get("shellHistory") is False:     # on by default; config "shellHistory": false turns it off
            return cmds
        for p in HISTORY:
            size = self._size(p)
            if size > self.pos[p]:
                try:
                    with open(p, "rb") as f:
                        f.seek(max(self.pos[p], size - HISTORY_CHUNK_MAX))   # bounded: only the newest 1 MB
                        chunk = f.read(HISTORY_CHUNK_MAX).decode("utf-8", "replace")
                except OSError:
                    chunk = ""
                for line in chunk.splitlines():
                    line = line.strip()
                    if p.endswith("zsh_history"):
                        line = line.split(";", 1)[-1]
                    elif p.endswith("fish_history"):
                        if not line.startswith("- cmd: "):
                            continue
                        line = line[7:]
                    if line and not line.startswith("#"):
                        cmds.append(line)
            self.pos[p] = size  # also resyncs after bash truncates to HISTFILESIZE
        return cmds


SEARCH = re.compile(r"^(sudo\s+)?(find|rg|grep|fd|fzf|locate|ag)\b")
# Building: builds, compiles and test runs (checked before SCRIPT, which they'd also match).
COOK = re.compile(r"^(sudo\s+)?(make|cmake|ninja|meson|makepkg|gcc|g\+\+|clang\+?\+?|rustc|javac|tsc"
                  r"|cargo\s+(build|run|test|check)|go\s+(build|test)|(npm|pnpm|yarn|bun)\s+(run|install|ci|test|build)"
                  r"|pytest|docker\s+build|zig\s+build)\b")
SCRIPT = re.compile(r"^(sudo\s+)?(python3?|node|npm|bash|sh|make|cargo|go\s+run|\./)")
# Cleanup: burning what you don't need.
BURN = re.compile(r"^(sudo\s+)?(rm|rmdir|shred|trash|trash-put|trash-empty|gio\s+trash|paccache"
                  r"|(pacman|yay|paru)\s+-S(c|cc)\b|journalctl\s+--vacuum|git\s+(clean|gc|prune)"
                  r"|docker\s+(system\s+|image\s+|container\s+)?prune|omarchy-cleanup)\b")
# Remote: voyages to other machines and remotes.
SAIL = re.compile(r"^(sudo\s+)?(ssh|scp|sftp|rsync|mosh|git\s+(push|pull|fetch|clone)|gh\s+repo\s+clone)\b")


def command_events(cmds):
    ev = collections.Counter()
    for c in cmds:
        words = c.split()
        if words and words[0] == "sudo":
            words = words[1:]
        if not words:
            continue
        ev["cmd"] += 1
        ev["cmd:" + words[0].lower()] += 1
        if len(words) > 1:
            ev["cmd2:" + " ".join(words[:2]).lower()] += 1
        # later commands in a pipeline or chain count too: `history | awk ...` uses awk
        for seg in re.split(r"\s*(?:\|\||&&|\||;)\s*", c)[1:]:
            w = seg.split()
            if w and w[0] == "sudo":
                w = w[1:]
            if w:
                ev["cmd:" + w[0].lower()] += 1
                if len(w) > 1:
                    ev["cmd2:" + " ".join(w[:2]).lower()] += 1
        if SEARCH.match(c):
            ev["search"] += 1
        elif COOK.match(c):
            ev["cook"] += 1
        elif SCRIPT.match(c):
            ev["script"] += 1
        elif BURN.match(c):
            ev["burn"] += 1
        elif SAIL.match(c):
            ev["sail"] += 1
        if words[0].startswith("omarchy-reminder") or words[:2] == ["omarchy", "reminder"]:
            ev["reminder"] += 1
    return ev


HISTORY_CHUNK_MAX = 1 << 20


def pacman_counts():
    """Installs and upgrades in pacman's log, streamed line by line (never loaded whole)."""
    inst = upg = 0
    try:
        with open("/var/log/pacman.log", "rb") as f:
            for line in f:
                if b"] installed " in line:
                    inst += 1
                elif b"] upgraded " in line:
                    upg += 1
    except OSError:
        pass
    return inst, upg


def chromium_visits():
    """Number of visits in Chromium's history (a count only: no URLs or titles are read).
    Opt-in: config "browserHistory": true. Opened read-only and immutable, so a running
    browser's lock is never touched."""
    if not config().get("browserHistory"):
        return 0
    import sqlite3
    hits = 0
    for prof in glob.glob(os.path.join(HOME, ".config/chromium/*/History")):
        try:
            con = sqlite3.connect("file:%s?mode=ro&immutable=1" % urllib_request.quote(prof), uri=True, timeout=2)
            try:
                hits += int(con.execute("SELECT count(*) FROM visits").fetchone()[0])
            finally:
                con.close()
        except (sqlite3.Error, ValueError, TypeError):
            pass
    return hits


def browser_history_mtime():
    return max([mtime(p) for p in glob.glob(os.path.join(HOME, ".config/chromium/*/History"))] or [0])


def theme_name():
    return read(os.path.join(HOME, ".local/state/omarchy/current/theme.name")).strip()


# Config folders whose saves train Theming (bounded walk; plugin code and backups are skipped).
CONFIG_WATCH = ("hypr", "omarchy", "alacritty", "ghostty", "kitty", "foot", "nvim", "tmux", "fish",
                "starship.toml", "mise", "btop", "fastfetch")
CONFIG_SKIP = ("plugins", "backups", "archive", "cache", ".git")


def config_mtimes(limit=3000):
    """{path: mtime} for the files in the watched config folders (depth 3, at most `limit` files)."""
    out = {}
    stack = [(os.path.join(CONFIG_HOME, n), 0) for n in CONFIG_WATCH]
    while stack and len(out) < limit:
        path, depth = stack.pop()
        try:
            st = os.lstat(path)
        except OSError:
            continue
        import stat as _stat
        if _stat.S_ISREG(st.st_mode):
            if not path.endswith((".bak", ".tmp", "~", ".swp", "lazy-lock.json")) and ".bak" not in os.path.basename(path):
                out[path] = st.st_mtime
        elif _stat.S_ISDIR(st.st_mode) and depth < 3:
            try:
                names = os.listdir(path)
            except OSError:
                continue
            stack += [(os.path.join(path, n), depth + 1) for n in names if n not in CONFIG_SKIP]
    return out


def screenshots():
    return set(glob.glob(os.path.join(HOME, "Pictures/screenshot-*")))


# ----------------------------------------------- live watchers (threads)
class Events:
    """Thread-safe counter the watchers feed and each tick drains."""
    def __init__(self):
        self.c, self.lock = collections.Counter(), threading.Lock()

    def add(self, key, n=1):
        with self.lock:
            self.c[key] += n

    def drain(self):
        with self.lock:
            out, self.c = self.c, collections.Counter()
        return out


HYPR_EVENTS = {   # socket2 event -> our event key (kb: = a keybind-driven action)
    "workspace": "ws_switch", "openwindow": "win_open", "closewindow": "win_close",
    "activewindowv2": "focus", "changefloatingmode": "kb:float", "activespecial": "kb:scratchpad",
    "togglegroup": "kb:group", "pin": "kb:pin", "movewindow": "kb:movewindow",
}


def watch_hyprland(ev):
    """Count window-management events from Hyprland's event socket."""
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    path = os.path.join(RUNTIME, "hypr", sig, ".socket2.sock")
    while True:
        try:
            s = socket.socket(socket.AF_UNIX)
            s.connect(path)
            buf = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
                *lines, buf = buf.split(b"\n")
                for line in lines:
                    name, _, arg = line.decode("utf-8", "replace").partition(">>")
                    if name == "fullscreen":
                        if arg.strip() == "1":
                            ev.add("kb:fullscreen")
                    elif name == "activespecial":
                        if arg.split(",")[0]:          # entering a special workspace
                            ev.add("kb:scratchpad")
                    elif name == "openlayer" and arg.startswith("omarchy-") and \
                            not arg.endswith("-dismiss") and \
                            arg not in ("omarchy-bar", "omarchy-dock", "omarchy-background"):
                        ev.add("layer:" + arg)
                    elif name in HYPR_EVENTS:
                        ev.add(HYPR_EVENTS[name])
        except OSError:
            pass
        time.sleep(5)   # Hyprland restarting, or socket missing: retry


# Omarchy commands the shell or scripts run for status, not because you pressed anything.
NOT_ACTIONS = {"capture:webcam-list", "capture:webcam-resize", "toggle:enabled"}


def classify_command(argv):
    """An Omarchy keybind command line -> event key, or None."""
    key = _classify(argv)
    return None if key in NOT_ACTIONS else key


def _classify(argv):
    if not argv:
        return None
    exe = os.path.basename(argv[0])
    args = argv[1:]
    if exe in ("bash", "sh") and args:          # `bash /usr/bin/omarchy-foo`
        exe, args = os.path.basename(args[0]), args[1:]
    if exe == "omarchy-menu-keybindings" or (exe == "omarchy-menu" and args[1:2] == ["keybindings"]):
        return "keybindings"
    if exe == "omarchy-menu":
        return "menu:" + (args[1] if len(args) > 1 else "root")
    if exe == "omarchy-shell" and args[:2] == ["shell", "toggle"] and len(args) > 2:
        if args[2] == "omarchy.menu":
            route = re.search(r'"menu"\s*:\s*"([^"]+)"', " ".join(args[3:]))
            return "menu:" + (route.group(1) if route else "root")
        return "panel:" + args[2]
    if exe.startswith("omarchy-toggle-"):
        return "toggle:" + exe[len("omarchy-toggle-"):]
    if exe.startswith("omarchy-hyprland-window-"):
        return "window:" + exe[len("omarchy-hyprland-window-"):]
    if exe.startswith("omarchy-capture-"):
        return "capture:" + exe[len("omarchy-capture-"):]
    if exe == "voxtype" and args[:1] == ["record"]:
        return "capture:text-dictation"
    if exe == "omarchy-reminder":
        return "reminder"
    if exe == "omarchy-update" or (exe == "omarchy" and args[:1] == ["update"]):
        return "update"
    if exe in ("omarchy-theme-bg-next", "omarchy-theme-bg-set", "omarchy-theme-bg-switcher"):
        return "wallpaper"
    return None


def watch_processes(ev):
    """Catch Omarchy's short-lived keybind commands (they live ~0.15-0.4 s) by
    checking /proc for new pids six times a second. Only command names are read."""
    seen = set(os.listdir("/proc"))
    while True:
        time.sleep(1 / 6.0)
        try:
            now = set(os.listdir("/proc"))
        except OSError:
            continue
        for pid in now - seen:
            if not pid.isdigit():
                continue
            try:
                with open("/proc/%s/cmdline" % pid, "rb") as f:
                    argv = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
            except OSError:
                continue
            key = classify_command(argv)
            if key:
                ev.add(key)
                if key not in ("reminder", "update", "wallpaper"):
                    ev.add("kb:" + key)
        seen = now


def maybe_random_event(data_meta_t, rng=random):
    if time.time() - data_meta_t < RANDOM_COOLDOWN or rng.random() >= RANDOM_CHANCE:
        return None
    return rng.choices(RANDOM_EVENTS, weights=[e[4] for e in RANDOM_EVENTS])[0]


def apply_random_event(event):
    eid, title, msg, kind, _ = event
    res = None
    with _Lock():
        data = load()
        data["meta"]["lastRandom"] = int(time.time())
        collect(data, "random:" + eid)
        if kind == "signal" and data["signal"]:
            kind = "token"
            msg += " (You already have a signal, so it's an XP token instead.)"
        if kind == "token":
            data["tokens"].append({"kind": "courier", "from": title, "t": int(time.time())})
        elif kind == "signal":
            _start_clue(data, random.choice(["easy", "medium", "medium", "hard"]))
            msg += " A %s signal: %s" % (data["signal"]["tier"], SIGNAL_BY_ID[data["signal"]["steps"][0]][1])
        save(data)
    if kind == "xp_random":
        key = random.choice(SKILL_KEYS)
        res = grant({key: 5 * level_for_xp(load()["xp"][key]) + 20}, why=title, token_drop=True)
    elif kind == "xp_focus":
        res = grant({"focus": 10 * level_for_xp(load()["xp"]["focus"]) + 50}, why=title, token_drop=True)
    notify(title, msg)
    print("RANDOM %s" % eid)
    if res:
        announce(res)


def maybe_star(rng=random):
    """Overclocks: one skill runs at double XP for SURGE_MINUTES, then cools down."""
    now = int(time.time())
    msg = None
    with _Lock():
        data = load()
        st = data.get("surge")
        if st and st["until"] <= now and not st.get("ended"):
            st["ended"] = now
            save(data)
            msg = ("Overclock over", "It gave you +%d extra %s XP."
                   % (st.get("xp", 0), SKILL_BY_KEY[st["skill"]][1]))
        elif not surge_active(data, now) and now - data["meta"].get("lastSurge", 0) >= SURGE_COOLDOWN \
                and rng.random() < SURGE_CHANCE:
            skill = rng.choice(SURGE_SKILLS)
            data["surge"] = {"skill": skill, "landed": now, "until": now + SURGE_MINUTES * 60, "xp": 0}
            data["meta"]["lastSurge"] = now
            collect(data, "surge")
            save(data)
            name = SKILL_BY_KEY[skill][1]
            msg = ("Overclock: %s" % name, "%s XP is doubled for the next %d minutes."
                   % (name, SURGE_MINUTES))
    if msg:
        notify(*msg)
        print("OVERCLOCK %s" % msg[1])


def daily_wom():
    """The Sysop sets one challenge a day, announced the first active minute."""
    with _Lock():
        data = load()
        w = data.get("sysop")
        if w and w.get("day") == today():
            return
        w = sysop_today(data)
        save(data)
    _, task, hint, _, reward, _ = SYSOP_BY_ID[w["id"]]
    notify("The Sysop", "Today's challenge: %s.\nTry: %s  (%s XP)"
           % (task, hint, ", ".join("%d %s" % (v, SKILL_BY_KEY[k][1]) for k, v in reward.items())))


def cmd_surge(argv):
    data = load()
    st = surge_active(data)
    if st:
        print("Overclock on %s: XP doubled for %s more (+%d extra so far)."
              % (SKILL_BY_KEY[st["skill"]][1], fmt_dur(st["until"] - time.time()), st.get("xp", 0)))
    else:
        last = data["meta"].get("lastSurge", 0)
        print("No overclock right now. %s" % ("The last one started %s ago." % fmt_dur(time.time() - last)
                                              if last else "Overclocks start a few times a day while you're active."))


def cmd_sysop(argv):
    if argv and argv[0] == "explain":
        return cmd_sysop_explain()
    with _Lock():
        data = load()
        w = sysop_today(data)
        save(data)
    _, task, hint, _, reward, _ = SYSOP_BY_ID[w["id"]]
    print("The Sysop's challenge for today%s:\n  %s\n  Try: %s\n  Reward: %s" % (
        " (done!)" if w.get("done") else "", task, hint,
        ", ".join("%d %s XP" % (v, SKILL_BY_KEY[k][1]) for k, v in reward.items())))


def cmd_collection(argv):
    data = load()
    col = data["collection"]
    companions = _companion_log(data)
    print("COLLECTION")
    print("Companions %d / %d" % (sum(p["owned"] for p in companions), len(companions)))
    for p in companions:
        print("  [%s] %-14s hatches at %s %d" % ("x" if p["owned"] else " ", p["name"], p["skillName"], p["level"]))
    marks = [k for k in data["badges"] if k in SKILL_BY_KEY]
    print("Mastery marks %d / %d%s" % (len(marks), len(SKILL_KEYS), ("  (" + ", ".join(SKILL_BY_KEY[k][1] for k in marks) + ")") if marks else ""))
    print("Theme stamps %d · relics %d / %d" % (len(data["stamps"]), len(data["relics"]), len(RELICS)))
    print("Caches  easy %d · medium %d · hard %d" % tuple(col.get("cache:" + t, 0) for t in ("easy", "medium", "hard")))
    print("Random events  " + " · ".join("%s %d" % (e[1], col.get("random:" + e[0], 0)) for e in RANDOM_EVENTS))
    print("Overclocks %d · Update Days %d · Sysop challenges %d"
          % (col.get("surge", 0), col.get("update_day", 0), col.get("sysop", 0)))


TRAINING_RATES = {  # skill -> [(activity, rate text)] for guides; values come from RATES
    "focus": [("Being at the computer", "%(focus_tick)d XP / 30 s"), ("A game focused", "+%(focus_game_min)d XP / min")],
    "workload": [("CPU time used while you're active", "%(workload_cpu_s)d XP / CPU-second"),
                 ("Data written to disk", "%(workload_mb)d XP / MB"), ("Finished jobs (omalvl collect)", "30 + 6 / min")],
    "browsing": [("Web pages visited (opt-in)", "%(browsing_visit)d XP each")],
    "shell": [("Omarchy keybind actions", "%(shell_kb)d XP each"), ("Ordinary shell commands", "%(shell_cmd)d XP each"),
              ("Keybind tree ranks", "100 / 300 / 1,000")],
    "tiling": [("Workspace switches", "%(tiling_ws)d XP each"), ("Window focus changes", "%(tiling_focus)d XP each"),
               ("Windows closed", "%(tiling_close)d XP each")],
    "theming": [("Theme switches", "%(theming_theme)d XP each"), ("Background changes", "%(theming_bg)d XP each"),
                ("Config files saved (hypr, omarchy, terminals ...)", "%(theming_edit)d XP each"),
                ("Theme stamps and dotfile relics", "300 / 600")],
    "packages": [("Packages installed", "%(packages_pkg)d XP each"), ("Packages upgraded", "%(packages_upg)d XP each")],
    "downloads": [("Downloads collected", "%(downloads_mb)d XP / MB"), ("Data received", "%(downloads_net_mb)d XP / MB")],
    "building": [("Builds (make, cargo, npm run ...)", "%(building_build)d XP each"), ("A compiler running", "%(building_tick)d XP / 30 s")],
    "editing": [("Files added in a commit", "%(editing_added)d XP each"), ("Files changed", "%(editing_file)d XP each"),
                ("Files removed", "%(editing_removed)d XP each")],
    "cleanup": [("Clean-ups (rm, trash, cache purges)", "%(cleanup_burn)d XP each")],
    "scripting": [("Scripts run", "%(scripting_script)d XP each")],
    "agents": [("AI agent CLIs working", "%(agents_cpu_s)d XP / CPU-second")],
    "models": [("Local model runtimes working", "%(models_cpu_s)d XP / CPU-second")],
    "commits": [("Git commits", "%(commits_commit)d XP each")],
    "searching": [("Searches (rg, fd, grep, find)", "%(searching_search)d XP each")],
    "remote": [("Remote trips (push, pull, ssh, rsync)", "%(remote_trip)d XP each")],
}


def skill_guide(key, data=None):
    """The skill guide for one skill: XP, pace, how to train it, and what each level unlocks."""
    data = data or load()
    xp = data["xp"][key]
    lvl = level_for_xp(xp)
    rate = int(data.get("rates", {}).get(key, 0))
    need, span = xp_to_next(xp)
    rows = []   # (level, kind, text)
    for qid, name, *_ in QUESTS:
        lv = QUEST_REQS.get(qid, {}).get(key)
        if lv:
            rows.append((lv, "quest", "Quest: %s" % name))
    for cid, task, hint, cond, reward, req in SYSOP_CHALLENGES:
        if SYSOP_REQS.get(cid, ("", 0))[0] == key:
            rows.append((SYSOP_REQS[cid][1], "challenge", "Sysop: %s" % task))
    for pid, name, skill, lv in COMPANIONS:
        if skill == key:
            rows.append((lv, "companion", "Companion: %s hatches" % name))
    if key in SURGE_SKILLS:
        rows.append((1, "surge", "Overclocks can land on %s" % SKILL_BY_KEY[key][1]))
    rows += [(HALFWAY, "milestone", "Halfway to 100 (%s XP)" % format(LEVEL_XP[HALFWAY], ",")),
             (MAX_LEVEL, "badge", "%s mastery mark" % SKILL_BY_KEY[key][1])]
    rows.sort(key=lambda r: (r[0], r[1]))
    return {
        "key": key, "name": SKILL_BY_KEY[key][1], "xp": xp, "level": lvl, "area": AREA_BY_ID[AREA_OF[key]][1],
        "toNext": need, "rate": rate, "eta": int(need / rate * 3600) if rate and need else 0,
        "toMax": max(0, MAX_XP - xp), "hoursToMax": round((MAX_XP - xp) / rate, 1) if rate and xp < MAX_XP else 0,
        "training": [{"what": a, "xp": r % RATES} for a, r in TRAINING_RATES.get(key, [])],
        "unlocks": [{"level": lv, "kind": kind, "text": t, "met": lvl >= lv} for lv, kind, t in rows],
    }


def cmd_guide(argv):
    key = skill_key(argv[0]) if argv else None
    if not key:
        print("usage: omalvl guide <skill> [--json]", file=sys.stderr)
        return 2
    g = skill_guide(key)
    if "--json" in argv:
        print(json.dumps(g))
        return 0
    print("%s (%s)  level %d  ·  %s XP  ·  %s to level %d" % (
        g["name"], g["area"], g["level"], "{:,}".format(g["xp"]), "{:,}".format(g["toNext"]),
        min(MAX_LEVEL, g["level"] + 1)))
    if g["rate"]:
        print("Pace: %s XP/hr · next level in %s · 100 in %s active hours" % (
            "{:,}".format(g["rate"]), fmt_dur(g["eta"]), "{:,}".format(g["hoursToMax"])))
    print("Training:")
    for t in g["training"]:
        print("  %-42s %s" % (t["what"], t["xp"]))
    print("Unlocks:")
    for u in g["unlocks"]:
        print("  [%s] %3d  %s" % ("x" if u["met"] else " ", u["level"], u["text"]))


def cmd_wiki(argv):
    """Rebuild the offline OmaLvL wiki from this game's data and open it."""
    import wiki
    path, n = wiki.build()
    print("OmaLvL wiki: %d pages -> %s" % (n, path))
    if "--no-open" not in argv:
        subprocess.Popen([tool("xdg-open"), path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- job runs
JOB_DIR = os.path.join(os.path.dirname(STATE), "jobs")


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:   # a finished child of a dead parent can linger as a zombie: not alive
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


def cmd_run(argv):
    """omalvl run <command...>  |  omalvl run --pid <pid> [label]"""
    if not argv:
        print("usage: omalvl run <command...>   (a long job: a build, a download, local-llm ...)\n"
              "       omalvl run --pid <pid> [label]   (watch something already running)", file=sys.stderr)
        return 2
    os.makedirs(JOB_DIR, exist_ok=True)
    with _Lock():
        data = load()
        used = {p["slot"] for p in data["jobs"]}
        free = [s for s in JOB_SLOTS if s not in used]
        if not free:
            print("All four job slots are in use. Collect one first (omalvl collect).")
            return 1
        slot, stamp = free[0], int(time.time())
        base = os.path.join(JOB_DIR, "%s-%d" % (slot.lower(), stamp))
        if argv[0] == "--pid":
            pid, label = int(argv[1]), " ".join(argv[2:]) or "pid %s" % argv[1]
            if not _alive(pid):
                print("No process %d is running." % pid)
                return 1
            exitf = None
        else:
            label = " ".join(argv)
            exitf = base + ".exit"
            with open(base + ".log", "w") as log:
                # the user's own command runs in a shell (it is theirs to type); our paths are arguments
                proc = subprocess.Popen([tool("sh"), "-c", '/usr/bin/sh -c "$1"; echo $? > "$2"', "omalvl-job",
                                         label, exitf],
                                        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        start_new_session=True, cwd=os.getcwd())
            pid = proc.pid
        data["jobs"].append({"slot": slot, "cmd": label, "planted": stamp, "pid": pid,
                                "exitFile": exitf, "log": base + ".log" if exitf else None,
                                "done": None, "exit": None})
        save(data)
    print("Queued %s in job slot %s. Collect it with omalvl collect when it's done."
          % ("'%s'" % label, slot))


def check_jobs():
    """Daemon: notice jobs that finished (or failed)."""
    ready = []
    with _Lock():
        data = load()
        changed = False
        for p in data["jobs"]:
            if p["done"]:
                continue
            if p["exitFile"] and os.path.exists(p["exitFile"]):
                try:
                    p["exit"] = int(open(p["exitFile"]).read().strip() or 0)
                except (OSError, ValueError):
                    p["exit"] = 0
            elif _alive(p["pid"]):
                continue
            p["done"] = int(time.time())
            changed = True
            ready.append(p)
        if changed:
            save(data)
    for p in ready:
        if p.get("exit"):
            notify("Job slot %s" % p["slot"], "'%s' failed with exit %d." % (p["cmd"][:60], p["exit"]))
        else:
            notify("Job slot %s" % p["slot"], "'%s' finished. Collect it: omalvl collect" % p["cmd"][:60])


def job_xp(p):
    mins = max(0, (p["done"] - p["planted"]) / 60)
    xp = min(HARVEST_MAX, HARVEST_BASE + HARVEST_PER_MIN * mins)
    return int(xp * DEAD_SHARE) if p.get("exit") else int(xp)


def cmd_collect(argv):
    want = argv[0].title() if argv else None
    with _Lock():
        data = load()
        ripe = [p for p in data["jobs"] if p["done"] and (not want or p["slot"] == want)]
        if not ripe:
            growing = [p["slot"] for p in data["jobs"] if not p["done"]]
            print("Nothing to collect yet." + (" Still running: %s." % ", ".join(growing) if growing else ""))
            return 0
        data["jobs"] = [p for p in data["jobs"] if p not in ripe]
        for p in ripe:
            collect(data, "job:failed" if p.get("exit") else "job")
        save(data)
    total = sum(job_xp(p) for p in ripe)
    res = grant({"workload": total}, why="jobs collected: " + ", ".join(p["slot"] for p in ripe), token_drop=True)
    for p in ripe:
        print(("Cleared the failed job in slot %s: +%d Workload XP." if p.get("exit")
               else "Collected slot %s: +%d Workload XP.") % (p["slot"], job_xp(p)))
    announce(res)


def cmd_jobs(argv):
    data = load()
    if not data["jobs"]:
        print("All four job slots are empty. Queue one: omalvl run <long command>")
    for p in data["jobs"]:
        state = ("failed (exit %d)" % p["exit"] if p.get("exit") else "ready to collect") if p["done"] \
            else "running for %s" % fmt_dur(time.time() - p["planted"])
        print("%-10s %-18s %s" % (p["slot"], state, p["cmd"][:70]))


# ---------------------------------------------------------------- daily streak
def daily_streak():
    """First active minute of the day: continue or restart the streak and pay the day's bonus."""
    with _Lock():
        data = load()
        st = data["streak"]
        if st["day"] == today():
            return
        yesterday = today(time.time() - 86400)
        st["count"] = st["count"] + 1 if st["day"] == yesterday else 1
        st["best"] = max(st["best"], st["count"])
        st["day"] = today()
        pool = [k for k in SKILL_KEYS if k not in PASSIVE]
        skill = pool[datetime.date.today().toordinal() % len(pool)]
        token = STREAK_TOKENS.get(st["count"])
        if token:
            data["tokens"].append({"kind": "fixed", "xp": token, "from": "%d-day streak" % st["count"],
                                  "t": int(time.time())})
            collect(data, "streak_lamp")
        count = st["count"]
        save(data)
    xp = STREAK_XP * min(count, STREAK_CAP_DAYS)
    res = grant({skill: xp}, why="daily streak: day %d" % count, token_drop=True)
    notify("Daily streak: day %d" % count, "Welcome back. +%d %s XP (today's skill)%s"
           % (xp, SKILL_BY_KEY[skill][1],
              ". A %d-day streak earns an XP token worth %d XP!" % (count, token) if token else "."))
    announce(res)


# ---------------------------------------------------------------- sysop x local AI
LLM_URL = "http://127.0.0.1:8080"


def _llm_up():
    try:
        urllib_request.urlopen(LLM_URL + "/health", timeout=2).read()
        return True
    except Exception:
        return False


def _reference(hint):
    """Local, real documentation for a challenge's command: its tldr page (cached, short and
    exact; `git log` -> git-log), else --help, else the man page."""
    words = [w for w in hint.split() if not w.startswith("-")]
    cmd = words[0] if words else hint
    tries = []
    if shutil.which("tldr"):
        if len(words) > 1 and words[1].isalpha():
            tries.append(["tldr", "%s-%s" % (cmd, words[1])])
        tries.append(["tldr", cmd])
    tries += [[cmd, "--help"], ["man", "-P", "cat", cmd]]
    for argv in tries:
        if not shutil.which(argv[0]):
            continue
        try:
            out = subprocess.run([tool(argv[0])] + argv[1:], capture_output=True, text=True, timeout=20,
                                 env=dict(os.environ, MANWIDTH="80", COLUMNS="80", NO_COLOR="1"))
        except (OSError, subprocess.SubprocessError):
            continue
        text = re.sub(r"\x1b\[[0-9;]*m", "", out.stdout or "").strip()
        if out.returncode == 0 and len(text) > 80 and "usage: tldr" not in text:
            return "\n".join(text.splitlines()[:40])[:2500]
    return ""


def cmd_sysop_explain():
    """Ask the local model to explain today's challenge, grounded in the command's own docs."""
    with _Lock():
        data = load()
        w = sysop_today(data)
        save(data)
    cid, task, hint, cond, reward, req = SYSOP_BY_ID[w["id"]]
    cmd = (req or hint.split()[0]).strip()
    ref = _reference(hint) if shutil.which(cmd) else ""
    started = False
    if not _llm_up():
        if not shutil.which("local-llm"):
            print("No local model (install with local-llm). Try: %s --help" % cmd)
            return 1
        print("Starting the local model (2b, fast)...", flush=True)
        subprocess.run([tool("local-llm"), "serve", "2b"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started = _llm_up()
        if not started:
            print("The local model didn't start (see local-llm status).")
            return 1
    prompt = ("You are the Sysop, a friendly Linux tutor. Using ONLY the reference text below, explain in "
              "3 short sentences what `%s` does and why it is useful, then give one useful variation as a "
              "command. If the reference doesn't cover something, don't guess.\n\nReference for %s:\n%s"
              % (hint, cmd, ref or "(no local documentation found; keep it very general)"))
    body = json.dumps({"model": "local", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 220, "temperature": 0.3}).encode()
    try:
        req_ = urllib_request.Request(LLM_URL + "/v1/chat/completions", body, {"Content-Type": "application/json"})
        text = json.load(urllib_request.urlopen(req_, timeout=240))["choices"][0]["message"]["content"].strip()
    except Exception as e:
        text = ""
        print("The local model didn't answer: %r" % e)
    finally:
        if started:
            subprocess.run([tool("local-llm"), "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not text:
        return 1
    with _Lock():
        data = load()
        if data.get("sysop") and data["sysop"].get("id") == cid:
            data["sysop"]["explain"] = text
            data["sysop"]["explainSource"] = "local AI, from %s" % ("its docs" if ref else "general knowledge")
        save(data)
    print("The Sysop (local AI%s) says:\n%s" % (", from the command's own docs" if ref else "", text))


def maybe_weekly_report():
    """Sundays from 18:00: one notification + a text file per ISO week."""
    now = datetime.datetime.now()
    if now.weekday() != 6 or now.hour < 18:
        return
    week = "%d-W%02d" % now.isocalendar()[:2]
    with _Lock():
        data = load()
        if data["meta"].get("weekSent") == week:
            return
        data["meta"]["weekSent"] = week
        save(data)
    text = week_report()
    out = os.path.join(os.path.dirname(STATE), "weekly", week + ".txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(text + "\n")
    notify("Your week in Omarchy", text.split("\n", 1)[1] if "\n" in text else text)


TICK = 30
FLUSH = 120       # routine (passive) xp is saved at most this often; anything notable saves at once
QUIET_EVENTS = {"focus", "active_min", "game_min", "agent_work_min"}
CAP = 60          # max xp per tick for each continuous skill, and for Shell/Tiling actions
ACTIVE_IRQS = 15  # i8042 interrupts per tick that count as "at the computer"


def daemon():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    global DAEMON_LOCK
    DAEMON_LOCK = open(LOCK + ".daemon", "w")
    try:
        fcntl.flock(DAEMON_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return   # another copy (one per monitor) is already running
    with _Lock():
        save(load())   # rewrite once so the UI gets the current format
    live = Events()
    threading.Thread(target=watch_hyprland, args=(live,), daemon=True).start()
    threading.Thread(target=watch_processes, args=(live,), daemon=True).start()
    hist = HistoryTail()
    repos = {r: {"m": mtime(os.path.join(r, ".git/logs/HEAD")), "n": git_commit_count(r)}
             for r in git_repos()}
    _, cur = focus_state()
    procs = processes()
    prev = {
        "irq": input_irqs(), "cpu": cpu_busy_ticks(), "disk": disk_written_bytes(),
        "net": net_received_bytes(), "dl": dir_size(os.path.join(HOME, "Downloads")),
        "pac": pacman_counts(), "hm": browser_history_mtime(), "visits": chromium_visits(),
        "cur": cur, "theme": theme_name(), "shots": screenshots(),
        "procs": {p for p in procs if p in WATCH_PROCS},
        "agents": agent_scan()[0], "conf": config_mtimes(),
    }
    recent = collections.deque()   # (t, {skill: xp}) for xp/hr
    # Agents already running count once, so the AI Agents quest sees them.
    first = collections.Counter({"proc:" + p: 1 for p in prev["procs"]})
    first.update({"agent:" + a: 1 for a in prev["agents"]})
    first.update({"local_model:" + a: 1 for a in prev["agents"] if is_local_runtime(a)})
    pend_xp, pend_ev, pend_why, last_flush = collections.Counter(), collections.Counter(), [], 0.0
    recent_cmds = {}                   # command -> last time seen (anti-spam)
    while True:
        time.sleep(TICK)
        xp, why, events = {}, [], collections.Counter(first)
        first = collections.Counter()
        try:
            cls, cur = focus_state()
            irq = input_irqs()
            active = irq - prev["irq"] >= ACTIVE_IRQS or bool(cur and prev["cur"] and cur != prev["cur"])
            prev["irq"], prev["cur"] = irq, cur
            gaming = any(g in cls for g in games())
            events.update(live.drain())

            # --- continuous skills: only while someone is actually here
            c, d, n = cpu_busy_ticks(), disk_written_bytes(), net_received_bytes()
            if active or gaming:
                why.append("playing" if gaming else "at the computer")
                events["active_min"] += TICK / 60.0
                xp["focus"] = R["focus_tick"]
                xp["workload"] = (max(0, c - prev["cpu"]) / os.sysconf("SC_CLK_TCK") * R["workload_cpu_s"]
                                  + max(0, d - prev["disk"]) / 1048576 * R["workload_mb"])
                xp["downloads"] = max(0, n - prev["net"]) / 1048576 * R["downloads_net_mb"]
                tk = _theme_key(prev["theme"])
                if tk:
                    events["theme_min:" + tk] += TICK / 60.0
            prev["cpu"], prev["disk"], prev["net"] = c, d, n
            if gaming:
                xp["focus"] = xp.get("focus", 0) + TICK / 60.0 * R["focus_game_min"]
                events["game_min"] += TICK / 60.0

            # --- Hyprland + keybind actions (from the watcher threads)
            kb = events_match(events, "kb:")
            moves = events["ws_switch"] + events["focus"] * 0.5
            if kb:
                xp["shell"] = kb * R["shell_kb"]
                why.append("%d keybind action%s" % (kb, "" if kb == 1 else "s"))
            if moves:
                xp["tiling"] = events["ws_switch"] * R["tiling_ws"] + events["focus"] * R["tiling_focus"]
            if events["win_close"]:
                xp["tiling"] = xp.get("tiling", 0) + events["win_close"] * R["tiling_close"]
                why.append("closed %d window%s" % (events["win_close"], "" if events["win_close"] == 1 else "s"))

            # --- downloads
            dl = dir_size(os.path.join(HOME, "Downloads"))
            if dl - prev["dl"] >= 1048576:
                xp["downloads"] = xp.get("downloads", 0) + (dl - prev["dl"]) / 1048576 * R["downloads_mb"]
                why.append("downloads")
            prev["dl"] = dl

            for k in list(xp):
                xp[k] = min(R["tick_cap"], xp[k])

            # --- shell history
            cmds, now_t = [], time.time()
            for c in hist.new_commands():      # the same command again within 5 min earns nothing
                key = " ".join(c.split())
                if now_t - recent_cmds.get(key, 0) >= R["repeat_window"]:
                    cmds.append(c)
                recent_cmds[key] = now_t
            if len(recent_cmds) > 500:
                for k_ in [k_ for k_, t_ in recent_cmds.items() if now_t - t_ > R["repeat_window"]]:
                    del recent_cmds[k_]
            if cmds:
                ce = command_events(cmds)
                if ce.get("cmd2:omarchy update"):
                    ce["update"] += 1
                events.update(ce)
                plain = ce["cmd"] - ce["search"] - ce["script"] - ce["cook"] - ce["burn"] - ce["sail"]
                xp["shell"] = xp.get("shell", 0) + min(R["cmd_tick_cap"], plain * R["shell_cmd"])
                xp["searching"] = min(R["cmd_tick_cap"], ce["search"] * R["searching_search"])
                xp["scripting"] = min(R["cmd_tick_cap"], ce["script"] * R["scripting_script"])
                xp["building"] = xp.get("building", 0) + min(R["cmd_tick_cap"], ce["cook"] * R["building_build"])
                xp["cleanup"] = min(R["cmd_tick_cap"], ce["burn"] * R["cleanup_burn"])
                xp["remote"] = min(R["cmd_tick_cap"], ce["sail"] * R["remote_trip"])
                why.append("shell commands")

            # --- watched programs that started this tick
            procs = processes()
            watched = {p for p in procs if p in WATCH_PROCS}
            for p in watched - prev["procs"]:
                events["proc:" + p] += 1
            prev["procs"] = watched

            # --- Building: a compiler running this tick (catches builds agents start too)
            if procs & COOK_PROCS:
                xp["building"] = xp.get("building", 0) + R["building_tick"]
                events["cook_min"] += TICK / 60.0
            # --- Agents and Models: their CPU time is the work; idle agents earn nothing
            agents, at, lt = agent_scan()
            for a in agents - prev["agents"]:
                events["agent:" + a] += 1
                if is_local_runtime(a):
                    events["local_model:" + a] += 1
            prev["agents"] = agents
            hz = os.sysconf("SC_CLK_TCK")
            worked = max(0, at - prev.get("agent_cpu", at)) / hz
            ran = max(0, lt - prev.get("model_cpu", lt)) / hz
            prev["agent_cpu"], prev["model_cpu"] = at, lt
            if worked > 0.2:
                xp["agents"] = min(R["tick_cap"], worked * R["agents_cpu_s"])
                events["agent_cpu_s"] += worked
            if ran > 0.2:
                xp["models"] = min(R["tick_cap"], ran * R["models_cpu_s"])
                events["model_cpu_s"] += ran
            if worked + ran > 0.2:              # an agent or model did real work this tick
                events["agent_work_min"] += TICK / 60.0

            # --- pacman
            inst, upg = pacman_counts()
            di, du = inst - prev["pac"][0], upg - prev["pac"][1]
            if di > 0:
                xp["packages"] = min(R["packages_max"], di * R["packages_pkg"])
                events["pkg_install"] += di
                why.append("installed %d package%s" % (di, "" if di == 1 else "s"))
            if du > 0:
                xp["packages"] = xp.get("packages", 0) + min(R["packages_upg_max"], du * R["packages_upg"])
                events["pkg_upgrade"] += du
                why.append("upgraded %d package%s" % (du, "" if du == 1 else "s"))
            prev["pac"] = (inst, upg)

            # --- chromium (only re-read when the History db changed)
            hm = browser_history_mtime()
            if hm != prev["hm"]:
                v = chromium_visits()
                if v > prev["visits"]:
                    xp["browsing"] = min(R["tick_cap"], (v - prev["visits"]) * R["browsing_visit"])
                    events["visit"] += v - prev["visits"]
                    why.append("browsing")
                prev["visits"], prev["hm"] = v, hm

            # --- git commits anywhere under ~/Work (file xp capped per commit)
            for r in git_repos():
                st = repos.setdefault(r, {"m": 0, "n": git_commit_count(r)})
                m = mtime(os.path.join(r, ".git/logs/HEAD"))
                if m == st["m"]:
                    continue
                st["m"] = m
                cnt = git_commit_count(r)
                if cnt is not None and st["n"] is not None and cnt > st["n"]:
                    k = cnt - st["n"]
                    added, modified, deleted, paths = git_head_numstat(r)
                    xp["commits"] = xp.get("commits", 0) + k * R["commits_commit"]
                    xp["editing"] = xp.get("editing", 0) + min(R["file_max"], added * R["editing_added"]
                                                               + modified * R["editing_file"]
                                                               + deleted * R["editing_removed"])
                    events["commit"] += k
                    for rid in relic_paths(paths):
                        events["relic:" + rid] += 1
                    why.append("%d commit%s in %s" % (k, "" if k == 1 else "s", os.path.basename(r)))
                st["n"] = cnt

            # --- theme + screenshots
            theme = theme_name()
            if theme and prev["theme"] and theme != prev["theme"]:
                events["theme"] += 1
                xp["theming"] = xp.get("theming", 0) + R["theming_theme"]
                why.append("theme: " + theme)
            prev["theme"] = theme or prev["theme"]
            if events["wallpaper"]:
                xp["theming"] = xp.get("theming", 0) + events["wallpaper"] * R["theming_bg"]
            conf = config_mtimes()
            edited = sum(1 for path, m in conf.items() if m > prev["conf"].get(path, m))
            prev["conf"] = conf
            if edited:
                xp["theming"] = xp.get("theming", 0) + min(R["cmd_tick_cap"], edited * R["theming_edit"])
                events["config_edit"] += edited
                why.append("config edits")
            shots = screenshots()
            if shots - prev["shots"]:
                events["screenshot"] += len(shots - prev["shots"])
            prev["shots"] = shots
        except Exception as e:  # never die: the shell respawns us, but quietly
            print("skills daemon: %r" % e, file=sys.stderr)

        xp = {k: int(v) for k, v in xp.items() if v >= 1 and k in SKILL_BY_KEY}
        now = time.time()
        if xp:
            recent.append((now, xp))
        while recent and now - recent[0][0] > 3600:
            recent.popleft()
        span = max(600.0, min(3600.0, now - recent[0][0] + TICK)) if recent else 3600.0
        rates = collections.Counter()
        for _, g in recent:
            rates.update(g)
        rates = {k: int(v * 3600 / span) for k, v in rates.items()}

        try:
            data = load()
            if not data["contract"]["task"] and data["contract"]["day"] != today() and (active or gaming):
                with _Lock():
                    data = load()
                    text = _new_contract_task(data)
                    save(data)
                if text:
                    notify("Dispatcher", "New contract: %s." % text)
            pend_xp.update(xp)
            pend_ev.update(events)
            pend_why += [w for w in why if w not in pend_why]
            notable = bool(set(xp) - PASSIVE) or bool({k for k, v in events.items() if v} - QUIET_EVENTS)
            if (pend_xp or pend_ev) and (notable or now - last_flush >= FLUSH):
                announce(grant(dict(pend_xp), why=", ".join(pend_why) or "activity",
                               events=dict(pend_ev), rates=rates, boost=True))
                pend_xp, pend_ev, pend_why, last_flush = collections.Counter(), collections.Counter(), [], now
            if active and (ev := maybe_random_event(data["meta"].get("lastRandom", 0))):
                apply_random_event(ev)
            maybe_weekly_report()
            if active or gaming:
                maybe_star()
                daily_wom()
                daily_streak()
            check_jobs()
        except Exception as e:
            print("skills daemon: %r" % e, file=sys.stderr)


def main():
    cmd, argv = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("list", [])
    handlers = {
        "list": cmd_list, "stats": cmd_list, "add": cmd_add,
        "agent": lambda a: cmd_add(a, agent=True), "admin": cmd_admin, "task": cmd_task, "get": cmd_get,
        "total": lambda a: print(snapshot()["total"]), "state": lambda a: print(json.dumps(snapshot())),
        "panel-state": cmd_panel_state, "rice": cmd_rice,
        "quests": cmd_quests, "quest": cmd_quest, "contract": cmd_contract, "signal": cmd_signal,
        "token": cmd_token, "journal": cmd_diary, "diary": cmd_diary, "log": cmd_log, "week": cmd_week,
        "reset": cmd_reset, "backup": cmd_backup, "backups": cmd_backup, "restore": cmd_restore,
        "import": cmd_import, "icons": cmd_icons, "fair": cmd_fair,
        "daemon": lambda a: daemon(),
        "overclock": cmd_surge, "sysop": cmd_sysop, "challenge": cmd_sysop,
        "collection": cmd_collection, "companions": cmd_collection,
        "season": cmd_season, "stamps": cmd_season, "relics": cmd_relics, "tree": cmd_tree,
        "skin": cmd_skin, "skins": cmd_skin, "wallpaper": cmd_wallpaper,
        "wiki": cmd_wiki, "guide": cmd_guide,
        "run": cmd_run, "collect": cmd_collect, "jobs": cmd_jobs,
        "streak": lambda a: print("Daily streak: %(count)d day(s) · best %(best)d · last %(day)s" % load()["streak"]),
    }
    if cmd in ("-h", "--help", "help"):
        print("\n".join(__doc__.splitlines()[1:]))
        return 0
    if cmd not in handlers:
        print("unknown command: %s  (try: omalvl help)" % cmd, file=sys.stderr)
        return 2
    return handlers[cmd](argv)


def cmd_wallpaper(argv):
    import wallpaper
    out = None
    if "--out" in argv and argv.index("--out") + 1 < len(argv):
        out = os.path.expanduser(argv[argv.index("--out") + 1])
    path = wallpaper.render(snapshot(), out)
    print("Wallpaper: %s\nSet it as your background: omarchy-theme-bg-set %s" % (path, path))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
