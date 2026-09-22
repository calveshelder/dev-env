# Neon Dev: native interactive Zsh. Source once at the end of your .zshrc.
[[ -n ${ZSH_VERSION:-} && -o interactive ]] || return 0
[[ -z ${_NEON_ZSH_INIT_DONE:-} ]] || return 0
typeset -g _NEON_ZSH_INIT_DONE=1
source "${${(%):-%x}:A:h}/env.zsh"

alias v='nvim'
alias gs='git status --short --branch'
alias gd='git diff'
alias gds='git diff --staged'
alias gl='git log --oneline --decorate --graph -20'
alias ..='cd ..'
alias ...='cd ../..'
alias c='clear'
if (( $+commands[eza] )); then
    alias ll='eza --long --all --group-directories-first --git'
    alias la='eza --all --group-directories-first'
    alias lt='eza --tree --level=2 --group-directories-first'
else
    alias ll='ls -alF'
    alias la='ls -A'
fi
mkcd() { [[ $# == 1 ]] || { print -u2 'Usage: mkcd DIRECTORY'; return 2; }; mkdir -p -- "$1" && builtin cd -- "$1"; }
croot() {
    local root
    root=$(git rev-parse --show-toplevel 2>/dev/null) || { print -u2 'Not inside a Git worktree.'; return 1; }
    builtin cd -- "$root"
}
take() { tmux-sessionizer "$@"; }

# Local aliases and integration switches override shared defaults.
[[ ! -r $HOME/.config/neon/local.zsh ]] || source "$HOME/.config/neon/local.zsh"

# Keep the actual Kickstart submodule untouched; add our parent-owned overlay
# only when that checkout is this machine's installed Neovim config.
if [[ ${NEON_NVIM_OVERLAY:-1} == 1 && ${+VIMINIT} == 0 &&
      -f $NEON_ROOT/nvim/init.lua &&
      $HOME/.config/nvim -ef $NEON_ROOT/../.config/nvim ]]; then
    export VIMINIT='execute has("nvim") ? "lua dofile(vim.env.NEON_ROOT .. \"/nvim/init.lua\")" : "source " . fnameescape($NEON_ROOT . "/nvim/vim-fallback.vim")'
fi

setopt APPEND_HISTORY INC_APPEND_HISTORY HIST_IGNORE_ALL_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS
HISTSIZE=${NEON_HISTORY_SIZE:-100000}
SAVEHIST=${NEON_HISTORY_FILE_SIZE:-200000}
: "${HISTFILE:=$HOME/.zsh_history}"
export HISTFILE
if [[ ! -e $HISTFILE ]]; then
    (umask 077; : >> "$HISTFILE") 2>/dev/null || :
fi

# Use an already initialized completion system (Oh My Zsh etc.) when present.
# -i skips insecure completion directories instead of trusting them silently.
if (( ! $+functions[compdef] )); then
    autoload -Uz compinit
    _neon_completion_cache=${XDG_CACHE_HOME:-$HOME/.cache}/neon
    if [[ -d $_neon_completion_cache ]] || (umask 077; command mkdir -p -- "$_neon_completion_cache") 2>/dev/null; then
        compinit -i -d "$_neon_completion_cache/zcompdump-$ZSH_VERSION"
    else
        compinit -i -D
    fi
    unset _neon_completion_cache
fi

# Keep NVM optional and lazy. A Homebrew/system Node already on PATH keeps
# working immediately; run `nvm use` when you want NVM to select a version.
export NVM_DIR=${NVM_DIR:-$HOME/.nvm}
if [[ ${NEON_LAZY_NVM:-1} == 1 && -s $NVM_DIR/nvm.sh && -z ${NVM_BIN:-} ]] && (( ! $+functions[nvm] )); then
    typeset -ga _neon_nvm_lazy_commands=(nvm)
    _neon_load_nvm() {
        local name
        for name in "${_neon_nvm_lazy_commands[@]}"; do unfunction "$name"; done
        unset _neon_nvm_lazy_commands
        source "$NVM_DIR/nvm.sh"
    }
    nvm() { _neon_load_nvm && nvm "$@"; }
    if (( ! $+commands[node] && ! $+functions[node] )); then
        node() { _neon_load_nvm && command node "$@"; }
        _neon_nvm_lazy_commands+=(node)
    fi
    if (( ! $+commands[npm] && ! $+functions[npm] )); then
        npm() { _neon_load_nvm && command npm "$@"; }
        _neon_nvm_lazy_commands+=(npm)
    fi
    if (( ! $+commands[npx] && ! $+functions[npx] )); then
        npx() { _neon_load_nvm && command npx "$@"; }
        _neon_nvm_lazy_commands+=(npx)
    fi
    if (( ! $+commands[corepack] && ! $+functions[corepack] )); then
        corepack() { _neon_load_nvm && command corepack "$@"; }
        _neon_nvm_lazy_commands+=(corepack)
    fi
fi

export FZF_DEFAULT_OPTS=${FZF_DEFAULT_OPTS:---height=45% --layout=reverse --border=rounded --color=bg+:#152238,fg+:#D6E1FF,hl:#FF72D5,hl+:#F5F570,pointer:#47EBFF,marker:#FF72D5,prompt:#47EBFF}
if (( $+commands[fd] )); then
    [[ -n ${FZF_DEFAULT_COMMAND+x} ]] || export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
    [[ -n ${FZF_CTRL_T_COMMAND+x} ]] || export FZF_CTRL_T_COMMAND=$FZF_DEFAULT_COMMAND
    [[ -n ${FZF_ALT_C_COMMAND+x} ]] || export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
elif (( $+commands[fdfind] )); then
    [[ -n ${FZF_DEFAULT_COMMAND+x} ]] || export FZF_DEFAULT_COMMAND='fdfind --type f --hidden --exclude .git'
    [[ -n ${FZF_CTRL_T_COMMAND+x} ]] || export FZF_CTRL_T_COMMAND=$FZF_DEFAULT_COMMAND
    [[ -n ${FZF_ALT_C_COMMAND+x} ]] || export FZF_ALT_C_COMMAND='fdfind --type d --hidden --exclude .git'
fi
if (( $+commands[fzf] && ! $+widgets[fzf-file-widget] )); then
    if _neon_fzf_init=$(fzf --zsh 2>/dev/null); then
        eval "$_neon_fzf_init"
    else
        for _neon_fzf_file in "$HOME/.fzf.zsh" /opt/homebrew/opt/fzf/shell/key-bindings.zsh \
            /usr/local/opt/fzf/shell/key-bindings.zsh /usr/share/fzf/key-bindings.zsh; do
            if [[ -r $_neon_fzf_file ]]; then source "$_neon_fzf_file"; break; fi
        done
    fi
    unset _neon_fzf_init _neon_fzf_file
fi
# Atuin owns Ctrl-r after fzf; normal Up-arrow history remains available.
if [[ ${NEON_ATUIN:-1} == 1 ]] && (( $+commands[atuin] && ! $+functions[_atuin_preexec] )); then
    if _neon_atuin_init=$(atuin init zsh --disable-up-arrow 2>/dev/null); then
        eval "$_neon_atuin_init"
    fi
    unset _neon_atuin_init
fi
if (( $+commands[zoxide] && ! $+functions[__zoxide_z] )); then
    if _neon_zoxide_init=$(zoxide init zsh 2>/dev/null); then eval "$_neon_zoxide_init"; fi
    unset _neon_zoxide_init
fi
if [[ ${NEON_STARSHIP:-1} == 1 ]]; then
    export STARSHIP_CONFIG=${STARSHIP_CONFIG:-$HOME/.config/starship.toml}
    if (( $+commands[starship] )); then
        if (( ! $+functions[prompt_starship_precmd] )); then
            if _neon_starship_init=$(starship init zsh 2>/dev/null); then eval "$_neon_starship_init"; fi
            unset _neon_starship_init
        fi
    else
        PROMPT=$'%F{cyan}%~%f\n❯ '
    fi
fi

# Ctrl-f opens/reuses the project workspace, then redraws the existing input.
# Do not force emacs/vi mode: bind each insertion map independently.
if (( $+commands[tmux-sessionizer] )); then
    _neon_project_widget() {
        zle -I
        command tmux-sessionizer </dev/tty
        zle reset-prompt
        return 0
    }
    zle -N neon-project-picker _neon_project_widget
    bindkey -M emacs '^F' neon-project-picker
    bindkey -M viins '^F' neon-project-picker
    bindkey -M main '^F' neon-project-picker
fi

if [[ $NEON_PROFILE == work ]]; then
    export NEON_ARENA_QUIET=${NEON_ARENA_QUIET:-1}
else
    export NEON_ARENA_QUIET=${NEON_ARENA_QUIET:-0}
fi
# The installed data directory is the Arena component marker. Its Bash adapter
# is never sourced by Zsh; the native adapter uses add-zsh-hook instead.
if [[ ${NEON_ARENA:-1} == 1 && -r $HOME/.local/share/shell-arena/arena.bash && -r $NEON_ROOT/shell/arena.zsh ]]; then
    source "$NEON_ROOT/shell/arena.zsh"
fi
return 0
