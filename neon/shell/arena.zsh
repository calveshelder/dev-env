# Native Zsh adapter for Shell Arena. The Bash adapter remains independent.
# Submit cues use preexec, preserving Enter widgets, Atuin and custom bindings.
# State is shared with Bash; command strings never enter the audio/state store.
[[ -o interactive && -n ${ZSH_VERSION:-} ]] || return 0
[[ -z ${_NEON_ARENA_ZSH_LOADED:-} ]] || return 0
[[ -n ${NEON_ROOT:-} && -f $NEON_ROOT/vendor/shell-arena/arena_state.py ]] || return 0
(( $+commands[python3] )) || return 0
_NEON_ARENA_ZSH_LOADED=1
_ARENA_DIR="$NEON_ROOT/vendor/shell-arena"

_ARENA_XP=0 _ARENA_WINS=0 _ARENA_MUTED=0 _ARENA_ENABLED=1 _ARENA_HUD=1
_ARENA_VIBE=1 _ARENA_VOLUME=60 _ARENA_OPS=0 _ARENA_PREVIOUS_RC=0 _ARENA_AUDIO_CONFIG=''
_ARENA_ACTIVE=0 _ARENA_BITS=0 _ARENA_PENDING=0 _ARENA_FOCUS_END=0
_ARENA_AUDIO_FD='' _ARENA_AUDIO_PID='' _ARENA_AUDIO_RUN='' _ARENA_CUE=''
_ARENA_LABEL='' _ARENA_LAST='READY' _ARENA_STARTED=0

