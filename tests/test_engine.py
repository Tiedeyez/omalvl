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


class HistoryPrivacy(unittest.TestCase):
    """v1.0.4 fixes: shell history keeps only allowlisted names; writes are private and symlink-safe."""

    def setUp(self):
        fresh()

    def test_arguments_and_secrets_are_not_counted(self):
        ev = S.command_events([
            "curl -H 'Authorization: Bearer sk-SECRET' https://x",
            "API_KEY=sk-SECRET env FOO=bar python3 run.py",
            "sudo pacman -Qi git",
            "mysecrettool --password hunter2",
            "git log | awk '{print $1}' && hunter2cmd",
        ])
        keys = [k for k in ev if k.startswith(("cmd:", "cmd2:"))]
        self.assertTrue(all(k in S.SAFE_HISTORY_STATS for k in keys), keys)
        self.assertNotIn("SECRET", json.dumps(ev))
        self.assertNotIn("hunter2", json.dumps(ev))
        self.assertEqual(ev["cmd:python3"], 1)               # env and assignments stripped
        self.assertEqual(ev["cmd2:pacman -qi"], 1)           # sudo stripped, pair kept
        self.assertEqual((ev["cmd:git"], ev["cmd2:git log"], ev["cmd:awk"]), (1, 1, 1))
        self.assertEqual(ev["cmd"], 5)                       # every command still counts toward the total

    def test_every_quest_counter_is_allowlisted(self):
        src = "".join(open(os.path.join(ROOT, f)).read() for f in ("content.py", "skills.py", "wiki.py"))
        keys = set(re.findall(r"[\"'](cmd2?:[^\"']+)[\"']", src))
        self.assertTrue(keys)
        self.assertEqual(sorted(k for k in keys if k not in S.SAFE_HISTORY_STATS), [],
                         "add these to SAFE_HISTORY_COMMANDS/PAIRS or the quest never progresses")

    def test_legacy_counters_scrubbed_from_state_and_backups(self):
        d = S.load()
        d["xp"]["shell"] = 1_000
        S.save(d, allow_drop=True)
        st = S._read_state(S.STATE)
        st["stats"].update({"cmd:git": 4, "cmd:mysecret": 2, "cmd2:curl sk-SECRET": 1})
        with open(S.STATE, "w") as f:
            json.dump(st, f)
        os.makedirs(S.BACKUP_DIR, exist_ok=True)
        old = os.path.join(S.BACKUP_DIR, "skills-2000-01-01.json")
        with open(old, "w") as f:
            json.dump(st, f)
        d = S.load()
        self.assertEqual(d["stats"].get("cmd:git"), 4)
        self.assertNotIn("cmd:mysecret", d["stats"])
        S._LEGACY_BACKUPS_SCRUBBED = False
        S.save(d)
        for path in (S.STATE, S.BACKUP, old):
            with open(path) as f:
                text = f.read()
            self.assertNotIn("SECRET", text, path)
            self.assertNotIn("mysecret", text, path)
        self.assertIn("cmd:git", open(old).read())

    def test_scrub_skips_symlinked_backups(self):
        target = os.path.join(TMP, "outside.json")
        with open(target, "w") as f:
            json.dump({"stats": {"cmd:mysecret": 1}}, f)
        os.makedirs(S.BACKUP_DIR, exist_ok=True)
        link = os.path.join(S.BACKUP_DIR, "skills-link.json")
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(target, link)
        try:
            S._LEGACY_BACKUPS_SCRUBBED = False
            S.save(S.load())
            self.assertTrue(os.path.islink(link))
            with open(target) as f:
                self.assertIn("cmd:mysecret", f.read())      # never written through the link
        finally:
            os.remove(link)

    def test_atomic_write_is_private_and_replaces_symlink(self):
        d = os.path.join(TMP, "aw")
        os.makedirs(d, exist_ok=True)
        victim = os.path.join(d, "victim.txt")
        with open(victim, "w") as f:
            f.write("keep")
        out = os.path.join(d, "out.json")
        os.symlink(victim, out + ".tmp")                     # the old predictable tmp name
        S._atomic_write(out, "{}")
        self.assertEqual(open(victim).read(), "keep")
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o600)
        self.assertEqual(open(out).read(), "{}")
        self.assertEqual(sorted(os.listdir(d)), ["out.json", "out.json.tmp", "victim.txt"])  # no leftovers


