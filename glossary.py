"""Glossary for the OmaLvL Wiki: Linux, developer, hacker-culture and AI terms, each a
teaching page. wiki.py turns every entry into term-<id>.html and auto-links the first
mention of any term (or alias) on every page, like Wikipedia.

Entry fields:
  id       page id (term-<id>.html)
  term     display name
  cat      category key (see CATEGORIES)
  aliases  extra words that link here (case-insensitive; a plural "s"/"es" also matches).
           Keep them unambiguous: common English words are left out on purpose.
  short    one sentence, shown in lists and tooltips
  body     paragraphs; `backticks` become code, {skill:key} {quest:id} {page:file|text} become links
  try      [(command, what it shows)] — all safe, read-only or easily undone
  related  ids of other terms
  irl      optional: where it shows up in this game
"""

CATEGORIES = [
    ("shell", "Shell & terminal"),
    ("files", "Files & storage"),
    ("system", "Processes & the system"),
    ("packages", "Packages & software"),
    ("net", "Networking"),
    ("dev", "Git & development"),
    ("desktop", "Desktop: Omarchy, Hyprland, Wayland"),
    ("security", "Security & hacker culture"),
    ("ai", "AI & local models"),
]

T = []


def term(id, term, cat, short, body, try_=(), related=(), aliases=(), irl=""):
    T.append({"id": id, "term": term, "cat": cat, "short": short, "body": body,
              "try": list(try_), "related": list(related), "aliases": list(aliases), "irl": irl})


# ------------------------------------------------------------------ shell & terminal
term("terminal", "Terminal", "shell",
     "A window where you type commands as text instead of clicking.",
     ["A terminal (or terminal emulator) is the program that shows a text screen and sends what you type to a "
      "shell. Omarchy opens one with `SUPER + RETURN`; its default terminal is set by `$TERMINAL`.",
      "The terminal draws the text; the shell inside it understands the commands. That is why you can change "
      "the shell without changing the terminal, and vice versa."],
     [("echo $TERM", "the terminal type the shell thinks it's in")],
     ["shell", "command-line", "prompt-shell"], ["terminal emulator", "terminals"],
     "Opening one with the keybind counts as a keybind action ({skill:shell}).")

term("shell", "Shell", "shell",
     "The program that reads your commands, runs them, and shows the results.",
     ["The shell is a command interpreter: you type `ls`, it finds the `ls` program and runs it. It also "
      "gives you variables, history, tab completion, pipes and scripting.",
      "Bash is the most common default; zsh and fish are popular alternatives. A shell running inside a terminal is "
      "called an interactive shell; one running a script file is non-interactive."],
     [("echo $SHELL", "your login shell"), ("type cd", "shows that cd is built into the shell itself")],
     ["bash", "terminal", "shell-script", "environment-variable"], ["shells"],
     "Every command you type is read from your shell history and trains {skill:shell}.")

term("bash", "Bash", "shell",
     "The Bourne Again SHell: the default shell on most Linux systems, including this one.",
     ["Bash reads `~/.bashrc` when it starts, which is where aliases, the prompt and settings like "
      "`PROMPT_COMMAND` live. This game adds `history -a` to `PROMPT_COMMAND` so every command is written to "
      "`~/.bash_history` the moment you run it, instead of when the terminal closes.",
      "Bash is also a scripting language: a file starting with `#!/bin/bash` is a bash script."],
     [("bash --version", "which bash you have"), ("help", "the list of bash builtins")],
     ["shell", "shell-script", "dotfiles", "shell-history"], [],
     "")

term("command-line", "Command line", "shell",
     "Working by typing commands; also called the CLI (command-line interface).",
     ["A CLI program is driven by text: its name, then arguments and flags. `omalvl`, `git`, `pacman` and "
      "`local-llm` are all CLIs. A GUI (graphical user interface) is the clicky opposite.",
      "CLIs are easy to script, repeat, search in your history and run over SSH, which is why developers "
      "lean on them."],
     [("omalvl help", "this game's own CLI")],
     ["shell", "argument", "flag", "terminal"], ["CLI", "command-line interface", "command line"])

term("prompt-shell", "Shell prompt", "shell",
     "The text before your cursor that says the shell is ready for a command.",
     ["The prompt often shows your user, host and current directory, and ends in `$` (normal user) or `#` "
      "(root). Bash builds it from the `PS1` variable."],
     [("echo \"$PS1\"", "the recipe for your prompt")],
     ["shell", "environment-variable", "root"], ["shell prompt"])

term("path-var", "PATH", "shell",
     "The list of directories the shell searches for programs.",
     ["When you type `rg`, the shell looks through each directory in `$PATH`, in order, for a file named "
      "`rg`. That is why tools you install in `~/.local/bin` work: it's on your PATH.",
      "If a program says 'command not found', it's either not installed or not in a PATH directory."],
     [("echo $PATH | tr ':' '\\n'", "one PATH directory per line"), ("which omalvl", "where the shell found omalvl")],
     ["environment-variable", "shell", "absolute-path"], ["$PATH"])

term("environment-variable", "Environment variable", "shell",
     "A named value a program inherits from the shell, like HOME or PATH.",
     ["Variables like `HOME`, `PATH`, `SHELL` and `EDITOR` are passed from parent processes to their "
      "children. Programs read them for settings; `MANWIDTH=80 man ls` sets one just for that command.",
      "`export NAME=value` sets one for the rest of the session; put it in `~/.bashrc` to keep it."],
     [("env | head", "some of your environment"), ("echo $HOME", "your home directory")],
     ["path-var", "shell", "process", "dotfiles"], ["environment variables", "env var", "env vars"])

term("alias", "Alias", "shell",
     "A short name you define for a longer command.",
     ["`alias ll='ls -la'` makes `ll` run `ls -la`. Aliases live in `~/.bashrc` so they load in every new "
      "shell. Omarchy ships several, and `alias` with no arguments lists them."],
     [("alias", "every alias defined in this shell")],
     ["bash", "dotfiles", "shell"], ["aliases", "shell alias"])

term("pipe", "Pipe", "shell",
     "The `|` symbol: it sends one command's output into the next command's input.",
     ["`history | rg git` sends your whole history into `rg`, which keeps only lines with 'git'. Chaining "
      "small tools with pipes is the core Unix idea: each program does one thing well.",
      "A pipe connects stdout of the left side to stdin of the right side."],
     [("ls /usr/bin | wc -l", "count the programs in /usr/bin"), ("history | rg git | tail -5", "your last five git commands")],
     ["standard-streams", "redirection", "grep", "unix-philosophy"], ["pipes", "pipeline", "piping"])

term("redirection", "Redirection", "shell",
     "Sending a command's output to a file (`>`, `>>`) or reading input from one (`<`).",
     ["`cmd > out.txt` overwrites out.txt with the output; `>>` appends; `2>` redirects errors; `&>` both. "
      "`> /dev/null` throws output away. Careful: `>` replaces the file without asking."],
     [("ls ~ > /tmp/home.txt && cat /tmp/home.txt", "write a listing to a file, then show it")],
     ["pipe", "standard-streams", "dev-null"], ["output redirection", "redirect"])

term("standard-streams", "stdin, stdout, stderr", "shell",
     "The three text channels every program has: input, normal output and error output.",
     ["Standard input (0) is what a program reads, standard output (1) is its normal output, standard "
      "error (2) is for errors. Keeping errors separate means a pipe can carry clean data while errors "
      "still show on screen."],
     [("ls /nope 2>/dev/null; echo done", "hide the error, keep going")],
     ["pipe", "redirection", "exit-code"], ["stdout", "stderr", "stdin", "standard output", "standard error", "standard input"])

term("dev-null", "/dev/null", "shell",
     "A special file that throws away whatever is written to it.",
     ["Writing to `/dev/null` discards the data; reading from it gives nothing. It's how you silence "
      "output: `command > /dev/null 2>&1`."],
     [("echo gone > /dev/null", "nothing appears")],
     ["redirection", "standard-streams", "device-file"], [])

