#!/usr/bin/env python3
"""Preview, install and restore Neon dotfiles without third-party dependencies."""
from __future__ import annotations

import argparse
import configparser
from contextlib import contextmanager
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid

BEGIN = "# >>> neon-dev managed >>>"
END = "# <<< neon-dev managed <<<"
COMPONENTS = {"shell", "nvim", "tmux", "starship", "arena", "ghostty", "atuin"}
DEFAULT_COMPONENTS = "shell,nvim,tmux,starship,arena"
BACKUP_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z")


class InstallError(RuntimeError):
    pass


def present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def fingerprint(path: Path) -> dict | None:
    """Never traverse a symlink or hash an unrelated existing directory tree."""
    if path.is_symlink():
        return {"type": "symlink", "target": os.readlink(path)}
    if not path.exists():
        return None
    mode = path.stat().st_mode
    if stat.S_ISREG(mode):
        return {"type": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "mode": stat.S_IMODE(mode)}
    if stat.S_ISDIR(mode):
        return {"type": "directory"}
    raise InstallError(f"Refusing to manage special file: {path}")


def atomic_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".neon-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def write_json(path: Path, value: dict) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


@dataclasses.dataclass
class Change:
    relative: str
    kind: str
    source: str | None = None
    data: bytes | None = None
    mode: int = 0o600
    reason: str = ""
    observed: dict | None = None

    def desired(self) -> dict:
        if self.kind == "symlink":
            return {"type": "symlink", "target": self.source}
        return {"type": "file", "sha256": hashlib.sha256(self.data).hexdigest(), "mode": self.mode}


