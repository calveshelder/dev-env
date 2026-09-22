" VIMINIT is shared with Vim. Keep conventional Unix Vim configuration loading
" when a real Vim is launched from the Neon shell; never ask Vim to execute Lua.
" Startup precedence: https://vimhelp.org/starting.txt.html#VIMINIT
let s:xdg = empty($XDG_CONFIG_HOME) ? expand('~/.config') : $XDG_CONFIG_HOME
let s:candidates = [expand('~/.vimrc'), expand('~/.vim/vimrc'), s:xdg . '/vim/vimrc', expand('~/_vimrc')]
let s:loaded = 0
for s:file in s:candidates
  if filereadable(s:file)
    let $MYVIMRC = s:file
    if s:file ==# s:xdg . '/vim/vimrc'
      let $MYVIMDIR = s:xdg . '/vim'
      let &runtimepath = escape($MYVIMDIR, ',') . ',' . &runtimepath . ',' . escape($MYVIMDIR . '/after', ',')
      let &packpath = escape($MYVIMDIR, ',') . ',' . &packpath . ',' . escape($MYVIMDIR . '/after', ',')
    endif
    execute 'source ' . fnameescape(s:file)
    let s:loaded = 1
    break
  endif
endfor
if !s:loaded
  if !empty($EXINIT)
    execute $EXINIT
  elseif filereadable(expand('~/.exrc'))
    execute 'source ' . fnameescape(expand('~/.exrc'))
  elseif filereadable($VIMRUNTIME . '/defaults.vim') && !exists('g:skip_defaults_vim')
    execute 'source ' . fnameescape($VIMRUNTIME . '/defaults.vim')
  endif
endif
unlet s:xdg s:candidates s:loaded s:file
