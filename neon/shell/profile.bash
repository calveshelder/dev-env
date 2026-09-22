# Login Bash enters the same interactive configuration exactly once.
source "${BASH_SOURCE[0]%/*}/env.bash"
if [[ $- == *i* && -z ${_NEON_INIT_DONE:-} && -r $HOME/.bashrc ]]; then
    source "$HOME/.bashrc"
fi