term("exit-code", "Exit code", "shell",
     "A number a program returns when it ends: 0 means success, anything else means failure.",
     ["The shell keeps the last exit code in `$?`. `&&` runs the next command only on success, `||` only on "
      "failure. Scripts and tools (like this game's {page:job-runs.html|job runs}) use it to know "
      "whether a job worked."],
     [("true; echo $?", "prints 0"), ("false; echo $?", "prints 1")],
     ["standard-streams", "shell-script", "process"], ["exit status", "return code", "exit codes"],
     "A queued job that ends with a non-zero exit code counts as failed and pays a tenth.")

term("argument", "Argument", "shell",
     "A word you pass to a command, like the file name in `cat notes.md`.",
     ["Everything after the command name is split into arguments by spaces (quotes keep spaces together). "
      "Arguments starting with `-` are usually flags."],
     [("echo one 'two three' four", "three arguments")],
     ["flag", "command-line", "glob"], ["arguments", "command-line argument"])

term("flag", "Flag", "shell",
     "An option that changes how a command behaves, like `-h` or `--help`.",
     ["Short flags are one dash and one letter (`-l`), and can often be combined (`-la`). Long flags are two "
      "dashes and a word (`--oneline`). `--help` is the near-universal way to ask a command what it accepts."],
     [("ls -la", "long listing, including hidden files"), ("git log --oneline -5", "compact history")],
     ["argument", "man-page", "command-line"], ["command-line flag", "command-line flags", "command-line option", "--help"])

term("man-page", "Man page", "shell",
     "The built-in manual for a command: `man <command>`.",
     ["Man pages are the full reference. Inside, `/word` searches, `n` jumps to the next match and `q` quits. "
      "They're split into sections: 1 for commands, 5 for file formats, 8 for admin tools."],
     [("man rg", "ripgrep's manual"), ("man 5 passwd", "the passwd file format")],
     ["tldr", "flag", "command-line"], ["man pages", "manual page", "manpage"],
     "Reading one is a {page:sysop.html|Sysop} challenge.")

term("tldr", "tldr", "shell",
     "Short, example-first help pages for common commands.",
     ["Where man pages are complete, tldr pages are the five commands you actually need. They're cached "
      "locally, so they work offline. The Sysop's local-AI explanations are grounded in them."],
     [("tldr tar", "the handful of tar commands you'll use"), ("tldr git-log", "git log examples")],
     ["man-page", "local-model", "grounding"], ["tldr pages"])

term("shell-history", "Shell history", "shell",
     "The list of commands you've run, saved to a file.",
     ["Bash keeps it in `~/.bash_history`. `history` prints it, `CTRL+R` searches it as you type, and `!!` "
      "repeats the last command. This game reads new lines from it to award XP; nothing leaves the machine."],
     [("history | tail", "your last few commands"), ("history | rg ssh", "every ssh you've run")],
     ["bash", "pipe", "grep"], ["bash history", "command history", ".bash_history"],
     "The source of {skill:shell}, {skill:searching}, {skill:scripting}, {skill:building}, {skill:cleanup} and {skill:remote} XP.")

term("tab-completion", "Tab completion", "shell",
     "Press TAB and the shell finishes the command or file name for you.",
     ["Type `cd ~/Wo` and press TAB: it becomes `cd ~/Work/`. Press TAB twice to see all options. It saves "
      "typing and prevents typos in long paths."],
     [], ["shell", "absolute-path"], ["tab complete", "autocomplete"])

term("shell-script", "Shell script", "shell",
     "A text file of shell commands that runs like a program.",
     ["Starts with a shebang (`#!/bin/bash`), then commands, one per line. Make it executable with "
      "`chmod +x script.sh` and run it as `./script.sh`. `local-llm`, `omalvl` and Omarchy's own `omarchy-*` "
      "commands are scripts."],
     [("head -20 ~/.local/bin/local-llm", "the start of a real script")],
     ["shebang", "bash", "permissions", "exit-code"], ["shell scripts", "bash script", "script"],
     "Running scripts trains {skill:scripting}; writing one with an agent is {quest:ai_builder3}.")

term("shebang", "Shebang", "shell",
     "The `#!` first line of a script that says which program should run it.",
     ["`#!/bin/bash` runs the file with bash, `#!/usr/bin/env python3` with whichever python3 is on your "
      "PATH. Without it, you'd have to type `bash script.sh`."],
     [("head -1 ~/.local/bin/local-llm", "a shebang")],
     ["shell-script", "path-var", "python"], ["hashbang", "#!"])

term("sudo", "sudo", "shell",
     "Run one command as the administrator (root), after typing your password.",
     ["`sudo pacman -S foo` installs software system-wide. sudo asks for your password, logs what you ran, "
      "and only lasts for that command. Use it for the few things that need it, not as a habit."],
     [("sudo -l", "what you're allowed to run (asks for your password)")],
     ["root", "permissions", "least-privilege"], ["superuser do"],
     "This game never needs it: everything it reads is yours.")

term("root", "root (superuser)", "shell",
     "The all-powerful administrator account on a Unix system.",
     ["root can read and change anything, including other users' files and the system itself. Normal work "
      "happens as your own user; sudo borrows root for one command. A `#` prompt usually means you're root."],
     [("id", "your user and groups (uid 0 would be root)")],
     ["sudo", "permissions", "least-privilege"], ["superuser", "root user", "root account"])

term("dotfiles", "Dotfiles", "shell",
     "Your personal config files, hidden because their names start with a dot.",
     ["`~/.bashrc`, `~/.gitconfig`, `~/.config/...`: dotfiles are how you customise tools. Many people keep "
      "them in a git repo and symlink them into place; a customised desktop setup is called a rice."],
     [("ls -a ~ | head", "the hidden files in your home"), ("ls ~/.config", "per-app config folders")],
     ["hidden-file", "config-file", "symlink", "git"], ["dotfile", "rice", "ricing"])

term("regex", "Regular expression", "shell",
     "A pattern language for matching text, used by grep, rg, sed and most editors.",
     ["`^` is start of line, `$` end, `.` any character, `*` repeat, `[0-9]` a digit. `rg '^def '` finds "
      "lines starting with 'def '. Powerful, but quote them so the shell doesn't touch the symbols."],
     [("rg -n '^def ' ~/.config/omarchy/plugins/omalvl/skills.py | head", "every function definition")],
     ["grep", "ripgrep", "glob"], ["regular expression", "regular expressions", "regexp", "regexes"])

term("glob", "Glob (wildcard)", "shell",
     "Shell patterns like `*.png` that expand to matching file names.",
     ["`*` matches anything, `?` one character, `{a,b}` either. The shell expands them before the command "
      "runs, so `ls *.md` really receives the list of .md files. Globs are simpler than regex."],
     [("ls ~/Pictures/*.png | head", "your PNGs")],
     ["regex", "argument", "shell"], ["wildcard", "wildcards", "globbing"])

term("grep", "grep", "shell",
     "The classic tool that prints lines matching a pattern.",
     ["`grep -r word dir` searches files recursively; `-i` ignores case, `-n` shows line numbers. Modern "
      "replacements like ripgrep are faster, but grep is everywhere."],
     [("grep -c bash /etc/passwd", "how many accounts use bash")],
     ["ripgrep", "regex", "pipe"], [],
     "Searches train {skill:searching} and count for the Contract 'Run N searches'.")

term("ripgrep", "ripgrep (rg)", "shell",
     "A very fast recursive search tool: `rg pattern`.",
     ["ripgrep searches the current directory tree, skips files listed in .gitignore, and uses all CPU "
      "cores in parallel. That's why it's the default search in Omarchy and in most AI coding agents."],
     [("rg -l Contracts ~/.config/omarchy/plugins/omalvl", "files that mention Contracts")],
     ["grep", "fd", "regex", "git"], ["rg"],
     "Trains {skill:searching}.")

term("fd", "fd", "shell",
     "A fast, friendly `find`: search for files by name.",
     ["`fd notes` finds every path containing 'notes'; `fd -e md` finds Markdown files. Like ripgrep it "
      "respects .gitignore and is fast."],
     [("fd -e qml . ~/.config/omarchy/plugins", "every QML file in your plugins")],
     ["find", "ripgrep", "glob"], [])

term("find", "find", "shell",
     "The classic tool for finding files by name, size, age and more.",
     ["`find ~/Downloads -size +100M` lists big files; `find . -mtime -1` files changed in the last day. "
      "Verbose but very powerful, and on every Unix system."],
     [("find ~/Downloads -maxdepth 1 -size +50M", "large downloads")],
     ["fd", "glob"], [])

