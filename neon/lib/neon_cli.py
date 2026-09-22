"""Neon command deck. Explicit commands, portable paths, no automatic sync."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(argv, **kwargs):
    try:
        return subprocess.run(argv, **kwargs).returncode
    except FileNotFoundError:
        print(f'Missing command: {argv[0]}. Run neon deps for installation guidance.', file=sys.stderr)
        return 127


def project_root(start=None):
    current = Path(start or Path.cwd()).resolve()
    result = subprocess.run(['git', '-C', str(current), 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True) if shutil.which('git') else None
    git_root = Path(result.stdout.strip()) if result and result.returncode == 0 else None
    for candidate in (current, *current.parents):
        if any((candidate / marker).is_file() for marker in ('go.mod', 'pyproject.toml', 'package.json', 'composer.json')):
            return candidate
        if candidate == git_root:
            break
    return git_root or current


def test_options(root):
    options = []
    if (root / 'go.mod').is_file():
        options.append(('Go: go test ./...', ['go', 'test', './...']))
    if any((root / marker).is_file() for marker in ('pyproject.toml', 'pytest.ini', 'setup.cfg')):
        python = str(root / '.venv/bin/python') if (root / '.venv/bin/python').is_file() else 'python3'
        options.append(('Python: pytest', [python, '-m', 'pytest']))
    if (root / 'package.json').is_file():
        options.append(('Node: npm test (runs this project’s test script)', ['npm', 'test']))
    if (root / 'vendor/bin/phpunit').is_file():
        options.append(('PHP: project PHPUnit', [str(root / 'vendor/bin/phpunit')]))
    return options


def tests(args):
    root = project_root()
    custom = args.command
    if custom and custom[0] == '--':
        custom = custom[1:]
    if custom:
        argv = custom
    else:
        choices = test_options(root)
        if not choices:
            print('No supported test preset here. Example: neon test -- go test ./...')
            return 2
        if not sys.stdin.isatty():
            print('Select an explicit command in noninteractive use: neon test -- COMMAND ARGS', file=sys.stderr)
            return 2
        print(f'Test root: {root}')
        for number, (label, _) in enumerate(choices, 1):
            print(f'  {number}. {label}')
        try:
            answer = input('Choose a check (Enter cancels): ').strip()
            if not answer:
                return 0
            choice = int(answer) - 1
            if not 0 <= choice < len(choices):
                raise ValueError
            argv = choices[choice][1]
        except (ValueError, EOFError):
            print('No check selected.', file=sys.stderr)
            return 2
    print(f'CHECK / {root}\n{shlex.join(argv)}', flush=True)
    return run(argv, cwd=root)


def edit(path):
    editor = shlex.split(os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'nvim')
    return run([*editor, str(path)])


def editor(arguments):
    """Explicit entry for shells that do not load the shared Bash environment."""
    if arguments and arguments[0] == '--':
        arguments = arguments[1:]
    env = dict(os.environ, NEON_ROOT=str(ROOT))
    if not env.get('NEON_PROFILE'):
        try:
            profile = json.loads((Path.home() / '.config/neon/machine.json').read_text()).get('profile')
            if profile in ('work', 'personal'):
                env['NEON_PROFILE'] = profile
        except (OSError, ValueError, AttributeError):
            pass
    explicit_init = any(arg == '-u' or arg.startswith('-u') or arg == '--clean'
                        for arg in arguments)
    prefix = [] if explicit_init else ['-u', str(ROOT / 'nvim/init.lua')]
    return run(['nvim', *prefix, *arguments], env=env)


def selected_shell():
    name = os.environ.get('NEON_SHELL') or Path(os.environ.get('SHELL', '')).name
    return name if name in ('zsh', 'bash') else ('zsh' if sys.platform == 'darwin' else 'bash')


def doctor():
    shell = selected_shell()
    required = (shell, 'git', 'python3', 'nvim', 'tmux', 'fzf', 'rg')
    optional = ('fd', 'starship', 'atuin', 'zoxide', 'eza', 'bat', 'go', 'node', 'uv', 'php')
    failures = 0
    print('NEON / SYSTEM CHECK')
    print(f'Platform: {platform.system()} {platform.machine()}')
    for name in (*required, *optional):
        found = shutil.which(name)
        print(f'{"OK" if found else "MISSING":7} {name:10} {found or ("required" if name in required else "optional")}')
        if not found and name in required:
            failures += 1
    for name, minimum in ((shell, (5, 8) if shell == 'zsh' else (4, 4)), ('nvim', (0, 12, 0))):
        if not shutil.which(name):
            continue
        result = subprocess.run([name, '--version'], capture_output=True, text=True, timeout=5)
        match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', result.stdout)
        if match:
            actual = tuple(int(part or 0) for part in match.groups())
            if actual < minimum:
                print(f'UPDATE  {name}: need {".".join(map(str, minimum))} or later.')
                failures += 1
    sound = shutil.which('afplay') if sys.platform == 'darwin' else shutil.which('paplay')
    print(f'Audio: {sound or "optional backend missing; HUD and editor still work"}')
    link = Path.home() / '.config/neon/root'
    print(f'Config link: {link} -> {link.resolve() if link.exists() else "not installed"}')
    print('Next: :NeonHealth inside Neovim; arena soundtest in your interactive shell.')
    return 1 if failures else 0


def deps(target, all_packages=False):
    osrelease = Path('/etc/os-release')
    current = 'macos' if sys.platform == 'darwin' else (
        'arch' if osrelease.exists() and re.search(r'^ID=arch$', osrelease.read_text(), re.M) else 'debian')
    target = current if target == 'auto' else target
    inspect = target == current and not all_packages
    shell = selected_shell() if target == current else ('zsh' if target == 'macos' else 'bash')
    print('Dependency suggestions — printed only; no installation or upgrade is performed.\n')
    if target == 'arch':
        print(f'sudo pacman -Syu --needed {shell} neovim tmux git python fzf ripgrep fd starship atuin zoxide eza bat jq unzip libpulse wl-clipboard gcc make tree-sitter-cli')
        print('\nOptional learning tools: sudo pacman -S --needed go uv')
    elif target == 'macos':
        formulas = {'neovim': 'nvim', 'tmux': 'tmux', 'git': 'git', 'python': 'python3',
                    'fzf': 'fzf', 'ripgrep': 'rg', 'fd': 'fd', 'starship': 'starship',
                    'atuin': 'atuin', 'zoxide': 'zoxide', 'eza': 'eza', 'bat': 'bat',
                    'jq': 'jq', 'tree-sitter-cli': 'tree-sitter'}
        if shell == 'bash':
            formulas['bash'] = 'bash'
        installed = set()
        if inspect and shutil.which('brew'):
            try:
                result = subprocess.run(['brew', 'list', '--formula', '-1'],
                                        capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    installed = {name.split('@', 1)[0] for name in result.stdout.splitlines()}
            except (OSError, subprocess.SubprocessError):
                pass
        missing = [formula for formula, command in formulas.items()
                   if not inspect or (formula not in installed and not shutil.which(command))]
        if missing:
            print('brew install ' + ' '.join(missing))
        else:
            print('All suggested tools are already installed or available on PATH. No brew install needed.')
        if inspect:
            print('\nInstalled formulae and available commands were omitted. Run neon doctor to check versions.')
        if shell == 'bash':
            print('Bash mode needs Homebrew Bash 4.4+; macOS system Bash is older. Use brew install bash if needed.')
        print('Zsh mode uses your existing zsh; no shell replacement is required.')
        print('Only if compiler tools are missing: xcode-select --install. No manual Neovim downloads are required.')
    else:
        print('sudo apt update')
        print(f'sudo apt install {shell} git python3 tmux fzf ripgrep fd-find bat jq unzip pulseaudio-utils build-essential')
        print('\nInstall Neovim >=0.12 and tree-sitter-cli, plus optional Starship/Atuin/zoxide from official instructions;')
        print('older distribution repositories may not provide compatible versions. See docs/PLATFORMS.md.')
    print('\nExisting NVM, Lando, Docker and project dependency versions are preserved. No global PHP standard is imposed.')
    print('Your current Kickstart fork uses vim.pack and needs Neovim 0.12+. Check with: nvim --version')
    return 0


def sync(pull):
    status = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if status.returncode or Path(status.stdout.strip()).resolve() != ROOT.parent:
        print('Keep neon/ inside your dev-env Git checkout. See neon/docs/SYNC.md.')
        return 2
    if not pull:
        return run(['git', '-C', str(ROOT), 'status', '--short', '--branch'])
    dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--ignore-submodules=none'], capture_output=True, text=True, check=True)
    if dirty.stdout:
        print('Commit or stash your configuration edits before pulling. No changes made.', file=sys.stderr)
        return 1
    code = run(['git', '-C', str(ROOT), 'pull', '--ff-only', '--recurse-submodules=no'])
    if code == 0:
        print('Next, from your dev-env root: git submodule update --init --recursive')
        print('This checks out the recorded Kickstart commit; review any local editor edits first.')
    return code


def menu():
    choices = {
        'Projects / jump into a workspace': ['projects'],
        'Editor / Kickstart with Neon controls': ['editor'],
        'Check / run a project test': ['test'],
        'Scratch / capture a thought': ['scratch'],
        'Guide / know your environment': ['docs'],
        'Doctor / diagnose missing pieces': ['doctor'],
        'Config / open shared settings': ['config'],
    }
    if not shutil.which('fzf'):
        print('Install fzf for the interactive deck. Try neon --help meanwhile.')
        return 2
    result = subprocess.run(['fzf', '--prompt=NEON / ', '--height=40%', '--layout=reverse', '--border=rounded'],
                            input='\n'.join(choices), capture_output=True, text=True)
    if result.returncode in (1, 130):
        return 0
    if result.returncode:
        return result.returncode
    command = choices.get(result.stdout.strip())
    return main(command) if command else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description='Neon Dev / portable command deck')
    commands = parser.add_subparsers(dest='action')
    commands.add_parser('menu', help='interactive command deck (also the default)')
    commands.add_parser('doctor', help='check installed tools without modifying them')
    dependency = commands.add_parser('deps', help='print platform dependency commands')
    dependency.add_argument('--platform', choices=('auto', 'arch', 'macos', 'debian'), default='auto')
    dependency.add_argument('--all', action='store_true', help='show the complete package set for a fresh machine')
    docs = commands.add_parser('docs', help='read the reference guide')
    docs.add_argument('chapter', nargs='?', choices=('readme', 'neovim', 'terminal', 'installer', 'platforms', 'sync', 'changes'), default='readme')
    commands.add_parser('config', help='edit the shared configuration root')
    nvim = commands.add_parser('editor', help='launch Kickstart plus Neon from any shell')
    nvim.add_argument('arguments', nargs=argparse.REMAINDER)
    commands.add_parser('scratch', help='open a local-only scratchpad')
    projects = commands.add_parser('projects', help='project picker / tmux sessionizer')
    projects.add_argument('path', nargs='?')
    test = commands.add_parser('test', help='choose a check or pass explicit argv after --')
    test.add_argument('command', nargs=argparse.REMAINDER)
    synchronization = commands.add_parser('sync', help='show config Git status; optional explicit pull')
    synchronization.add_argument('--pull', action='store_true')
    args = parser.parse_args(argv)
    if args.action in (None, 'menu'):
        return menu()
    if args.action == 'doctor':
        return doctor()
    if args.action == 'deps':
        return deps(args.platform, args.all)
    if args.action == 'docs':
        path = ROOT / ('README.md' if args.chapter == 'readme' else f'docs/{args.chapter.upper()}.md')
        return edit(path)
    if args.action == 'config':
        return edit(ROOT)
    if args.action == 'editor':
        return editor(args.arguments)
    if args.action == 'scratch':
        path = Path.home() / '.local/state/neon/notes/inbox.md'
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            path.touch(mode=0o600)
        return edit(path)
    if args.action == 'projects':
        return run([str(ROOT / 'bin/tmux-sessionizer'), *([args.path] if args.path else [])])
    if args.action == 'test':
        return tests(args)
    if args.action == 'sync':
        return sync(args.pull)
    return 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Neon: {error}', file=sys.stderr)
        raise SystemExit(1)
