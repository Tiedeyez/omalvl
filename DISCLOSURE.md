# Disclosure

What OmaLvL puts on your computer and what it looks at, written from the source at this commit.

## What it is and what runs it

OmaLvL is an Omarchy shell plugin of kind `bar-widget`. Its entry point, `Panel.qml`, runs inside `omarchy-shell` (Quickshell) **with your user account's full access, unsandboxed**, like every Omarchy plugin. It loads only after you add it to your bar.

`Panel.qml` starts one long-running helper, `skills.py daemon` (Python standard library only), which does the measuring. By default, activity data stays local. If you configure an offsite backup folder, OmaLvL writes copies there; that folder may be synced by another service.

## What it needs

- Omarchy's shell (Quickshell with Qt 6).
- `/usr/bin/python3` (any Python 3.9+). No Python packages beyond the standard library.
- Optional: `tldr` and a local model server on `127.0.0.1:8080` for the Sysop's "Explain it" button.

## What it reads, and why

The daemon wakes every 30 seconds. Two background threads watch Hyprland's events and new processes.

| What | How | What is kept |
|---|---|---|
| Keyboard and touchpad interrupt counts | `/proc/interrupts` (the `i8042` line) | Whether you were active this tick. No keys, no timings. |
| CPU, disk and network totals | `/proc/stat`, `/proc/diskstats`, `/proc/net/dev` | Byte and tick counters, turned into XP. |
| Window events (open, close, focus, workspace, fullscreen, float, group) | Hyprland's event socket (`.socket2.sock`) | Counts per event type. No window titles. |
| The focused window's class and the cursor position | `hyprctl activewindow -j`, `hyprctl cursorpos -j` | Whether a game window is focused (classes in the built-in list or your `games` setting), and whether the pointer moved. Neither is stored. |
| New processes, six times a second | `/proc/<pid>/cmdline` and `/proc/<pid>/stat` of **your own** processes that just appeared (other users' processes are skipped before anything is read) | One event name when it is an Omarchy keybind command (`omarchy-toggle-nightlight` → `toggle:nightlight`), a known tool (`nvim`, `btop`) or an AI agent / local model runtime. Event names come from a fixed list of Omarchy's own menus, panels, toggles, window and capture commands; any other name is counted as `menu:other`, `panel:other` and so on, so no argument is ever stored. Older saves are folded the same way on the next save. |
| Running AI agents' and local models' CPU time | `ps -o comm= -u <your uid>`, and `/proc/<pid>/stat` (plus `/proc/<pid>/cmdline` for agents run by `node`, `python`, `bun` or `deno`) of **your own** processes only; other users' processes are skipped before anything is read | CPU seconds, turned into Agents XP (agent CLIs) and Models XP (local runtimes), and the agent's name from a fixed list (`claude`, `opencode`, `ollama`, `llama.cpp` ...). A process or script name that only starts like a runtime (`llama-server`, `whisper-cli`) is counted under that runtime's fixed name; script paths and arguments are never stored, and anything else is `agent:other`. Older saves are folded the same way on the next save. |
| Shell history: `~/.bash_history`, `~/.zsh_history`, `~/.local/share/fish/fish_history` | Read from the last position onwards, at most 1 MiB per tick | Command counts, plus names from a fixed allowlist and fixed safe pairs (for example `git` and `git log`). Arbitrary words, arguments and environment assignments are not stored. On the first save after updating, old arbitrary `cmd:` / `cmd2:` counters are removed from state and up to 256 app backup JSON files (64 MiB total); if this limit is exceeded, the program warns that older files need manual review or removal. Turn it off with `"shellHistory": false`. |
| Package installs and upgrades | `/var/log/pacman.log`, streamed line by line | Two counts. |
| Chromium visit count | `~/.config/chromium/*/History`, opened read-only with SQLite (`immutable=1`) | One number: the visit count. No URLs, no titles. **Off unless you set `"browserHistory": true`.** |
| Size of `~/Downloads` | Directory sizes | One number. File names are not stored. |
| New screenshots | Names matching `~/Pictures/screenshot-*` | A count. |
| Git commits | `git rev-list --count HEAD` and `git show --numstat HEAD` in each repo directly inside `~/Work`, `~/Projects`, `~/src`, `~/code`, `~/dev`, `~/git` (or your `repos` setting) | Commit counts and how many files changed, were added or were removed. The newest commit's file paths are matched against a list of config paths (for dotfile relics) and then discarded. No code or messages are read. |
| The theme | `~/.local/state/omarchy/current/theme/colors.toml` (the first 64 KiB, `name = "#rrggbb"` lines only) and `theme.name` | Colours for the pixel art; a count of theme changes; the theme name and minutes worn (for seasons and stamps). |
| Config saves | File modification times (never contents) in `~/.config/` `hypr`, `omarchy` (not `plugins`), `alacritty`, `ghostty`, `kitty`, `foot`, `nvim`, `tmux`, `fish`, `mise`, `btop`, `fastfetch` and `starship.toml`; at most 3,000 files, three folders deep | How many files were saved this tick, turned into Theming XP. |
| The focused monitor's size | `hyprctl monitors -j`, only when you run `omalvl wallpaper` | The size of the PNG to draw. |
| Its own files | `~/.config/omalvl/config.json` (at most 64 KiB), `~/.local/state/omalvl/state.json` and backups (at most 4 MiB per file) | Settings and your progress. The panel receives a display snapshot from the helper, not the raw save file. |

OmaLvL reads only the paths listed above. It does not read general documents, window titles or contents, the clipboard, or keystrokes. The shell-history exception is deliberate: it reads appended history lines, retains command counts and only allowlisted command names or fixed safe pairs, and discards arguments. It does not read browser URLs. The local-model request described below is the only HTTP request.

## What it writes

| Where | What |
|---|---|
| `~/.local/state/omalvl/state.json` (+ `.bak`, `.lock`, `.lock.daemon`) | Your progress. State and backup files are written atomically with private mode `0600` (fsync'd, then renamed). OmaLvL's folders (`~/.local/state/omalvl`, `backups`, `jobs`, `weekly` and the offsite host folder) are created `0700`; on the first save after updating, files an older build left readable in them (job logs, exit files, weekly reports, kept-aside saves) are set to `0600` (your own regular files only; symlinks are never followed). |
| `~/.local/state/omalvl/backups/` | One copy a day (14 kept), plus a copy before every reset, restore or import. Backups from before 1.0.8 are cleaned once on the first save: the same scrub as the state (history names, event names, keybind tree keys, job labels) is applied, and the display views an older build saved beside the state (`treeInfo`, `jobInfo` and the rest) are dropped, since they were built from unscrubbed data; the raw progress, and so `omalvl restore`, is kept. Cleaned files are marked with `meta.privV` so current backups are not rewritten. A manual `omalvl backup` copies only the scrubbed raw state. |
| `~/.local/state/omalvl/weekly/` | A short text report each week, written atomically with private mode `0600`. |
| `~/.local/state/omalvl/jobs/` | Output and exit codes of jobs you queue with `omalvl run`, private mode `0600`. The state file (and so its backups) keeps only the job's program name, such as `make ...`; its arguments are never saved. Job labels from releases before 1.0.6 are re-cut to the program name on the next load or save, before any backup is written, and marked with `labelV` so the clean-up never has to guess from the text. |
| The folder named by `offsite` in your config | A daily off-machine copy (60 kept), written atomically with private mode `0600`. Off unless you set it. |
| `~/.local/share/omalvl/wiki/` | The offline wiki, only when you run `omalvl wiki`. It shows your stats and some machine details, so the folder is owner-only (`0700`) and every page is `0600`; pages from older builds are corrected on the next build. |
| `~/Pictures/omalvl/` (or `--out`) | A wallpaper PNG, only when you run `omalvl wallpaper`. Nothing sets it as your background; you run `omarchy-theme-bg-set` yourself. |

## Subprocesses

Commands are launched by an absolute path, preferring `/usr/bin/<name>` and falling back to the resolved helper path when Omarchy installs a tool elsewhere. Ordinary helper arguments are passed as separate arguments, not pasted into a shell command. `omalvl run` is the exception by design: it runs the command the user explicitly typed in a separate shell session.

- From the panel: `/usr/bin/python3 -I skills.py daemon` runs as the long-lived sampler; `icons --json` runs at startup, `panel-state` runs every three seconds, `guide <skill> --json` runs when you select a guide, and the action you click runs on demand (`quest`, `contract new|skip`, `token`, `collect`, `skin`, `sysop explain`). The panel receives a bounded display snapshot and never reads the save file directly.
- From the daemon: `hyprctl`, `ps`, `git`, `notify-send` (level-ups and events).
- `omalvl wallpaper` runs `hyprctl monitors -j` for the screen size.
- `omalvl run <command>` runs **the command you typed** in `sh -c`, in its own session; that is what a job slot is for.
- `omalvl sysop explain` runs `tldr <command>` and, if `local-llm` is installed, `local-llm serve` / `local-llm stop`.
- `omalvl wiki` runs `git log`, `lsblk`, `bash --version`, `pacman -Qq`, `hyprctl version` and `omarchy-theme-current` for its "on this machine" facts, then `xdg-open` on the result (unless `--no-open`).

## Network

The only HTTP request is to `http://127.0.0.1:8080` (a local model on your own machine), and only when you press "Explain it". It is a direct loopback connection: proxy settings such as `http_proxy` are ignored and redirects are refused, so the prompt cannot be passed on. OmaLvL makes no remote HTTP requests and has no telemetry, analytics, account service or auto-update. An optional offsite backup is a filesystem write to the folder you configure, not an HTTP upload; if that folder is synced, the sync service handles transfer.

## Fair play

OmaLvL voids XP that real use doesn't back up (agent awards and manual adds above what your recent activity supports, where activity means minutes at the keyboard or minutes in which an agent or local model was measurably using CPU, a sweep across many skills at once, repeated awards for the same work, and measured XP from a machine that is "active" around the clock). Every change is tallied by source, and an account whose save was edited by hand shows as **unverified**. The public release has no admin override. Historical grants from the maintainer's local-only override remain recorded with their reason and shown on that local fair-play card. All of this is local and readable in `anticheat.py`; nothing is reported anywhere.

## Files that are not part of the running plugin

- `tools/contact_sheet.py`: renders the icons to a PNG with ImageMagick (`magick`), writing only the path you give.
- `tests/`: unit tests. They use a temporary folder and never touch your real state.
- `migrate.py`: a local-only importer for the prototype's save format. It is intentionally excluded from the public package; `omalvl import` reports that it is unavailable there.
- `admin.local.py`: a maintainer-only local override. It is intentionally excluded from the public package.
- `promo/`: the sizzle reel's source, kept out of the plugin repo. The rendered reels are attached to GitHub releases; their music is original and generated by a script (MIT).

## Maintainer and licence

Tiedeyez, MIT licence (see [LICENSE](LICENSE)). All art (icons, pixel font) and all names are original to OmaLvL.

## Check it yourself

```bash
# every subprocess the engine can start:
grep -nE "subprocess\.(run|Popen)" skills.py wiki.py
# the only network address:
grep -n "urlopen\|LLM_URL =" skills.py
# what the panel runs:
grep -nE "command|run\(\[" Panel.qml
# the tests (temporary state only):
python3 -m unittest discover -s tests
```
