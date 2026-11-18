"""Game content for OmaLvL: quests (with helper steps), contracts, signal hunts,
the Omarchy journal, random events, relics, the keybind tree, skins and rice ranks.

Everything that "detects" something refers to an *event key*. The daemon
counts these per tick and keeps lifetime totals in state["stats"]:

  cmd, search, script            shell commands (from history)
  cmd:<word>, cmd2:<two words>   allowlisted command name / fixed safe command pair
  win_open, win_close, focus     Hyprland window events
  ws_switch, fullscreen, float, scratchpad, group, pin, movewindow
  menu:<route>                   an Omarchy menu opened (menu:root, menu:theme, ...)
  panel:<plugin>                 a shell panel toggled (panel:omarchy.clipboard, ...)
  toggle:<name>                  omarchy-toggle-<name> (nightlight, idle, ...)
  window:<name>                  omarchy-hyprland-window-<name> (pop, gaps-toggle, ...)
  capture:<name>, dictation, reminder, keybindings
  screenshot, theme, commit, pkg_install, pkg_upgrade, visit
  active_min, game_min           minutes at the computer / with a game focused
  proc:<name>                    a watched program started (claude, nvim, btop, ...)
  agent:<name>                   an AI agent or local-model runtime started (cloud or local)
  local_model:<name>             a local-model runtime started (ollama, llama.cpp, LM Studio ...)

A condition is a tuple:
  ("sum", prefix, n)       lifetime total of every key starting with prefix >= n
  ("distinct", prefix, n)  at least n different keys starting with prefix seen
  ("quest", id) ("quests", n) ("total", n) ("level", n) ("contract", n) ("signals", n)
  ("stamps", n) ("relics", n) ("rice", n) ("tree", rank, n)  n nodes of the keybind tree at rank or above
  theme_min:<name>, update, wallpaper, config_edit   theme time, omarchy update, background changes, config saves
"""