term("fzf", "fzf", "shell",
     "A fuzzy finder: pick from any list by typing a few letters.",
     ["Pipe anything into `fzf` and it becomes an interactive search menu. Omarchy wires it into the shell, "
      "so `CTRL+R` history search uses it."],
     [("ls ~/Work | fzf", "choose a folder")],
     ["pipe", "shell-history"], ["fuzzy finder"])

term("unix-philosophy", "Unix philosophy", "shell",
     "Small tools that each do one job well and work together through text.",
     ["Instead of one giant program, you combine `history`, `rg`, `sort`, `uniq` and `head` with pipes. Plain "
      "text is the universal interface. Linux inherits this from Unix (1970s)."],
     [("history | awk '{print $2}' | sort | uniq -c | sort -rn | head", "your ten most-used commands")],
     ["pipe", "linux", "command-line"], ["Unix way"])

# ------------------------------------------------------------------ files & storage
term("filesystem", "Filesystem", "files",
     "How files and folders are organised and stored on a disk.",
     ["Linux has one tree starting at `/`. Disks are attached (mounted) somewhere in it; there are no drive "
      "letters. `/home` holds users' files, `/etc` system config, `/usr` programs, `/tmp` scratch space."],
     [("ls /", "the top of the tree"), ("findmnt -t btrfs,ext4,vfat", "what's mounted where")],
     ["directory", "mount", "absolute-path", "proc"], ["file system", "filesystems", "directory tree"])

term("directory", "Directory", "files",
     "A folder: a file that holds other files.",
     ["`pwd` prints where you are, `cd dir` moves, `ls` lists, `mkdir` creates. `.` is the current directory "
      "and `..` its parent."],
     [("pwd", "where you are"), ("cd ~/Work && ls", "go to Work and list it")],
     ["filesystem", "home-directory", "absolute-path"], ["directories", "folder", "folders"])

term("home-directory", "Home directory", "files",
     "Your personal folder, `/home/<you>`, shortened to `~`.",
     ["Everything you own lives here: documents, downloads, config (dotfiles) and your projects in "
      "`~/Work`. `cd` with no arguments takes you home."],
     [("echo ~", "the full path of ~")],
     ["directory", "dotfiles", "absolute-path"], ["home folder", "home dir"])

term("absolute-path", "Absolute vs relative path", "files",
     "`/home/you/notes.md` works from anywhere; `notes.md` is relative to where you are.",
     ["An absolute path starts with `/` (or `~`). A relative path starts from the current directory. "
      "`../` means 'one folder up'. Scripts should use absolute paths so they work no matter where they "
      "run from."],
     [("realpath .", "the absolute path of where you are")],
     ["directory", "home-directory", "path-var"], ["absolute path", "relative path", "file path", "file paths"])

term("hidden-file", "Hidden file", "files",
     "A file whose name starts with `.`; `ls` hides it unless you add `-a`.",
     ["It's a convention, not security: anyone can list them with `ls -a`. Config files (dotfiles) use it "
      "to keep your home tidy."],
     [("ls -a ~ | head", "show the hidden ones")],
     ["dotfiles", "directory"], ["hidden files", "dot file"])

term("permissions", "File permissions", "files",
     "Who may read, write or execute a file: the owner, the group, and everyone else.",
     ["`ls -l` shows them like `-rwxr-xr-x`: owner can read/write/execute, group and others read/execute. In "
      "numbers, read=4, write=2, execute=1, so `755` = rwxr-xr-x and `644` = rw-r--r--.",
      "`chmod +x file` adds execute, which is what makes a script runnable. `chown` changes the owner."],
     [("ls -l ~/.local/bin | head", "permissions of your tools"), ("stat -c '%A %a %n' ~/.bashrc", "symbolic and numeric")],
     ["chmod", "root", "least-privilege", "shell-script"], ["file permissions", "rwx", "unix permissions"])

term("chmod", "chmod", "files",
     "Change a file's permissions, e.g. `chmod +x script.sh`.",
     ["`chmod +x` makes something executable; `chmod 600 secret.txt` makes it readable only by you. Avoid "
      "`chmod 777`: it lets anyone change the file."],
     [("touch /tmp/t.sh && chmod +x /tmp/t.sh && ls -l /tmp/t.sh", "see the x appear")],
     ["permissions", "shell-script"], [],
     "A {page:sysop.html|Sysop} challenge.")

term("symlink", "Symbolic link", "files",
     "A shortcut file that points to another path.",
     ["`ln -s target linkname` creates one. Programs follow it transparently. Keeping your dotfiles "
      "in one git repo and symlinking them into place makes that repo the single source of truth."],
     [("ls -l ~/.config/omarchy/plugins/ | rg skills", "the omalvl symlink")],
     ["dotfiles", "filesystem", "absolute-path"], ["symlinks", "symbolic link", "soft link"])

term("archive", "Archive (tar)", "files",
     "Many files packed into one, usually compressed: `.tar.gz`, `.tar.zst`, `.zip`.",
     ["`tar czf out.tar.gz folder/` creates (c) a gzip-compressed (z) file (f); `tar xzf out.tar.gz` "
      "extracts (x). Arch packages are `.pkg.tar.zst` archives."],
     [("tar czf /tmp/notes.tar.gz ~/Documents && ls -lh /tmp/notes.tar.gz", "pack, then check the size")],
     ["compression", "package"], ["tarball", "tar", "tar.gz", "archives"])

term("compression", "Compression", "files",
     "Making data smaller by encoding repetition more efficiently.",
     ["Lossless compression (gzip, zstd, xz) gives back the exact original; lossy (JPEG, MP3) throws away "
      "detail you won't notice. zram is compressed RAM used as swap."],
     [], ["archive", "swap"], ["compressed", "zstd", "gzip"])

term("disk-usage", "Disk usage", "files",
     "How full your disks are (`df -h`) and what's using the space (`du -sh`).",
     ["`df -h` shows each mounted filesystem's size and free space in human units. `du -sh *` totals each "
      "item in the current folder. Together they answer 'what filled my disk?'."],
     [("df -h /home", "space on your home"), ("du -sh ~/Downloads/* | sort -h | tail", "biggest downloads")],
     ["filesystem", "hdd-ssd"], ["df", "du", "disk space"],
     "Both are {page:sysop.html|Sysop} challenges; disk writes train {skill:workload}.")

term("mount", "Mount", "files",
     "Attaching a disk or partition to a folder in the filesystem tree.",
     ["A USB stick gets mounted (e.g. under `/run/media/you/`) so its files appear in the tree. Unmount "
      "(`umount`, or eject) before unplugging so pending writes finish."],
     [("findmnt /home", "what /home is mounted from")],
     ["filesystem", "encryption"], ["mounted", "mounting", "unmount"])

term("proc", "/proc and /sys", "files",
     "Virtual folders where the kernel shows live information as files.",
     ["`/proc` has a folder per process (`/proc/1234/`) plus system stats like `/proc/meminfo` and "
      "`/proc/interrupts`. `/sys` exposes hardware: battery, GPU, disks. Nothing is stored on disk; reading "
      "them asks the kernel. This game reads them to measure your activity."],
     [("cat /proc/loadavg", "load averages"), ("cat /sys/class/power_supply/*/capacity", "battery %")],
     ["kernel", "process", "pid", "filesystem"], ["/proc", "/sys", "procfs", "sysfs"],
     "Source of {skill:workload}, {skill:downloads}, {skill:agents} and {skill:models} XP.")

term("device-file", "Device file", "files",
     "A file in `/dev` that stands for a piece of hardware or a special source.",
     ["`/dev/sda` is a disk, `/dev/null` a black hole, `/dev/urandom` endless random bytes. 'Everything is a "
      "file' is a Unix idea: hardware is read and written like files."],
     [("ls /dev | head", "some devices")],
     ["dev-null", "proc", "kernel"], ["/dev"])

