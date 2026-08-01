# aur-cooldown ledger reminder. Sourced from bash or zsh; POSIX apart from the
# two marked per-shell branches, which have no portable spelling.
# Speaks up at most once per calendar day when the ledger is older than N days,
# and offers to run `observe` right there, so refreshing it is one keypress
# instead of a retyped command. Wired up by `aur-cooldown setup`; to do it by
# hand, add to your shell rc:   . /usr/share/aur-cooldown/nudge.sh
# Tunables: AUR_COOLDOWN_NUDGE_DAYS  staleness threshold in days (default 3)
#           AUR_COOLDOWN_NUDGE_ASK=0 only print the reminder, never prompt

# True when input is already waiting: the shell was slow to start and the user
# is mid-command, so those keystrokes are meant for the shell, not for us.
# Canonical mode only reports whole lines, so leave it to notice a half-typed
# command too, and put the terminal back exactly as it was. (The approach is
# oh-my-zsh's; the shells disagree on how to poll without consuming.)
_aur_cooldown_typed_input() {
	local saved pending
	saved=$(stty -g 2>/dev/null) || return 1        # not a terminal: nothing typed
	stty -icanon 2>/dev/null
	if [ -n "${ZSH_VERSION:-}" ]; then
		zmodload zsh/zselect 2>/dev/null
		zselect -t 0 -r 0 2>/dev/null               # zsh: ready-to-read test
	else
		read -t 0 2>/dev/null                       # bash: tests, consumes nothing
	fi
	pending=$?
	stty "$saved" 2>/dev/null
	return $pending
}

_aur_cooldown_nudge() {
	case $- in *i*) ;; *) return 0 ;; esac   # interactive shells only
	local state obs nag days today now last age why ans nl
	nl='
'
	state="${XDG_DATA_HOME:-$HOME/.local/share}/aur-cooldown"
	obs="$state/last-observe"
	nag="$state/last-nudge"
	days="${AUR_COOLDOWN_NUDGE_DAYS:-3}"
	today=$(date +%F)

	[ -f "$nag" ] && [ "$(cat "$nag" 2>/dev/null)" = "$today" ] && return 0
	mkdir -p "$state" 2>/dev/null

	now=$(date +%s)
	last=0
	[ -f "$obs" ] && last=$(cat "$obs" 2>/dev/null)
	if [ -z "$last" ] || [ "$last" = 0 ]; then
		why='no metadata yet'
	else
		age=$(( (now - last) / 86400 ))
		[ "$age" -ge "$days" ] || return 0
		why="ledger is ${age}d old"
	fi

	# Stamp the day before saying anything: a declined or interrupted prompt
	# must not come back in the next shell, and two shells starting at the same
	# time must not both ask.
	printf '%s\n' "$today" >"$nag"

	# Fall back to the plain reminder when there is nobody to answer (stdin is
	# not a terminal), when the tool is not on PATH, when asking is off, or when
	# a prompt would steal keystrokes the user has already typed.
	if [ ! -t 0 ] || [ "${AUR_COOLDOWN_NUDGE_ASK:-1}" = 0 ] \
		|| ! command -v aur-cooldown >/dev/null 2>&1 \
		|| _aur_cooldown_typed_input; then
		printf '\033[33m[aur-cooldown]\033[0m %s, run \033[36maur-cooldown observe\033[0m (then \033[36maur-cooldown upgrade\033[0m for updates)\n' "$why"
		return 0
	fi

	# One keypress, no Enter needed, so the prompt is gone as fast as possible.
	printf '\033[33m[aur-cooldown]\033[0m %s, run \033[36mobserve\033[0m now? [Y/n] ' "$why"
	# IFS= so that a lone space stays a space instead of being stripped to the
	# empty string, which would read as Enter and mean yes.
	if [ -n "${ZSH_VERSION:-}" ]; then
		IFS= read -r -k 1 ans || { printf '\n'; return 0; }
	else
		IFS= read -r -n 1 ans || { printf '\n'; return 0; }   # non-zero: EOF
	fi
	# Only y/Y and Enter start work: a stray keypress must not set anything
	# going. Enter has already ended the prompt line, a character has not.
	case "$ans" in
		"" | "$nl") ;;
		[yY]) printf '\n' ;;
		*) printf '\n'; return 0 ;;
	esac

	# Only observe: it is read-only and quick. Installing is left explicit —
	# it wants root and can build for minutes, which is not something to walk
	# into from a shell prompt.
	aur-cooldown observe && \
		printf '\033[33m[aur-cooldown]\033[0m run \033[36maur-cooldown upgrade\033[0m to install what has aged in\n'
}

_aur_cooldown_nudge
