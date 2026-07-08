# aur-cooldown ledger reminder. POSIX; works sourced from bash or zsh.
# Prints at most once per calendar day when the ledger is older than N days,
# and never blocks. Wired up by `aur-cooldown setup`; to do it by hand, add to
# your shell rc:   . /usr/share/aur-cooldown/nudge.sh
# Tunable: AUR_COOLDOWN_NUDGE_DAYS (staleness threshold in days, default 3).

_aur_cooldown_nudge() {
	case $- in *i*) ;; *) return 0 ;; esac   # interactive shells only
	local state obs nag days today now last age
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
		printf '\033[33m[aur-cooldown]\033[0m no metadata yet, run \033[36maur-cooldown observe\033[0m\n'
		printf '%s\n' "$today" >"$nag"
		return 0
	fi

	age=$(( (now - last) / 86400 ))
	[ "$age" -ge "$days" ] || return 0
	printf '\033[33m[aur-cooldown]\033[0m ledger is %sd old, run \033[36maur-cooldown observe\033[0m (then \033[36maur-cooldown upgrade\033[0m for updates)\n' "$age"
	printf '%s\n' "$today" >"$nag"
}

_aur_cooldown_nudge