term("config-file", "Config file", "files",
     "A text file that holds a program's settings.",
     ["Usually in `~/.config/<app>/` (yours) or `/etc` (system-wide). Formats include INI, TOML, JSON, YAML "
      "and Lua (Hyprland). Back one up before editing: `cp file file.bak`."],
     [("ls ~/.config/hypr", "Hyprland's config")],
     ["dotfiles", "json", "lua", "backup"], ["config files", "configuration file", "configs"],
     "Changing a config with an agent is {quest:ai_builder2}.")

term("log-file", "Log", "files",
     "A running record of what a program did, for debugging later.",
     ["Services log to the systemd journal (`journalctl`); some apps write their own files. When something "
      "breaks, the log usually says why."],
     [("journalctl --user -n 20", "your last 20 user-service log lines")],
     ["journal", "debugging", "daemon"], ["logs", "log file", "log files", "logging"])

term("hdd-ssd", "HDD vs SSD", "files",
     "Spinning hard disks are slow to seek; solid-state drives are fast everywhere.",
     ["An HDD has a moving read head, so jumping around costs milliseconds; an SSD is flash memory with no "
      "moving parts. On an HDD, small frequent writes are costly, which is why this game batches its saves."],
     [("lsblk -d -o NAME,ROTA,SIZE,MODEL", "ROTA 1 means a rotational disk")],
     ["disk-usage", "swap"], ["HDD", "SSD", "hard disk", "solid-state drive"])

term("swap", "Swap and zram", "files",
     "Disk (or compressed RAM) used as overflow when memory runs out.",
     ["When RAM fills, the kernel moves rarely used pages to swap. zram is swap inside RAM, compressed, which "
      "is much faster than an HDD. Heavy swapping makes everything slow; `free -h` shows how much is used."],
     [("free -h", "memory and swap"), ("swapon --show", "swap devices")],
     ["ram", "hdd-ssd", "compression"], ["zram", "swap space", "swapping"])

# ------------------------------------------------------------------ processes & system
term("linux", "Linux", "system",
     "The kernel at the heart of this operating system, plus everything usually built on it.",
     ["Strictly, Linux is the kernel Linus Torvalds started in 1991. In everyday speech it means a whole "
      "system: the kernel plus tools, a desktop and apps, packaged as a distribution like Arch."],
     [("uname -r", "your kernel version"), ("cat /etc/os-release", "your distribution")],
     ["kernel", "arch-linux", "distribution", "open-source"], ["GNU/Linux"])

term("distribution", "Distribution (distro)", "system",
     "A complete Linux system: kernel, tools, package manager and defaults, put together by a project.",
     ["Arch, Debian, Fedora and Ubuntu are distros. They differ in package manager, release style and "
      "defaults. Omarchy is built on Arch."],
     [("cat /etc/os-release", "which distro this is")],
     ["linux", "arch-linux", "package-manager", "omarchy"], ["distro", "distros", "distributions"])

term("kernel", "Kernel", "system",
     "The core of the OS: it runs processes, manages memory and talks to hardware.",
     ["Programs ask the kernel to do things (open a file, send a packet) through system calls. Drivers live "
      "in or alongside it. "],
     [("uname -a", "kernel version and build"), ("dmesg | tail", "recent kernel messages (may need sudo)")],
     ["linux", "process", "proc", "syscall"], ["Linux kernel", "kernels"])

term("syscall", "System call", "system",
     "How a program asks the kernel to do something, like read a file.",
     ["read, write, open, fork, exec, kill: the small set of kernel services every program is built on. "
      "`strace` shows a program's system calls, a classic debugging trick."],
     [], ["kernel", "process"], ["system call", "syscalls", "system calls"])

term("process", "Process", "system",
     "A running program. Every program you start is one or more processes.",
     ["Each process has a PID, an owner, memory, and a parent that started it. `btop` and `ps` list them. "
      "Closing a window usually ends its process; daemons keep running in the background."],
     [("ps -e | wc -l", "how many processes are running"), ("pstree -p $$ | head", "your shell's family tree")],
     ["pid", "daemon", "signal", "btop"], ["processes", "running program"],
     "This game watches new processes to detect keybinds, agents ({skill:agents}) and local models ({skill:models}).")

term("pid", "PID", "system",
     "Process ID: the number that identifies a running process.",
     ["`echo $$` prints your shell's PID. You use PIDs to inspect or stop a process: `kill 1234`. PID 1 is "
      "systemd, the first process started at boot."],
     [("echo $$", "your shell's PID"), ("pgrep -a \"$(basename \"${TERMINAL:-foot}\")\"", "PIDs of your terminals")],
     ["process", "signal", "systemd"], ["PIDs", "process id"])

term("daemon", "Daemon", "system",
     "A background process that runs without a window, waiting to do its job.",
     ["Names often end in 'd': `sshd`, `bluetoothd`, `systemd`. This game's activity sampler is a daemon: "
      "`skills.py daemon`, started by the bar widget."],
     [("pgrep -af 'skills.py daemon'", "this game's daemon")],
     ["process", "service", "systemd"], ["daemons", "background process"])

term("systemd", "systemd", "system",
     "The service manager that starts Linux, runs services and keeps logs.",
     ["systemd is PID 1. It starts services in order at boot, restarts them if they crash, runs timers "
      "(like cron) and collects logs in the journal. `systemctl` controls it."],
     [("systemctl --user list-units --type=service | head", "services running as you")],
     ["service", "systemctl", "journal", "pid"], [])

term("service", "Service (unit)", "system",
     "Something systemd manages, described by a unit file: a daemon, a timer, a mount.",
     ["`systemctl status bluetooth` shows a service's state and recent logs. System services run as root; "
      "user services (`--user`) run as you and need no sudo."],
     [("systemctl --user status wireplumber", "your audio session service")],
     ["systemd", "systemctl", "daemon"], ["systemd unit", "unit file", "systemd service", "user service", "user services"])

term("systemctl", "systemctl", "system",
     "The command for starting, stopping and checking systemd services.",
     ["`start`, `stop`, `restart`, `status`, `enable` (start at boot), `disable`. Add `--user` for your own "
      "services."],
     [("systemctl --user list-units --type=service", "a Sysop challenge")],
     ["systemd", "service", "journal"], [])

term("journal", "Journal (journalctl)", "system",
     "systemd's central log of everything services and the kernel report.",
     ["`journalctl -b` shows this boot, `-p 3` only errors, `-u name` one service, `-f` follows live. The first "
      "place to look when something breaks."],
     [("journalctl -p 3 -b --no-pager | tail", "this boot's errors")],
     ["log-file", "systemd", "debugging"], ["journalctl", "systemd journal"],
     "A signal step and a {page:sysop.html|Sysop} challenge.")

term("cpu-time", "CPU time", "system",
     "How long a process actually ran on a processor, not how long it existed.",
     ["A process waiting for input uses almost no CPU time. Busy ones use up to one second per second per "
      "core. This game pays {skill:workload} for CPU time while you're active, and {skill:agents} for the CPU "
      "time of AI agents, and {skill:models} for local models."],
     [("ps -o pid,etime,time,comm -p $$", "elapsed time vs CPU time of your shell")],
     ["process", "load-average", "cpu"], ["CPU-seconds", "CPU seconds"])

term("cpu", "CPU and cores", "system",
     "The processor; each core runs one thing at a time, threads let it juggle two.",
     ["More cores run more things at once; local AI models are limited mostly by "
      "cores and memory speed."],
     [("nproc", "threads available"), ("lscpu | head -15", "CPU details")],
     ["cpu-time", "load-average", "ram"], ["processor", "cores", "CPU core"])

term("ram", "RAM (memory)", "system",
     "Fast working memory that programs use while running; it's emptied at power-off.",
     ["When RAM fills, the system swaps, which is slow. Local AI models need RAM roughly equal to "
      "their file size plus some working space."],
     [("free -h", "memory in use"), ("ps -eo rss,comm --sort=-rss | head", "biggest memory users (KB)")],
     ["swap", "process", "cpu"], ["memory", "RAM"])

term("load-average", "Load average", "system",
     "The average number of processes running or waiting, over 1, 5 and 15 minutes.",
     ["Compare it with your number of threads: a load equal to the thread count means fully busy. Processes "
      "stuck waiting for the disk also count, so a slow HDD can raise it."],
     [("uptime", "the three load averages")],
     ["cpu", "process", "btop"], ["load averages", "system load"])

