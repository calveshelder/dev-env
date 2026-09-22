# Shared environment for native Zsh. No Bash startup files are evaluated here.
[[ -n ${ZSH_VERSION:-} ]] || return 0
_neon_path_prepend() {
    [[ -d $1 ]] || return 0
    case :$PATH: in *:"$1":*) ;; *) export PATH="$1:$PATH";; esac
}
# %x is the currently sourced file; :A resolves symlinks before walking upward.
export NEON_ROOT=${${(%):-%x}:A:h:h}
export NEON_SHELL=zsh
for _neon_path in /usr/local/go/bin /opt/sonar-scanner/bin /usr/local/bin /opt/homebrew/bin \
    "$HOME/.ebcli-virtual-env/executables" "$HOME/.lando/bin" \
    "$HOME/.config/composer/vendor/bin" "$HOME/.cargo/bin" "$HOME/.local/scripts" \
    "$HOME/.local/bin" "$NEON_ROOT/bin"; do
    _neon_path_prepend "$_neon_path"
done
unset _neon_path
# Despite its legacy extension, this generated file contains only portable
# quoted export assignments. It is data shared by Bash and Zsh.
[[ ! -r $HOME/.config/neon/machine.bash ]] || source "$HOME/.config/neon/machine.bash"
export NEON_PROFILE=${NEON_PROFILE:-personal}
case $NEON_PROFILE in work|personal) ;; *) export NEON_PROFILE=personal;; esac
export EDITOR=${EDITOR:-nvim}
export VISUAL=${VISUAL:-nvim}
export PAGER=${PAGER:-less}
export LESS=${LESS:--FRX}
