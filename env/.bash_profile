[[ -f ~/.bashrc ]] && . ~/.bashrc
. "$HOME/.cargo/env"

# uv
export PATH="/home/helder/.local/bin:$PATH"

## All that sweet sweet fzf
[ -f ~/.fzf.bash ] && source ~/.fzf.bash