_arena_read_state() {
    emulate -L zsh
    local line xp wins muted enabled hud vibe volume
    (($#)) || set -- read
    line=$(python3 "$_ARENA_DIR/arena_state.py" "$@" 2>/dev/null) || return 1
    [[ $line =~ ^([0-9]{1,10})\ ([0-9]{1,10})\ ([01])\ ([01])\ ([01])\ ([012])\ ([0-9]{1,3})$ ]] || return 1
    IFS=' ' read -r xp wins muted enabled hud vibe volume <<< "$line"
    ((10#$volume <= 100)) || return 1
    _ARENA_XP=$((10#$xp)) _ARENA_WINS=$((10#$wins))
    _ARENA_MUTED=$muted _ARENA_ENABLED=$enabled _ARENA_HUD=$hud
    _ARENA_VIBE=$vibe _ARENA_VOLUME=$((10#$volume))
    # A work-session preference never writes over the saved personal settings.
    if [[ ${NEON_ARENA_QUIET:-0} == 1 ]]; then
        _ARENA_MUTED=1 _ARENA_VIBE=2
    fi
    return 0
}

_arena_profile() {
    emulate -L zsh
    case $_ARENA_VIBE in 0) _ARENA_PROFILE=classic;; 2) _ARENA_PROFILE=ghost;; *) _ARENA_PROFILE=cyber;; esac
}

_arena_audio_start() {
    emulate -L zsh
    _arena_profile
    local config="$_ARENA_PROFILE:$_ARENA_VOLUME:$_ARENA_MUTED:$_ARENA_ENABLED"
    [[ -n $_ARENA_AUDIO_PID && $_ARENA_AUDIO_CONFIG == "$config" ]] && kill -0 "$_ARENA_AUDIO_PID" 2>/dev/null && return 0
    # Release a previous dead daemon's descriptor before starting another one.
    _arena_audio_stop
    [[ $_ARENA_ENABLED == 1 && $_ARENA_MUTED == 0 && $_ARENA_VOLUME != 0 ]] || return 0
    command -v paplay >/dev/null 2>&1 || command -v afplay >/dev/null 2>&1 || return 0
    local run
    run=$(mktemp -d "${TMPDIR:-/tmp}/shell-arena.${UID}.XXXXXXXX") || return 0
    if ! mkfifo -m 600 "$run/events"; then rmdir -- "$run" 2>/dev/null; return 0; fi
    if ! exec {_ARENA_AUDIO_FD}<>"$run/events"; then
        command rm -f -- "$run/events"
        rmdir -- "$run"
        _ARENA_AUDIO_FD=''
        return 0
    fi
    # O_NONBLOCK is shared by the inherited descriptor: a full pipe must never
    # stall the shell. No interpreter is started on the per-command hot path.
    if ! python3 -c 'import os,sys; os.set_blocking(int(sys.argv[1]), False)' "$_ARENA_AUDIO_FD"; then
        exec {_ARENA_AUDIO_FD}>&-
        _ARENA_AUDIO_FD=''
        command rm -f -- "$run/events"
        rmdir -- "$run"
        return 0
    fi
    # Spawn inside a command substitution so no visible background job is added.
    _ARENA_AUDIO_PID=$(
        python3 "$_ARENA_DIR/arena_audio.py" daemon --fifo "$run/events" \
            --sounds "$_ARENA_DIR/sounds" --parent "$$" \
            --profile "$_ARENA_PROFILE" --volume "$_ARENA_VOLUME" </dev/null >/dev/null 2>&1 &
        printf '%s' "$!"
    )
    _ARENA_AUDIO_RUN=$run
    _ARENA_AUDIO_CONFIG=$config
    return 0
}

_arena_sound() {
    emulate -L zsh
    [[ $_ARENA_ENABLED == 1 && $_ARENA_MUTED == 0 && -n $_ARENA_AUDIO_FD ]] || return 0
    kill -0 "$_ARENA_AUDIO_PID" 2>/dev/null || return 0
    # Both ends are held open by this shell, so a daemon exit cannot SIGPIPE it.
    local event=$1
    if [[ $_ARENA_VIBE == 1 ]] && (( _ARENA_OPS % 2 )); then
        case $event in launch|ok) event+=2;; esac
    fi
    { printf '%s\n' "$event" >&"$_ARENA_AUDIO_FD"; } 2>/dev/null || :
    return 0
}

_arena_audio_stop() {
    emulate -L zsh
    if [[ -n $_ARENA_AUDIO_FD ]]; then
        { printf 'quit\n' >&"$_ARENA_AUDIO_FD"; } 2>/dev/null || :
        exec {_ARENA_AUDIO_FD}>&-
    fi
    if [[ -n $_ARENA_AUDIO_RUN ]]; then
        # Only remove the one private FIFO we created; never recurse into paths.
        [[ ! -p $_ARENA_AUDIO_RUN/events ]] || command rm -f -- "$_ARENA_AUDIO_RUN/events"
        rmdir -- "$_ARENA_AUDIO_RUN" 2>/dev/null || :
    fi
    _ARENA_AUDIO_FD='' _ARENA_AUDIO_PID='' _ARENA_AUDIO_RUN=''
    _ARENA_AUDIO_CONFIG=''
    return 0
}

_arena_stage_count() {
    emulate -L zsh
    _ARENA_STAGE=$(( (_ARENA_BITS & 1) + ((_ARENA_BITS >> 1) & 1) + ((_ARENA_BITS >> 2) & 1) ))
}

_arena_draw() {
    emulate -L zsh
    [[ $_ARENA_ENABLED == 1 && $_ARENA_HUD == 1 && -t 2 ]] || return 0
    if [[ $_ARENA_VIBE != 0 ]]; then _arena_neon_draw; return 0; fi
    local cyan='' pink='' grey='' reset='' accent='' width=${COLUMNS:-80} text meter=''
    local head tail room
    local lvl=$((_ARENA_XP / 300 + 1)) progress=$((_ARENA_XP % 300)) i
    if [[ -z ${NO_COLOR+x} && ${TERM:-} != dumb ]]; then
        cyan=$'\e[38;2;100;235;255m' pink=$'\e[38;2;218;160;255m'
        grey=$'\e[38;2;140;151;175m' reset=$'\e[0m'
        accent=$'\e[38;2;160;235;175m'
        [[ $_ARENA_LAST != RETRY* ]] || accent=$'\e[38;2;255;200;120m'
    fi
    _arena_stage_count
    for ((i=0; i<6; i++)); do
        if (( i < progress / 50 )); then meter+='━'; else meter+='─'; fi
    done
    head="ARENA  LV.$lvl  $meter  $progress/300 XP  $_ARENA_LAST"
    tail=''
    if [[ $_ARENA_ACTIVE == 1 ]]; then
        tail+="  |  $_ARENA_STAGE/3 $_ARENA_LABEL"
    else
        tail+='  |  arena quest "one small goal"'
    fi
    if (( _ARENA_FOCUS_END > 0 )); then
        local left=$((_ARENA_FOCUS_END - SECONDS))
        ((left < 0)) && left=0
        tail+="  [$((left / 60))m]"
    fi
    [[ $width =~ ^[0-9]{1,5}$ ]] || width=80
    width=$((10#$width))
    ((width < 20)) && width=20
    # One bounded line: no cursor movement, animation, title escape, or TUI writes.
    if ((width <= ${#head} + 1)); then
        text="$head$tail"
        printf '%s%s%s\n' "$cyan" "${text:0:$((width - 1))}" "$reset" >&2
    else
        room=$((width - ${#head} - 1))
        printf '%sARENA%s  LV.%s  %s%s%s  %s/300 XP  %s%s%s%s%s\n' \
            "$cyan" "$pink" "$lvl" "$cyan" "$meter" "$grey" "$progress" \
            "$accent" "$_ARENA_LAST" "$grey" "${tail:0:$room}" "$reset" >&2
    fi
    return 0
}

_arena_neon_draw() {
    emulate -L zsh
    local width=${COLUMNS:-80} ink='' accent='' dim='' reset='' name=CYBER
    local level=$((_ARENA_XP / 300 + 1)) progress=$((_ARENA_XP % 300))
    local meter='' i node arena_status=$_ARENA_LAST line detail place=${PWD##*/}
    [[ $width =~ ^[0-9]{1,5}$ ]] || width=80
    width=$((10#$width))
    ((width >= 2)) || return 0
    width=$((width - 1))
    [[ $_ARENA_VIBE != 2 ]] || name=GHOST
    if [[ -z ${NO_COLOR+x} && ${TERM:-} != dumb ]]; then
        ink=$'\e[38;2;71;235;255m' accent=$'\e[38;2;245;245;112m'
        dim=$'\e[38;2;147;163;185m' reset=$'\e[0m'
        [[ $_ARENA_VIBE != 2 ]] || { ink=$'\e[38;2;132;245;177m'; accent=$ink; }
        [[ $arena_status != RETRY* ]] || accent=$'\e[38;2;255;154;112m'
        [[ $arena_status != RECOVERED* && $arena_status != 'LEVEL UP'* ]] || accent=$'\e[38;2;255;114;213m'
    fi
    for ((i=0; i<6; i++)); do
        if ((i < progress / 50)); then meter+='━'; else meter+='─'; fi
    done
    case $((_ARENA_OPS % 4)) in 0) node=◇;; 1) node=◈;; 2) node=◆;; 3) node=◈;; esac
    case $arena_status in CLEAR*) arena_status="ACK${arena_status#CLEAR}";; READY) arena_status='LINK READY';; esac
    _arena_stage_count
    # Cosmetic operation count, never XP or evidence of learning. Nothing is logged.
    place=${place//[[:cntrl:]]/}
    place=${place:0:24}
    detail="${place:-/}"
    [[ $_ARENA_ACTIVE != 1 ]] || detail="$_ARENA_STAGE/3 $_ARENA_LABEL"
    if ((_ARENA_FOCUS_END > 0)); then
        local left=$((_ARENA_FOCUS_END - SECONDS))
        ((left < 0)) && left=0
        detail+=" | FOCUS $((left / 60))m"
    fi
    if ((width >= 69)); then
        line="$node SHELL ARENA / $name  //  LV.$level  $meter  $progress/300 XP"
        printf '%s%s%s\n' "$ink" "${line:0:$width}" "$reset" >&2
        line="  $_ARENA_OPS OPS / $arena_status"
        local room=$((width - ${#line} - 3))
        if ((room > 0)); then
            printf '%s%s%s | %s%s\n' "$accent" "$line" "$dim" "${detail:0:$room}" "$reset" >&2
        else
            printf '%s%s%s\n' "$accent" "${line:0:$width}" "$reset" >&2
        fi
    else
        line="$node ARENA L$level / $arena_status / $_ARENA_OPS OPS"
        printf '%s%s%s\n' "$ink" "${line:0:$width}" "$reset" >&2
    fi
    return 0
}

_arena_preexec() {
    emulate -L zsh
    [[ $_ARENA_ENABLED == 1 ]] || return 0
    _ARENA_PENDING=1
    _ARENA_STARTED=$SECONDS
    _ARENA_CUE=''
    _arena_sound launch
    return 0
}

_arena_precmd() {
    local rc=$?
    emulate -L zsh
    [[ $_ARENA_ENABLED == 1 ]] || return 0
    if [[ $_ARENA_PENDING == 1 ]]; then
        _ARENA_PENDING=0
        _ARENA_OPS=$((_ARENA_OPS + 1))
        local elapsed=$((SECONDS - _ARENA_STARTED)) event=ok
        if ((rc == 0)); then
            _ARENA_LAST="CLEAR ${elapsed}s"
            if [[ $_ARENA_VIBE != 0 ]]; then
                if ((_ARENA_PREVIOUS_RC != 0 && _ARENA_PREVIOUS_RC != 130)); then
                    _ARENA_LAST="RECOVERED ${elapsed}s"; event=recover
                elif ((elapsed >= 10)); then
                    _ARENA_LAST="JOB DONE ${elapsed}s"; event=complete
                fi
                case $_ARENA_CUE in
                    quest) if [[ $_ARENA_ACTIVE == 1 ]]; then _ARENA_LAST='QUEST LOADED'; else _ARENA_LAST='QUEST CLEARED'; fi;;
                    level) _ARENA_LAST='LEVEL UP';;
                esac
            fi
            _arena_sound "${_ARENA_CUE:-$event}"
        elif ((rc == 130)); then
            _ARENA_LAST='CANCELLED'
        else
            # Nonzero is not always an error (e.g. grep found no match).
            _ARENA_LAST="RETRY ($rc)"
            _arena_sound error
        fi
        _ARENA_PREVIOUS_RC=$rc
    fi
    if (( _ARENA_FOCUS_END > 0 && SECONDS >= _ARENA_FOCUS_END )); then
        _ARENA_FOCUS_END=0
        printf 'Arena: focus round complete. Save your work and take a breather.\n' >&2
        _arena_sound quest
    fi
    _arena_draw
    return 0
}

arena() {
    emulate -L zsh
    local action=${1:-status} value rc old_level cleaned
    (($#)) && shift
    case $action in
        quest)
            [[ $_ARENA_ACTIVE == 0 ]] || { printf 'Finish this quest, or use arena abandon first.\n'; return 1; }
            [[ -n $* ]] || { printf 'Usage: arena quest "one specific learning goal"\n'; return 2; }
            cleaned=$*
            # Strip control bytes (including ESC) and limit display length.
            cleaned=${cleaned//[[:cntrl:]]/}
            [[ $cleaned == *[![:space:]]* ]] || { printf 'Give your quest a short, visible goal.\n'; return 2; }
            _ARENA_LABEL=${cleaned:0:60}
            _ARENA_ACTIVE=1 _ARENA_BITS=0 _ARENA_CUE=quest
            printf 'QUEST: %s\n1. Predict the result; arena predict\n2. Run a check; arena check COMMAND [ARGS]\n3. Explain from memory; arena recall\nThen arena finish.\n' "$_ARENA_LABEL"
            ;;
        predict)
            [[ $_ARENA_ACTIVE == 1 ]] || { printf 'Start a quest first.\n'; return 1; }
            _ARENA_BITS=$((_ARENA_BITS | 1))
            printf 'Prediction marked. Say or write your prediction before checking it.\n'
            ;;
        check)
            [[ $_ARENA_ACTIVE == 1 && $((_ARENA_BITS & 1)) == 1 ]] || { printf 'Start a quest and mark your prediction first.\n'; return 1; }
            [[ ${1:-} != -- ]] || shift
            (($#)) || { printf 'Usage: arena check go test ./...\n'; return 2; }
            _ARENA_BITS=$((_ARENA_BITS & 1))
            # Explicit argv, no eval or re-execution of history.
            "$@"
            rc=$?
            if ((rc == 0)); then
                _ARENA_BITS=$((_ARENA_BITS | 2))
                printf 'Check passed. Now explain WHY without looking at the answer.\n'
            else
                printf 'Check returned %s. Adjust your model and try again; no XP lost.\n' "$rc"
            fi
            return "$rc"
            ;;
        recall)
            [[ $_ARENA_ACTIVE == 1 && $((_ARENA_BITS & 3)) == 3 ]] || { printf 'Predict and pass a check first.\n'; return 1; }
            _ARENA_BITS=$((_ARENA_BITS | 4))
            printf 'Recall marked (self-reported). Ready: arena finish\n'
            ;;
        finish)
            [[ $_ARENA_ACTIVE == 1 && $_ARENA_BITS == 7 ]] || { printf 'Complete predict -> check -> recall first.\n'; return 1; }
            old_level=$((_ARENA_XP / 300 + 1))
            if ! _arena_read_state award; then
                printf 'Could not save XP. Quest remains active; check state-file access.\n' >&2
                return 1
            fi
            _ARENA_ACTIVE=0 _ARENA_BITS=0 _ARENA_LABEL=''
            _ARENA_CUE=quest
            printf '+100 XP | %s quests complete | total %s XP\n' "$_ARENA_WINS" "$_ARENA_XP"
            if (( _ARENA_XP / 300 + 1 > old_level )); then
                _ARENA_CUE=level
                printf 'LEVEL UP: %s\n' "$((_ARENA_XP / 300 + 1))"
            fi
            ;;
        abandon)
            _ARENA_ACTIVE=0 _ARENA_BITS=0 _ARENA_LABEL=''
            printf 'Quest cleared. Earned XP is unchanged.\n'
            ;;
        focus)
            value=${1:-20}
            [[ $value =~ ^[0-9]{1,2}$ ]] && ((10#$value >= 1 && 10#$value <= 90)) || {
                printf 'Usage: arena focus MINUTES (1-90)\n'; return 2;
            }
            _ARENA_FOCUS_END=$((SECONDS + 10#$value * 60))
            printf '%s-minute focus round. Break notice appears at the next shell prompt after it ends.\n' "$value"
            ;;
        mute|unmute)
            value=1; [[ $action == mute ]] || value=0
            _arena_read_state set muted "$value" || { printf 'Could not save sound preference.\n' >&2; return 1; }
            if [[ $_ARENA_MUTED == 1 ]]; then _arena_audio_stop; else _arena_audio_start; fi
            [[ $value != 0 || ${NEON_ARENA_QUIET:-0} != 1 ]] || printf 'This work session stays quiet. Set NEON_ARENA_QUIET=0 to enable sound here.\n'
            printf 'Arena sounds: %s\n' "$action"
            ;;
        off|on)
            value=0; [[ $action == off ]] || value=1
            _arena_read_state set enabled "$value" || { printf 'Could not save preference.\n' >&2; return 1; }
            _ARENA_PENDING=0
            if [[ $value == 0 ]]; then _arena_audio_stop; elif [[ $_ARENA_MUTED == 0 ]]; then _arena_audio_start; fi
            printf 'Arena %s. Existing shell and Neovim settings are unchanged.\n' "$action"
            ;;
        hud)
            case ${1:-} in on) value=1;; off) value=0;; *) printf 'Usage: arena hud on|off\n'; return 2;; esac
            _arena_read_state set hud "$value" || return 1
            ;;
        vibe)
            case ${1:-} in classic) value=0;; cyber) value=1;; ghost) value=2;;
                *) printf 'Usage: arena vibe cyber|ghost|classic\n'; return 2;; esac
            _arena_read_state set vibe "$value" || return 1
            _arena_audio_start
            _arena_profile
            printf 'Neon Link: %s. Saved for future shells.\n' "$_ARENA_PROFILE"
            _ARENA_CUE=boot
            ;;
        volume)
            value=${1:-}
            [[ $value =~ ^[0-9]{1,3}$ ]] && ((10#$value <= 100)) || {
                printf 'Usage: arena volume 0-100 (default 60; capped source level)\n'; return 2;
            }
            _arena_read_state set volume "$((10#$value))" || return 1
            _arena_audio_start
            printf 'Arena volume: %s%% of source level. System volume also applies.\n' "$_ARENA_VOLUME"
            ;;
        soundtest)
            _arena_audio_stop
            _arena_profile
            python3 "$_ARENA_DIR/arena_audio.py" test --sounds "$_ARENA_DIR/sounds" \
                --profile "$_ARENA_PROFILE" --volume "$_ARENA_VOLUME"
            rc=$?
            _arena_audio_start
            return "$rc"
            ;;
        status)
            _arena_read_state read || printf 'Warning: could not refresh saved totals.\n' >&2
            if [[ $_ARENA_ENABLED == 1 && $_ARENA_MUTED == 0 ]]; then
                _arena_audio_start
            else
                _arena_audio_stop
            fi
            _arena_stage_count
            printf 'SHELL ARENA | level %s | %s XP | %s completed quests\n' "$((_ARENA_XP / 300 + 1))" "$_ARENA_XP" "$_ARENA_WINS"
            printf 'Enabled: %s | muted: %s | HUD: %s | this quest: %s/3\n' "$_ARENA_ENABLED" "$_ARENA_MUTED" "$_ARENA_HUD" "$_ARENA_STAGE"
            printf 'Quest: %s\n' "${_ARENA_LABEL:-none}"
            _arena_profile
            printf 'Vibe: %s | volume: %s%% | session operations: %s (cosmetic, not XP)\n' "$_ARENA_PROFILE" "$_ARENA_VOLUME" "$_ARENA_OPS"
            ;;
        help)
            printf '%s\n' \
                'arena quest "goal"       Start a tiny learning quest' \
                'arena predict            Mark your prediction (self-reported)' \
                'arena check go test ./... Run your actual test command' \
                'arena recall             Mark explanation from memory (self-reported)' \
                'arena finish             +100 XP once; level up every 300 XP' \
                'arena focus 20           A prompt-based focus countdown' \
                'arena status             Totals; refresh from other terminals' \
                'arena abandon            Clear the current quest; no XP penalty' \
                'arena mute / unmute      Persist sound preference' \
                'arena hud off / on       Hide/show the status line' \
                'arena vibe cyber         Neon cyan/yellow HUD + digital sound pack' \
                'arena vibe ghost         Green HUD + softer sound pack' \
                'arena vibe classic       Original single-line HUD + original core sounds' \
                'arena volume 60          Save volume, 0-100; system volume also applies' \
                'arena off / on           Persistently disable/enable effects' \
                'arena soundtest          Test audio and show diagnostics' \
                'No rewards for command volume; no lost streaks. Quests are per-shell.'
            ;;
        *) printf 'Unknown arena command. Try arena help.\n' >&2; return 2;;
    esac
    return 0
}


_arena_read_state read || printf 'Arena: cannot read local stats; using session defaults.\n' >&2
if [[ ${NEON_ARENA_QUIET:-0} == 1 ]]; then
    _ARENA_MUTED=1 _ARENA_VIBE=2
fi
[[ $_ARENA_ENABLED == 0 || $_ARENA_MUTED == 1 ]] || _arena_audio_start
[[ $_ARENA_VIBE == 0 ]] || _arena_sound boot
autoload -Uz add-zsh-hook
add-zsh-hook preexec _arena_preexec
add-zsh-hook precmd _arena_precmd
add-zsh-hook zshexit _arena_audio_stop
# Do not run compinit or alter key maps; use an existing completion setup.
_arena_complete() {
    emulate -L zsh
    local -a arena_actions
    arena_actions=(quest predict check recall finish focus status abandon mute unmute hud vibe volume off on soundtest help)
    compadd -- "${arena_actions[@]}"
}
(( $+functions[compdef] )) && compdef _arena_complete arena
return 0