# ---------------------------------------------------------------- quests
# id, name, renown, what to do, reward {skill: xp}, auto conditions
# (all must hold; empty = complete by hand), helper steps [(text, condition|None)]
QUESTS = [
    ("welcome", "Welcome to Omarchy", 1, "Read manual 01 (Welcome) and the Omarchy philosophy",
     {"workload": 25, "searching": 25}, [],
     [("Open the manual: SUPER + SPACE, then Learn, then Omarchy", ("sum", "menu:", 1)),
      ("Read the Welcome page to the end", None)]),
    ("getting_started", "Getting Started", 1, "Read manual 02 and get oriented",
     {"workload": 50}, [],
     [("Read manual 02 (Getting Started)", None),
      ("Open the Omarchy menu once: SUPER + SPACE", ("sum", "menu:", 1))]),
    ("from_mac_win", "Coming from Mac or Windows", 1, "Read manual 03 and map what you knew",
     {"workload": 30}, [],
     [("Read manual 03", None)]),
    ("navigation", "Navigation", 1, "Manual 04: move, focus and tile windows with the keyboard",
     {"tiling": 60, "shell": 40}, [("sum", "ws_switch", 10), ("sum", "movewindow", 1)],
     [("Switch workspaces 10 times: SUPER + 1..9", ("sum", "ws_switch", 10)),
      ("Move a window to another workspace: SUPER + SHIFT + 1..9", ("sum", "movewindow", 1)),
      ("Swap or move focus with SUPER + arrow keys", ("sum", "focus", 20))]),
    ("top_bar", "The Top Bar", 1, "Manual 05: open the bar's panels",
     {"searching": 40, "tiling": 30}, [("sum", "layer:", 3)],
     [("Click bar widgets to open their panels three times", ("sum", "layer:", 3))]),
    ("themes", "Themes", 1, "Manual 06: switch to another theme (and back)",
     {"theming": 100}, [("sum", "theme", 1)],
     [("Open the theme menu: SUPER + SHIFT + CTRL + SPACE", ("sum", "menu:theme", 1)),
      ("Pick any theme, then switch back to your own", ("sum", "theme", 1))]),
    ("hotkeys", "Hotkeys", 2, "Manual 07: use five different Omarchy keybind actions",
     {"shell": 150}, [("sum", "keybindings", 1), ("distinct", "kb:", 5)],
     [("Open the keybindings list: SUPER + K", ("sum", "keybindings", 1)),
      ("Use five different Omarchy actions (menus, toggles, window tricks)", ("distinct", "kb:", 5))]),
    ("clipboard", "Clipboard & History", 1, "Manual 08: paste something from clipboard history",
     {"shell": 50, "tiling": 40}, [("sum", "panel:omarchy.clipboard", 1)],
     [("Copy two things: SUPER + C", None),
      ("Open the clipboard manager: SUPER + CTRL + V", ("sum", "panel:omarchy.clipboard", 1)),
      ("Paste an older entry from it", None)]),
    ("reminders", "Reminders & Notices", 1, "Manuals 09-10: set a reminder",
     {"editing": 60}, [("sum", "reminder", 1)],
     [("Set a reminder from the menu or: omarchy-reminder 5 'stretch'", ("sum", "reminder", 1))]),
    ("text_dictation", "Text Extraction & Dictation", 1, "Manual 11: OCR a screen region or dictate once",
     {"searching": 40, "shell": 40}, [("distinct", "capture:text", 1)],
     [("Open the capture menu: SUPER + CTRL + C", ("sum", "menu:capture", 1)),
      ("Extract text from a region, or dictate with SUPER + CTRL + X", ("sum", "capture:text", 1))]),
    ("screenshots", "Screenshots & Recording", 1, "Manual 12: take a screenshot",
     {"shell": 50}, [("sum", "screenshot", 1)],
     [("Press PRINT and drag a region", ("sum", "screenshot", 1))]),
    ("toggles", "Toggles, Idle & Screensaver", 1, "Manual 13: toggle nightlight, idle or the screensaver",
     {"tiling": 50}, [("distinct", "toggle:", 1)],
     [("Nightlight: SUPER + CTRL + N (press again to undo)", ("sum", "toggle:nightlight", 1)),
      ("Or idle locking: SUPER + CTRL + I", ("sum", "toggle:idle", 1))]),
    ("omarchy_cli", "Omarchy CLI", 1, "Manual 14: run omarchy commands from a terminal",
     {"shell": 120}, [("sum", "cmd:omarchy", 1)],
     [("Run: omarchy --help", ("sum", "cmd:omarchy", 1)),
      ("Try two subcommands it lists", ("sum", "cmd:omarchy", 3))]),
    ("terminal", "Terminal Mastery", 2, "Manual 15: run twenty commands in the terminal",
     {"shell": 100, "focus": 50}, [("sum", "cmd", 20)],
     [("Open a terminal: SUPER + RETURN", None),
      ("Run 20 commands (ls, cd, cat, man ...)", ("sum", "cmd", 20))]),
    ("neovim", "Neovim", 2, "Manual 16: open, edit and save a file in Neovim",
     {"shell": 120, "editing": 60}, [("sum", "proc:nvim", 1)],
     [("Run: nvim notes.md", ("sum", "proc:nvim", 1)),
      ("i to type, ESC, then :wq to save and quit", None)]),
    ("ai_agents", "AI Agents", 2, "Manual 17: launch an AI agent and give it a task",
     {"shell": 150, "packages": 75, "scripting": 75},
     [("distinct", "agent:", 1)],
     [("Launch an AI agent: Claude Code, OpenCode, Codex, or one running a local model",
       ("distinct", "agent:", 1)),
      ("Give it one small, real task and review what it did", None)]),
    ("off_grid", "Off the Grid", 2, "Run an AI model on this machine, with no cloud",
     {"agents": 150, "shell": 75, "workload": 75},
     [("distinct", "local_model:", 1)],
     [("Install a local runtime: sudo pacman -S ollama (or llama.cpp)", None),
      ("Run a small model; 1-3B fits this RAM: ollama run llama3.2:1b",
       ("distinct", "local_model:", 1)),
      ("Point an agent at it: OpenCode with the Ollama provider, or codex --oss", None)]),
    ("dev_tools", "Development Tools", 2, "Manual 18: set up a language with mise",
     {"scripting": 100, "editing": 40}, [("sum", "cmd:mise", 1)],
     [("Run: mise ls", ("sum", "cmd:mise", 1)),
      ("Install a runtime: mise use -g node@lts", ("sum", "cmd:mise", 2))]),
    ("shell", "Shell Tools & Functions", 2, "Manuals 19-20: use eza, zoxide and fzf",
     {"scripting": 60, "shell": 60}, [("distinct", "cmd:z", 1), ("sum", "cmd:fzf", 1)],
     [("Jump somewhere with zoxide: z Work", ("sum", "cmd:z", 1)),
      ("Fuzzy-find a file: fzf", ("sum", "cmd:fzf", 1))]),
    ("tuis_guis", "TUIs, GUIs & Browsers", 1, "Manuals 21-23: try btop or lazygit",
     {"searching": 40, "tiling": 40}, [("distinct", "proc:btop", 1)],
     [("Run: btop  (q quits)", ("sum", "proc:btop", 1)),
      ("Bonus: lazygit inside a repo", ("sum", "proc:lazygit", 1))]),
    ("dotfiles_updates", "Dotfiles & Updates", 2, "Manuals 30-31: run omarchy update and read what changed",
     {"focus": 60, "packages": 60}, [("sum", "cmd2:omarchy update", 1)],
     [("Run: omarchy update", ("sum", "cmd2:omarchy update", 1)),
      ("Skim the changelog it prints", None)]),
    ("troubleshooting", "Troubleshooting", 2, "Manual 45: read a journalctl log to find a real problem",
     {"tiling": 80, "downloads": 80}, [("sum", "cmd:journalctl", 1)],
     [("Run: journalctl --user -b -p warning", ("sum", "cmd:journalctl", 1)),
      ("Pick one warning and find out what it means", None)]),
    ("snapshots_security", "Snapshots & Security", 2, "Manuals 47-48: learn how to roll back",
     {"focus": 120}, [],
     [("Read manuals 47-48", None), ("Find where your snapshots or backups live", None)]),
    ("make_theme", "Making Your Own Theme", 3, "Manual 43: build or tweak your own theme",
     {"theming": 200, "editing": 100, "commits": 100}, [],
     [("Copy a theme folder into ~/.config/omarchy/themes/<name>", None),
      ("Change colors.toml, then apply it from the theme menu", ("sum", "theme", 2))]),
    ("arch_basics", "Arch Basics", 1, "Query pacman: what is installed and why",
     {"workload": 40, "focus": 40}, [("sum", "cmd:pacman", 1)],
     [("Run: pacman -Qi bash", ("sum", "cmd:pacman", 1)),
      ("Find what pulled a package in: pacman -Qi <pkg> | grep Required", None)]),
    ("systemd", "Services & systemd", 2, "List and inspect a user service with systemctl --user",
     {"downloads": 70, "tiling": 70}, [("sum", "cmd:systemctl", 1)],
     [("Run: systemctl --user list-units --type=service", ("sum", "cmd:systemctl", 1)),
      ("Inspect one: systemctl --user status <name>", ("sum", "cmd:systemctl", 2))]),
    ("hyprland", "Hyprland Internals", 2, "Change one safe value in ~/.config/hypr and reload",
     {"editing": 90, "workload": 90}, [("sum", "cmd:hyprctl", 1)],
     [("Look around: hyprctl clients", ("sum", "cmd:hyprctl", 1)),
      ("Edit a gap or border in ~/.config/hypr, then hyprctl reload", ("sum", "cmd:hyprctl", 2))]),
    ("quickshell", "Quickshell", 3, "Read a bar plugin's QML and change something small",
     {"editing": 120, "packages": 120}, [],
     [("Open ~/.config/omarchy/plugins/tiedeyez.omalvl/Panel.qml (or any plugin's)", None),
      ("Change one colour, omarchy restart shell, and see it", None)]),
    ("arch_wiki", "Arch Wiki Deep Dive", 3, "Fix a real problem using the Arch wiki, not an AI",
     {"workload": 150, "tiling": 150}, [],
     [("Pick a small annoyance", None), ("Solve it from wiki.archlinux.org alone", None)]),
    ("ai_builder1", "AI Builder: First Task", 1, "Have an agent do a tiny safe cleanup; review it",
     {"shell": 60, "packages": 60}, [],
     [("Ask an agent to tidy one file or folder", None), ("Read its diff before keeping it", None)]),
    ("ai_builder2", "AI Builder: Tweak a Config", 2, "Have an agent tweak a config and explain it",
     {"shell": 70, "editing": 70}, [],
     [("Ask an agent to change one setting and explain why", None),
      ("Make sure you know how to undo it", None)]),
    ("ai_builder3", "AI Builder: Ship Something", 3, "Build and test a small tool with an agent, then commit it",
     {"commits": 150, "scripting": 100, "shell": 75}, [("sum", "commit", 1)],
     [("Build a small script with an agent", None), ("Test it yourself", None),
      ("Commit it in a repo under ~/Work", ("sum", "commit", 1))]),
]

