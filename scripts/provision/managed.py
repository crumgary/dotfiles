"""Compare a conservative subset of managed source paths without rendering."""

import os
import stat
from pathlib import Path


def inspect_files(source_home, home, add):
    """Compare only an audited subset of chezmoi source attributes, without rendering."""
    if not source_home.is_dir():
        add(
            "managed-files",
            "missing",
            "Managed home source directory is missing.",
            source_home,
        )
        return
    ignores_unverified = (source_home / ".chezmoiignore.tmpl").exists() or (
        source_home / ".chezmoiignore"
    ).exists()
    if ignores_unverified:
        add(
            "managed-coverage",
            "unverified",
            "Ignore rules are not evaluated; absent targets may be excluded.",
            source_home,
        )

    def traversal_error(error):
        add(
            "source-traversal",
            "blocked",
            "Cannot traverse part of the managed source tree.",
            error.filename,
        )

    for directory, dirs, files in os.walk(
        source_home, followlinks=False, onerror=traversal_error
    ):
        for name in list(dirs):
            path = Path(directory) / name
            if name.startswith(".chezmoi") or path.is_symlink():
                dirs.remove(name)
                if path.is_symlink():
                    add(
                        "source:" + str(path.relative_to(source_home)),
                        "unverified",
                        "Source symlink was not followed.",
                        path,
                    )
            if name in dirs:
                decoded = decode_source(path.relative_to(source_home))
                if decoded is None:
                    dirs.remove(name)
                    add(
                        "source:" + str(path.relative_to(source_home)),
                        "unverified",
                        "Source directory path or attributes are unsupported.",
                        path,
                    )
                    continue
                parts, attributes = decoded
                if attributes:
                    target = home.joinpath(*parts)
                    check = "directory:" + str(target.relative_to(home))
                    if any(
                        parent.is_symlink()
                        for parent in (target, *target.parents)
                        if parent != home and home in parent.parents
                    ):
                        add(
                            check,
                            "unverified",
                            "Directory has a symlink component; metadata was not read.",
                            target,
                        )
                    elif not target.is_dir():
                        add(
                            check,
                            "unverified" if ignores_unverified else "missing",
                            "Declared directory is absent or has the wrong type.",
                            target,
                        )
                    else:
                        mode = stat.S_IMODE(target.stat().st_mode)
                        matches = not (
                            ("private" in attributes and mode & 0o077)
                            or ("readonly" in attributes and mode & 0o222)
                        )
                        add(
                            check,
                            "matching" if matches else "drifted",
                            "Compared directory access attributes independently of its files.",
                            target,
                        )
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(source_home)
            if relative.parts[0].startswith(".chezmoi") or name.startswith("run_"):
                continue
            if path.is_symlink() or not path.is_file():
                add(
                    "source:" + str(relative),
                    "unverified",
                    "Source is not an ordinary file; it was not read.",
                    path,
                )
                continue
            decoded = decode_source(relative)
            if decoded is None:
                add(
                    "source:" + str(relative),
                    "unverified",
                    "Source path or attributes are outside the audited subset.",
                    path,
                )
                continue
            parts, attributes = decoded
            private = "private" in attributes
            readonly = "readonly" in attributes
            executable = "executable" in attributes
            symlink = "symlink" in attributes
            templated = parts[-1].endswith(".tmpl")
            if templated:
                parts[-1] = parts[-1][:-5]
            if parts[-1] in {"", ".", ".."}:
                add(
                    "source:" + str(relative),
                    "blocked",
                    "Decoded source path is unsafe.",
                    path,
                )
                continue
            target = home.joinpath(*parts)
            check = "file:" + str(target.relative_to(home))
            # Ancestor symlinks could escape the fixture/home boundary or misidentify ownership.
            if any(
                parent.is_symlink()
                for parent in target.parents
                if parent != home and home in parent.parents
            ):
                add(
                    check,
                    "unverified",
                    "Target has a symlinked parent; contents were not read.",
                    target,
                )
            elif templated:
                add(
                    check,
                    "unverified",
                    "Template was not evaluated; rendered contents and mode need an audited renderer.",
                    target,
                )
            elif not target.exists() and not target.is_symlink():
                add(
                    check,
                    "unverified" if ignores_unverified else "missing",
                    "Target is absent; ignore rules are unverified."
                    if ignores_unverified
                    else "Managed target is missing.",
                    target,
                )
            elif symlink:
                matches = (
                    target.is_symlink()
                    and os.readlink(target) == path.read_text().strip()
                )
                add(
                    check,
                    "matching" if matches else "drifted",
                    "Compared literal symlink destination.",
                    target,
                )
            elif target.is_symlink() or not target.is_file():
                add(
                    check,
                    "drifted",
                    "Expected an ordinary managed file; contents were not read.",
                    target,
                )
            else:
                try:
                    matches = path.read_bytes() == target.read_bytes()
                    mode = stat.S_IMODE(target.stat().st_mode)
                    if private and mode & 0o077:
                        matches = False
                    if readonly and mode & 0o222:
                        matches = False
                    if executable and not mode & stat.S_IXUSR:
                        matches = False
                    add(
                        check,
                        "matching" if matches else "drifted",
                        "Compared static contents and declared access attributes.",
                        target,
                    )
                except OSError:
                    add(
                        check,
                        "blocked",
                        "Cannot read managed file metadata or contents.",
                        target,
                    )


def decode_source(relative):
    """Decode supported source attributes, rejecting paths that could escape home."""
    parts, attributes = [], set()
    for part in relative.parts:
        attributes = set()
        for prefix in ("private_", "readonly_", "executable_", "symlink_"):
            if part.startswith(prefix):
                attributes.add(prefix[:-1])
                part = part[len(prefix) :]
        if part.startswith("dot_"):
            part = "." + part[4:]
        if part.startswith(
            (
                "modify_",
                "remove_",
                "create_",
                "exact_",
                "encrypted_",
                "literal_",
                "external_",
            )
        ):
            return None
        if part in {"", ".", ".."}:
            return None
        parts.append(part)
    return parts, attributes