class Installer:
    def __init__(self, repo: Path, home: Path):
        self.repo = repo.resolve()
        self.checkout = self.repo.parent
        self.home = Path(os.path.abspath(home.expanduser()))
        if self.home.is_symlink() or not self.home.is_dir():
            raise InstallError(f"Home must be an existing, real directory: {self.home}")
        self.backups = self.home / ".local/state/neon/backups"
        self.notices: list[str] = []

    def target(self, relative: str) -> Path:
        part = Path(relative)
        if part.is_absolute() or not part.parts or any(x in ("..", ".") for x in part.parts):
            raise InstallError(f"Invalid managed relative path: {relative!r}")
        return self.home / part

    def check_ancestors(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.home)
        except ValueError as exc:
            raise InstallError(f"Target is outside the selected home: {path}") from exc
        current = self.home
        for item in relative.parts[:-1]:
            current /= item
            if current.is_symlink():
                raise InstallError(f"Refusing to write through symlink directory: {current}")
            if current.exists() and not current.is_dir():
                raise InstallError(f"Expected a directory: {current}")

    def mkdirs(self, parent: Path, created: list[str]) -> None:
        self.check_ancestors(parent / "__neon_check__")
        missing = []
        cursor = parent
        while not cursor.exists():
            missing.append(cursor)
            cursor = cursor.parent
        for item in reversed(missing):
            item.mkdir(mode=0o700)
            created.append(str(item.relative_to(self.home)))

    @contextmanager
    def lock(self):
        """Serialise mutations in one home; previews do not create a lock."""
        self.mkdirs(self.backups, [])
        path = self.backups / ".installer.lock"
        self.check_ancestors(path)
        if path.is_symlink():
            raise InstallError(f"Refusing a symlinked installer lock: {path}")
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise InstallError("Another Neon install or restore is using this home; let it finish first") from exc
            yield
        finally:
            os.close(fd)

    def editable(self, relative: str) -> tuple[bytes, int]:
        path = self.target(relative)
        self.check_ancestors(path)
        if path.is_symlink():
            raise InstallError(f"{path} is already managed by a symlink; edit its source or exclude shell.")
        if not path.exists():
            return b"", 0o600
        if not path.is_file():
            raise InstallError(f"Expected a regular configuration file: {path}")
        return path.read_bytes(), stat.S_IMODE(path.stat().st_mode)

    def startup(self, relative: str, source: str, mode: str) -> Change:
        path = self.target(relative)
        self.check_ancestors(path)
        if path.is_symlink():
            # Legacy dotfiles often symlink Bash startup into env/. Replacing the
            # link itself preserves that tracked source and makes rollback exact.
            if mode == "clean":
                raw, file_mode = b"", 0o600
            elif path.is_file():
                raw, file_mode = path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            else:
                raise InstallError(f"Cannot merge unreadable startup symlink {path}; repair it or use --shell-mode clean")
            self.notices.append(f"Back up startup symlink {relative}; its source is left unchanged")
        else:
            raw, file_mode = self.editable(relative)
        old = raw.decode("utf-8", errors="surrogateescape")
        block = (f'{BEGIN}\n'
                 f'if [ -r "$HOME/.config/neon/root/shell/{source}" ]; then\n'
                 f'    . "$HOME/.config/neon/root/shell/{source}"\n'
                 f'fi\n{END}')
        if mode == "clean":
            local_file = "local.zsh" if source.endswith(".zsh") else "local.bash"
            text = ("# Neon manages this startup file. Put your own exports and aliases in\n"
                    f"# ~/.config/neon/{local_file}. The installer keeps the previous file in its backup.\n"
                    + block + "\n")
        else:
            if old.count(BEGIN) != old.count(END) or old.count(BEGIN) > 1:
                raise InstallError(f"Malformed or duplicate Neon markers in {relative}; resolve them before applying.")
            if BEGIN in old:
                start, end = old.index(BEGIN), old.index(END) + len(END)
                if start > end:
                    raise InstallError(f"Reversed Neon markers in {relative}")
                text = old[:start] + block + old[end:]
            else:
                text = old + ("" if not old or old.endswith("\n") else "\n") + "\n" + block + "\n"
            # Recognise only a whole standalone source command, optionally guarded.
            # Do not comment compound commands, evals, custom functions or exports.
            for suffix in (".config/dev-shell/init.bash", ".local/share/shell-arena/arena.bash"):
                alternatives = [re.escape('"$HOME/' + suffix + '"'),
                                re.escape('"${HOME}/' + suffix + '"'),
                                re.escape("~/" + suffix),
                                re.escape('"' + str(self.home / suffix) + '"'),
                                re.escape(str(self.home / suffix))]
                token = "(?:" + "|".join(alternatives) + ")"
                guard = r"(?:(?:\[\[\s+-[fr]\s+" + token + r"\s+\]\]|\[\s+-[fr]\s+" + token + r"\s+\])\s*&&\s*)?"
                pattern = re.compile(r"^[ \t]*" + guard + r"(?:source|\.)\s+" + token + r"[ \t]*(?:#[^\n]*)?$", re.MULTILINE)
                text = pattern.sub(lambda match: "# Migrated to neon-dev: " + match.group(0).lstrip(), text)
        return Change(relative, "file", data=text.encode("utf-8", errors="surrogateescape"),
                      mode=file_mode, reason=f"{mode} {'zsh' if source.endswith('.zsh') else 'Bash'} startup")

    def zsh_startup_path(self) -> str:
        """Honor a home-local ZDOTDIR without writing outside the chosen home."""
        raw = os.environ.get("ZDOTDIR")
        if raw is None:
            return ".zshrc"
        if raw == "~":
            directory = self.home
        elif raw.startswith("~/"):
            directory = self.home / raw[2:]
        else:
            directory = Path(raw)
        if not directory.is_absolute() or ".." in directory.parts:
            raise InstallError("ZDOTDIR must be an absolute directory inside the selected home; "
                               "use a home-local ZDOTDIR or install without the shell component")
        try:
            relative = directory.relative_to(self.home) / ".zshrc"
        except ValueError as exc:
            raise InstallError("ZDOTDIR is outside the selected home; use a home-local ZDOTDIR or "
                               "install without the shell component and source neon/shell/init.zsh yourself") from exc
        return str(relative)

    def kickstart_source(self) -> Path:
        """Require the existing submodule without editing or fetching its files."""
        manifest = self.checkout / ".gitmodules"
        config = configparser.ConfigParser(interpolation=None, strict=True)
        try:
            with manifest.open(encoding="utf-8") as stream:
                config.read_file(stream)
        except (OSError, UnicodeError, configparser.Error) as exc:
            raise InstallError(f"Cannot read the parent repository's .gitmodules: {manifest}. "
                               "Place neon/ inside your dev-env checkout, or omit the nvim component.") from exc
        matches = [section for section in config.sections()
                   if section.startswith('submodule "')
                   and config.get(section, "path", fallback="").strip() == ".config/nvim"
                   and config.get(section, "url", fallback="").strip()]
        if len(matches) != 1:
            raise InstallError("Expected one .gitmodules entry with path = .config/nvim and a repository URL; "
                               "retain your existing Kickstart submodule, or omit the nvim component")
        source = self.checkout / ".config/nvim"
        if not (source / "init.lua").is_file():
            raise InstallError("Kickstart submodule is not initialized (.config/nvim/init.lua is missing). "
                               "From the dev-env root run: git submodule update --init --recursive. "
                               "Alternatively install --components shell,tmux,starship,arena for now.")
        return source.resolve()

    def plan(self, profile: str, components: set[str], shell_mode: str = "merge", shell: str = "bash") -> list[Change]:
        if (profile not in ("personal", "work") or components - COMPONENTS
                or shell_mode not in ("merge", "clean") or shell not in ("auto", "bash", "zsh", "both")):
            raise InstallError("Invalid profile, components, shell mode or shell")
        if shell == "auto":
            shell = "zsh" if Path(os.environ.get("SHELL", "")).name == "zsh" else "bash"
        self.notices = []
        changes = []
        protected_sources = [self.repo]
        if "nvim" in components:
            protected_sources.append(self.kickstart_source())

        def link(relative: str, source: str, preserve: bool = False):
            target = self.target(relative)
            self.check_ancestors(target)
            if preserve and present(target):
                self.notices.append(f"Preserve existing {relative}")
                return
            origin = (self.repo / source).resolve()
            if not origin.exists():
                raise InstallError(f"Package is incomplete; missing {origin}")
            resolved_target = target.resolve()
            if (not target.is_symlink()
                    and any(resolved_target == origin_path or resolved_target in origin_path.parents
                            for origin_path in protected_sources)):
                raise InstallError(f"Installing {target} would move the repository or its Kickstart submodule; "
                                   "keep dev-env outside the managed destination")
            changes.append(Change(relative, "symlink", source=str(origin), reason=f"link {source}"))

        link(".config/neon/root", ".")
        link(".local/bin/neon", "bin/neon")
        raw, machine_mode = self.editable(".config/neon/machine.json")
        try:
            machine = json.loads(raw) if raw else {}
        except (ValueError, UnicodeDecodeError) as exc:
            raise InstallError("machine.json is invalid JSON; repair it before applying") from exc
        if not isinstance(machine, dict):
            raise InstallError("machine.json must contain a JSON object")
        machine.update(schema=1, profile=profile)
        changes.append(Change(".config/neon/machine.json", "file",
                              data=(json.dumps(machine, indent=2, sort_keys=True) + "\n").encode(), mode=machine_mode,
                              reason="machine profile (existing extra keys retained)"))
        _, profile_mode = self.editable(".config/neon/machine.bash")
        changes.append(Change(".config/neon/machine.bash", "file",
                              data=("# Generated by neon/install.py; change profile through the installer.\n"
                                    f"export NEON_PROFILE='{profile}'\n").encode(), mode=profile_mode,
                              reason="fast shell profile selection"))
        if "shell" in components:
            startup_files = []
            if shell in ("bash", "both"):
                startup_files.extend(((".bashrc", "init.bash"), (".bash_profile", "profile.bash")))
            if shell in ("zsh", "both"):
                startup_files.append((self.zsh_startup_path(), "init.zsh"))
            for path, source in startup_files:
                if not (self.repo / "shell" / source).is_file():
                    raise InstallError(f"Package is incomplete; missing shell/{source}")
                changes.append(self.startup(path, source, shell_mode))
        if components & {"shell", "tmux"}:
            link(".local/bin/neon-copy", "bin/neon-copy")
        for component, target, source in (
            ("nvim", ".config/nvim", "../.config/nvim"),
            ("tmux", ".config/tmux/tmux.conf", "config/tmux/tmux.conf"),
            ("tmux", ".tmux.conf", "config/tmux/tmux.conf"),
            ("tmux", ".local/bin/tmux-sessionizer", "bin/tmux-sessionizer"),
            ("starship", ".config/starship.toml", "config/starship.toml"),
            ("arena", ".local/share/shell-arena", "vendor/shell-arena"),
            ("ghostty", ".config/ghostty/config", "config/ghostty/config"),
        ):
            if component in components:
                link(target, source)
        if components & {"shell", "atuin"}:
            link(".config/atuin/config.toml", "config/atuin/config.toml", preserve=True)
        result = []
        for change in changes:
            path = self.target(change.relative)
            self.check_ancestors(path)
            change.observed = fingerprint(path)
            if change.observed != change.desired():
                result.append(change)
        return result

    def show_plan(self, changes: list[Change]) -> None:
        for notice in self.notices:
            label = "KEEP" if notice.startswith("Preserve ") else "NOTE"
            print(f"{label:8} {notice}")
        for change in changes:
            action = "REPLACE" if present(self.target(change.relative)) else "CREATE"
            print(f"{action:8} ~/{change.relative} — {change.reason}")
        if not changes:
            print("Already installed; nothing to change.")
        else:
            print(f"{len(changes)} changes. Replacements will be moved into a recoverable backup.")

    def install_change(self, change: Change, path: Path) -> None:
        """Small method intentionally isolated for failure-injection tests."""
        if change.kind == "symlink":
            path.symlink_to(change.source)
        else:
            atomic_bytes(path, change.data, change.mode)

    def apply(self, changes: list[Change], profile: str) -> str | None:
        if not changes:
            return None
        with self.lock():
            return self._apply(changes, profile)

    def _apply(self, changes: list[Change], profile: str) -> str:
        for change in changes:
            path = self.target(change.relative)
            self.check_ancestors(path)
            if fingerprint(path) != change.observed:
                raise InstallError(f"{path} changed after planning; rerun plan/apply to preserve the latest contents")
        self.check_ancestors(self.backups / "__neon_check__")
        created: list[str] = []
        self.mkdirs(self.backups, created)
        identifier = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        backup = self.backups / identifier
        backup.mkdir(mode=0o700)
        (backup / "files").mkdir(mode=0o700)
        manifest = {"schema": 1, "id": identifier, "status": "applying", "profile": profile,
                    "home": str(self.home), "repo": str(self.repo), "entries": [], "created_dirs": []}
        manifest_path = backup / "manifest.json"
        write_json(manifest_path, manifest)
        try:
            for index, change in enumerate(changes):
                path = self.target(change.relative)
                self.check_ancestors(path)
                self.mkdirs(path.parent, manifest["created_dirs"])
                original = fingerprint(path)
                entry = {"path": change.relative, "original": original,
                         "backup": f"files/{index:04d}", "installed": change.desired(), "stage": "prepared"}
                manifest["entries"].append(entry)
                write_json(manifest_path, manifest)
                if original is not None:
                    os.replace(path, backup / entry["backup"])
                entry["stage"] = "original_moved"
                write_json(manifest_path, manifest)
                self.install_change(change, path)
                entry["stage"] = "installed"
                write_json(manifest_path, manifest)
            manifest["status"] = "applied"
            write_json(manifest_path, manifest)
            return identifier
        except BaseException as exc:
            issues = self._rollback(backup, manifest)
            manifest["status"] = "rollback_conflict" if issues else "failed_rolled_back"
            manifest["error"] = str(exc)
            manifest["rollback_issues"] = issues
            write_json(manifest_path, manifest)
            detail = f" Rollback needs attention: {'; '.join(issues)}" if issues else " Original files restored."
            raise InstallError(f"Installation failed: {exc}.{detail} Backup: {identifier}") from exc

    def _rollback(self, backup: Path, manifest: dict) -> list[str]:
        issues = []
        for entry in reversed(manifest["entries"]):
            try:
                path = self.target(entry["path"])
                self.check_ancestors(path)
                saved = backup / entry["backup"]
                current = fingerprint(path)
                if present(saved):
                    if current is not None and current != entry["installed"]:
                        raise InstallError("changed unexpectedly; original retained in backup")
                    if current is not None:
                        path.unlink()
                    os.replace(saved, path)
                elif entry["original"] is None and current is not None:
                    if current != entry["installed"]:
                        raise InstallError("changed unexpectedly; retained for inspection")
                    path.unlink()
            except (OSError, InstallError) as exc:
                issues.append(f"{entry['path']}: {exc}")
        for relative in reversed(manifest["created_dirs"]):
            try:
                self.target(relative).rmdir()
            except OSError:
                pass
        return issues

    def load_manifest(self, identifier: str) -> tuple[Path, dict]:
        if not BACKUP_ID.fullmatch(identifier):
            raise InstallError("Invalid backup ID; use list-backups to find one")
        backup = self.backups / identifier
        path = backup / "manifest.json"
        self.check_ancestors(path)
        if path.is_symlink():
            raise InstallError("Refusing a symlinked backup manifest")
        try:
            manifest = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise InstallError(f"Cannot read backup {identifier}: {exc}") from exc
        if manifest.get("schema") != 1 or manifest.get("home") != str(self.home) or manifest.get("id") != identifier:
            raise InstallError("Backup belongs to a different home or unsupported schema")
        for index, entry in enumerate(manifest.get("entries", [])):
            self.target(entry["path"])
            if entry["backup"] != f"files/{index:04d}":
                raise InstallError("Invalid file path in backup manifest")
            self.check_ancestors(backup / entry["backup"])
        return backup, manifest

    def restore(self, identifier: str) -> None:
        self.load_manifest(identifier)
        with self.lock():
            self._restore(identifier)

    def _restore(self, identifier: str) -> None:
        backup, manifest = self.load_manifest(identifier)
        if manifest["status"] == "restored":
            print("This backup has already been restored.")
            return
        if manifest["status"] != "applied":
            raise InstallError(f"Backup status is {manifest['status']}; inspect its manifest before manual recovery")
        conflicts = []
        for entry in manifest["entries"]:
            path = self.target(entry["path"])
            self.check_ancestors(path)
            if fingerprint(path) != entry["installed"]:
                conflicts.append(entry["path"])
            if entry["original"] is not None and not present(backup / entry["backup"]):
                raise InstallError(f"Missing original in backup: {entry['path']}")
        if conflicts:
            raise InstallError("Restore refused before changing anything: installed paths were changed: "
                               + ", ".join(conflicts)
                               + ". Save your edits elsewhere, then restore the installed path to its recorded state.")
        # Keep both originals and the displaced installed files recoverable if restoration fails.
        displaced = backup / "restored-installation"
        if present(displaced):
            raise InstallError("An earlier restore attempt needs inspection; restored-installation already exists")
        displaced.mkdir(mode=0o700)
        done = []
        try:
            manifest["status"] = "restoring"
            write_json(backup / "manifest.json", manifest)
            for index, entry in reversed(list(enumerate(manifest["entries"]))):
                path = self.target(entry["path"])
                self.check_ancestors(path)
                retired = displaced / f"{index:04d}"
                os.replace(path, retired)
                item = (entry, retired, False)
                done.append(item)
                if entry["original"] is not None:
                    os.replace(backup / entry["backup"], path)
                    done[-1] = (entry, retired, True)
            manifest["status"] = "restored"
            write_json(backup / "manifest.json", manifest)
        except BaseException as exc:
            problems = []
            for entry, retired, original_restored in reversed(done):
                try:
                    path = self.target(entry["path"])
                    if original_restored:
                        os.replace(path, backup / entry["backup"])
                    os.replace(retired, path)
                except OSError as issue:
                    problems.append(str(issue))
            manifest["status"] = "restore_conflict" if problems else "applied"
            manifest["restore_error"] = str(exc)
            write_json(backup / "manifest.json", manifest)
            if not problems:
                displaced.rmdir()
            raise InstallError(f"Restore failed: {exc}. Recovery details: {backup / 'manifest.json'}") from exc
        for relative in reversed(manifest["created_dirs"]):
            try:
                self.target(relative).rmdir()
            except OSError:
                pass

    def list_backups(self) -> None:
        self.check_ancestors(self.backups / "__neon_check__")
        if not self.backups.exists():
            print("No Neon backups yet.")
            return
        for child in sorted(self.backups.iterdir(), reverse=True):
            if BACKUP_ID.fullmatch(child.name):
                try:
                    _, manifest = self.load_manifest(child.name)
                    print(f"{child.name}  {manifest['status']:20} {manifest['profile']}")
                except InstallError as exc:
                    print(f"{child.name}  unreadable: {exc}")


