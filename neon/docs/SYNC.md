# Commit once, install on each computer

All commands in this guide run from your **dev-env repository root** unless a
different directory is shown. Your existing branch and history remain intact.
The integration does not contain a replacement Git repository or Git bundle.

## Commit this integration

After applying the drop-in files, inspecting the preview, and trying the setup:

```bash
git status --short
git diff -- .gitmodules
git diff --submodule=short -- .config/nvim
git add -- README-NEON.md neon-install.py neon/
git diff --cached --stat
git diff --cached --check
git diff --cached -- .gitmodules .config/nvim
git commit --only README-NEON.md neon-install.py neon/ -m "Integrate Neon shell and Kickstart overlay"
```

The two submodule-related diffs should be empty unless you already had editor
changes before this integration. Review such changes separately. The explicit
commit paths avoid committing unrelated work that was already staged; do not
use `git add .` to scoop up other files. Check `git diff --cached` to inspect
the full new code before committing if you want more than the summary.

Push the branch you actually use, for example if you are on `develop`:

```bash
git push -u origin develop
```

If your branch has a different name, substitute that name. Nothing in the ZIP
pushes, merges a branch, stages files or changes a remote for you.

## Fresh MacBook or Arch/WSL machine

Install Git and Python 3.10+ first (on macOS use Homebrew Python; on Arch the
`git` and `python` packages). Once the integration is pushed to `develop`:

```bash
mkdir -p "$HOME/code"
git clone --branch develop https://github.com/calveshelder/dev-env.git "$HOME/code/dev-env"
cd "$HOME/code/dev-env"
git submodule update --init --recursive
python3 neon/bin/neon deps
```

Your `.gitmodules` uses an SSH URL for Kickstart. If this machine does not yet
have GitHub SSH access, use this **clone-local override** before initializing:

```bash
git config submodule..config/nvim.url https://github.com/calveshelder/kickstart.nvim.git
git submodule update --init --recursive
```

It changes only this clone's `.git/config`; tracked `.gitmodules` stays intact.
The public HTTPS URL is enough to read the fork; pushing changes to it still
requires your GitHub authentication. A later `git submodule sync` would reset
that override from `.gitmodules`, so reapply it if you use sync.

Run the printed platform dependency commands. Then:

```bash
python3 neon-install.py plan --profile personal --shell zsh --shell-mode merge
python3 neon-install.py apply --profile personal --shell zsh --shell-mode merge
```

Choose `--profile work` for the work computer, and `--shell bash` if you prefer
Bash on Arch. macOS can keep its current zsh and Homebrew tools: see
[PLATFORMS.md](PLATFORMS.md). Open a fresh terminal
and run `neon doctor`, then `neon editor`. Kickstart installs its usual plugins;
Neon's overlay requires no additional plugins. There is no need to run the old
`./dev-env` or `./run` scripts to install Neon.

## Routine sync

Commit your intended shared settings and push from the machine where you edited
them. On the other machine, inspect and save any work first:

```bash
git status --short
git -C .config/nvim status --short
git pull --ff-only --recurse-submodules=no
git submodule update --init --recursive
```

`neon sync` shows parent repository status. `neon sync --pull` refuses a dirty
working tree (including submodule edits) and performs the fast-forward pull;
it then prints the submodule update command for you to run. It never uses
`--remote`, so the editor follows the commit recorded by dev-env instead of
jumping to the newest Kickstart branch head. Review or commit submodule changes
before updating; do not use `--force` to discard them.

Open a new terminal after shell updates, restart Neovim after editor
updates, and use tmux Prefix then `r` after tmux config changes. Run another
installer plan/apply only when installed paths/components/profile need changing.

## When you edit Kickstart itself

Changes in `neon/nvim/` are normal dev-env changes. Changes in `.config/nvim/`
belong to your separate Kickstart repository and require **two commits**:

1. Inside `.config/nvim`, work on a named branch (submodule checkouts are often
   detached), commit your chosen init/plugin files, then push that branch to
   your fork. For example `git switch -c my-editor-update` starts a new branch.
2. Back in dev-env, `git add .config/nvim`, inspect
   `git diff --cached --submodule=log -- .config/nvim`, then commit the pointer
   update and push dev-env. Publish the fork commit first so another machine
   can fetch it.

Your current fork uses native `vim.pack`, with `nvim-pack-lock.json` in the
config directory. Its `.gitignore` currently excludes that lockfile. Plugin
updates are therefore not fully reproducible on a new computer until you
deliberately track it in the fork with `git add -f nvim-pack-lock.json`, then
commit/push the fork and the updated parent pointer. Keep the lockfile generated
by your working setup; this ZIP does not invent plugin revisions. An older fork
using lazy.nvim has `lazy-lock.json` instead. The integration never silently
changes your lockfile policy or updates your plugin manager.

See the official [Git submodules guide](https://git-scm.com/docs/gitsubmodules)
for the relationship between the parent repository and its recorded gitlink.