# ---------------------------------------------------------------- contract
# id, task text ({n} = amount), event key prefix, (min, max), xp per unit, the skill it pays
CONTRACT_TASKS = [
    ("windows", "Close {n} windows", "win_close", (10, 25), 12, "tiling"),
    ("commands", "Run {n} shell commands", "cmd", (20, 50), 8, "shell"),
    ("workspaces", "Switch workspaces {n} times", "ws_switch", (20, 60), 4, "tiling"),
    ("searches", "Run {n} searches (rg, grep, fd, find)", "search", (5, 15), 25, "searching"),
    ("commits", "Make {n} git commits", "commit", (1, 3), 250, "commits"),
    ("focus", "Spend {n} minutes at the computer", "active_min", (30, 90), 6, "focus"),
    ("screenshots", "Take {n} screenshots", "screenshot", (1, 3), 120, "theming"),
    ("fullscreen", "Toggle fullscreen {n} times", "fullscreen", (3, 8), 40, "tiling"),
    ("menus", "Open {n} Omarchy menus", "menu:", (3, 10), 35, "shell"),
    ("scripts", "Run {n} scripts (python, bash, node ...)", "script", (3, 10), 40, "scripting"),
    ("builds", "Run {n} builds (make, cargo, npm run ...)", "cook", (2, 6), 60, "building"),
    ("burn", "Clean up {n} things (rm, trash, cache purges)", "burn", (3, 10), 30, "cleanup"),
    ("voyages", "Make {n} remote trips (git push/pull, ssh, rsync)", "sail", (2, 6), 60, "remote"),
    ("gaming", "Play for {n} minutes", "game_min", (20, 60), 5, "focus"),
    ("keybinds", "Use {n} Omarchy keybind actions", "kb:", (10, 25), 15, "shell"),
    ("themes", "Try {n} different themes", "theme", (1, 3), 150, "theming"),
]
CONTRACT_PER_DAY = 3      # tasks you can take in one day (first is automatic)

