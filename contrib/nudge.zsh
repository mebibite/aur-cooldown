# aur-cooldown reminder — reminds you to refresh the metadata ledger when it's gone
# stale (default: every 3 days). Non-blocking, at most once per calendar day.
#
# Enable by adding ONE line to your ~/.zshrc:
#   [[ -f ~/.local/share/aur-cooldown/nudge.zsh ]] && source ~/.local/share/aur-cooldown/nudge.zsh
#
# Tunable: AUR_COOLDOWN_NUDGE_DAYS (staleness threshold, default 3).

aur_cooldown_nudge() {
  emulate -L zsh
  [[ -o interactive ]] || return 0
  local state="${XDG_DATA_HOME:-$HOME/.local/share}/aur-cooldown"
  local obs="$state/last-observe" nag="$state/last-nudge"
  local days="${AUR_COOLDOWN_NUDGE_DAYS:-3}"
  local now today; now=$(date +%s); today=$(date +%F)

  [[ -f $nag && "$(<$nag)" == "$today" ]] && return 0   # nag at most once per day

  local last=0; [[ -f $obs ]] && last=$(<$obs)
  if (( last == 0 )); then
    print -P "%F{yellow}[aur-cooldown]%f no metadata captured yet — start with %F{cyan}aur-cooldown observe%f"
    print -- "$today" > "$nag"; return 0
  fi

  local age=$(( (now - last) / 86400 ))
  (( age >= days )) || return 0
  print -P "%F{yellow}[aur-cooldown]%f ledger is ${age}d stale (>${days}d) — refresh: %F{cyan}aur-cooldown observe%f   then, when you want updates: %F{cyan}aur-cooldown upgrade%f"
  print -- "$today" > "$nag"

  # Optional: auto-run observe on confirm (short timeout; won't hang a shell).
  # if read -q "REPLY?Run 'aur-cooldown observe' now? [y/N] "; then print; aur-cooldown observe; fi
}

aur_cooldown_nudge