term("signal", "Signal", "system",
     "A message the system sends a process, like 'please stop' (SIGTERM) or 'stop now' (SIGKILL).",
     ["`kill PID` sends SIGTERM, which a program can catch to clean up. `kill -9 PID` sends SIGKILL, which it "
      "can't. `CTRL+C` in a terminal sends SIGINT."],
     [("sleep 60 & kill %1", "start a sleep, then stop it")],
     ["process", "pid", "kill"], ["SIGTERM", "SIGKILL", "SIGINT", "Unix signal"])

term("kill", "kill / pkill", "system",
     "Commands that send signals to processes, usually to stop them.",
     ["`kill 1234` by PID, `pkill name` by name. Careful with `pkill -f pattern`: it matches full command "
      "lines, which can include your own shell."],
     [("pgrep -a sleep", "find before you kill")],
     ["signal", "pid", "process"], ["pkill", "killall"])

term("btop", "btop", "system",
     "A colourful terminal dashboard of CPU, memory, disks, network and processes.",
     ["Press `q` to quit, `f` to filter, and arrow keys to pick a process. It's the quickest way to see "
      "what's slowing the machine down."],
     [("btop", "open it (q to quit)")],
     ["process", "cpu", "ram", "load-average"], ["htop", "top"],
     "Opening it solves a signal step and a {page:sysop.html|Sysop} challenge.")

term("cron", "Scheduled tasks (cron, timers)", "system",
     "Running something automatically at set times.",
     ["Classic Unix uses cron (`crontab -e`). On systemd systems, timers do the same with logging and "
      "catch-up after sleep."],
     [("systemctl list-timers --no-pager | head", "scheduled timers")],
     ["systemd", "service"], ["cron job", "crontab", "systemd timer", "timers"])

term("boot", "Boot", "system",
     "Starting the computer: firmware, bootloader, kernel, then systemd and your desktop.",
     ["`systemd-analyze` shows how long boot took and `systemd-analyze blame` which services were slowest."],
     [("systemd-analyze", "boot time")],
     ["kernel", "systemd", "encryption"], ["booting", "bootloader"])

term("interrupt", "Interrupt (IRQ)", "system",
     "A signal from hardware to the CPU: 'a key was pressed', 'a packet arrived'.",
     ["The kernel counts them per device in `/proc/interrupts`. This game counts keyboard and touchpad "
      "interrupts to know someone is really at the computer, without reading what you type."],
     [("grep i8042 /proc/interrupts", "keyboard/touchpad interrupt counters")],
     ["kernel", "proc", "cpu"], ["IRQ", "IRQs", "interrupts"])

# ------------------------------------------------------------------ packages & software
term("package-manager", "Package manager", "packages",
     "The tool that installs, updates and removes software, with its dependencies.",
     ["Instead of downloading installers from websites, you ask the package manager. It knows every file "
      "each package owns, so removing is clean and updating is one command. Arch's is pacman."],
     [("pacman -Q | wc -l", "how many packages are installed")],
     ["pacman", "package", "dependency", "aur"], ["package managers"])

term("package", "Package", "packages",
     "A bundle of a program's files plus info about what it needs.",
     ["A package lists its version, its dependencies and the files it installs. `pacman -Qi bash` shows a "
      "package's details; `pacman -Ql bash` its files."],
     [("pacman -Qi bash | head -12", "details of the bash package")],
     ["package-manager", "dependency", "pacman"], ["packages"],
     "Installing and upgrading both train {skill:packages}.")

term("pacman", "pacman", "packages",
     "Arch Linux's package manager.",
     ["`sudo pacman -S name` installs, `-Syu` updates everything, `-R` removes, `-Ss word` searches, `-Qi name` "
      "shows an installed package. Omarchy's updater runs pacman for you."],
     [("pacman -Ss ripgrep", "search the repos"), ("pacman -Qi bash", "a Sysop challenge")],
     ["package-manager", "aur", "arch-linux", "sudo"], [],
     "Reads from `/var/log/pacman.log` power {skill:packages}.")

term("aur", "AUR", "packages",
     "The Arch User Repository: community build recipes for software not in the official repos.",
     ["AUR packages are scripts (PKGBUILDs) written by users, so read them before installing. Helpers like "
      "`yay` automate it. Official repos are vetted; the AUR is not."],
     [("yay -Ss llama", "search the AUR (if yay is installed)")],
     ["pacman", "package", "makepkg"], ["Arch User Repository", "yay", "paru"])

term("makepkg", "Building from source", "packages",
     "Compiling software yourself instead of installing a ready-made package.",
     ["Source code is turned into a program by a build system (make, cargo, cmake). On Arch, `makepkg` "
      "builds a package from a PKGBUILD."],
     [], ["compiler", "build", "aur"], ["build from source", "from source", "makepkg"])

term("dependency", "Dependency", "packages",
     "Something a program needs in order to work, like a library.",
     ["Package managers install dependencies for you. In code, dependencies are other people's libraries "
      "(npm packages, Python modules, Rust crates)."],
     [("pacman -Qi git | rg 'Depends On'", "what git needs")],
     ["package", "package-manager", "library"], ["dependencies", "deps"])

term("library", "Library", "packages",
     "Reusable code that many programs share.",
     ["System libraries (`.so` files on Linux) are loaded by programs at start. `ldd /usr/bin/git` shows "
      "which ones git uses."],
     [("ldd $(which git) | head", "git's libraries")],
     ["dependency", "package"], ["libraries", "shared library"])

term("arch-linux", "Arch Linux", "packages",
     "A rolling-release Linux distribution: always up to date, minimal by default.",
     ["No big version upgrades: packages update continuously. The Arch Wiki is one of the best Linux "
      "references anywhere. Omarchy is Arch plus an opinionated desktop."],
     [("cat /etc/os-release", "confirms Arch")],
     ["distribution", "pacman", "omarchy", "aur"], ["Arch", "rolling release", "Arch Wiki"],
     "The {quest:arch_wiki} quest.")

# ------------------------------------------------------------------ networking
term("ip-address", "IP address", "net",
     "A machine's address on a network, like 192.168.1.20.",
     ["Your computer has a private address on your home network and reaches the internet through the router. "
      "IPv4 addresses are four numbers; IPv6 are longer."],
     [("ip -br a", "your addresses, briefly")],
     ["localhost", "port", "dns", "wifi"], ["IP", "IP addresses", "IPv4", "IPv6"],
     "A {page:sysop.html|Sysop} challenge.")

term("localhost", "localhost (127.0.0.1)", "net",
     "Your own machine, as a network address.",
     ["Services listening on 127.0.0.1 are reachable only from this computer. The local AI server runs on "
      "`127.0.0.1:8080`, so nothing outside can talk to it."],
     [("curl -s 127.0.0.1:8080/health", "is the local model up?")],
     ["ip-address", "port", "api"], ["127.0.0.1", "loopback"])

term("port", "Port", "net",
     "A numbered door on a machine that one service listens on.",
     ["SSH uses 22, web servers 80/443, the local model 8080. An address plus a port, like `127.0.0.1:8080`, "
      "names one service."],
     [("ss -ltn", "ports listening on this machine")],
     ["ip-address", "localhost", "firewall"], ["ports", "TCP port"])

term("dns", "DNS", "net",
     "The internet's phone book: turns names like archlinux.org into IP addresses.",
     ["When a site 'won't load' but the internet works, DNS is a usual suspect."],
     [("resolvectl query archlinux.org", "look a name up")],
     ["ip-address", "ping"], ["domain name", "name server", "DNS server"])

term("ping", "ping", "net",
     "Checks whether another machine answers, and how long the round trip takes.",
     ["`ping -c 3 archlinux.org` sends three probes. Times in milliseconds show your latency; no answer can "
      "mean no connection, or a host that ignores pings."],
     [("ping -c 3 archlinux.org", "a Sysop challenge")],
     ["ip-address", "dns", "wifi"], ["latency"])

term("ssh", "SSH", "net",
     "Secure Shell: an encrypted way to log into and run commands on another machine.",
     ["`ssh user@host` gives you a shell on a remote computer; everything is encrypted. Keys "
      "(`ssh-keygen`) are safer and easier than passwords. `scp` and `rsync` copy files over it."],
     [("ssh -V", "your SSH version")],
     ["rsync", "encryption", "key-pair", "remote"], ["secure shell", "ssh key", "ssh keys"],
     "Every ssh is a voyage: {skill:remote}.")

