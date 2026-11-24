#!/usr/bin/python
"""Apply exactly the Dovecot package and configuration revision that passed validation."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import NamedTuple

from ansible.module_utils.basic import AnsibleModule

CONFIG = Path("/etc/dovecot")
RECORD = ".ansible-activation"
PACKAGE_QUERIES = {
    "dpkg": [
        "dpkg-query",
        "-W",
        r"-f=${db:Status-Status} ${binary:Package} ${Version}\n",
        "dovecot*",
    ],
    "rpm": [
        "rpm",
        "-qa",
        "--queryformat",
        r"installed %{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\n",
        "dovecot*",
    ],
}


class Revision(NamedTuple):
    """The two lines also written by earlier versions of the role."""

    packages: str
    config: str

    def serialize(self) -> str:
        """Write the acknowledgement in its original format."""
        return f"packages={self.packages}\nconfig={self.config}\n"


def installed_revision(directory: Path, packages: str) -> Revision:
    """Include file identity so restoring previously acknowledged bytes still triggers a reload."""
    installed = sorted(
        line for line in packages.splitlines() if line.startswith("installed ")
    )
    if not installed:
        raise ValueError("The package database returned no installed Dovecot packages")
    # The previous Jinja expression used a literal backslash-n between sorted package records.
    package_hash = hashlib.sha256(r"\n".join(installed).encode()).hexdigest()
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
    return Revision(package_hash, config.hexdigest())


def service_action(
    previous: str, desired: Revision, package_change: bool, config_change: bool
) -> str:
    """Restart after package changes and reload only for master configuration changes."""
    if package_change or f"packages={desired.packages}" not in previous.splitlines():
        return "restart"
    if config_change or f"config={desired.config}" not in previous.splitlines():
        return "reload"
    return "none"


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


def reconcile(
    module: AnsibleModule, directory: Path, run: Callable[[list[str]], str]
) -> tuple[str, str]:
    """Preview changes or apply the same revision inspected before Sieve compilation."""
    with directory_lock(directory) as lock:
        revision = installed_revision(
            directory, run(PACKAGE_QUERIES[module.params["package_database"]])
        )
        receipt = revision.serialize()
        try:
            previous = (
                (directory / RECORD).read_bytes().decode("ascii", errors="replace")
            )
        except FileNotFoundError:
            previous = ""
        action = service_action(
            previous,
            revision,
            module.params["predict_package_change"],
            module.params["predict_config_change"],
        )
        if module.params["operation"] == "apply":
            if receipt != module.params["expected_revision"]:
                raise ValueError(
                    "Dovecot inputs changed during validation. "
                    "Rerun the role to validate the new revision."
                )
            if action != "none" and not module.check_mode:
                if module.params["service_manager"] == "systemd":
                    verb = "reload-or-restart" if action == "reload" else "restart"
                    run(["systemctl", verb, "dovecot.service"])
                else:
                    run(["service", "dovecot", action])
                acknowledge(directory, receipt, lock)
        return action, receipt


def main() -> None:
    """Run native commands without a shell or environment expansion of package format strings."""
    module = AnsibleModule(
        argument_spec={
            "operation": {
                "type": "str",
                "required": True,
                "choices": ["plan", "apply"],
            },
            "package_database": {
                "type": "str",
                "required": True,
                "choices": list(PACKAGE_QUERIES),
            },
            "expected_revision": {"type": "str"},
            "service_manager": {"type": "str"},
            "predict_package_change": {"type": "bool", "default": False},
            "predict_config_change": {"type": "bool", "default": False},
        },
        required_if=[("operation", "apply", ["expected_revision", "service_manager"])],
        supports_check_mode=True,
    )

    def run(argv: list[str]) -> str:
        code, output, _ = module.run_command(
            argv, expand_user_and_vars=False, environ_update={"LC_ALL": "C"}
        )
        if code:
            raise ValueError(
                f"{argv[0]} failed with status {code}. "
                "Check the package database or the Dovecot service journal."
            )
        return str(output)

    try:
        action, receipt = reconcile(module, CONFIG, run)
    except (OSError, ValueError) as error:
        module.fail_json(msg=str(error))
    else:
        changed = action != "none" and (
            module.check_mode or module.params["operation"] == "apply"
        )
        module.exit_json(changed=changed, action=action, revision=receipt)


if __name__ == "__main__":
    main()