# ---------------------------------------------------------------- signals
# id, riddle, condition. Tiers draw 2 / 3 / 4 distinct steps.
SIGNAL_STEPS = [
    ("oracle", "Ask the oracle who knows every spell. (Hint: the list of keybinds)", ("sum", "keybindings", 1)),
    ("moment", "Capture a moment of the realm.", ("sum", "screenshot", 1)),
    ("night", "Bring dusk upon the land, then lift it.", ("sum", "toggle:nightlight", 1)),
    ("colours", "Repaint the world in another's colours.", ("sum", "theme", 1)),
    ("shadow", "Hide a window in the shadow realm, then call it back.", ("sum", "scratchpad", 1)),
    ("float", "Make a window rise above the others.", ("sum", "float", 1)),
    ("vast", "Let one window fill your whole sight.", ("sum", "fullscreen", 1)),
    ("ledger", "Write your deeds in the ledger of changes.", ("sum", "commit", 1)),
    ("scroll", "Read the scroll the system keeps of its troubles.", ("sum", "cmd:journalctl", 1)),
    ("tome", "Ask the package keeper what one of its wares is.", ("sum", "cmd:pacman", 1)),
    ("heart", "Gaze into the beating heart of the machine.", ("sum", "proc:btop", 1)),
    ("note", "Leave a note for your future self.", ("sum", "reminder", 1)),
    ("satchel", "Open the satchel of things you once copied.", ("sum", "panel:omarchy.clipboard", 1)),
    ("bundle", "Bind two windows together as one.", ("sum", "group", 1)),
    ("seeker", "Seek a word through many files at once.", ("sum", "search", 1)),
    ("pin", "Pop a window out so it follows you everywhere.", ("sum", "window:pop", 1)),
    ("faces", "Find the picture-words. (Hint: SUPER + CTRL + E)", ("sum", "panel:omarchy.emojis", 1)),
    ("glass", "Make a window as clear as glass.", ("sum", "window:transparency", 1)),
]
SIGNAL_TIERS = {   # steps, crate xp range (total), token chance
    "easy": (2, (300, 600), 0.10),
    "medium": (3, (900, 1500), 0.25),
    "hard": (4, (2500, 4000), 0.50),
}

