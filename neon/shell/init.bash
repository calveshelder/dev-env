# Neon Dev: shared interactive Bash. Use a fresh terminal after changing this.
[[ $- == *i* && -n ${BASH_VERSION:-} ]] || return 0
[[ -z ${_NEON_INIT_DONE:-} ]] || return 0
_NEON_INIT_DONE=1
source "${BASH_SOURCE[0]%/*}/env.bash"

alias v='nvim'
alias gs='git status --short --branch'
alias gd='git diff'
alias gds='git diff --staged'
alias gl='git log --oneline --decorate --graph -20'
alias ..='cd ..'
alias ...='cd ../..'
alias c='clear'
if command -v eza >/dev/null 2>&1; then
    alias ll='eza --long --all --group-directories-first --git'
    alias la='eza --all --group-directories-first'
    alias lt='eza --tree --level=2 --group-directories-first'
else
    alias ll='ls -alF'
    alias la='ls -A'
fi
mkcd() { [[ $# == 1 ]] || { printf 'Usage: mkcd DIRECTORY\n' >&2; return 2; }; mkdir -p -- "$1" && cd -- "$1"; }
croot() {
    local root
    root=$(git rev-parse --show-toplevel 2>/dev/null) || { printf 'Not inside a Git worktree.\n' >&2; return 1; }
    cd -- "$root"
}
take() { tmux-sessionizer "$@"; }

# Local overrides win over shared aliases/functions and configure integrations.
[[ ! -r $HOME/.config/neon/local.bash ]] || source "$HOME/.config/neon/local.bash"

# Kickstart remains the real Neovim config. VIMINIT only adds the parent-owned
# layer when this machine has installed our submodule as its config directory.
# An explicit -u/--clean bypasses it; an existing VIMINIT remains authoritative.
if [[ ${NEON_NVIM_OVERLAY:-1} == 1 && -z ${VIMINIT+x} &&
      -f $NEON_ROOT/nvim/init.lua &&
      $HOME/.config/nvim -ef $NEON_ROOT/../.config/nvim ]]; then
    export VIMINIT='execute has("nvim") ? "lua dofile(vim.env.NEON_ROOT .. \"/nvim/init.lua\")" : "source " . fnameescape($NEON_ROOT . "/nvim/vim-fallback.vim")'
fi
shopt -s histappend checkwinsize
HISTCONTROL=${HISTCONTROL:-ignoreboth}
HISTSIZE=${NEON_HISTORY_SIZE:-100000}
HISTFILESIZE=${NEON_HISTORY_FILE_SIZE:-200000}
: "${HISTFILE:=$HOME/.bash_history}"
export HISTFILE
if [[ ! -e $HISTFILE ]]; then
    (umask 077; : >> "$HISTFILE") 2>/dev/null || :
fi

# Keep NVM available without sourcing its large script on every shell startup.
# No directory-change hooks, automatic .nvmrc execution, or silent downloads.
export NVM_DIR=${NVM_DIR:-$HOME/.nvm}
if [[ ${NEON_LAZY_NVM:-1} == 1 && -s $NVM_DIR/nvm.sh && -z ${NVM_BIN:-} ]]; then
    _neon_load_nvm() {
        unset -f nvm node npm npx corepack
        source "$NVM_DIR/nvm.sh"
    }
    nvm() { _neon_load_nvm && nvm "$@"; }
    node() { _neon_load_nvm && command node "$@"; }
    npm() { _neon_load_nvm && command npm "$@"; }
    npx() { _neon_load_nvm && command npx "$@"; }
    corepack() { _neon_load_nvm && command corepack "$@"; }
fi

if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 4))); then
    PS1='\u@\h:\w \$ '
    printf 'Neon: use Bash 4.4+ for Atuin and Arena (on macOS: brew install bash).\n' >&2
    return 0
fi

