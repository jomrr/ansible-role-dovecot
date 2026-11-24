#!/usr/bin/python3
"""Provision private mailbox homes using Dovecot's effective LMTP identities."""

import argparse
import errno
import fcntl
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
# doveadm also uses EX_TEMPFAIL when Dovecot rejects one user's effective identity.
DENIED_ID = re.compile(
    r"Mail access (?:for users with (?:UID|GID) [0-9]+ not permitted|not allowed for root)\b"
)


class Mailbox(NamedTuple):
    """One canonical userdb record beneath the trusted mail root."""

    name: str
    path: Path
    uid: int
    gid: int


def doveadm(*args: str) -> list[str]:
    """Accept only complete output from a successful lookup or iteration."""
    output = subprocess.check_output(
        ["/usr/bin/doveadm", *args], text=True, stderr=subprocess.PIPE
    )
    return output.splitlines()


def mailbox(login: str, root: Path) -> Mailbox:
    """Read the canonical effective delivery identity for one literal login."""
    if (
        not login
        or login.startswith("-")
        or any(c.isspace() or c in "/*?\\" for c in login)
    ):
        raise ValueError("invalid iterated login")
    result = doveadm("-f", "tab", "user", "-x", "service=lmtp", login)
    if not result or result[0] != "field\tvalue":
        raise ValueError("unexpected userdb output")
    try:
        fields = dict(line.split("\t", 1) for line in result[1:])
        path = Path(fields["home"]).relative_to(root)
        uid, gid = int(fields["uid"]), int(fields["gid"])
    except (KeyError, ValueError) as error:
        raise ValueError("invalid home, UID or GID in userdb") from error
    if not path.parts or ".." in path.parts:
        raise ValueError("home must be beneath the mail root")
    return Mailbox(fields.get("user", login), path, uid, gid)


@dataclass
class Result:
    """Progress for a complete pass, including entries needing administrator attention."""

    homes: int = 0
    skipped: int = 0

    def skip(self, name: str, reason: object) -> None:
        """Report this entry immediately and preserve partial failure through the last mailbox."""
        self.skipped += 1
        print(f"Skipping mailbox {name!r}: {reason}", file=sys.stderr)


def records(args: argparse.Namespace, result: Result) -> Iterator[Mailbox]:
    """Exclude every participant in a conflict before assigning any ownership."""
    boxes: set[Mailbox] = set()
    lookup_failure: subprocess.CalledProcessError | None = None
    for login in sorted(set(doveadm("user", "*"))):
        try:
            boxes.add(mailbox(login, args.root))
        except ValueError as error:
            result.skip(login, error)
        except subprocess.CalledProcessError as error:
            denial = DENIED_ID.search(error.stderr or "")
            reason = (
                denial[0]
                if denial
                else f"doveadm user exited with status {error.returncode}"
            )
            result.skip(login, reason)
            if denial is None and error.returncode != os.EX_NOUSER:
                lookup_failure = error
    if not boxes and lookup_failure is not None:
        raise lookup_failure

    homes = Counter(box.path for box in boxes)
    owners = Counter(box.uid for box in boxes)
    parents = {
        parent for box in boxes for parent in box.path.parents if parent in homes
    }
    for box in sorted(boxes):
        if homes[box.path] > 1 or owners[box.uid] > 1:
            result.skip(box.name, "conflicting home or UID")
        elif box.path in parents or any(parent in homes for parent in box.path.parents):
            result.skip(box.name, "overlapping mailbox homes")
        elif not (
            args.uid_min <= box.uid <= args.uid_max
            and args.gid_min <= box.gid <= args.gid_max
        ):
            result.skip(
                box.name, f"UID {box.uid} or GID {box.gid} outside permitted range"
            )
        else:
            yield box


def trusted(fd: int) -> None:
    """Check the parent before using it to address a child."""
    info = os.fstat(fd)
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError(
            "mailbox parents must be root-owned and private to administrators"
        )


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
        if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (
            box.uid,
            box.gid,
            0o700,
        ):
            raise ValueError(
                f"existing home {str(box.path)!r} has UID {info.st_uid}, GID {info.st_gid} "
                f"and mode {stat.S_IMODE(info.st_mode):04o}, expected {box.uid}:{box.gid} and 0700"
            )
    finally:
        os.close(fd)
    return False


def reconcile(args: argparse.Namespace, result: Result) -> None:
    """Serialize role and timer runs against the same directory inode."""
    anchor = os.open("/", DIRECTORY)
    try:
        with directory(anchor, args.root.relative_to("/")) as root:
            fcntl.flock(root, fcntl.LOCK_EX)
            for box in records(args, result):
                try:
                    with directory(
                        root, box.path.parent, create=not args.check
                    ) as parent:
                        result.homes += provision(parent, box, args.check)
                except FileNotFoundError:
                    if not args.check:
                        raise
                    result.homes += 1
                except ValueError as error:
                    result.skip(box.name, error)
                except OSError as error:
                    if error.errno not in (
                        errno.ENOTDIR,
                        errno.ELOOP,
                        errno.ENAMETOOLONG,
                    ):
                        raise
                    result.skip(box.name, error.strerror)
    finally:
        os.close(anchor)


def main() -> int:
    """Report how many homes are missing or return a failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("root", type=Path)
    for limit in ("uid_min", "uid_max", "gid_min", "gid_max"):
        parser.add_argument(limit, type=int)
    args = parser.parse_args()
    result = Result()
    try:
        reconcile(args, result)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Mailbox provisioning failed: {error}", file=sys.stderr)
        return 1
    finally:
        print(result.homes)
    return os.EX_DATAERR if result.skipped else 0


if __name__ == "__main__":
    sys.exit(main())