term("rsync", "rsync", "net",
     "Copies and syncs files efficiently, locally or over SSH.",
     ["`rsync -a src/ dest/` copies only what changed and keeps permissions and times. The trailing slash on "
      "`src/` means 'the contents'. Great for backups."],
     [("rsync -a ~/Documents/ /tmp/docs-backup/", "a Sysop challenge")],
     ["ssh", "backup"], ["scp"], "Trains {skill:remote}.")

term("wifi", "Wi-Fi", "net",
     "Wireless networking.",
     ["Speed depends on signal, band (2.4 vs 5 GHz), interference and the card. `iw dev` shows the link."],
     [("iw dev | head", "wireless interfaces")],
     ["ip-address", "ping"], ["wireless", "WLAN"], "Data received trains {skill:downloads}.")

term("api", "API", "net",
     "Application Programming Interface: the defined way one program talks to another.",
     ["A web API is usually HTTP + JSON. The local model speaks the 'OpenAI-compatible' API, so any tool that "
      "supports OpenAI's format can use it by changing the URL."],
     [("curl -s 127.0.0.1:8080/v1/models", "list the local model (if it's running)")],
     ["http", "json", "localhost", "local-model"], ["APIs", "OpenAI-compatible", "endpoint", "REST API"])

term("http", "HTTP", "net",
     "The protocol of the web: a client asks for a URL, a server answers.",
     ["HTTPS is HTTP encrypted with TLS. `curl` speaks HTTP from the terminal."],
     [("curl -sI https://archlinux.org | head -5", "response headers")],
     ["api", "dns", "encryption"], ["HTTPS", "curl"])

# ------------------------------------------------------------------ git & development
term("git", "Git", "dev",
     "Version control: records every change to a project so you can review, undo and share it.",
     ["Git keeps the full history of a folder (a repository) as commits. You change files, stage them "
      "(`git add`), and commit (`git commit`). Branches let you try things without breaking the main line.",
      "Keeping your configs and projects in git means every change can be reviewed and undone; this "
      "game's own code is a git repo."],
     [("git -C ~/.config/omarchy/plugins/omalvl log --oneline -5", "the last five changes"), ("git status", "what changed (inside a repo)")],
     ["repository", "commit", "diff", "branch", "remote"], ["version control", "VCS"],
     "Commits train {skill:commits} and {skill:editing}, and config commits unearth relics.")

term("repository", "Repository", "dev",
     "A project folder tracked by git, including its full history (in `.git/`).",
     ["Every repo is complete on its own: history, branches, everything. GitHub hosts copies so people can "
      "share. Not to be confused with a package repository, where pacman downloads software."],
     [("ls ~/Work", "your repos")],
     ["git", "commit", "remote", "github"], ["repo", "repos", "git repo", "git repository", "repositories"])

term("commit", "Commit", "dev",
     "A saved snapshot of changes in git, with a message and an author.",
     ["Good commits are small and focused, with a message saying why. Each has a hash like `ca58da5` that "
      "names it forever."],
     [("git -C ~/.config/omarchy/plugins/omalvl show --stat HEAD", "the latest commit and its files")],
     ["git", "diff", "repository"], ["commits", "git commit", "commit message"],
     "500 {skill:commits} XP each; {quest:ai_builder3}.")

term("diff", "Diff", "dev",
     "The line-by-line difference between two versions of files.",
     ["`git diff` shows unstaged changes; `--stat` summarises. Lines starting `+` were added, `-` removed. "
      "Reviewing a diff before committing catches mistakes."],
     [("git -C ~/.config/omarchy/plugins/omalvl diff --stat HEAD~1", "what the last commit changed")],
     ["commit", "git", "code-review"], ["diffs", "git diff"],
     "A {page:sysop.html|Sysop} challenge.")

term("branch", "Branch", "dev",
     "A separate line of commits in git, for working on something without touching the main line.",
     ["`git switch -c idea` creates one; `git switch main` goes back; `git merge idea` brings it in."],
     [("git -C ~/.config/omarchy/plugins/omalvl branch", "branches here")],
     ["git", "merge", "commit"], ["branches", "git branch", "main branch"])

term("merge", "Merge", "dev",
     "Combining the changes from one branch into another.",
     ["If both sides changed the same lines, git can't decide and reports a merge conflict for you to "
      "resolve by hand."],
     [], ["branch", "git", "diff"], ["merges", "merge conflict", "merge conflicts"])

term("remote", "Remote (push, pull, clone)", "dev",
     "Another copy of a repo, usually on GitHub, that you sync with.",
     ["`git clone url` copies a repo down, `git pull` brings new commits in, `git push` sends yours up, "
      "`git fetch` checks without merging. `git remote -v` lists them."],
     [("git remote -v", "this repo's remotes (inside a repo)")],
     ["git", "github", "repository", "ssh"], ["git push", "git pull", "git clone", "git fetch", "remotes", "push", "clone"],
     "Every one is a voyage: {skill:remote}.")

term("github", "GitHub", "dev",
     "A website that hosts git repositories and the collaboration around them.",
     ["Issues, pull requests (proposed changes), and code review all happen there. `gh` is its CLI. "],
     [("gh repo list --limit 5", "your repos (needs gh auth)")],
     ["git", "remote", "pull-request", "open-source"], [])

term("pull-request", "Pull request", "dev",
     "A proposal to merge your changes into someone's repo, with discussion and review.",
     ["You push a branch, open a PR, others review the diff and comment, and a maintainer merges it."],
     [], ["github", "code-review", "branch"], ["PR", "PRs", "pull requests", "merge request"])

term("code-review", "Code review", "dev",
     "Reading someone's changes before they're merged, to catch bugs and share knowledge.",
     ["Read the diff, run it if you can, ask about anything unclear. Reviewing an AI agent's work before "
      "keeping it is the same skill."],
     [], ["diff", "pull-request", "bug"], ["reviewing code", "review"],
     "{quest:ai_builder1} asks you to read an agent's diff before keeping it.")

term("open-source", "Open source", "dev",
     "Software whose source code anyone may read, change and share, under a license.",
     ["Linux, Arch, Hyprland, git, llama.cpp and Omarchy are all open source. Licenses differ: GPL requires "
      "changes to stay open; MIT, Apache-2.0 and CC0 are permissive."],
     [("pacman -Qi bash | rg Licenses", "bash's license")],
     ["license", "linux", "github"], ["FOSS", "free software", "open-source software"])

term("license", "Software license", "dev",
     "The legal terms for using and sharing code.",
     ["MIT and Apache-2.0 let you do almost anything if you keep the notice; GPL asks that changes you share "
      "stay GPL; CC0 gives a work to the public domain. OmaLvL itself is MIT: see its LICENSE file."],
     [], ["open-source"], ["licence", "licenses", "MIT license", "Apache-2.0", "GPL", "CC0"])

term("compiler", "Compiler", "dev",
     "A program that turns source code into a program the CPU can run.",
     ["gcc and clang compile C/C++, rustc compiles Rust, tsc turns TypeScript into JavaScript. Interpreted "
      "languages (Python, bash) skip this step."],
     [("gcc --version | head -1", "your C compiler")],
     ["build", "makepkg", "python"], ["compilers", "compile", "compiling", "compiled"],
     "A compiler running trains {skill:building}.")

term("build", "Build", "dev",
     "Turning a project's source into something runnable, usually with a build tool.",
     ["`make`, `cargo build`, `npm run build` and `go build` read the project's recipe, compile what changed "
      "and link it together."],
     [("make --version", "is make installed?")],
     ["compiler", "make", "dependency"], ["build system", "build tool", "build tools"],
     "Every build trains {skill:building}.")

term("make", "make", "dev",
     "The classic build tool: runs the recipe in a Makefile, rebuilding only what changed.",
     ["A Makefile lists targets, what they depend on, and the commands to make them."],
     [("printf 'hi:\\n\\techo hi\\n' > /tmp/Makefile && make -C /tmp hi", "a one-target Makefile")],
     ["build", "compiler"], ["Makefile", "makefiles"])