def parse_components(raw: str) -> set[str]:
    values = {item.strip() for item in raw.split(",") if item.strip()}
    if not values or values - COMPONENTS:
        raise argparse.ArgumentTypeError("Components: " + ",".join(sorted(COMPONENTS)))
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        child = commands.add_parser(name)
        child.add_argument("--profile", required=True, choices=("personal", "work"))
        child.add_argument("--components", type=parse_components, default=parse_components(DEFAULT_COMPONENTS))
        child.add_argument("--shell-mode", choices=("merge", "clean"), default="merge",
                           help="merge preserves existing startup; clean installs minimal backed-up startup files")
        child.add_argument("--shell", choices=("auto", "zsh", "bash", "both"), default="auto",
                           help="startup files to manage; auto selects zsh when SHELL names zsh, otherwise Bash")
        child.add_argument("--home", type=Path, default=Path.home(), help="target an existing home without changing HOME")
    restore = commands.add_parser("restore")
    restore.add_argument("backup_id")
    restore.add_argument("--home", type=Path, default=Path.home())
    backups = commands.add_parser("list-backups")
    backups.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args(argv)
    try:
        installer = Installer(Path(__file__).parent, args.home)
        if args.command in ("plan", "apply"):
            changes = installer.plan(args.profile, args.components, args.shell_mode, args.shell)
            installer.show_plan(changes)
            if args.command == "apply":
                identifier = installer.apply(changes, args.profile)
                if identifier:
                    print(f"Installed. Backup: {identifier}\nOpen a new terminal to use the configuration.")
            else:
                print("Preview only. No files were written. Run apply with the same options when ready.")
        elif args.command == "restore":
            installer.restore(args.backup_id)
            print("Restore complete. Open a new terminal.")
        else:
            installer.list_backups()
        return 0
    except (InstallError, OSError) as exc:
        print(f"neon installer: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