class JobPrivacy(unittest.TestCase):
    """A queued job's command line never reaches the state file or its backups."""

    def setUp(self):
        fresh()

    def test_job_label_keeps_only_the_program(self):
        self.assertEqual(S._job_label("curl -H 'Authorization: Bearer sk-SECRET' https://x"), "curl ...")
        self.assertEqual(S._job_label("TOKEN=sk-SECRET sudo env A=1 /usr/bin/make -j8"), "make ...")
        self.assertEqual(S._job_label("make"), "make")
        self.assertEqual(S._job_label("   "), "job")

    def test_run_saves_no_arguments_and_private_files(self):
        self.assertIn(S.cmd_run(["/usr/bin/true", "--password=hunter2"]), (None, 0))
        for path in (S.STATE, S.BACKUP):
            with open(path) as f:
                self.assertNotIn("hunter2", f.read(), path)
        job = S.load()["jobs"][-1]
        self.assertEqual(job["cmd"], "true ...")
        self.assertEqual(os.stat(job["log"]).st_mode & 0o777, 0o600)
        for _ in range(200):                                  # the job is /usr/bin/true: gone in ms
            if os.path.exists(job["exitFile"]) and open(job["exitFile"]).read().strip():
                break
            time.sleep(0.01)
        self.assertEqual(os.stat(job["exitFile"]).st_mode & 0o777, 0o600)

    def test_legacy_job_commands_scrubbed(self):
        st = S._read_state(S.STATE)
        st["jobs"] = [{"slot": "Alpha", "cmd": "curl -u admin:hunter2 https://x", "planted": 1, "pid": 1,
                       "exitFile": None, "log": None, "done": None, "exit": None}]
        with open(S.STATE, "w") as f:
            json.dump(st, f)
        S.save(S.load())
        for path in (S.STATE, S.BACKUP):
            with open(path) as f:
                self.assertNotIn("hunter2", f.read(), path)
        self.assertEqual(S.load()["jobs"][0]["cmd"], "curl ...")

    def test_legacy_label_ending_in_dots_is_still_scrubbed(self):
        # Review of 1.0.5: a legacy full command line ending in " ..." was taken as already clean.
        import tempfile as _tf
        off = _tf.mkdtemp()
        old_off = S.OFFSITE
        S.OFFSITE = os.path.join(off, "omalvl")
        try:
            st = S._read_state(S.STATE)
            st["jobs"] = [{"slot": "Alpha", "cmd": "deploy --token sk-SECRET ...", "planted": 1, "pid": 1,
                           "exitFile": None, "log": None, "done": None, "exit": None},
                          {"slot": "Beta", "cmd": "make ...", "planted": 1, "pid": 1, "exitFile": None,
                           "log": None, "done": None, "exit": None}]
            with open(S.STATE, "w") as f:
                json.dump(st, f)
            S.save(S.load())
            day = time.strftime("%Y-%m-%d")
            written = [S.STATE, S.BACKUP, os.path.join(S.BACKUP_DIR, "skills-%s.json" % day),
                       os.path.join(S._offsite_dir(), "skills-%s.json" % day)]
            for path in written:
                if os.path.exists(path):
                    with open(path) as f:
                        self.assertNotIn("sk-SECRET", f.read(), path)
            self.assertTrue(os.path.exists(written[-1]), "offsite copy was not written")
            jobs = S.load()["jobs"]
            self.assertEqual([j["cmd"] for j in jobs], ["deploy ...", "make ..."])
            self.assertTrue(all(j["labelV"] == S.JOB_LABEL_VERSION for j in jobs))
        finally:
            S.OFFSITE = old_off

    def test_marked_labels_are_left_alone_and_scrub_is_idempotent(self):
        jobs = [{"cmd": "make ...", "labelV": S.JOB_LABEL_VERSION}]
        self.assertFalse(S._scrub_jobs(jobs))
        self.assertEqual(jobs[0]["cmd"], "make ...")
        unmarked = [{"cmd": "make ..."}, {"cmd": None}]
        self.assertTrue(S._scrub_jobs(unmarked))
        self.assertEqual([j["cmd"] for j in unmarked], ["make ...", "job"])
        self.assertFalse(S._scrub_jobs(unmarked))

    def test_new_jobs_carry_the_label_marker(self):
        self.assertIn(S.cmd_run(["/usr/bin/true"]), (None, 0))
        self.assertEqual(S.load()["jobs"][-1]["labelV"], S.JOB_LABEL_VERSION)