term("python", "Python", "dev",
     "A popular, readable programming language; this game's engine is written in it.",
     ["`python3 file.py` runs a script; `python3` alone opens an interactive prompt. Python is interpreted, "
      "so there's no compile step."],
     [("python3 -c 'print(2 ** 10)'", "1024")],
     ["shell-script", "json", "library"], ["python3", "Python script"],
     "Running scripts trains {skill:scripting}.")

term("node", "Node.js and npm", "dev",
     "JavaScript outside the browser, and its package manager.",
     ["Many CLIs (Gemini CLI, HyperFrames) are Node programs. `npm install` fetches dependencies; `npx tool` "
      "runs one without installing it globally."],
     [("node --version", "your Node version")],
     ["dependency", "package-manager", "build"], ["Node.js", "npm", "npx", "JavaScript"])

term("json", "JSON", "dev",
     "A simple text format for structured data: objects, lists, strings, numbers.",
     ["This game's whole save is one JSON file. APIs send JSON. `jq` is the classic tool for reading it."],
     [("python3 -m json.tool ~/.local/state/omalvl/state.json | head -20", "the start of your save")],
     ["api", "config-file", "python"], ["jq"])

term("lua", "Lua", "dev",
     "A small scripting language; Hyprland's newer configs are written in it.",
     ["Lua is designed to be embedded in other programs for configuration and scripting. `hyprctl eval` runs "
      "a Lua snippet in Hyprland."],
     [("head -20 ~/.config/hypr/hyprland.lua", "Hyprland's Lua config")],
     ["hyprland", "config-file"], [])

term("qml", "QML", "dev",
     "Qt's language for user interfaces; the Omarchy shell and this game's panel are written in it.",
     ["QML describes visual items (Rectangle, Text, Image) and binds their properties to data, with "
      "JavaScript for logic. Quickshell uses it to draw the bar."],
     [("head -40 ~/.config/omarchy/plugins/omalvl/Panel.qml", "this game's panel")],
     ["quickshell", "omarchy"], ["Qt Quick", "Qt"])

term("bug", "Bug", "dev",
     "A mistake in a program that makes it behave wrongly.",
     ["Found by testing, reading logs, or users hitting it. Fixing one well means finding the root cause, not "
      "just hiding the symptom."],
     [], ["debugging", "log-file", "code-review"], ["bugs", "bugfix"],
     "Root-causing and fixing a bug is what {skill:commits} agent awards are for.")

term("debugging", "Debugging", "dev",
     "Finding out why a program misbehaves, then fixing it.",
     ["Reproduce it, read the error and the logs, narrow it down, form a guess, test it. Change one thing at "
      "a time."],
     [("journalctl --user -n 50 --no-pager | rg -i error", "recent errors")],
     ["bug", "log-file", "journal"], ["debug", "troubleshooting"])

term("backup", "Backup", "dev",
     "A copy you can restore from when something goes wrong.",
     ["Before editing a config: `cp file file.bak`. For folders: rsync or git. A backup you've never tested "
      "restoring isn't proven."],
     [("cp ~/.bashrc /tmp/bashrc.bak && ls -l /tmp/bashrc.bak", "the simplest backup")],
     ["rsync", "git", "config-file"], ["backups", "backed up", "back up"],
     "Backups and safety fixes are {skill:focus} agent awards.")

# ------------------------------------------------------------------ desktop
term("omarchy", "Omarchy", "desktop",
     "An opinionated Arch Linux setup with Hyprland, made by DHH.",
     ["Omarchy gives you a keyboard-driven desktop, themes, a menu (`SUPER + SPACE`), a system menu "
      "(`SUPER + ESCAPE`) and dozens of `omarchy-*` helper commands. `SUPER + K` lists every keybind."],
     [("omarchy --help", "its command-line helper"), ("ls /usr/share/omarchy/bin | wc -l", "how many helpers")],
     ["arch-linux", "hyprland", "keybind", "theme"], [],
     "The quests teach Omarchy step by step, following its manual.")

term("hyprland", "Hyprland", "desktop",
     "The tiling Wayland compositor that runs this desktop: it draws and arranges windows.",
     ["Windows tile automatically, workspaces are numbered, and everything has a keybind. Config is in "
      "`~/.config/hypr/`. `hyprctl` talks to it from the terminal."],
     [("hyprctl activewindow", "the focused window"), ("hyprctl clients | rg class", "every window's class")],
     ["wayland", "tiling", "workspace", "keybind", "lua"], ["hyprctl"])

term("wayland", "Wayland", "desktop",
     "The modern way Linux desktops draw windows, replacing X11.",
     ["The compositor (Hyprland) is the display server: apps hand it their pixels and it combines them. "
      "Older X11 apps run through XWayland."],
     [("echo $XDG_SESSION_TYPE", "prints wayland")],
     ["hyprland", "compositor"], ["X11", "XWayland"])

term("compositor", "Compositor", "desktop",
     "The program that combines all windows into the image on your screen.",
     ["On Wayland, the compositor is also the window manager. Hyprland is one; it handles animations, blur "
      "and rounded corners too."],
     [], ["hyprland", "wayland", "tiling"], ["window manager", "compositors"])

term("tiling", "Tiling window manager", "desktop",
     "Windows are arranged side by side automatically instead of overlapping.",
     ["You move between them with the keyboard (`SUPER + arrows`) and rarely drag anything. Floating windows "
      "are still possible for dialogs."],
     [], ["hyprland", "workspace", "keybind"], ["tiling", "tiled windows", "floating window"],
     "The {quest:navigation} quest.")

term("workspace", "Workspace", "desktop",
     "A virtual desktop; switch with `SUPER + 1..9`.",
     ["Put each task on its own workspace: browser on 1, terminal on 2, game on 5. `SUPER + SHIFT + number` "
      "moves the focused window there."],
     [], ["hyprland", "tiling", "keybind"], ["workspaces", "virtual desktop"],
     "Switching trains {skill:tiling}.")

term("keybind", "Keybind", "desktop",
     "A keyboard shortcut that runs an action, like `SUPER + RETURN` for a terminal.",
     ["Omarchy is built around them. `SUPER + K` lists every one. They're defined in Hyprland's config and "
      "usually run an `omarchy-*` command."],
     [], ["hyprland", "omarchy", "workspace"], ["keybinds", "keybinding", "keybindings", "shortcut", "keyboard shortcut"],
     "Keybind actions train {skill:shell}; {quest:hotkeys}.")

term("scratchpad", "Scratchpad", "desktop",
     "A hidden workspace you can pop a window onto and call back instantly.",
     ["Handy for a calculator or notes you want one keypress away."],
     [], ["workspace", "hyprland"], ["special workspace"], "A signal step.")

term("theme", "Theme", "desktop",
     "A coordinated set of colours, wallpaper and styling for the whole desktop.",
     ["Omarchy themes recolour the terminal, bar, editor, browser and more at once. `SUPER + CTRL + SHIFT + "
      "SPACE` opens the theme menu. "],
     [("omarchy-theme-current", "the active theme")],
     ["omarchy", "dotfiles"], ["themes", "color scheme", "colour scheme"],
     "Changing it is a signal step and a {page:sysop.html|Sysop} challenge.")

term("quickshell", "Quickshell", "desktop",
     "The QML toolkit the Omarchy shell (bar, menus, panels) is built on.",
     ["Plugins like this game's Skill Log are QML files the shell loads. QML isn't hot-reloaded, so changes "
      "need `omarchy restart shell`."],
     [("pgrep -a quickshell", "the shell process")],
     ["qml", "omarchy"], ["Omarchy shell", "bar widget"])

term("notification", "Notification", "desktop",
     "A pop-up message from an app; `notify-send` sends one from the terminal.",
     ["Level-ups, quests and random events in this game arrive as notifications."],
     [("notify-send 'Hello' 'from the terminal'", "send yourself one")],
     ["omarchy"], ["notifications", "notify-send"])

# ------------------------------------------------------------------ security & hacker culture
term("hacker", "Hacker", "security",
     "Originally: someone who loves understanding and bending systems to do clever things.",
     ["The word comes from 1960s MIT, where a 'hack' was an elegant or playful solution. The hacker ethic "
      "values curiosity, sharing knowledge and hands-on learning. Breaking into systems without permission "
      "is a different thing, often called cracking; doing it with permission to find weaknesses is "
      "penetration testing."],
     [], ["open-source", "ctf", "least-privilege"], ["hackers", "hacking", "hacker culture", "hacker ethic"])