if [[ -z ${BASH_COMPLETION_VERSINFO:-} ]]; then
    for _neon_completion in /usr/share/bash-completion/bash_completion \
        /opt/homebrew/etc/profile.d/bash_completion.sh /usr/local/etc/profile.d/bash_completion.sh; do
        if [[ -r $_neon_completion ]]; then source "$_neon_completion"; break; fi
    done
    unset _neon_completion
fi

# Initialise each integration once. Atuin takes Ctrl-r after fzf is loaded.
export FZF_DEFAULT_OPTS=${FZF_DEFAULT_OPTS:---height=45% --layout=reverse --border=rounded --color=bg+:#152238,fg+:#D6E1FF,hl:#FF72D5,hl+:#F5F570,pointer:#47EBFF,marker:#FF72D5,prompt:#47EBFF}
if command -v fd >/dev/null 2>&1; then
    [[ -n ${FZF_DEFAULT_COMMAND+x} ]] || export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
    [[ -n ${FZF_CTRL_T_COMMAND+x} ]] || export FZF_CTRL_T_COMMAND=$FZF_DEFAULT_COMMAND
    [[ -n ${FZF_ALT_C_COMMAND+x} ]] || export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
elif command -v fdfind >/dev/null 2>&1; then
    [[ -n ${FZF_DEFAULT_COMMAND+x} ]] || export FZF_DEFAULT_COMMAND='fdfind --type f --hidden --exclude .git'
    [[ -n ${FZF_CTRL_T_COMMAND+x} ]] || export FZF_CTRL_T_COMMAND=$FZF_DEFAULT_COMMAND
    [[ -n ${FZF_ALT_C_COMMAND+x} ]] || export FZF_ALT_C_COMMAND='fdfind --type d --hidden --exclude .git'
fi
if command -v fzf >/dev/null 2>&1; then
    if _neon_fzf_init=$(fzf --bash 2>/dev/null); then
        eval "$_neon_fzf_init"
    else
        for _neon_fzf_file in "$HOME/.fzf.bash" /usr/share/fzf/key-bindings.bash /usr/share/doc/fzf/examples/key-bindings.bash; do
            if [[ -r $_neon_fzf_file ]]; then source "$_neon_fzf_file"; break; fi
        done
    fi
    unset _neon_fzf_init _neon_fzf_file
fi
if command -v atuin >/dev/null 2>&1 && [[ ${NEON_ATUIN:-1} == 1 ]]; then
    if _neon_atuin_init=$(atuin init bash --disable-up-arrow 2>/dev/null); then
        eval "$_neon_atuin_init"
    fi
    unset _neon_atuin_init
fi
if [[ -z ${bash_preexec_imported:-} ]] && ! declare -F __bp_precmd_invoke_cmd >/dev/null; then
    source "$NEON_ROOT/vendor/bash-preexec.sh"
fi
if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init bash)"
fi
if command -v starship >/dev/null 2>&1; then
    export STARSHIP_CONFIG=${STARSHIP_CONFIG:-$HOME/.config/starship.toml}
    eval "$(starship init bash)"
else
    PS1='\[\e[38;2;71;235;255m\]\w\[\e[0m\]\n❯ '
fi

# Preserve the familiar project-picker chord in both default and vi insert maps.
if command -v tmux-sessionizer >/dev/null 2>&1; then
    bind -m emacs-standard -x '"\C-f":tmux-sessionizer'
    bind -m vi-insert -x '"\C-f":tmux-sessionizer'
fi

# Work starts with Ghost visuals and silent cues. Override in local.bash.
if [[ $NEON_PROFILE == work ]]; then
    export NEON_ARENA_QUIET=${NEON_ARENA_QUIET:-1}
else
    export NEON_ARENA_QUIET=${NEON_ARENA_QUIET:-0}
fi
if [[ ${NEON_ARENA:-1} == 1 && -r $HOME/.local/share/shell-arena/arena.bash ]]; then
    source "$HOME/.local/share/shell-arena/arena.bash"
fi
return 0