class EventPrivacy(unittest.TestCase):
    """Review of 1.0.6: watcher events built from menu/panel arguments reached state and backups."""

    def setUp(self):
        fresh()

    def test_argument_derived_names_are_fixed(self):
        cls = S.classify_command
        self.assertEqual(cls(["omarchy-menu", "toggle", "--token=sk-SECRET"]), "menu:other")
        self.assertEqual(cls(["omarchy-menu", "summon", "appearance.theme"]), "menu:appearance")
        self.assertEqual(cls(["omarchy-menu", "toggle", "theme"]), "menu:theme")
        self.assertEqual(cls(["omarchy-menu"]), "menu:root")
        self.assertEqual(cls(["omarchy-shell", "shell", "toggle", "evil.sk-SECRET"]), "panel:other")
        self.assertEqual(cls(["omarchy-shell", "shell", "toggle", "omarchy.clipboard"]), "panel:omarchy.clipboard")
        self.assertEqual(cls(["omarchy-shell", "shell", "toggle", "omarchy.menu", '{"menu":"sk-SECRET"}']),
                         "menu:other")
        self.assertEqual(cls(["/home/x/bin/omarchy-toggle-sk-SECRET"]), "toggle:other")
        self.assertEqual(S.safe_event("layer:omarchy-sk-SECRET"), "layer:other")
        self.assertEqual(S.safe_event("kb:panel:sk-SECRET"), "kb:panel:other")
        self.assertEqual(S.safe_event("kb:float"), "kb:float")

    def test_every_event_the_game_uses_is_kept(self):
        text = "".join(open(os.path.join(ROOT, f)).read() for f in ("content.py", "skills.py"))
        used = set(re.findall(r'"((?:kb:)?(?:menu|panel|toggle|window|capture|layer):[a-z0-9.-]+)"', text))
        self.assertTrue(used)
        for key in used:
            self.assertEqual(S.safe_event(key), key, key)

    def test_legacy_event_keys_scrubbed_everywhere(self):
        st = S._read_state(S.STATE)
        st["stats"].update({"menu:--token=sk-SECRET": 2, "kb:panel:evil.sk-SECRET": 1, "menu:other": 1,
                            "toggle:nightlight": 4})
        with open(S.STATE, "w") as f:
            json.dump(st, f)
        S.save(S.load())
        for path in (S.STATE, S.BACKUP):
            with open(path) as f:
                self.assertNotIn("sk-SECRET", f.read(), path)
        stats = S.load()["stats"]
        self.assertEqual(stats["menu:other"], 3)
        self.assertEqual(stats["kb:panel:other"], 1)
        self.assertEqual(stats["toggle:nightlight"], 4)

    def test_watcher_reads_only_your_processes(self):
        d = tempfile.mkdtemp()
        exe = os.path.join(d, "omarchy-toggle-nightlight")
        with open(exe, "w") as f:
            f.write("#!/bin/sh\nsleep 5\ntrue\n")
        os.chmod(exe, 0o700)
        import subprocess
        proc = subprocess.Popen(["/bin/sh", exe, "sk-SECRET"])
        try:
            time.sleep(0.1)
            self.assertEqual(S._proc_event(str(proc.pid), os.getuid()), "toggle:nightlight")
            self.assertIsNone(S._proc_event(str(proc.pid), os.getuid() + 1))
            self.assertIsNone(S._proc_event("self", os.getuid()))
        finally:
            proc.kill()
            proc.wait()


