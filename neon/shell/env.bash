# Shared PATH and machine environment; no prompt hooks or network calls.
_neon_path_prepend() {
    [[ -d $1 ]] || return 0
    case :$PATH: in *:"$1":*) ;; *) PATH="$1:$PATH";; esac
}
NEON_ROOT=$(CDPATH= cd -- "${BASH_SOURCE[0]%/*}/.." && pwd -P) || return 1
export NEON_ROOT
export NEON_SHELL=bash
# Preserve platform PATH ordering, with personal tools ahead of system tools.
for _neon_path in /usr/local/go/bin /opt/sonar-scanner/bin /usr/local/bin /opt/homebrew/bin \
    "$HOME/.ebcli-virtual-env/executables" "$HOME/.lando/bin" \
    "$HOME/.config/composer/vendor/bin" "$HOME/.cargo/bin" "$HOME/.local/scripts" \
    "$HOME/.local/bin" "$NEON_ROOT/bin"; do
    _neon_path_prepend "$_neon_path"
done
export PATH
unset _neon_path
[[ ! -r $HOME/.config/neon/machine.bash ]] || source "$HOME/.config/neon/machine.bash"
export NEON_PROFILE=${NEON_PROFILE:-personal}
case $NEON_PROFILE in work|personal) ;; *) NEON_PROFILE=personal;; esac
export EDITOR=${EDITOR:-nvim}
export VISUAL=${VISUAL:-nvim}
export PAGER=${PAGER:-less}
export LESS=${LESS:--FRX}
