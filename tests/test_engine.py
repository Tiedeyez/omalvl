"""OmaLvL engine tests. Run: python3 -m unittest discover -s tests  (from the repo root)."""
import json
import os
import re
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="omalvl-test-")
os.environ["XDG_STATE_HOME"] = os.path.join(TMP, "state")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ.pop("OMALVL_OFFSITE", None)
sys.path.insert(0, ROOT)

import anticheat  # noqa: E402
import icons  # noqa: E402
try:
    import migrate  # noqa: E402  (local-only importer for the prototype save)
except ImportError:
    migrate = None
import pixelfont  # noqa: E402
import skills as S  # noqa: E402
import content as C  # noqa: E402
import wallpaper  # noqa: E402

SHIPPED = ["skills.py", "content.py", "glossary.py", "wiki.py", "icons.py", "pixelfont.py", "anticheat.py",
           "wallpaper.py", "Panel.qml", "manifest.json", "README.md", "DISCLOSURE.md", "bin/omalvl"]


def fresh():
    for p in (S.STATE, S.BACKUP):
        if os.path.exists(p):
            os.remove(p)
    S.save(S._blank(), allow_drop=True)


class Curve(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(S.level_for_xp(0), 1)
        self.assertEqual(S.LEVEL_XP[2], 101)
        self.assertEqual(S.MAX_XP, 10_000_000)
        self.assertEqual(S.level_for_xp(S.MAX_XP), 100)
        self.assertEqual(S.level_for_xp(S.MAX_XP - 1), 99)
        self.assertEqual(S.level_for_xp(10 ** 12), 100)
        self.assertEqual(S.MAX_TOTAL, 1700)
        self.assertTrue(all(S.LEVEL_XP[l] < S.LEVEL_XP[l + 1] for l in range(1, 100)))

    def test_rice_rating(self):
        d = S._blank()
        self.assertEqual(S.rice_info(d)["rating"], 10)
        self.assertEqual(S.rice_info(d)["rank"], "Fresh install")
        for k in S.SKILL_KEYS:
            d["xp"][k] = S.MAX_XP
        self.assertEqual(S.rice_info(d)["rating"], 1000)
        self.assertEqual(S.rice_info(d)["rank"], "Omarchist")

    def test_areas_cover_every_skill_once(self):
        keys = [k for a in S.AREAS for k in a[2]]
        self.assertEqual(sorted(keys), sorted(S.SKILL_KEYS))
        self.assertEqual(len(S.AREAS), 6)


class Content(unittest.TestCase):
    def test_icons_valid(self):
        self.assertEqual(icons.check(), [])
        for key in S.SKILL_KEYS:
            self.assertIn(key, icons.ICONS, key)
        for c in S.COMPANIONS:
            self.assertIn(c[0], icons.ICONS, c[0])

    def test_font_valid(self):
        self.assertEqual(pixelfont.check(), [])

    def test_content_names_real_skills(self):
        for q in C.QUESTS:
            for k in q[4]:
                self.assertIn(k, S.SKILL_BY_KEY, q[0])
        for reqs in C.QUEST_REQS.values():
            for k in reqs:
                self.assertIn(k, S.SKILL_BY_KEY)
        for c in C.SYSOP_CHALLENGES:
            for k in c[4]:
                self.assertIn(k, S.SKILL_BY_KEY, c[0])
        for k, _ in C.SYSOP_REQS.values():
            self.assertIn(k, S.SKILL_BY_KEY)
        for t in C.CONTRACT_TASKS:
            self.assertIn(t[5], S.SKILL_BY_KEY, t[0])
        for c in C.COMPANIONS:
            self.assertIn(c[2], S.SKILL_BY_KEY, c[0])
        for k in C.SURGE_SKILLS + list(C.RELIC_XP):
            self.assertIn(k, S.SKILL_BY_KEY)
        for k in list(S.TRAINING_RATES):
            self.assertIn(k, S.SKILL_BY_KEY)

    def test_tints_are_theme_names(self):
        for s in S.SKILLS:
            self.assertIn(s[4], ("red", "orange", "yellow", "green", "cyan", "blue", "magenta", "brown"))

    def test_no_third_party_game_ip(self):
        """Original IP only: no names, places or credits from another game in what ships."""
        banned = re.compile(r"jagex|runescape|old school|\bosrs\b|gielinor|guthix|lumbridge|varrock|falador|catherby|"
                            r"ardougne|morytania|runelite|runestar|chinchompa|tangleroot|rift guardian|wise old man|"
                            r"slayer|skillcape|treasure trail|clue scroll|drunken dwarf|sandwich lady|\bgenie\b|"
                            r"13,?034,?431|200,?000,?000|power level|combat level|quest points?\b|virtual level|"
                            r"funny feeling|you've completed a quest|speak to the|tears of|shooting star|omaquest|omascape", re.I)
        for name in SHIPPED:
            path = os.path.join(ROOT, name)
            if not os.path.exists(path):
                continue
            text = open(path, encoding="utf-8").read()
            if name == "skills.py":      # the import of the local-only migration helper is allowed
                text = text.replace("import migrate", "")
            hits = sorted(set(m.group(0).lower() for m in banned.finditer(text)))
            self.assertEqual(hits, [], "%s mentions %s" % (name, hits))


class SaveSafety(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_drop_guard(self):
        d = S.load()
        d["xp"]["workload"] = 500_000
        S.save(d, allow_drop=True)
        S.save(S._blank())                      # a would-be wipe
        self.assertEqual(S.load()["xp"]["workload"], 500_000)

    def test_recovers_from_empty_file(self):
        d = S.load()
        d["xp"]["shell"] = 123_456
        S.save(d, allow_drop=True)
        open(S.STATE, "w").close()              # power loss mid-write
        self.assertEqual(S.load()["xp"]["shell"], 123_456)


class Mechanics(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_tree_ranks_persist_and_pay_once(self):
        r = S.grant({}, why="keys", events={"kb:menu:theme": 12, "active_min": 0.5})
        self.assertEqual(r.gains["shell"], 400)
        r = S.grant({}, why="keys", events={"kb:menu:theme": 1, "active_min": 0.5})
        self.assertEqual(r.gains.get("shell", 0), 0)
        self.assertEqual(S.load()["tree"]["menu:theme"], 2)

    def test_relic_from_commit_paths(self):
        self.assertEqual(S.relic_paths(["dotfiles/hypr/bindings.conf", "README.md"]), {"hypr"})
        self.assertEqual(S.relic_paths([".config/nvim/init.lua"]), {"nvim"})
        self.assertEqual(S.relic_paths(["src/main.py"]), set())
        S.grant({}, why="commit", events={"relic:hypr": 1, "active_min": 0.5})
        S.grant({}, why="commit", events={"relic:hypr": 1, "active_min": 0.5})
        d = S.load()
        self.assertIn("hypr", d["relics"])
        self.assertEqual(d["xp"]["theming"], C.RELIC_XP["theming"])

    def test_theme_stamp_and_update_day(self):
        r = S.grant({}, why="theme", events={"theme_min:ristretto": C.STAMP_MINUTES, "update": 1, "active_min": 0.5})
        d = S.load()
        self.assertIn("ristretto", d["stamps"])
        self.assertTrue(S.update_day_active(d))
        self.assertEqual(d["tokens"][-1]["xp"], C.UPDATE_DAY_TOKEN)
        self.assertTrue(any("Update Day" in n[0] for n in r.notes))

    def test_season_is_stable_per_theme(self):
        self.assertEqual(S.theme_area("tokyo-night"), S.theme_area("Tokyo-Night "))
        self.assertIn(S.theme_area("anything"), S.AREA_BY_ID)

    def test_companion_hatches_at_level(self):
        pid, name, skill, lvl = C.COMPANIONS[0]
        S.grant({skill: S.LEVEL_XP[lvl]}, why="test", source="game")
        self.assertIn(pid, S.load()["companions"])

    def test_snapshot_does_not_clobber_state(self):
        snap_keys = set(S.snapshot(S._blank()))
        self.assertEqual((snap_keys & set(S.STATE_KEYS)) - {"skin"}, set())

    def test_wallpaper_png(self):
        out = os.path.join(TMP, "wall.png")
        wallpaper.render(S.snapshot(), out, (640, 360))
        with open(out, "rb") as f:
            head = f.read(24)
        self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(int.from_bytes(head[16:20], "big"), 640)

    def test_renamed_skills_resolve(self):
        self.assertEqual(S.skill_key("contracts"), "editing")
        self.assertEqual(S.skill_key("storage"), "workload")
        self.assertEqual(S.skill_key("Presence"), "focus")
        self.assertEqual(S.skill_key("THM"), "theming")
        self.assertTrue(all(v in S.SKILL_BY_KEY for v in S.RENAMED.values()))

    def test_skin_needs_rating(self):
        self.assertEqual(S.cmd_skin(["neon"]), 1)
        self.assertEqual(S.cmd_skin(["plain"]), 0)


class FairPlay(unittest.TestCase):
    def setUp(self):
        fresh()

    def activity(self, hours):
        with S._Lock():
            d = S.load()
            for h in range(hours):
                anticheat.note_active(d["fair"], 60, time.time() - h * 3600)
            S.save(d)

    def test_max_all_stats_is_void(self):
        for k in S.SKILL_KEYS:
            r = S.grant({k: 30_000}, why="agent [master]: max all stats", source="agent")
        d = S.load()
        self.assertTrue(all(S.level_for_xp(d["xp"][k]) < 40 for k in S.SKILL_KEYS))
        self.assertGreaterEqual(d["fair"]["voided"], len(S.SKILL_KEYS) - 2)

    def test_real_work_is_paid(self):
        self.activity(3)
        r = S.grant({"commits": 3000}, why="agent [hard]: shipped the backup system", source="agent")
        self.assertEqual(r.voided, "")
        self.assertEqual(S.load()["xp"]["commits"], 3000)

    def test_duplicate_and_burst(self):
        self.activity(10)
        self.assertEqual(S.grant({"shell": 300}, why="agent: fixed the panel layout", source="agent").voided, "")
        self.assertNotEqual(S.grant({"editing": 300}, why="agent: fixed the panel layout", source="agent").voided, "")
        voids = 0
        for i, k in enumerate(["focus", "workload", "theming", "models", "cleanup", "browsing", "tiling"]):
            voids += bool(S.grant({k: 300}, why="agent: distinct real work item %d" % i, source="agent").voided)
        self.assertGreaterEqual(voids, 1)

    def test_agent_work_backs_awards(self):
        """Work you wait on counts: agent CPU minutes raise the budget; no work, no budget."""
        self.assertNotEqual(S.grant({"commits": 12_000}, why="agent [expert]: shipped the release", source="agent").voided, "")
        S.grant({}, why="agents working", events={"agent_work_min": 60.0})
        S.grant({}, why="agents working", events={"agent_work_min": 60.0})       # same hour: capped at 60
        d = S.load()
        self.assertEqual(anticheat.worked_minutes(d["fair"]), 60)
        r = S.grant({"commits": 10_000}, why="agent [expert]: shipped the release, second try", source="agent")
        self.assertEqual(r.voided, "")

    def test_keyboard_and_agent_minutes_do_not_double(self):
        f = anticheat.blank()
        now = time.time()
        anticheat.note_active(f, 50, now)
        anticheat.note_work(f, 50, now)
        self.assertEqual(anticheat.worked_minutes(f, now=now), 60)
        self.assertEqual(anticheat.active_minutes(f, now=now), 50)      # the around-the-clock hold ignores agents

    def test_single_award_cap(self):
        self.activity(20)
        self.assertNotEqual(S.grant({"shell": 10_000_000}, why="manual", source="manual").voided, "")

    def test_nonstop_activity_holds_measured_xp(self):
        self.activity(24)
        r = S.grant({"workload": 60}, why="at the computer", events={"active_min": 0.5})
        self.assertNotEqual(r.voided, "")
        self.assertEqual(dict(r.gains), {})

    def test_hand_edit_is_unverified(self):
        S.grant({"workload": 60}, why="at the computer", events={"active_min": 0.5})
        self.assertTrue(S.fair_info(S.load())["verified"])
        st = json.load(open(S.STATE))
        st["xp"]["workload"] += 1_000_000
        json.dump(st, open(S.STATE, "w"))
        fp = S.fair_info(S.load())
        self.assertFalse(fp["verified"])
        self.assertIn("Workload", fp["unverified"])


if __name__ == "__main__":
    unittest.main()