class AgentAndBackupPrivacy(unittest.TestCase):
    """Review of 1.0.7: agent_scan kept names from other users' interpreter processes, and the keybind
    tree plus older backups' derived views (treeInfo, jobInfo[].cmd) carried old arguments forward."""

    def setUp(self):
        fresh()

    def _offsite(self):
        off = tempfile.mkdtemp()
        old = S.OFFSITE
        S.OFFSITE = os.path.join(off, "omalvl")
        self.addCleanup(setattr, S, "OFFSITE", old)
        return S._offsite_dir()

    def test_agent_names_are_fixed(self):
        self.assertEqual(S.canon_agent("llama-sk-SECRET"), "llama.cpp")
        self.assertEqual(S.canon_agent("ollama_llama_server"), "ollama")
        self.assertEqual(S.canon_agent("whisper-sk-SECRET"), "whisper.cpp")
        self.assertEqual(S.canon_agent("claude"), "claude")
        self.assertIsNone(S.canon_agent("sk-SECRET"))
        self.assertEqual(S.safe_event("agent:llama-sk-SECRET"), "agent:llama.cpp")
        self.assertEqual(S.safe_event("agent:sk-SECRET"), "agent:other")
        self.assertEqual(S.safe_event("local_model:vllm-sk-SECRET"), "local_model:vllm")
        self.assertEqual(S.safe_event("local_model:claude"), "local_model:other")
        for name in S.AGENT_VOCAB:
            self.assertEqual(S.safe_event("agent:" + name), "agent:" + name, name)
            self.assertEqual(S.canon_agent(name), name, name)
        for name in S.LOCAL_VOCAB:
            self.assertTrue(S.is_local_runtime(name), name)
            self.assertEqual(S.safe_event("local_model:" + name), "local_model:" + name, name)
        self.assertTrue(S.is_local_runtime("llama.cpp") and S.is_local_runtime("whisper.cpp"))
        self.assertFalse(S.is_local_runtime("claude"))

    def test_agent_scan_reads_only_your_processes(self):
        import subprocess
        d = tempfile.mkdtemp()
        script = os.path.join(d, "llama-sk-SECRET.py")
        with open(script, "w") as f:
            f.write("import time\ntime.sleep(5)\n")
        proc = subprocess.Popen([sys.executable, script, "--api-key", "sk-SECRET"])
        try:
            time.sleep(0.2)
            names, _, _ = S.agent_scan()
            self.assertIn("llama.cpp", names)
            self.assertFalse(any("SECRET" in n for n in names), names)
            self.assertTrue(S._owned_by_me(str(proc.pid)))
            self.assertFalse(S._owned_by_me(str(proc.pid), os.getuid() + 1))
            real = S._owned_by_me
            S._owned_by_me = lambda pid, me=None: False      # every process belongs to someone else
            try:
                self.assertEqual(S.agent_scan()[0], set())
            finally:
                S._owned_by_me = real
        finally:
            proc.kill()
            proc.wait()

    def test_process_list_is_your_own(self):
        import subprocess
        seen = []
        real = subprocess.run

        def fake(args, **kw):
            seen.append(list(args))
            return real(["true"], capture_output=True, text=True)
        S.subprocess.run = fake
        try:
            S.processes()
        finally:
            S.subprocess.run = real
        self.assertIn("-u", seen[0])
        self.assertEqual(seen[0][seen[0].index("-u") + 1], str(os.getuid()))
        self.assertNotIn("-e", " ".join(seen[0]).split())

    def _legacy(self):
        st = S._read_state(S.STATE)
        st["tree"] = {"menu:--token=sk-SECRET": 2, "panel:evil.sk-SECRET": 3, "toggle:nightlight": 1,
                      "menu:other": 1}
        st["stats"].update({"agent:llama-sk-SECRET": 1, "local_model:llama-sk-SECRET": 1, "kb:menu:sk-SECRET": 9})
        st["jobs"] = [{"slot": "Alpha", "cmd": "deploy --token sk-SECRET", "planted": 1, "pid": 1,
                       "exitFile": None, "log": None, "done": None, "exit": None}]
        st["treeInfo"] = [{"id": "keys", "nodes": [{"id": "menu:sk-SECRET", "name": "Sk-SECRET menu"}]}]
        st["jobInfo"] = [{"slot": "Alpha", "cmd": "deploy --token sk-SECRET"}]
        st["meta"].pop("privV", None)
        return st

    def test_legacy_tree_and_backup_views_scrubbed(self):
        off = self._offsite()
        st = self._legacy()
        with open(S.STATE, "w") as f:
            json.dump(st, f)
        os.makedirs(S.BACKUP_DIR, exist_ok=True)
        os.makedirs(off, exist_ok=True)
        old_files = [os.path.join(S.BACKUP_DIR, "skills-2020-01-01.json"),
                     os.path.join(S.BACKUP_DIR, "skills-manual-20200101-000000.json"),
                     os.path.join(off, "skills-2020-01-01.json")]
        for path in old_files:
            with open(path, "w") as f:
                json.dump(st, f)
        # a manual backup taken before the first save on the new build must not copy the old views
        snap = S.snapshot_file("manual")
        with open(snap) as f:
            self.assertNotIn("sk-SECRET", f.read())
        S._LEGACY_BACKUPS_SCRUBBED = False
        S.save(S.load())
        written = [S.STATE, S.BACKUP]
        for folder in (S.BACKUP_DIR, off):
            written += [os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".json")]
        self.assertGreaterEqual(len(written), 6)
        for path in written:
            with open(path) as f:
                self.assertNotIn("SECRET", f.read(), path)
        data = S.load()
        self.assertEqual(data["tree"]["menu:other"], 2)          # best rank wins
        self.assertEqual(data["tree"]["panel:other"], 3)
        self.assertEqual(data["tree"]["toggle:nightlight"], 1)
        self.assertEqual(data["stats"]["agent:llama.cpp"], 1)
        self.assertEqual(data["stats"]["kb:menu:other"], 9)
        for path in old_files:                                   # still restorable, XP intact
            old = S._read_state(path)
            self.assertEqual(old["xp"], st["xp"])
            self.assertEqual(old["meta"]["privV"], S.PRIVACY_VERSION)
            self.assertNotIn("treeInfo", old)

    def test_current_backups_are_not_rewritten(self):
        S._LEGACY_BACKUPS_SCRUBBED = False
        S.save(S.load())
        daily = os.path.join(S.BACKUP_DIR, "skills-%s.json" % time.strftime("%Y-%m-%d"))
        os.utime(daily, (1, 1))
        S._LEGACY_BACKUPS_SCRUBBED = False
        S.save(S.load())
        self.assertEqual(os.stat(daily).st_mtime, 1)
        with open(daily) as f:
            self.assertIn("treeInfo", json.load(f))          # a current backup keeps its full view

    def test_legacy_file_modes_tightened(self):
        os.makedirs(S.JOB_DIR, exist_ok=True)
        weekly = os.path.join(os.path.dirname(S.STATE), "weekly")
        os.makedirs(weekly, exist_ok=True)
        os.chmod(S.JOB_DIR, 0o755)
        log = os.path.join(S.JOB_DIR, "Alpha-1.log")
        rep = os.path.join(weekly, "2020-W01.txt")
        outside = os.path.join(tempfile.mkdtemp(), "not-ours.txt")
        for path in (log, rep, outside):
            with open(path, "w") as f:
                f.write("x")
            os.chmod(path, 0o644)
        link = os.path.join(S.JOB_DIR, "link.log")
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(outside, link)
        S._tighten_legacy_files()
        self.assertEqual(os.stat(log).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(rep).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(S.JOB_DIR).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(outside).st_mode & 0o777, 0o644)   # a symlink target is never touched
        os.remove(link)

    def test_new_folders_are_private(self):
        for d in (S.BACKUP_DIR, S.JOB_DIR):
            os.chmod(d, 0o755) if os.path.isdir(d) else None
        S._LEGACY_BACKUPS_SCRUBBED = False
        S.save(S.load())
        self.assertEqual(os.stat(os.path.dirname(S.STATE)).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(S.BACKUP_DIR).st_mode & 0o777, 0o700)


