"""Exercise the activation receipt across upgrades, interruptions and concurrent edits."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from library import dovecot_activate as activation


class ActivationTests(unittest.TestCase):
    """Use real files and substitute only service control."""

    def setUp(self) -> None:
        self.config = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.config)
        self.master = self.config / "dovecot.conf"
        self.master.write_bytes(b"config")
        self.record = self.config / activation.RECORD
        self.module = Mock(check_mode=False)
        self.module.params = {
            "operation": "plan",
            "service_manager": "systemd",
            "predict_config_change": False,
            "lookup_drivers": [],
        }
        self.module.run_command.return_value = (0, "", "")

    def plan(self) -> tuple[bool, str]:
        """Read the current configuration revision without recording it."""
        self.module.params["operation"] = "plan"
        return activation.reconcile(self.module, self.config)

    def apply(self, receipt: str) -> bool:
        """Activate exactly the revision returned by the preflight."""
        self.module.params.update(operation="apply", expected_revision=receipt)
        return activation.reconcile(self.module, self.config)[0]

    def test_previous_role_receipt_survives_upgrade(self) -> None:
        """Recognize the config line in an existing two-line acknowledgement."""
        sql = self.config / "sql.conf.ext"
        sql.write_text("mysql db {\n}\n", encoding="utf-8")
        _, revision = self.plan()
        self.record.write_text(
            f"packages=previous\n{revision}\n",
            encoding="ascii",
        )
        self.assertFalse(self.plan()[0])
        self.assertTrue(activation.record_existing_drivers(self.config, False))
        self.assertIn(
            "drivers=mysql", self.record.read_text(encoding="ascii").splitlines()
        )
        self.assertFalse(activation.record_existing_drivers(self.config, False))
        self.module.run_command.assert_not_called()

    def test_failed_service_is_retried_before_acknowledgement(self) -> None:
        """A failed reload leaves the same revision pending until a successful retry."""
        pending, receipt = self.plan()
        self.assertTrue(pending)
        self.module.run_command.side_effect = [(0, "", ""), (1, "", "")]
        with self.assertRaisesRegex(ValueError, "reload failed"):
            self.apply(receipt)
        self.assertFalse(self.record.exists())
        self.module.run_command.side_effect = None
        self.assertTrue(self.apply(receipt))
        self.module.run_command.assert_called_with(
            ["systemctl", "reload", "dovecot.service"]
        )
        self.assertEqual(self.record.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            self.record.read_text(encoding="ascii").splitlines(), [receipt, "drivers="]
        )
        self.assertFalse(self.plan()[0])

    def test_changed_inputs_must_be_revalidated(self) -> None:
        """Even restoring identical bytes on a different inode leaves the reload pending."""
        _, receipt = self.plan()
        self.module.run_command.side_effect = [(3, "", ""), (0, "", "")]
        self.apply(receipt)
        self.module.run_command.assert_called_with(
            ["systemctl", "start", "dovecot.service"]
        )
        (self.config / "replacement").write_bytes(b"config")
        (self.config / "replacement").replace(self.master)
        with self.assertRaisesRegex(ValueError, "changed before activation"):
            self.apply(receipt)
        pending, updated = self.plan()
        self.assertTrue(pending)
        self.module.check_mode = True
        self.assertTrue(self.apply(updated))
        self.assertEqual(
            self.record.read_text(encoding="ascii").splitlines(), [receipt, "drivers="]
        )
