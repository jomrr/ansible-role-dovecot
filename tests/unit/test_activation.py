"""Exercise the activation receipt across upgrades, interruptions and concurrent edits."""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from library import dovecot_activate as activation


class ActivationTests(unittest.TestCase):
    """Use real files and substitute only package queries and service control."""

    def setUp(self) -> None:
        self.config = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.config)
        self.master = self.config / "dovecot.conf"
        self.master.write_bytes(b"config")
        self.record = self.config / activation.RECORD
        self.module = Mock(check_mode=False)
        self.module.params = {
            "operation": "plan",
            "package_database": "dpkg",
            "service_manager": "systemd",
            "predict_package_change": False,
            "predict_config_change": False,
        }
        self.native_command = Mock(return_value="installed b\ninstalled a\n")

    def plan(self) -> tuple[str, str]:
        """Read the current package and file revision without recording it."""
        self.module.params["operation"] = "plan"
        return activation.reconcile(self.module, self.config, self.native_command)

    def apply(self, receipt: str) -> str:
        """Activate exactly the revision returned by the preflight."""
        self.module.params.update(operation="apply", expected_revision=receipt)
        return activation.reconcile(self.module, self.config, self.native_command)[0]

    def test_previous_role_receipt_survives_upgrade(self) -> None:
        """Use the separator, file metadata and SHA256 encoding of the original role."""
        info = self.master.stat()
        content = hashlib.sha256(b"config").hexdigest()
        row = f"{self.master} {info.st_ino} {info.st_ctime} {content}\n"
        self.record.write_text(
            "packages=ca5a7a3fca98d01068d90c6a6c8acfa9619d1be5b0b74346d4ef6e9d79224b07\n"
            f"config={hashlib.sha256(row.encode()).hexdigest()}\n",
            encoding="ascii",
        )
        self.assertEqual(self.plan()[0], "none")

    def test_failed_service_is_retried_before_acknowledgement(self) -> None:
        """A successful retry records the revision privately and closes the pending restart."""
        action, receipt = self.plan()
        self.assertEqual(action, "restart")
        self.native_command.side_effect = [
            "installed a\ninstalled b",
            ValueError("service unavailable"),
        ]
        with self.assertRaisesRegex(ValueError, "service unavailable"):
            self.apply(receipt)
        self.assertFalse(self.record.exists())
        self.native_command.side_effect = None
        self.assertEqual(self.apply(receipt), "restart")
        self.assertEqual(self.record.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.plan()[0], "none")
        self.native_command.return_value = "installed new version"
        self.assertEqual(self.plan()[0], "restart")

    def test_changed_inputs_must_be_revalidated(self) -> None:
        """Even restoring identical bytes on a different inode leaves the reload pending."""
        _, receipt = self.plan()
        self.apply(receipt)
        (self.config / "replacement").write_bytes(b"config")
        (self.config / "replacement").replace(self.master)
        with self.assertRaisesRegex(ValueError, "changed during validation"):
            self.apply(receipt)
        action, updated = self.plan()
        self.assertEqual(action, "reload")
        self.module.check_mode = True
        self.assertEqual(self.apply(updated), "reload")
        self.assertEqual(self.record.read_text(encoding="ascii"), receipt)