# ---------------------------------------------------------------- diary
# tier id, title, tasks [(text, condition)], reward token xp
DIARIES = [
    ("easy", "Boot", [
        ("Complete Welcome to Omarchy", ("quest", "welcome")),
        ("Take a screenshot", ("sum", "screenshot", 1)),
        ("Switch theme", ("sum", "theme", 1)),
        ("Open the keybindings list", ("sum", "keybindings", 1)),
        ("Run 50 shell commands", ("sum", "cmd", 50)),
        ("Close 20 windows", ("sum", "win_close", 20)),
    ], 500),
    ("medium", "Login", [
        ("Complete 5 quests", ("quests", 5)),
        ("Make 3 git commits", ("sum", "commit", 3)),
        ("Reach total level 80", ("total", 80)),
        ("Collect a theme stamp", ("stamps", 1)),
        ("Float a window", ("sum", "float", 1)),
        ("Use the scratchpad", ("sum", "scratchpad", 1)),
        ("Complete 3 Contracts", ("contract", 3)),
        ("Solve a signal", ("signals", 1)),
    ], 1500),
    ("hard", "Root", [
        ("Complete 15 quests", ("quests", 15)),
        ("Complete Making Your Own Theme", ("quest", "make_theme")),
        ("Make 25 git commits", ("sum", "commit", 25)),
        ("Reach total level 250", ("total", 250)),
        ("Find a dotfile relic", ("relics", 1)),
        ("Master a keybind (50 uses)", ("tree", 3, 1)),
        ("Complete 15 Contracts", ("contract", 15)),
        ("Run 1,000 shell commands", ("sum", "cmd", 1000)),
        ("Use 15 different Omarchy keybind actions", ("distinct", "kb:", 15)),
    ], 5000),
    ("elite", "Kernel", [
        ("Complete every quest", ("quests", -1)),
        ("Reach total level 550", ("total", 550)),
        ("Reach a Rice rating of 350", ("rice", 350)),
        ("Collect 5 theme stamps", ("stamps", 5)),
        ("Get any skill to level 70", ("level", 70)),
        ("Complete 50 Contracts", ("contract", 50)),
        ("Solve 10 signals", ("signals", 10)),
        ("Make 100 git commits", ("sum", "commit", 100)),
    ], 15000),
]

# ---------------------------------------------------------------- random events
# id, title, message, kind (token | signal | xp_random | xp_focus), weight
RANDOM_EVENTS = [
    ("courier", "A courier pings you", "A package lands in your tray: one XP token. Redeem it on any skill for 10x its level in XP.",
     "token", 4),
    ("sysop_note", "The Sysop leaves a note", "A folded printout slides under the door. It's a signal.",
     "signal", 3),
    ("gremlin", "A gremlin in the wires", "Something chewed through a cable and the sparks land on one of your skills.",
     "xp_random", 3),
    ("coffee", "Fresh coffee", "Someone left a hot mug by your keyboard. You feel refreshed.",
     "xp_focus", 2),
]
RANDOM_COOLDOWN = 90 * 60   # seconds of real time between events
RANDOM_CHANCE = 1 / 120.0   # per active tick after the cooldown (~1 h of activity)

# ---------------------------------------------------------------- companions
# Nine pixel companions. Each one hatches, for certain, the moment its skill reaches the level
# below: no drop tables, no luck. id, name, skill, level (the icon has the same id in icons.py)
COMPANIONS = [
    ("hopper", "Hopper", "tiling", 10),
    ("glyph", "Glyph", "scripting", 15),
    ("lens_owl", "Lens owl", "searching", 15),
    ("pocket_mouse", "Pocket mouse", "browsing", 20),
    ("sproutling", "Sproutling", "agents", 20),
    ("prune_bot", "Prune bot", "cleanup", 25),
    ("tugboat", "Tugboat", "remote", 25),
    ("ping_fish", "Ping fish", "downloads", 30),
    ("dust_bunny", "Dust bunny", "workload", 35),
]

# ---------------------------------------------------------------- overclocks
# An overclock lands on one skill you train by doing things; for SURGE_MINUTES that skill's
# measured XP is doubled (not tokens, caches or agent awards).
SURGE_SKILLS = ["shell", "searching", "scripting", "building", "cleanup", "remote", "tiling",
                "theming", "downloads", "commits", "editing", "packages"]
SURGE_MINUTES = 15
SURGE_COOLDOWN = 2 * 3600     # seconds between overclocks
SURGE_CHANCE = 1 / 60.0       # per active tick after the cooldown (~30 min of activity)

# ---------------------------------------------------------------- theme seasons
# The theme you're wearing sets a season: one of the six areas gets SEASON_BONUS more measured XP
# while that theme is on. Which area is fixed per theme name, so every theme has a character.
SEASON_BONUS = 0.25
# Update Day: running `omarchy update` (once a day) boosts the System area for UPDATE_DAY_MINUTES
# and gives an XP token.
UPDATE_DAY_BONUS = 0.5
UPDATE_DAY_MINUTES = 60
UPDATE_DAY_TOKEN = 1500
# Theme stamps: wear a theme for STAMP_MINUTES active minutes to stamp it into your passport.
STAMP_MINUTES = 30
STAMP_XP = 300

