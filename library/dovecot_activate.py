#!/usr/bin/python
"""Activate Dovecot's validated configuration and record a successful reload."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from ansible.module_utils.basic import AnsibleModule

CONFIG = Path("/etc/dovecot")
RECORD = ".ansible-activation"


def configuration_revision(directory: Path) -> str:
    """Use content and file identity to detect configurations restored after manual drift."""
    config = hashlib.sha256()
    for name in ("dovecot.conf", "ldap.conf.ext", "sql.conf.ext"):
        path = directory / name
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            if name == "dovecot.conf":
                raise
            continue
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Expected a regular configuration file at {path}")
            digest = hashlib.sha256()
            while chunk := stream.read(65536):
                digest.update(chunk)
        config.update(
            f"{path} {info.st_ino} {info.st_ctime} {digest.hexdigest()}\n".encode()
        )
    return f"config={config.hexdigest()}"


@contextmanager
def directory_lock(directory: Path) -> Iterator[int]:
    """Serialize service actions and acknowledgements on the existing configuration directory."""
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)


def acknowledge(directory: Path, receipt: str, directory_fd: int) -> None:
    """Publish a private, complete record only after the service command succeeded."""
    with NamedTemporaryFile(dir=directory, delete=False) as stream:
        path = Path(stream.name)
        try:
            stream.write(receipt.encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(path, directory / RECORD)
            os.fsync(directory_fd)
        finally:
            path.unlink(missing_ok=True)


def activate_service(module: AnsibleModule, new_driver: bool) -> None:
    """A new lookup driver needs a fresh config process to load its settings."""
    systemd = module.params["service_manager"] == "systemd"
    status_command = (
        ["systemctl", "is-active", "--quiet", "dovecot.service"]
        if systemd
        else ["service", "dovecot", "status"]
    )
    status, _, _ = module.run_command(status_command)
    if status == 0:
        action = "restart" if new_driver else "reload"
    elif status == 3 or (not systemd and status in (1, 2)):
        action = "start"
    else:
        raise ValueError(
            f"Could not determine the Dovecot service state (status {status})"
        )
    command = (
        ["systemctl", action, "dovecot.service"]
        if systemd
        else ["service", "dovecot", action]
    )
    code, _, _ = module.run_command(command)
    if code:
        raise ValueError(
            f"Dovecot {action} failed with status {code}. Check the service journal."
        )


def read_record(directory: Path) -> list[str]:
    """Read the last successfully applied configuration."""
    try:
        return (
            (directory / RECORD)
            .read_text(encoding="ascii", errors="replace")
            .splitlines()
        )
    except FileNotFoundError:
        return []


def format_record(revision: str, drivers: set[str]) -> str:
    """Store only the configuration revision and selected lookup drivers."""
    return f"{revision}\ndrivers={' '.join(sorted(drivers))}\n"


def record_existing_drivers(directory: Path, check_mode: bool) -> bool:
    """Identify drivers from the still-acknowledged configuration before changing its files."""
    with directory_lock(directory) as lock:
        previous = read_record(directory)
        if not previous or any(line.startswith("drivers=") for line in previous):
            return False
        revision = configuration_revision(directory)
        if revision not in previous:
            return False
        drivers = {"ldap"} if (directory / "ldap.conf.ext").is_file() else set()
        sql = directory / "sql.conf.ext"
        if sql.is_file():
            with sql.open(encoding="utf-8") as stream:
                drivers.update(
                    line.split(" ", 1)[0]
                    for line in stream
                    if line.startswith(("mysql ", "pgsql "))
                )
        if not check_mode:
            acknowledge(directory, format_record(revision, drivers), lock)
        return True


def reconcile(module: AnsibleModule, directory: Path) -> tuple[bool, str]:
    """Acknowledge the inspected revision only after the service accepts the action."""
    with directory_lock(directory) as lock:
        revision = configuration_revision(directory)
        previous = read_record(directory)
        pending = revision not in previous or (
            module.check_mode and module.params["predict_config_change"]
        )
        if module.params["operation"] == "apply":
            if revision != module.params["expected_revision"]:
                raise ValueError(
                    "Dovecot inputs changed before activation. "
                    "Rerun the role to validate the new revision."
                )
            if pending and not module.check_mode:
                drivers = set(module.params["lookup_drivers"])
                active = next(
                    (
                        line.removeprefix("drivers=").split()
                        for line in previous
                        if line.startswith("drivers=")
                    ),
                    [],
                )
                activate_service(module, bool(drivers.difference(active)))
                acknowledge(directory, format_record(revision, drivers), lock)
        return pending, revision


def main() -> None:
    """Plan or apply the configuration reload."""
    module = AnsibleModule(
        argument_spec={
            "operation": {
                "type": "str",
                "required": True,
                "choices": ["baseline", "plan", "apply"],
            },
            "expected_revision": {"type": "str"},
            "service_manager": {"type": "str"},
            "lookup_drivers": {
                "type": "list",
                "elements": "str",
                "choices": ["mysql", "pgsql", "ldap"],
            },
            "predict_config_change": {"type": "bool", "default": False},
        },
        required_if=[
            (
                "operation",
                "apply",
                ["expected_revision", "service_manager", "lookup_drivers"],
            )
        ],
        supports_check_mode=True,
    )

    try:
        if module.params["operation"] == "baseline":
            module.exit_json(changed=record_existing_drivers(CONFIG, module.check_mode))
        pending, revision = reconcile(module, CONFIG)
    except (OSError, ValueError) as error:
        module.fail_json(msg=str(error))
    else:
        changed = pending and (
            module.check_mode or module.params["operation"] == "apply"
        )
        module.exit_json(changed=changed, pending=pending, revision=revision)


if __name__ == "__main__":
    main()
