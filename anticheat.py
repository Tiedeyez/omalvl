"""Fair play: OmaLvL never caps how fast a person levels by using the machine, but XP that
no real use backs up is voided. Everything here is local and explained in the wiki's
Fair play page and DISCLOSURE.md.

Two kinds of XP:

  measured    the daemon saw it happen (input, commits, builds...). Already paced by the
              per-tick caps in skills.RATES, so a human can't outrun it and neither can a bot,
              except by never stopping:
              * a person sleeps. If the machine reports activity for more than ACTIVE_DAY_MAX
                of the last 24 hours, measured XP is voided until the pattern breaks.

  unmeasured  awards from agents (`omalvl agent`), manual adds (`omalvl add`) and claimed
              tasks (`omalvl task`). Each one must be backed by real recent use:
              * the XP awarded in any 24 hours is at most BASE + PER_ACTIVE_MIN x active minutes
                in those hours (about 6,000 XP per active hour: a full day's real project
                easily fits; "max all my stats" does not);
              * a single award is at most MAX_SINGLE (the master tier);
              * at most BURST_SKILLS different skills in BURST_WINDOW (a sweep across every
                skill is the botting pattern, real work touches a few);
              * the same reason twice in DUP_DAYS is voided, and a reason must say something;
              * one award per skill per SAME_SKILL_GAP.

A voided award grants nothing; it is logged with its reason, counted on the account and
shown in the panel. Nothing is deleted or hidden.

Tamper evidence: every XP change is tallied by source. If a skill's XP stops matching
baseline + its tallies (the save was edited by hand), the account is marked unverified.
A save file on your own computer can always be edited; this makes it visible, not impossible.
"""
import time

BASE = 5_000
PER_ACTIVE_MIN = 100
MAX_SINGLE = 30_000
BURST_WINDOW = 15 * 60
BURST_SKILLS = 6
DUP_DAYS = 7
SAME_SKILL_GAP = 5 * 60
MIN_REASON = 12
ACTIVE_DAY_MAX = 20 * 60          # minutes of activity in 24 h before measured XP stops
DAY = 24 * 3600
KEEP_AWARDS = 400


def blank():
    return {"active": {}, "awards": [], "voided": 0, "voidedXp": 0, "sources": {}, "baseline": None,
            "measuredHold": False}


def _hour(t):
    return str(int(t // 3600))


def note_active(fair, minutes, now=None):
    """The daemon reports active minutes each tick; kept per hour for the last 48 hours."""
    now = now or time.time()
    h = _hour(now)
    fair["active"][h] = round(fair["active"].get(h, 0) + minutes, 2)
    cutoff = int(now // 3600) - 48
    for k in [k for k in fair["active"] if int(k) < cutoff]:
        del fair["active"][k]


def active_minutes(fair, seconds=DAY, now=None):
    now = now or time.time()
    first = int((now - seconds) // 3600)
    return sum(v for k, v in fair["active"].items() if int(k) >= first)


def measured_ok(fair, now=None):
    """False while the machine has been 'active' for more than ACTIVE_DAY_MAX in 24 h."""
    held = active_minutes(fair, DAY, now) > ACTIVE_DAY_MAX
    fair["measuredHold"] = held
    return not held


def _norm(reason):
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in reason).split())


def check_award(fair, skill, xp, reason, kind, now=None):
    """(ok, why_not) for one unmeasured award. Does not record it."""
    now = now or time.time()
    recent = [a for a in fair["awards"] if a["ok"]]
    if xp > MAX_SINGLE:
        return False, "more than %s XP in one award" % format(MAX_SINGLE, ",")
    r = _norm(reason or "")
    if kind == "agent" and len(r) < MIN_REASON:
        return False, "no real description of the work"
    if kind == "agent" and any(_norm(a.get("reason", "")) == r and now - a["t"] < DUP_DAYS * 86400
                               for a in recent if a["kind"] == "agent"):
        return False, "the same work was already awarded"
    if any(a["skill"] == skill and now - a["t"] < SAME_SKILL_GAP for a in recent):
        return False, "another award for this skill a moment ago"
    burst = {a["skill"] for a in recent if now - a["t"] < BURST_WINDOW} | {skill}
    if len(burst) > BURST_SKILLS:
        return False, "awards across %d skills in %d minutes" % (len(burst), BURST_WINDOW // 60)
    spent = sum(a["xp"] for a in recent if now - a["t"] < DAY)
    budget = BASE + PER_ACTIVE_MIN * active_minutes(fair, DAY, now)
    if spent + xp > budget:
        return False, "more than the last 24 hours of real use backs up (%s of %s XP)" % (
            format(int(spent + xp), ","), format(int(budget), ","))
    return True, ""


def record_award(fair, skill, xp, reason, kind, ok, why_not, now=None):
    fair["awards"].append({"t": int(now or time.time()), "skill": skill, "xp": int(xp), "kind": kind,
                           "reason": (reason or "")[:200], "ok": ok, "void": why_not})
    del fair["awards"][:-KEEP_AWARDS]
    if not ok:
        fair["voided"] += 1
        fair["voidedXp"] += int(xp)


def tally(fair, gains, source):
    for k, v in gains.items():
        s = fair["sources"].setdefault(k, {})
        s[source] = s.get(source, 0) + int(v)


def set_baseline(fair, xp):
    """Start (or restart) the books: the current XP is taken as given; changes from here are tallied."""
    fair["baseline"] = dict(xp)
    fair["sources"] = {}


def verify(fair, xp, cap):
    """Skills whose XP doesn't match baseline + tallied sources (the save was edited)."""
    base = fair.get("baseline")
    if base is None:
        return []
    bad = []
    for k, v in xp.items():
        expect = base.get(k, 0) + sum(fair["sources"].get(k, {}).values())
        if v != min(cap, expect):
            bad.append(k)
    return bad