# ---------------------------------------------------------------- the sysop
# One small "learn this" challenge a day, picked by date from the ones whose command is
# installed. id, task, hint, condition (sum <prefix> <n>), reward, required binary or None
SYSOP_CHALLENGES = [
    ("df", "Check how full your disks are", "df -h", ("sum", "cmd:df", 1), {"workload": 200}, "df"),
    ("du", "Find what is eating space in a folder", "du -sh ~/Downloads/*", ("sum", "cmd:du", 1), {"workload": 200}, "du"),
    ("journal", "Read this boot's errors", "journalctl -p 3 -b", ("sum", "cmd:journalctl", 1), {"focus": 200}, "journalctl"),
    ("man", "Read a manual page", "man rg   (q quits, / searches)", ("sum", "cmd:man", 1), {"shell": 200}, "man"),
    ("tldr", "Get the short version of a command", "tldr tar", ("sum", "cmd:tldr", 1), {"shell": 200}, "tldr"),
    ("which", "Find where a program lives", "which rg", ("sum", "cmd:which", 1), {"searching": 150}, "which"),
    ("systemctl", "See what services run as you", "systemctl --user list-units --type=service",
     ("sum", "cmd2:systemctl --user", 1), {"commits": 200}, "systemctl"),
    ("free", "Check your memory", "free -h", ("sum", "cmd:free", 1), {"focus": 150}, "free"),
    ("ip", "Find your IP address", "ip -br a", ("sum", "cmd:ip", 1), {"downloads": 200}, "ip"),
    ("ping", "Test your connection", "ping -c 3 archlinux.org", ("sum", "cmd:ping", 1), {"remote": 150}, "ping"),
    ("pacman_qi", "Ask the package keeper about a program", "pacman -Qi bash",
     ("sum", "cmd2:pacman -qi", 1), {"packages": 200}, "pacman"),
    ("theme", "Wear different colours today", "SUPER+CTRL+SHIFT+SPACE opens the theme picker",
     ("sum", "theme", 1), {"editing": 200}, None),
    ("keybinds", "Look up a keybind you don't know", "SUPER+K lists them all",
     ("sum", "keybindings", 1), {"shell": 150}, None),
    ("screenshot", "Capture a region of the screen", "PRINT, then drag", ("sum", "screenshot", 1), {"editing": 150}, None),
    ("git_log", "Read a repo's history", "git log --oneline -10", ("sum", "cmd2:git log", 1), {"commits": 150}, "git"),
    ("git_diff", "Review a change before committing it", "git diff --stat", ("sum", "cmd2:git diff", 1), {"tiling": 150}, "git"),
    ("btop", "Find what is using your CPU", "btop   (q quits)", ("sum", "proc:btop", 1), {"workload": 150}, "btop"),
    ("local_llm", "Ask your local AI something", "local-llm ask \"explain chmod 755\"",
     ("sum", "cmd:local-llm", 1), {"agents": 200}, "local-llm"),
    ("fd", "Find files by name", "fd -e md ~/Work", ("sum", "cmd:fd", 1), {"searching": 150}, "fd"),
    ("chmod", "Make a script executable", "chmod +x myscript.sh", ("sum", "cmd:chmod", 1), {"scripting": 150}, "chmod"),
    ("tar", "Pack a folder into an archive", "tar czf /tmp/notes.tar.gz ~/Documents",
     ("sum", "cmd:tar", 1), {"packages": 200}, "tar"),
    ("nightlight", "Rest your eyes", "SUPER+CTRL+N toggles nightlight", ("sum", "toggle:nightlight", 1), {"focus": 150}, None),
    ("rsync", "Back something up", "rsync -a ~/Documents/ /tmp/docs-backup/", ("sum", "cmd:rsync", 1), {"focus": 250}, "rsync"),
    ("history", "Search your shell history", "history | rg git", ("sum", "cmd:history", 1), {"searching": 150}, None),
]

# ---------------------------------------------------------------- job runs
# Queue a long job (a build, a download, a local-AI run) in one of four job
# slots; when it finishes, collect it for Workload XP by how long it ran.
JOB_SLOTS = ["Alpha", "Bravo", "Charlie", "Delta"]
HARVEST_BASE = 30          # xp for any finished job
HARVEST_PER_MIN = 6        # + xp per minute it ran
HARVEST_MAX = 1500
DEAD_SHARE = 0.1           # a job that failed (non-zero exit) pays 10%

# ---------------------------------------------------------------- daily streak
# The first active minute of each day continues (or restarts) your streak and pays
# STREAK_XP x streak (capped) to the day's skill; long streaks give XP tokens.
STREAK_XP = 20
STREAK_CAP_DAYS = 25
STREAK_TOKENS = {7: 1000, 30: 5000, 100: 20000, 365: 50000}

