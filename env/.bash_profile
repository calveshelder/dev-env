[[ -f ~/.bashrc ]] && . ~/.bashrc
. "$HOME/.cargo/env"

#dev-env
export PATH="/home/helder/local/scripts:$PATH"

# uv
export PATH="/home/helder/.local/bin:$PATH"

## All that sweet sweet fzf
[ -f ~/.fzf.bash ] && source ~/.fzf.bash

bind -x '"\C-f":tmux-sessionizer'
