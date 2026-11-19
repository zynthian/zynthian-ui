# -*- coding: utf-8 -*-
"""Refuse filesystem writes to real Zynthian locations while the tests run.

The suite must be safe to run ON a Zynthian (or on a desktop where zynthian_envars.sh was
sourced): production code writes config, snapshots, presets... to ``$ZYNTHIAN_*_DIR`` and to a
few hard-coded ``/zynthian/...`` paths. tests/bootstrap.py points the environment at a sandbox;
this module is the safety net for everything else.

A Python audit hook (PEP 578) sees every ``open()`` for writing, ``os.remove``, ``os.rename``,
``os.mkdir``, ``shutil.rmtree``, ... done by Python code. A write whose target is under a
*protected* root and not under a more specific *allowed* root raises ``WriteGuardError``
(a ``PermissionError``) BEFORE anything is touched, and is recorded in ``VIOLATIONS`` so the
test fails even when production code swallows the exception (tests/conftest.py checks it).

Not covered: writes done by native code (the C/C++ libraries) and by child processes.
"""

import os
import threading

PROTECTED_DEFAULT = ("/zynthian", "/boot", "/etc", "/usr", "/opt", "/lib", "/var/lib")

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

# audit event -> indexes of the arguments that are paths being written / removed
_EVENTS = {
    "os.remove": (0,),
    "os.rmdir": (0,),
    "os.mkdir": (0,),
    "os.rename": (0, 1),  # also os.replace
    "os.link": (1,),
    "os.symlink": (1,),
    "os.truncate": (0,),
    "os.chmod": (0,),
    "os.chown": (0,),
    "os.utime": (0,),
    "os.setxattr": (0,),
    "os.removexattr": (0,),
    "shutil.rmtree": (0,),
    "shutil.copyfile": (1,),
    "shutil.copytree": (1,),
    "shutil.move": (0, 1),
}


# audit event -> {path argument index: dir_fd argument index}, for paths relative to a directory
# descriptor (e.g. shutil.rmtree removes entries with os.rmdir(name, dir_fd=fd))
_DIR_FD = {
    "os.remove": {0: 1},
    "os.rmdir": {0: 1},
    "os.mkdir": {0: 2},
    "os.rename": {0: 2, 1: 3},
    "os.link": {1: 3},
    "os.symlink": {1: 2},
    "os.chmod": {0: 2},
    "os.chown": {0: 3},
    "os.utime": {0: 3},
}


class WriteGuardError(PermissionError):
    pass


VIOLATIONS = []  # (event, path) in order of occurrence

_allowed = ()
_protected = ()
_installed = False
_busy = threading.local()


def _norm(path):
    return os.path.realpath(os.path.abspath(path))


def _under(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def is_protected(path):
    """True when writing ``path`` must be refused: the longest matching root decides, so an
    allowed directory inside a protected one (the repo inside /zynthian) stays writable. On a tie the
    allowed root wins: on a device the inherited ZYNTHIAN_UI_DIR is protected and IS the repo root."""
    path = _norm(path)
    best_len, best_allowed = -1, True
    for roots, allowed in ((_protected, False), (_allowed, True)):
        for root in roots:
            if _under(path, root) and (len(root) > best_len or (allowed and len(root) == best_len)):
                best_len, best_allowed = len(root), allowed
    return not best_allowed


def _as_path(arg):
    if isinstance(arg, int) or arg is None:  # file descriptor / nothing to check
        return None
    try:
        return os.fsdecode(os.fspath(arg))
    except TypeError:
        return None


def _resolve_dir_fd(path, dir_fd):
    """Make a path relative to a directory descriptor absolute (else it would be checked
    against the current directory, e.g. a false refusal when a temporary folder has the name
    of a symlink in the repo)."""
    if path is None or os.path.isabs(path) or not isinstance(dir_fd, int) or dir_fd < 0:
        return path
    try:
        return os.path.join(os.readlink(f"/proc/self/fd/{dir_fd}"), path)
    except OSError:
        return path


def _check(event, path):
    if path is None or "__pycache__" in path:  # byte-code caches are harmless
        return
    if event == "os.mkdir" and os.path.isdir(path):  # makedirs(exist_ok=True) on an existing dir
        return
    if is_protected(path):
        VIOLATIONS.append((event, _norm(path)))
        raise WriteGuardError(f"tests/write_guard: refused {event} on {_norm(path)!r} "
                              "(outside the test sandbox; would modify a real Zynthian)")


def _hook(event, args):
    if event == "open":
        path, mode, flags = args
        writes = (isinstance(flags, int) and flags & _WRITE_FLAGS) or \
                 (isinstance(mode, str) and any(c in mode for c in "wax+"))
        if not writes:
            return
        indexes = (0,)
    else:
        indexes = _EVENTS.get(event)
        if indexes is None:
            return
    if getattr(_busy, "on", False):  # realpath() inside the check must not re-enter
        return
    _busy.on = True
    try:
        dir_fds = _DIR_FD.get(event, {})
        for i in indexes:
            if i < len(args):
                path = _as_path(args[i])
                j = dir_fds.get(i)
                if j is not None and j < len(args):
                    path = _resolve_dir_fd(path, args[j])
                _check(event, path)
    finally:
        _busy.on = False


def install(allowed, protected):
    """Activate the guard (once per process; audit hooks cannot be removed)."""
    global _allowed, _protected, _installed
    _allowed = tuple(_norm(p) for p in allowed if p)
    _protected = tuple(_norm(p) for p in (*PROTECTED_DEFAULT, *protected) if p and _norm(p) != "/")
    if not _installed:
        import sys
        sys.addaudithook(_hook)
        _installed = True