# ---------------------------------------------------------------- milestones
# Total level milestones: a notification, fireworks, and a collection log entry.
TOTAL_MILESTONES = list(range(100, 1700, 100)) + [1700]

# ---------------------------------------------------------------- quest xp scale
# Quests are a big XP source; scaled so their rewards stay meaningful next to the
# activity rates (skills.RATES). Applied once here, so the engine, panel and wiki agree.
QUEST_XP_MULT = 4
QUESTS = [(qid, name, qp, desc, {k: v * QUEST_XP_MULT for k, v in reward.items()}, auto, steps)
          for qid, name, qp, desc, reward, auto, steps in QUESTS]

# ---------------------------------------------------------------- level requirements
# Advanced content needs skill levels. A quest whose steps you've done still
# completes automatically the moment you meet its requirements.
QUEST_REQS = {
    "dev_tools": {"scripting": 5},
    "dotfiles_updates": {"packages": 5},
    "off_grid": {"agents": 5},
    "systemd": {"shell": 10},
    "troubleshooting": {"focus": 10},
    "hyprland": {"shell": 15, "tiling": 10},
    "quickshell": {"scripting": 10, "editing": 10},
    "make_theme": {"editing": 15},
    "snapshots_security": {"focus": 15},
    "arch_wiki": {"workload": 15},
    "ai_builder2": {"agents": 10},
    "ai_builder3": {"agents": 15, "commits": 10},
}

# Contracts the Dispatcher only assigns once your total level is this high.
CONTRACT_REQS = {"scripts": 60, "burn": 90, "commits": 90, "builds": 120, "voyages": 150, "themes": 40}

# Harder Sysop challenges, unlocked by level (same fields as SYSOP_CHALLENGES).
SYSOP_CHALLENGES += [
    ("ip_route", "See your default route to the internet", "ip route", ("sum", "cmd2:ip route", 1), {"remote": 300}, "ip"),
    ("nvim_edit", "Edit and save a file in Neovim", "nvim /tmp/practice.md   (i to type, Esc, then :wq)",
     ("sum", "proc:nvim", 1), {"editing": 300}, "nvim"),
    ("ss", "See which ports are listening", "ss -ltn", ("sum", "cmd:ss", 1), {"downloads": 300}, "ss"),
    ("lsblk", "Map your disks and partitions", "lsblk -f", ("sum", "cmd:lsblk", 1), {"workload": 300}, "lsblk"),
    ("sha256", "Fingerprint a file", "sha256sum ~/.bashrc", ("sum", "cmd:sha256sum", 1), {"focus": 300}, "sha256sum"),
    ("curl_head", "Read a web server's response headers", "curl -sI https://archlinux.org", ("sum", "cmd:curl", 1), {"browsing": 300}, "curl"),
    ("find_big", "Find the biggest files in your home", "find ~ -xdev -size +200M 2>/dev/null | head",
     ("sum", "cmd:find", 1), {"searching": 300}, "find"),
    ("sed_lines", "Print only lines 10-20 of a file", "sed -n '10,20p' ~/.bashrc", ("sum", "cmd:sed", 1), {"editing": 300}, "sed"),
    ("awk", "Count your most-used commands with awk", "history | awk '{print $2}' | sort | uniq -c | sort -rn | head",
     ("sum", "cmd:awk", 1), {"shell": 350}, "awk"),
    ("xargs", "Feed a list of files into a command", "fd -e md ~/Work | head -3 | xargs wc -l",
     ("sum", "cmd:xargs", 1), {"scripting": 350}, "xargs"),
    ("lsof", "See which program has a file open", "lsof +D ~/Downloads | head", ("sum", "cmd:lsof", 1), {"downloads": 300}, "lsof"),
    ("analyze", "Find what slows your boot", "systemd-analyze blame | head", ("sum", "cmd:systemd-analyze", 1),
     {"focus": 350}, "systemd-analyze"),
    ("journal_unit", "Read one service's log", "journalctl --user -u wireplumber -n 30",
     ("sum", "cmd2:journalctl --user", 1), {"focus": 350}, "journalctl"),
    ("resolve", "Look up a domain's address", "resolvectl query archlinux.org", ("sum", "cmd:resolvectl", 1),
     {"downloads": 350}, "resolvectl"),
    ("jq", "Read one value out of JSON", "jq '.total' ~/.local/state/omalvl/state.json",
     ("sum", "cmd:jq", 1), {"editing": 350}, "jq"),
    ("git_stash", "Park unfinished work with git stash", "git stash list   (then: git stash, git stash pop)",
     ("sum", "cmd2:git stash", 1), {"commits": 350}, "git"),
    ("tmux", "Split your terminal with tmux", "tmux   (CTRL+b then %, type exit to close)", ("sum", "cmd:tmux", 1),
     {"shell": 400}, "tmux"),
    ("strace", "Watch a program's system calls", "strace -c ls", ("sum", "cmd:strace", 1), {"shell": 450}, "strace"),
    ("llm_api", "Serve a local model and call its API", "local-llm serve 2b; curl -s 127.0.0.1:8080/v1/models; local-llm stop",
     ("sum", "cmd2:local-llm serve", 1), {"agents": 450}, "local-llm"),
]
# challenge id -> (skill, level) needed before the Sysop sets it
SYSOP_REQS = {
    "ip_route": ("remote", 5), "nvim_edit": ("editing", 5),
    "ss": ("downloads", 10), "lsblk": ("workload", 10), "sha256": ("focus", 10), "curl_head": ("browsing", 10),
    "find_big": ("searching", 10), "sed_lines": ("editing", 15), "awk": ("shell", 15), "xargs": ("scripting", 15),
    "lsof": ("downloads", 15), "analyze": ("focus", 15), "journal_unit": ("focus", 20), "resolve": ("downloads", 20),
    "jq": ("editing", 20), "git_stash": ("commits", 20), "tmux": ("shell", 25), "strace": ("shell", 30),
    "llm_api": ("agents", 20),
}