class LocalModelOnly(unittest.TestCase):
    """Review of 1.0.6: urlopen honoured http_proxy, so the prompt could leave the machine."""

    def _server(self, handler):
        import http.server
        import threading
        srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return srv

    def setUp(self):
        import http.server
        self.proxied = []
        proxied = self.proxied

        class Proxy(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                proxied.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"proxy")
            do_POST = do_GET

            def log_message(self, *a):
                pass

        class Model(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "http://example.com/steal")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *a):
                pass

        proxy = self._server(Proxy)
        model = self._server(Model)
        self.old = S.LLM_URL, {k: os.environ.get(k) for k in ("http_proxy", "HTTP_PROXY", "no_proxy", "NO_PROXY")}
        S.LLM_URL = "http://127.0.0.1:%d" % model.server_port
        for k in ("http_proxy", "HTTP_PROXY"):
            os.environ[k] = "http://127.0.0.1:%d" % proxy.server_port
        for k in ("no_proxy", "NO_PROXY"):
            os.environ.pop(k, None)

    def tearDown(self):
        S.LLM_URL = self.old[0]
        for k, v in self.old[1].items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_direct_connection_ignores_proxy(self):
        self.assertTrue(S._llm_up())
        self.assertEqual(S._local_open(S.LLM_URL + "/health", 2).read(), b"ok")
        self.assertEqual(self.proxied, [])

    def test_redirects_refused(self):
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError) as cm:
            S._local_open(S.LLM_URL + "/redirect", 2)
        cm.exception.close()
        self.assertEqual(self.proxied, [])

    def test_only_the_local_model_url(self):
        with self.assertRaises(ValueError):
            S._local_open("http://example.com/", 2)


class WikiPrivacy(unittest.TestCase):
    """Review of 1.0.6: wiki pages inherited the umask, so other local users could read them."""

    def test_pages_are_owner_only_and_old_pages_fixed(self):
        import stat
        import wiki
        fresh()
        os.makedirs(wiki.OUT, exist_ok=True)
        old = os.path.join(wiki.OUT, "index.html")
        with open(old, "w") as f:
            f.write("old")
        os.chmod(old, 0o644)
        os.chmod(wiki.OUT, 0o755)
        prev = os.umask(0o022)
        try:
            wiki.build()
        finally:
            os.umask(prev)
        self.assertEqual(stat.S_IMODE(os.stat(wiki.OUT).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(wiki.OUT)).st_mode), 0o700)
        names = os.listdir(wiki.OUT)
        self.assertIn("index.html", names)
        for name in names:
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(wiki.OUT, name)).st_mode), 0o600, name)


class DailySysop(unittest.TestCase):
    """1.0.0-1.0.4: sysop_today raised KeyError on any save, so the daemon's daily block
    (Sysop, streak, job checks) aborted every active minute."""

    def setUp(self):
        fresh()

    def test_fresh_save_gets_a_challenge(self):
        d = S.load()
        w = S.sysop_today(d)
        self.assertIn(w["id"], S.SYSOP_BY_ID)
        self.assertIn(S.cmd_sysop([]), (None, 0))         # the CLI exits 0 on None

    def test_locked_challenges_stay_out_until_unlocked(self):
        d = S.load()
        for _ in range(3):
            d.pop("sysop", None)
            cid = S.sysop_today(d)["id"]
            req = C.SYSOP_REQS.get(cid)
            self.assertTrue(not req or S.level_for_xp(d["xp"][req[0]]) >= req[1], cid)

    def test_daily_block_reaches_the_streak(self):
        S.daily_wom()
        S.daily_streak()
        d = S.load()
        self.assertEqual(d["sysop"]["day"], S.today())
        self.assertEqual(d["streak"]["day"], S.today())
        self.assertGreaterEqual(d["streak"]["count"], 1)


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


