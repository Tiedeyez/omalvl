# OmaLvL

Level up by using your Omarchy machine.

![OmaLvL: six area cards and the Rice rating hexagon in the bar panel](preview.png)

OmaLvL is a bar widget for [Omarchy](https://omarchy.org). It watches what you actually do (commands, keybinds, commits, builds, theme changes, window moves) and turns it into XP across 17 skills in six areas: Terminal, Desktop, Code, System, Web and AI. Quests teach Omarchy, Linux and AI by having you do them. Everything is drawn as pixel art in your current theme's colours, and it all stays on your machine.

**Sizzle reel:** [16:9](https://github.com/Tiedeyez/omalvl/releases/latest/download/omalvl-reel-16x9.mp4) · [9:16](https://github.com/Tiedeyez/omalvl/releases/latest/download/omalvl-reel-9x16.mp4) · [1:1](https://github.com/Tiedeyez/omalvl/releases/latest/download/omalvl-reel-1x1.mp4)

## What's in it

- **17 skills in six areas**, each named for what trains it: Shell, Scripting, Searching · Tiling, Theming, Focus · Commits, Editing, Building · Packages, Cleanup, Workload · Browsing, Downloads, Remote · Agents, Models. Levels run 1 to 100 on OmaLvL's own curve.
- **Rice rating.** Your six area levels drawn as a hexagon, scored 10 to 1000, with ranks from Fresh install to Omarchist. Your weakest area tells you what to train next.
- **Theme seasons.** Every Omarchy theme favours one area (+25% XP while you wear it). Wear a theme for 30 active minutes to stamp it into your passport.
- **Update Day.** Running `omarchy update` boosts System XP for an hour and gives an XP token.
- **Dotfile relics.** Commit your config (hypr, nvim, colours, shell, git, tmux ...) to unearth a relic for each.
- **Keybind tree.** Every Omarchy action you use is a node: learned at 1 use, practised at 10, mastered at 50.
- **Skins and wallpaper.** Panel frames unlock with your Rice rating, and `omalvl wallpaper` draws your stats as a pixel wallpaper in your theme's colours.
- **Quests** with step-by-step helpers; most complete themselves when you do the steps.
- **Daily contracts** from the Dispatcher, **signals** (desktop riddles that solve themselves), **XP tokens**, the **Sysop's** daily "learn this command" challenge (with an optional local-AI explanation), **overclocks** (double XP on one skill for 15 minutes) and **job slots** (queue a long build or download, collect XP when it's done).
- **A journal** of four tiers (Boot, Login, Root, Kernel), **companions** that hatch at set skill levels (no luck involved), **mastery marks** at 100, and an **offline wiki** generated from the game data (`omalvl wiki`).
- **Fair play.** No cap on how fast you level by using the machine, but XP that real use doesn't back up is voided (see below).

## Install

```bash
omarchy plugin add https://github.com/Tiedeyez/omalvl
```

Then add `tiedeyez.omalvl` to a bar section in `~/.config/omarchy/shell.json` (or the bar settings), and put the CLI on your `PATH`:

```bash
ln -s ~/.config/omarchy/plugins/tiedeyez.omalvl/bin/omalvl ~/.local/bin/omalvl
```

Needs only Omarchy's shell and `/usr/bin/python3` (standard library). No other dependencies.

## Remove

Take `tiedeyez.omalvl` out of your bar, then:

```bash
omarchy plugin remove tiedeyez.omalvl
rm -f ~/.local/bin/omalvl
rm -rf ~/.local/state/omalvl ~/.config/omalvl ~/.local/share/omalvl   # your progress, settings and wiki, if you want them gone
```

## Use

Click the bar button for the panel. From a terminal:

```bash
omalvl                 # your skills, by area
omalvl rice            # Rice rating, rank and what to train next
omalvl quests          # quest list;   omalvl quest <id>  for its steps
omalvl contract        # today's contract;  omalvl contract new | skip
omalvl season          # this theme's season, your stamps, Update Day
omalvl tree            # the keybind tree
omalvl relics          # dotfile relics
omalvl skin rivet      # wear an unlocked panel skin
omalvl wallpaper       # draw your stats as a wallpaper (then: omarchy-theme-bg-set <file>)
omalvl guide shell     # a skill's guide
omalvl run make -j8    # queue a long job in a job slot; omalvl collect when it's done
omalvl fair            # fair-play status
omalvl backup          # save a copy now and list backups;  omalvl restore latest
omalvl wiki            # build and open the offline wiki
omalvl help            # everything
```

## Settings

Optional, in `~/.config/omalvl/config.json`:

```json
{
  "repos": ["~/Work/*", "~/Projects/*"],
  "offsite": "~/Sync/omalvl-backups",
  "browserHistory": false,
  "shellHistory": true,
  "games": ["mygameclient"],
  "reduceMotion": false
}
```

| Key | Default | What it does |
|---|---|---|
| `repos` | `~/Work/*`, `~/Projects/*`, `~/src/*`, `~/code/*`, `~/dev/*`, `~/git/*` | Where commits (and dotfile relics) are counted. |
| `offsite` | off | A folder synced to another machine for a daily off-machine copy of your save. |
| `browserHistory` | `false` | Count Chromium visits (a number only) for the Browsing skill. |
| `shellHistory` | `true` | Read your shell history (first words only) for Shell, quests and challenges. |
| `games` | a built-in list of emulators and launchers | Extra window classes that count as playing (Focus). |
| `reduceMotion` | `false` | Turn off the pixel dissolve and hover lift. |

## Fair play

Leveling is never capped: measured activity is already paced per 30-second tick. What's voided is XP that real use doesn't back up:

- Agent awards (`omalvl agent`) and manual adds share a budget of 5,000 XP plus 100 per worked minute in the last 24 hours, and 30,000 per award. A worked minute is one where you were at the keyboard **or an AI agent or local model was measurably working for you** (the daemon sees its CPU time), so work you wait on earns XP too. Each hour counts at most 60 worked minutes.
- Awards across more than 6 skills in 15 minutes are voided (a sweep across every skill is the botting pattern).
- The same work can't be awarded twice in a week, and an award needs a real description.
- A machine "active" for more than 20 of the last 24 hours stops earning measured XP until the pattern breaks.
- Every XP change is tallied by source. If the save is edited by hand, the account shows as unverified.

`omalvl fair` and the panel's Log tab show the status.

## Privacy

OmaLvL processes activity locally. It stores counts and small command prefixes from shell history; it does not send activity anywhere. If you enable offsite backups, it writes save copies to the folder you choose, which may be synced elsewhere. The optional Sysop explanation uses a local model endpoint only when you press its button. [DISCLOSURE.md](DISCLOSURE.md) lists the exact files, data and subprocesses.

## Develop

```bash
python3 -m unittest discover -s tests     # engine tests (temporary state only)
python3 tools/contact_sheet.py ~/.local/state/omarchy/current/theme/colors.toml /tmp/icons.png
```

The engine is `skills.py` (plus `content.py` for quests and tasks, `anticheat.py` for fair play, `wallpaper.py` for the wallpaper), the panel is `Panel.qml`, the art is `icons.py` (12x12 bitmaps) and `pixelfont.py` (a 5x7 face).

## Licence

The OmaLvL source, in-product artwork and the sizzle reel's music are MIT licensed; see [LICENSE](LICENSE). All in-product art and names are original to OmaLvL.
