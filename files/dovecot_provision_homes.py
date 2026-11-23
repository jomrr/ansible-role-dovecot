#!/usr/bin/python3
"""Provision private mailbox homes using Dovecot's effective LMTP identities."""

import argparse
import fcntl
import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NamedTuple

DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class Mailbox(NamedTuple):
    """One canonical userdb record beneath the trusted mail root."""

    name: str
    path: Path
    uid: int
    gid: int


def doveadm(*args: str) -> list[str]:
    """Accept only complete output from a successful lookup or iteration."""
    return subprocess.check_output(["/usr/bin/doveadm", *args], text=True).splitlines()


def records(args: argparse.Namespace) -> list[Mailbox]:
    """Validate the identity snapshot before granting ownership of any path."""
    homes: dict[Path, Mailbox] = {}
    owners: dict[int, Mailbox] = {}
    for login in sorted(set(doveadm("user", "*"))):
        if not login or login.startswith("-") or any(c.isspace() or c in "/*?\\" for c in login):
            raise ValueError(f"invalid iterated login {login!r}")
        result = doveadm("-f", "tab", "user", "-x", "service=lmtp", login)
        if not result or result[0] != "field\tvalue":
            raise ValueError(f"unexpected userdb output for {login!r}")
        fields = dict(line.split("\t", 1) for line in result[1:])
        path = Path(fields["home"]).relative_to(args.root)
        uid, gid = int(fields["uid"]), int(fields["gid"])
        if not path.parts or ".." in path.parts or not args.uid_min <= uid <= args.uid_max:
            raise ValueError(f"invalid home or UID for {login!r}")
        if not args.gid_min <= gid <= args.gid_max:
            raise ValueError(f"out-of-range GID for {login!r}")
        box = Mailbox(fields.get("user", login), path, uid, gid)
        if homes.setdefault(path, box) != box or owners.setdefault(uid, box) != box:
            raise ValueError(f"conflicting home or UID for {login!r}")
    for path in homes:
        if any(parent in homes for parent in path.parents):
            raise ValueError(f"home nested inside another mailbox: {path}")
    return list(homes.values())


def trusted(fd: int) -> None:
    """Check the parent before using it to address a child."""
    info = os.fstat(fd)
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("mailbox parents must be root-owned and private to administrators")


@contextmanager
def directory(start: int, path: Path, create: bool = False) -> Iterator[int]:
    """Walk beneath an open descriptor without following symlinks."""
    fd = os.dup(start)
    try:
        trusted(fd)
        for part in path.parts:
            try:
                child = os.open(part, DIRECTORY, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o711, dir_fd=fd)
                child = os.open(part, DIRECTORY, dir_fd=fd)
                os.fchmod(child, 0o711)
            os.close(fd)
            fd = child
            trusted(fd)
        yield fd
    finally:
        os.close(fd)


def provision(parent: int, box: Mailbox, check: bool) -> bool:
    """Only assign ownership to a newly created leaf under a trusted parent."""
    name = box.path.name
    try:
        fd = os.open(name, DIRECTORY, dir_fd=parent)
    except FileNotFoundError:
        if not check:
            os.mkdir(name, 0o700, dir_fd=parent)
            fd = os.open(name, DIRECTORY, dir_fd=parent)
            try:
                os.fchown(fd, box.uid, box.gid)
            except OSError:
                os.rmdir(name, dir_fd=parent)
                raise
            finally:
                os.close(fd)
        return True
    try:
        info = os.fstat(fd)
        if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (box.uid, box.gid, 0o700):
            raise ValueError(f"existing home {box.path} has unexpected owner or permissions")
    finally:
        os.close(fd)
    return False


def reconcile(args: argparse.Namespace) -> int:
    """Serialize role and timer runs against the same directory inode."""
    anchor = os.open("/", DIRECTORY)
    try:
        with directory(anchor, args.root.relative_to("/")) as root:
            fcntl.flock(root, fcntl.LOCK_EX)
            count = 0
            for box in records(args):
                try:
                    with directory(root, box.path.parent, create=not args.check) as parent:
                        count += provision(parent, box, args.check)
                except FileNotFoundError:
                    if not args.check:
                        raise
                    count += 1
            return count
    finally:
        os.close(anchor)


def main() -> int:
    """Report how many homes are missing or return a failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("root", type=Path)
    for limit in ("uid_min", "uid_max", "gid_min", "gid_max"):
        parser.add_argument(limit, type=int)
    try:
        print(reconcile(parser.parse_args()))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Mailbox provisioning failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
