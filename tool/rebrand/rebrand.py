#!/usr/bin/env python3
"""Idempotent fork rebranding for the Android and Windows apps.

Rewrites upstream identity (name, application ID, link scheme and host,
repository, Windows publisher and installer GUID) into the fork identity from
brand.json. Re-run it after every upstream merge; `--check` reports pending
changes and any brand occurrence that is neither rewritten nor explicitly kept.
Generated code is never edited: regenerate it after applying.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).resolve().with_name("brand.json")

# The rebrand tool itself necessarily names the upstream identity.
EXCLUDED_PREFIXES = ("tool/rebrand", "lib/l10n/localizations")
GENERATED_SUFFIXES = (".g.dart", ".g.kt", ".g.swift")
WALK_SKIPPED_DIRS = {".git", ".dart_tool", ".gradle", "build", "ephemeral"}
KOTLIN_ROOTS = ("android/app/src/main/kotlin", "android/app/src/test/kotlin")

DART = ("lib", "test")
APP = (*DART, "android/app/src", "windows/runner", "windows/CMakeLists.txt",
       "windows/packaging")
MANIFEST = "android/app/src/main/AndroidManifest.xml"
CHECKED = (*APP, "android", "windows", "pigeon/message.dart", "tool", "pubspec.yaml")

BRAND_PATTERN = re.compile(r"(?i)onexray|yuan\s?dev")

# Upstream names that stay unchanged on purpose. See README.md for reasons.
# ASCII word classes keep CJK or Persian text next to the name rewritable.
KEPT_PATTERNS = tuple(re.compile(pattern, re.ASCII) for pattern in (
    r"package:onexray/",
    r"dev\.flutter\.pigeon\.onexray\.",
    r"dartPackageName: 'onexray'",
    r"(?m)^name: onexray\r?$",
    r"(?<![\w\\])[A-Za-z_]\w*OneXray\w*|OneXray\w+",
    r"oneXray\w*",
    r"ONEXRAY_\w+",
    r"\.?onexray-[a-z][\w-]*",
    r"about-onexray",
    r"OneXray-android-universal",
    r"ShareLinkFormat\.onexray\b",
    r"\boriginal, onexray\b",
    r"https://onexray\.com[^\s'\"]*",
    r"_domain = \"onexray\.com\"",
    r"apps\.apple\.com/us/app/onexray",
    r"iCloud\.net\.yuandev\.onexray",
    r"net\.yuandev\.onexray\.desktop",
    r"(?m)^.*\"@?donationDescription\"\s*:.*$",
    r"Yuan Dev LLC\. All rights reserved",
    r"(?m)^  (?:display_name: OneXray|publisher_display_name: Yuan Dev LLC"
    r"|identity_name: YuanDevLLC\.OneXray|protocol_activation: onexray)\r?$",
))


class RebrandError(Exception):
    pass


@dataclass(frozen=True)
class Brand:
    name: str
    application_id: str
    scheme: str
    link_host: str
    github_repository: str
    windows_publisher: str
    windows_app_guid: str

    @property
    def package_path(self) -> str:
        return self.application_id.replace(".", "/")


@dataclass(frozen=True)
class Rule:
    name: str
    scope: tuple[str, ...]
    pattern: re.Pattern[str]
    replacement: str
    skip_line: re.Pattern[str] | None = None

    def apply(self, text: str) -> tuple[str, int]:
        if self.skip_line is None:
            return self.pattern.subn(lambda _: self.replacement, text)
        total = 0
        lines = []
        for line in text.splitlines(keepends=True):
            if not self.skip_line.search(line):
                line, count = self.pattern.subn(lambda _: self.replacement, line)
                total += count
            lines.append(line)
        return "".join(lines), total


@dataclass
class Report:
    moves: list[tuple[str, str]]
    changes: dict[str, dict[str, int]]
    residuals: list[tuple[str, int, str]]

    @property
    def pending(self) -> bool:
        return bool(self.moves or self.changes)


def load_brands(config: Path) -> tuple[Brand, Brand]:
    data = json.loads(config.read_text(encoding="utf-8"))
    return Brand(**data["upstream"]), Brand(**data["fork"])


def build_rules(upstream: Brand, fork: Brand) -> list[Rule]:
    """Returns rules in application order; specific rules precede the name rule."""
    u = upstream
    scheme = re.escape(u.scheme)

    def token(pattern: str, extra: str = "") -> re.Pattern[str]:
        # A token starts after a non-word character or a string escape such as \n.
        start = rf"(?:(?<![\w{extra}])|(?<=\\[nrt]))"
        return re.compile(start + pattern, re.ASCII)

    return [
        Rule("github repository", APP,
             re.compile(rf"(?:(?<=github\.com/)|(?<=/repos/)){re.escape(u.github_repository)}(?![\w-])"),
             fork.github_repository),
        Rule("windows app guid", APP,
             re.compile(re.escape(u.windows_app_guid), re.IGNORECASE), fork.windows_app_guid),
        Rule("installer urls", ("windows/packaging",),
             re.compile(rf"https://{re.escape(u.link_host)}(?![\w./-])"),
             f"https://github.com/{fork.github_repository}"),
        Rule("windows publisher", ("windows/runner", "windows/packaging"),
             re.compile(rf"(?<![\w.]){re.escape(u.windows_publisher)}(?![\w.])"),
             fork.windows_publisher),
        Rule("application id",
             (*APP, "android/app/build.gradle.kts", "android/fastlane", "pigeon/message.dart"),
             re.compile(rf"(?<![\w.]){re.escape(u.application_id)}(?!\w)(?!\.desktop\b)"),
             fork.application_id),
        Rule("kotlin source path", ("test", "tool", "pigeon/message.dart"),
             token(rf"{re.escape(u.package_path)}(?!\w)", "."),
             fork.package_path),
        Rule("link scheme url", APP,
             token(rf"{scheme}://", ".+-"), f"{fork.scheme}://"),
        Rule("link scheme literal", (*DART, MANIFEST),
             re.compile(rf"(?<=['\"]){scheme}(?=['\"])"), fork.scheme),
        Rule("link scheme registry", ("windows/packaging",),
             re.compile(rf"(?<=Classes\\){scheme}(?!\w)"), fork.scheme),
        # Documentation stays on the upstream site: only the App Link host moves.
        Rule("link host", (*DART, MANIFEST),
             re.compile(rf"(?<!https://)(?<!http://)(?<![\w.-]){re.escape(u.link_host)}(?![\w-])"),
             fork.link_host, skip_line=re.compile(r"_domain\s*=")),
        Rule("lowercase executable", DART,
             re.compile(rf"(?<![\w.-]){re.escape(u.name.lower())}\.exe(?!\w)"),
             f"{fork.name.lower()}.exe"),
        # Donations still fund upstream development, so that text keeps its name.
        # The lookbehind protects a fork repository that keeps the upstream name.
        Rule("display name", APP,
             token(rf"(?<!{re.escape(fork.github_repository.split('/')[0])}/){re.escape(u.name)}(?!\w)"),
             fork.name, skip_line=re.compile(r"\"@?donationDescription\"\s*:")),
    ]


def in_scope(path: str, scope: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in scope)


def is_generated(path: str) -> bool:
    return path.endswith(GENERATED_SUFFIXES)


def list_files(root: Path) -> list[str]:
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, check=True,
        ).stdout.decode("utf-8")
        paths = {path for path in output.split("\0") if path}
    except (OSError, subprocess.CalledProcessError):
        paths = set()
        for directory, names, files in os.walk(root):
            names[:] = [name for name in names if name not in WALK_SKIPPED_DIRS]
            for file in files:
                paths.add(Path(directory, file).relative_to(root).as_posix())
    return sorted(
        path for path in paths
        if in_scope(path, CHECKED) and not in_scope(path, EXCLUDED_PREFIXES)
        and (root / path).is_file()
    )


def read_text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def rebrand_text(path: str, text: str, rules: list[Rule]) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    if is_generated(path):
        return text, counts
    for rule in rules:
        if in_scope(path, rule.scope):
            text, count = rule.apply(text)
            if count:
                counts[rule.name] = count
    return text, counts


def residuals(path: str, text: str, kept_patterns: tuple[re.Pattern[str], ...]
              ) -> list[tuple[str, int, str]]:
    kept = [match.span() for pattern in kept_patterns for match in pattern.finditer(text)]
    found: dict[int, str] = {}
    for match in BRAND_PATTERN.finditer(text):
        start, end = match.span()
        if any(kept_start <= start and end <= kept_end for kept_start, kept_end in kept):
            continue
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start)
        found.setdefault(text.count("\n", 0, start) + 1,
                         text[line_start:None if line_end < 0 else line_end].strip())
    return [(path, line, content) for line, content in found.items()]


def kotlin_moves(root: Path, upstream: Brand, fork: Brand) -> list[tuple[str, str]]:
    moves = []
    for base in KOTLIN_ROOTS:
        old = root / base / upstream.package_path
        new = root / base / fork.package_path
        if old.is_dir():
            for source in sorted(path for path in old.rglob("*") if path.is_file()):
                target = new / source.relative_to(old)
                moves.append((source.relative_to(root).as_posix(),
                              target.relative_to(root).as_posix()))
    return moves


def apply_moves(root: Path, moves: list[tuple[str, str]], rules: list[Rule],
                upstream: Brand) -> None:
    for source, target in moves:
        source_path, target_path = root / source, root / target
        if target_path.exists():
            # A merge may restore an upstream file that the fork already moved.
            # Identical content after rebranding is a duplicate; anything else
            # needs a manual merge so neither side's changes are lost.
            text = read_text(source_path)
            rebranded = None if text is None else rebrand_text(target, text, rules)[0]
            if rebranded is None or rebranded != read_text(target_path):
                raise RebrandError(
                    f"{source} and {target} both exist with different content; "
                    f"merge {source} into {target} manually, delete {source}, and re-run")
            source_path.unlink()
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.rename(target_path)
    for base in KOTLIN_ROOTS:
        old = root / base / upstream.package_path
        if old.is_dir():
            for directory, _, _ in os.walk(old, topdown=False):
                if not any(Path(directory).iterdir()):
                    Path(directory).rmdir()
        directory = old.parent
        while directory != root / base and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
            directory = directory.parent


def run(root: Path, config: Path, write: bool) -> Report:
    upstream, fork = load_brands(config)
    rules = build_rules(upstream, fork)
    kept = (*KEPT_PATTERNS, re.compile(re.escape(fork.github_repository)))
    moves = kotlin_moves(root, upstream, fork)
    if write:
        apply_moves(root, moves, rules, upstream)

    moved = dict(moves)
    changes: dict[str, dict[str, int]] = {}
    found: list[tuple[str, int, str]] = []
    for path in list_files(root):
        text = read_text(root / path)
        if text is None:
            continue
        # Dry runs evaluate a pending Kotlin move under its destination path.
        target = moved.get(path, path)
        new_text, counts = rebrand_text(target, text, rules)
        if counts:
            changes[target] = counts
            if write:
                (root / target).write_bytes(new_text.encode("utf-8"))
        found.extend(residuals(target, new_text, kept))
    return Report(moves=moves, changes=changes, residuals=found)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report pending changes without writing; exit 1 if any")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)

    try:
        report = run(args.root.resolve(), args.config, write=not args.check)
    except RebrandError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    verb = "would" if args.check else "did"
    for source, target in report.moves:
        print(f"{verb} move {source} -> {target}")
    for path, counts in sorted(report.changes.items()):
        details = ", ".join(f"{name} x{count}" for name, count in counts.items())
        print(f"{verb} rewrite {path}: {details}")
    if report.residuals:
        print("\nUnhandled brand occurrences (add a rule or a kept pattern):")
        for path, line, content in report.residuals:
            suffix = "  [generated: regenerate it]" if is_generated(path) else ""
            print(f"  {path}:{line}: {content}{suffix}")
    if not args.check and report.pending:
        print("\nNext: dart run pigeon --input pigeon/message.dart && flutter gen-l10n")
        dart_files = [path for path in sorted(report.changes) if path.endswith(".dart")]
        if dart_files:
            print("      dart format " + " ".join(dart_files))
    if not report.pending and not report.residuals:
        print("Rebrand is up to date.")
    return 1 if report.residuals or (args.check and report.pending) else 0


if __name__ == "__main__":
    sys.exit(main())