# ---------------------------------------------------------------- dotfile relics
# A commit that touches one of these config paths, in any watched repo, unearths that relic
# (once). id, name, path regex (matched against each file path in the commit)
RELICS = [
    ("hypr", "Hyprland relic", r"(^|/)hypr/|hyprland\.(conf|lua)$"),
    ("omarchy", "Omarchy relic", r"(^|/)omarchy/"),
    ("theme", "Palette relic", r"colors\.toml$|(^|/)themes?/"),
    ("terminal", "Terminal relic", r"(^|/)(alacritty|ghostty|kitty|foot|wezterm)/"),
    ("nvim", "Neovim relic", r"(^|/)nvim/|init\.(lua|vim)$"),
    ("shell", "Shell relic", r"(^|/)\.?(bashrc|zshrc|bash_profile|inputrc|profile)$|(^|/)fish/"),
    ("git", "Git relic", r"(^|/)\.?gitconfig$|(^|/)git/config$"),
    ("prompt", "Prompt relic", r"starship\.toml$"),
    ("tmux", "Tmux relic", r"(^|/)\.?tmux(\.conf|/)"),
    ("mise", "Runtime relic", r"(^|/)mise/|\.tool-versions$|mise\.toml$"),
]
RELIC_XP = {"theming": 600, "editing": 200}

# ---------------------------------------------------------------- the keybind tree
# Every Omarchy keybind action you use is a node on a branch; using it ranks it up.
# Branch: (id, name, event prefixes after "kb:", hint nodes shown before you find them)
TREE_BRANCHES = [
    ("windows", "Windows", ("float", "fullscreen", "scratchpad", "group", "pin", "movewindow", "window:"),
     ("float", "fullscreen", "scratchpad", "group", "window:pop", "window:transparency")),
    ("menus", "Menus", ("menu:", "keybindings"), ("menu:root", "menu:theme", "menu:capture", "keybindings")),
    ("toggles", "Toggles", ("toggle:",), ("toggle:nightlight", "toggle:idle")),
    ("capture", "Capture", ("capture:",), ("capture:screenshot", "capture:text-extraction", "capture:text-dictation")),
    ("panels", "Panels", ("panel:",), ("panel:omarchy.clipboard", "panel:omarchy.emojis")),
]
TREE_RANKS = [(1, "Learned", 100), (10, "Practiced", 300), (50, "Mastered", 1000)]   # uses, title, Shell XP

# ---------------------------------------------------------------- rice rating
# The Rice rating (10-1000) is ten times the mean of your six area levels; an area's level is the
# mean of its skills. Ranks: (rating, title)
RICE_RANKS = [(0, "Fresh install"), (100, "Tinkerer"), (200, "Ricer"), (350, "Daily driver"),
              (500, "Power user"), (650, "Dotfile sage"), (800, "Kernel whisperer"), (1000, "Omarchist")]

# ---------------------------------------------------------------- panel skins
# Frame styles for the panel, unlocked by Rice rating: (id, name, rating needed)
SKINS = [("plain", "Plain", 0), ("rivet", "Rivet", 150), ("circuit", "Circuit", 300),
         ("scanline", "Scanline", 450), ("neon", "Neon", 600), ("glyph", "Glyph", 800)]