term("ctf", "Capture the Flag (CTF)", "security",
     "A security game: solve puzzles and break deliberately vulnerable systems to find hidden 'flags'.",
     ["CTFs are a legal, ethical way to learn security: web, crypto, reverse engineering, forensics. Many "
      "are beginner friendly, like picoCTF and OverTheWire's Bandit (which teaches Linux basics over SSH)."],
     [], ["hacker", "ssh", "encryption"], ["CTF", "CTFs", "capture the flag"])

term("least-privilege", "Least privilege", "security",
     "Give every user and program only the access it truly needs.",
     ["Work as your normal user, use sudo only when needed, keep services bound to localhost, and don't "
      "`chmod 777`. If something is compromised, least privilege limits the damage."],
     [], ["root", "sudo", "permissions", "localhost"], ["principle of least privilege"])

term("encryption", "Encryption", "security",
     "Scrambling data so only someone with the key can read it.",
     ["Omarchy encrypts the disk with LUKS by default (that's the password at boot), so "
      "a stolen drive is unreadable. SSH and HTTPS encrypt data in transit."],
     [("lsblk -o NAME,TYPE,FSTYPE | rg crypt", "the encrypted volume")],
     ["key-pair", "ssh", "http", "checksum"], ["encrypted", "LUKS", "full-disk encryption"])

term("key-pair", "Public/private key pair", "security",
     "Two linked keys: share the public one, guard the private one.",
     ["What the public key locks, only the private key opens; what the private key signs, anyone can verify "
      "with the public key. SSH keys and git commit signing work this way."],
     [("ls ~/.ssh", "your SSH keys, if any")],
     ["ssh", "encryption", "checksum"], ["public key", "private key", "SSH key pair"])

term("checksum", "Checksum (hash)", "security",
     "A fingerprint of a file; if one byte changes, the fingerprint changes.",
     ["`sha256sum file` prints a SHA-256 hash. Comparing it with the publisher's hash proves the download "
      "is intact and untampered. llama.cpp and the local models were verified this way."],
     [("sha256sum ~/.local/share/models/Qwen3.5-2B-Q4_K_M.gguf", "the model's fingerprint (slow on an HDD)")],
     ["encryption", "key-pair", "local-model"], ["hash", "hashes", "sha256", "SHA-256", "checksums", "sha256sum"])

term("firewall", "Firewall", "security",
     "Rules for which network connections are allowed in or out.",
     ["A firewall blocks unwanted incoming connections. Services that only listen on localhost don't need "
      "one to be safe from the network."],
     [], ["port", "localhost", "least-privilege"], ["firewalls", "ufw"])

term("telemetry", "Telemetry", "security",
     "Usage data a program sends home to its makers.",
     ["Often anonymous, sometimes not. You can usually turn it off; HyperFrames' telemetry was disabled "
      "here. This game sends nothing anywhere."],
     [], ["open-source", "least-privilege"], [])

# ------------------------------------------------------------------ AI & local models
term("ai-agent", "AI agent", "ai",
     "An AI model that can take actions (run commands, edit files) in a loop to complete a task.",
     ["Claude Code, OpenCode and Codex are agents: they read your project, plan, run tools, look at the "
      "results and keep going. Always review what an agent changed."],
     [], ["llm", "local-model", "code-review", "prompt"], ["AI agents", "coding agent", "agents"],
     "Agents' CPU time trains {skill:agents}; they award XP with `omalvl agent`; {quest:ai_agents}.")

term("llm", "Large language model (LLM)", "ai",
     "An AI trained on huge amounts of text to predict the next token; the brain inside chatbots and agents.",
     ["Given text, an LLM predicts what comes next, one token at a time. Size is measured in parameters "
      "(4B = four billion). Bigger usually means smarter but slower and hungrier for RAM."],
     [], ["token", "local-model", "context-window", "inference", "hallucination"], ["LLM", "LLMs", "language model", "language models"])

term("local-model", "Local model", "ai",
     "An AI model running on your own computer instead of a company's servers.",
     ["Private and offline, but limited by your hardware. This project's `local-llm` "
      "runs small Qwen3.5 models with llama.cpp: `local-llm serve`, `local-llm ask \"…\"`."],
     [("local-llm status", "is one running?")],
     ["llm", "llama-cpp", "quantization", "inference"], ["local models", "local AI", "running locally", "offline AI"],
     "Running one completes {quest:off_grid} and trains {skill:agents}.")

term("llama-cpp", "llama.cpp", "ai",
     "A fast, open-source engine for running LLMs on ordinary CPUs and GPUs.",
     ["It loads GGUF model files and serves them with `llama-server` (an OpenAI-compatible API) or chats with "
      "`llama-cli`. Ollama and LM Studio are built on it."],
     [("llama-cli --version", "the installed build")],
     ["local-model", "gguf", "api", "ollama"], ["llama-server", "llama-cli"])

term("ollama", "Ollama", "ai",
     "A friendly app for downloading and running local models (`ollama run model`).",
     ["Built on llama.cpp, with a model library and a background service. This project uses llama.cpp "
      "directly, which needs no sudo."],
     [], ["llama-cpp", "local-model"], [])

term("gguf", "GGUF", "ai",
     "The file format llama.cpp uses for models: weights plus everything needed to run them.",
     ["One file per model and quantization, e.g. `Qwen3.5-4B-IQ4_XS.gguf`."],
     [("ls -lh ~/.local/share/models/", "your model files")],
     ["quantization", "llama-cpp"], [])

term("quantization", "Quantization", "ai",
     "Storing a model's numbers with fewer bits so it's smaller and faster, at a small cost in quality.",
     ["Models are trained in 16-bit; Q4 stores about 4 bits per weight, so a 4B model shrinks from ~8 GB "
      "to ~2.5 GB. IQ4_XS and Q4_K_M are popular 4-bit schemes."],
     [], ["gguf", "local-model", "ram"], ["quantized", "Q4", "Q4_K_M", "IQ4_XS", "4-bit"])

term("token", "Token", "ai",
     "A chunk of text (often part of a word) that a language model reads and writes.",
     ["Roughly 1 token ≈ ¾ of an English word. Speed is measured in tokens per second; a small model on a "
      "laptop CPU reads tens and writes a handful per second."],
     [], ["llm", "context-window", "inference"], ["tokens", "tokens per second", "tok/s"])

term("context-window", "Context window", "ai",
     "How much text a model can consider at once: the prompt, the documents and its own answer.",
     ["Measured in tokens. The local server is set to 16k. Coding agents send long instructions every time, "
      "which is why they're slow on small CPUs."],
     [], ["token", "prompt", "llm"], ["context length", "context"])

term("inference", "Inference", "ai",
     "Running a trained model to get answers (as opposed to training it).",
     ["Everything you do with a local model is inference. It's limited by memory bandwidth and compute."],
     [], ["llm", "local-model", "token"], [])

term("prompt", "Prompt", "ai",
     "The text you give an AI model: your question plus any instructions and context.",
     ["Clear, specific prompts with the relevant material get better answers. The Sysop's prompt "
      "includes the command's tldr page and says not to guess."],
     [("local-llm ask \"In one sentence, what does chmod 755 do?\"", "ask the local model (if running)")],
     ["llm", "context-window", "grounding"], ["prompts", "prompting"])

term("hallucination", "Hallucination", "ai",
     "When an AI model states something false with confidence.",
     ["Small models do it more. In testing, a 2B model confidently said Omarchy was from a cartoon. Check important "
      "facts, and prefer answers grounded in real documents."],
     [], ["grounding", "llm", "local-model"], ["hallucinations", "hallucinate", "hallucinates"])

term("grounding", "Grounding", "ai",
     "Giving a model real source material and asking it to answer only from that.",
     ["It sharply reduces hallucination. The Sysop's explanations are grounded in the command's tldr "
      "page, --help or man page. Retrieval-augmented generation (RAG) is the same idea at scale."],
     [], ["hallucination", "prompt", "tldr"], ["grounded", "RAG", "retrieval-augmented generation"])