class QaBatch(unittest.TestCase):
    """Regressions from the 2026-11-27 end-to-end QA (1.0.10)."""

    def setUp(self):
        fresh()
        self._notify = S.notify
        S.notify = lambda *a: None

    def tearDown(self):
        S.notify = self._notify

    def call(self, fn, *argv):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fn(list(argv))
        return rc or 0, out.getvalue(), err.getvalue()

    @staticmethod
    def read(path):
        with open(path) as f:
            return f.read()

    def edit_save(self, change):
        st = json.loads(self.read(S.STATE))
        change(st)
        with open(S.STATE, "w") as f:
            json.dump(st, f)

    def main(self, *argv):
        old = sys.argv
        sys.argv = ["omalvl"] + list(argv)
        try:
            return self.call(lambda a: S.main())
        finally:
            sys.argv = old

    # ---- award input
    def test_task_xp_must_be_a_positive_number(self):
        for bad in ("-500", "0", "abc", "inf", "-inf", "nan", ""):
            rc, _, err = self.call(S.cmd_task, "write", bad)
            self.assertEqual(rc, 2, bad)
            self.assertIn("positive number", err)
        self.assertEqual(S.load()["xp"]["editing"], 0)
        self.assertEqual(S.load()["fair"]["awards"], [])

    def test_add_rejects_infinite_and_nonsense_amounts(self):
        for bad in ("inf", "-inf", "nan", "abc", ""):
            rc, _, err = self.call(S.cmd_add, "shell", bad)
            self.assertEqual(rc, 2, bad)
        self.assertEqual(self.call(S.cmd_add, "shell", "-5")[0], 2)
        self.assertEqual(self.call(S.cmd_add, "shell", "1e2")[0], 0)
        self.assertEqual(S.load()["xp"]["shell"], 100)

    def test_engine_refuses_a_negative_award(self):
        S.grant({"shell": 500}, why="measured", events={"cmd": 1})
        r = S.grant({"shell": -400}, why="task: write", source="manual")
        self.assertEqual(r.voided, "not a positive amount")
        self.assertEqual(S.load()["xp"]["shell"], 500)

    def test_reason_checks_look_at_the_work_not_the_label(self):
        # "agent [medium]: " used to count towards the minimum length, and a new tier hid a duplicate
        rc, _, err = self.call(lambda a: S.cmd_add(a, agent=True), "editing", "medium", "short")
        self.assertEqual(rc, 1)
        self.assertIn("no real description", err)
        ok = lambda *a: self.call(lambda v: S.cmd_add(v, agent=True), *a)[0]
        self.assertEqual(ok("editing", "easy", "fixed the panel layout bug"), 0)
        self.assertEqual(ok("commits", "medium", "Fixed the panel layout bug!"), 1)
        self.assertEqual(S.load()["fair"]["awards"][-1]["void"], "the same work was already awarded")

    def test_reason_is_stored_as_one_plain_line(self):
        self.call(lambda a: S.cmd_add(a, agent=True), "scripting", "easy", "line one\nline two \x1b[31mred\x1b[0m \u202edone")
        d = S.load()
        for text in (d["log"][-1]["why"], d["fair"]["awards"][-1]["reason"]):
            self.assertTrue(text.isprintable(), repr(text))
            self.assertNotIn("\n", text)
        self.assertEqual(S._plain("a\tb\r\n  c\x07"), "a b c")

    def test_voided_total_stays_readable(self):
        S.grant({"shell": 10 ** 14}, why="omalvl add", source="manual")
        f = S.load()["fair"]
        self.assertEqual(f["voided"], 1)
        self.assertLessEqual(f["voidedXp"], anticheat.VOID_COUNT_MAX)

    def test_log_prints_the_whole_void_reason(self):
        S.grant({"shell": 50_000}, why="omalvl add", source="manual")
        _, out, _ = self.call(S.cmd_log)
        self.assertIn("more than 30,000 XP in one award", out)

    # ---- jobs
    def test_collect_sees_a_finished_job_without_the_daemon(self):
        self.assertEqual(self.call(S.cmd_run, "true")[0], 0)
        for _ in range(100):
            if os.path.exists(S.load()["jobs"][0]["exitFile"]):
                break
            time.sleep(0.05)
        rc, out, _ = self.call(S.cmd_collect)
        self.assertIn("Collected slot Alpha", out)
        self.assertEqual(S.load()["jobs"], [])

    def test_run_keeps_the_quoting_of_its_arguments(self):
        marker = os.path.join(TMP, "two words.txt")
        self.call(S.cmd_run, "sh", "-c", "exit 3")                     # was run as: sh -c exit 3  (exit 0)
        self.call(S.cmd_run, "touch", marker)                          # was: touch two; touch words.txt
        self.call(S.cmd_run, "exit 4 && true")                         # one argument stays a shell line
        for _ in range(100):
            if all(os.path.exists(j["exitFile"]) for j in S.load()["jobs"]):
                break
            time.sleep(0.05)
        S.check_jobs(tell=False)
        jobs = S.load()["jobs"]
        self.assertEqual([j["exit"] for j in jobs], [3, 0, 4])
        self.assertTrue(os.path.exists(marker))
        self.assertEqual([j["cmd"] for j in jobs], ["sh ...", "touch ...", "exit ..."])

    def test_run_pid_needs_a_real_number(self):
        for bad in ([], ["abc"], ["0"], ["-1"], ["12x"]):
            rc, _, err = self.call(S.cmd_run, "--pid", *bad)
            self.assertEqual(rc, 2, bad)
            self.assertIn("usage", err)
        self.assertEqual(S.load()["jobs"], [])

    def test_drop_frees_a_slot_without_xp(self):
        self.call(S.cmd_run, "--pid", str(os.getpid()), "watching", "myself")
        self.assertEqual(len(S.load()["jobs"]), 1)
        self.assertEqual(self.call(S.cmd_collect)[1].split(".")[0], "Nothing to collect yet")
        rc, out, _ = self.call(S.cmd_drop, "alpha")
        self.assertEqual(rc, 0)
        d = S.load()
        self.assertEqual(d["jobs"], [])
        self.assertEqual(d["xp"]["workload"], 0)
        self.assertEqual(self.call(S.cmd_drop, "zeta")[0], 2)
        self.assertEqual(self.call(S.cmd_collect, "zeta")[0], 2)

    # ---- commands that used to print a traceback or nonsense
    def test_backup_before_any_save(self):
        for p in (S.STATE, S.BACKUP):
            os.remove(p)
        _, out, _ = self.call(S.cmd_backup)
        self.assertIn("Nothing to back up yet", out)
        self.assertNotIn("None", out)

    def test_reset_checks_the_skill_before_copying(self):
        before = set(os.listdir(S.BACKUP_DIR)) if os.path.isdir(S.BACKUP_DIR) else set()
        rc, out, _ = self.call(S.cmd_reset, "nosuch")
        self.assertEqual((rc, out), (2, ""))
        self.assertEqual(set(os.listdir(S.BACKUP_DIR)) if os.path.isdir(S.BACKUP_DIR) else set(), before)

    def test_wallpaper_to_an_unwritable_place(self):
        rc, _, err = self.call(S.cmd_wallpaper, "--out", "/proc/omalvl-nope/x.png")
        self.assertEqual(rc, 1)
        self.assertIn("can't write the wallpaper", err)

    def test_wallpaper_covers_the_screen(self):
        out = os.path.join(TMP, "cover.png")
        for size in ((1600, 900), (1366, 768), (1920, 1080), (2560, 1440), (3840, 2160)):
            wallpaper.render(S.snapshot(), out, size)
            with open(out, "rb") as f:
                head = f.read(24)
            w, h = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
            self.assertTrue(size[0] <= w < size[0] + 16 and size[1] <= h < size[1] + 16, (size, w, h))

    def test_quest_without_an_id(self):
        rc, _, err = self.call(S.cmd_quest)
        self.assertEqual(rc, 2)
        self.assertIn("usage", err)

    # ---- damaged saves
    def test_wrong_shapes_in_a_save_are_repaired_on_load(self):
        def damage(st):
            st["xp"].update({"shell": "abc", "editing": None, "commits": -50, "focus": 1e30, "models": True})
            st.update({"surge": 3.7, "updateDay": [1, 2], "signal": "x", "drop": 5})
        self.edit_save(damage)
        d = S.load()
        self.assertEqual([d["xp"][k] for k in ("shell", "editing", "commits", "models")], [0, 0, 0, 0])
        self.assertEqual(d["xp"]["focus"], S.XP_CAP)
        self.assertEqual([d[k] for k in S.NULLABLE_DICT_KEYS], [None] * 4)
        S.snapshot(d)

    def test_a_damaged_save_gives_one_line_not_a_traceback(self):
        def damage(st):
            st["contract"]["streak"] = None
            st["log"] = [{"t": {"a": 1}, "why": 5}]
        self.edit_save(damage)
        rc, _, err = self.main("week")
        rc2, _, err2 = self.main("log")
        for code, text in ((rc, err), (rc2, err2)):
            if code:
                self.assertEqual(code, 1)
                self.assertIn("omalvl restore latest", text)
                self.assertNotIn("Traceback", text)
        self.assertTrue(rc or rc2)

    # ---- files
    def test_lock_files_never_follow_a_symlink_or_truncate(self):
        victim = os.path.join(TMP, "victim.txt")
        with open(victim, "w") as f:
            f.write("keep me")
        for lock in (S.LOCK, S.LOCK + ".daemon"):
            if os.path.lexists(lock):
                os.remove(lock)
            os.symlink(victim, lock)
            with self.assertRaises(OSError):
                S._open_lock(lock)
            os.remove(lock)
        self.assertEqual(self.read(victim), "keep me")
        with S._Lock():
            pass
        self.assertEqual(os.stat(S.LOCK).st_mode & 0o777, 0o600)      # created private
        with open(S.LOCK, "w") as f:
            f.write("old")
        with S._Lock():
            pass
        self.assertEqual(self.read(S.LOCK), "old")                    # and never truncated

    def test_leftovers_are_swept(self):
        base = os.path.dirname(S.STATE)
        old_tmp, new_tmp = os.path.join(base, ".state.json.bak.aaaa.tmp"), os.path.join(base, ".state.json.bbbb.tmp")
        for p in (old_tmp, new_tmp):
            open(p, "w").close()
        os.utime(old_tmp, (time.time() - 7200,) * 2)
        aside = []
        for i in range(8):
            p = "%s.corrupt-%d" % (S.STATE, 1000 + i)
            open(p, "w").close()
            os.utime(p, (time.time() - 1000 + i,) * 2)
            aside.append(p)
        link = os.path.join(base, ".linked.tmp")
        os.symlink(S.STATE, link)
        os.utime(link, (time.time() - 7200,) * 2, follow_symlinks=False)
        S._sweep_leftovers()
        self.assertFalse(os.path.exists(old_tmp))
        self.assertTrue(os.path.exists(new_tmp))
        self.assertEqual([os.path.exists(p) for p in aside], [False] * 3 + [True] * 5)
        self.assertTrue(os.path.islink(link) and os.path.exists(S.STATE))
        for p in [new_tmp, link] + aside[3:]:
            os.remove(p)

    def test_a_relative_offsite_folder_is_ignored(self):
        old = S.OFFSITE
        try:
            S.OFFSITE = "5"
            self.assertIsNone(S._offsite_dir())
            S.OFFSITE = TMP + "/off"
            self.assertTrue(S._offsite_dir().startswith(TMP))
        finally:
            S.OFFSITE = old

    # ---- the keybind tree
    def test_status_questions_and_helpers_are_not_actions(self):
        cls = S.classify_command
        self.assertEqual(cls(["omarchy-toggle-nightlight"]), "toggle:nightlight")
        self.assertIsNone(cls(["omarchy-toggle-nightlight", "--status"]))
        self.assertIsNone(cls(["bash", "/usr/bin/omarchy-toggle-idle", "--status"]))
        self.assertIsNone(cls(["omarchy-capture-screenrecording", "--status"]))
        self.assertEqual(cls(["omarchy-capture-screenrecording", "--stop-recording"]), "capture:screenrecording")
        self.assertIsNone(cls(["omarchy-capture-screenrecording-process", "--pid", "5"]))
        d = S.load()
        d["stats"]["kb:capture:screenrecording-process"] = 147
        names = [n["id"] for b in S.tree_info(d) for n in b["nodes"]]
        self.assertNotIn("capture:screenrecording-process", names)

    # ---- the sampler
    def test_a_second_sampler_stands_by_instead_of_exiting(self):
        import subprocess
        env = dict(os.environ)
        code = ("import sys, fcntl; sys.path.insert(0, %r); import skills as S; S._private_dir(S.os.path.dirname(S.LOCK));"
                "f = S._open_lock(S.LOCK + '.daemon'); fcntl.flock(f, fcntl.LOCK_EX); print('held', flush=True);"
                "sys.stdin.read()" % ROOT)
        holder = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
        try:
            self.assertEqual(holder.stdout.readline().strip(), b"held")
            second = subprocess.Popen([sys.executable, os.path.join(ROOT, "skills.py"), "daemon"], env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    second.wait(timeout=1.5)          # it used to return at once, and the panel respawned it
            finally:
                second.kill()
                second.wait()
        finally:
            holder.kill()
            holder.wait()
            holder.stdin.close()
            holder.stdout.close()

    def test_the_engine_starts_without_urllib(self):
        import subprocess
        out = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import skills; "
                              "print('urllib.request' in sys.modules)" % ROOT],
                             capture_output=True, text=True, env=dict(os.environ)).stdout.strip()
        self.assertEqual(out, "False")

    def test_panel_log_is_newest_first(self):
        S.grant({"shell": 10}, why="first thing", events={"cmd": 1})
        S.grant({"shell": 10}, why="second thing", events={"cmd": 1})
        a = S.snapshot()["activity"]
        self.assertEqual([e["why"] for e in a[:2]], ["second thing", "first thing"])
        qml = self.read(os.path.join(ROOT, "Panel.qml"))
        self.assertNotIn("root.activity.slice().reverse()", qml)


if __name__ == "__main__":
    unittest.main()
