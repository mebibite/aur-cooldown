# bash completion for aur-cooldown.

_aur_cooldown() {
    local cur prev words cword
    _init_completion 2>/dev/null || {
        cur=${COMP_WORDS[COMP_CWORD]}
        prev=${COMP_WORDS[COMP_CWORD-1]}
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
    }

    local commands='observe upgrade status refresh setup'

    # find the subcommand, if any
    local cmd='' i
    for (( i=1; i < cword; i++ )); do
        case "${words[i]}" in
            observe|upgrade|status|refresh|setup) cmd=${words[i]}; break ;;
        esac
    done

    if [[ -z $cmd ]]; then
        if [[ $cur == -* ]]; then
            COMPREPLY=($(compgen -W '--version --help' -- "$cur"))
        else
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
        fi
        return
    fi

    local pkgs
    case "$cmd" in
        observe|status)
            pkgs=$(pacman -Qmq 2>/dev/null)
            COMPREPLY=($(compgen -W "$pkgs" -- "$cur"))
            ;;
        upgrade)
            if [[ $cur == -* ]]; then
                COMPREPLY=($(compgen -W '--dry-run -y --yes' -- "$cur"))
            else
                pkgs=$(pacman -Qmq 2>/dev/null)
                COMPREPLY=($(compgen -W "$pkgs" -- "$cur"))
            fi
            ;;
        setup)
            COMPREPLY=($(compgen -W '--print --revert' -- "$cur"))
            ;;
    esac
}

complete -F _aur_cooldown aur-cooldown
