"""Test the mailbox reconciler's per-entry and system-wide failure contracts."""

import argparse
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from files import dovecot_provision_homes as homes


class ProvisioningTests(unittest.TestCase):
    """Control userdb responses independently of host accounts and privileges."""

    def setUp(self) -> None:
        self.args = argparse.Namespace(
            root=Path("/var/vmail"),
            uid_min=70000,
            uid_max=99999,
            gid_min=70000,
            gid_max=99999,
            check=False,
        )

    def test_conflicts_and_invalid_ids_do_not_hide_eligible_mailboxes(self) -> None:
        """Exclude both sides of UID and path collisions, including nested homes."""
        identities = [
            ("a", "a", 70001),
            ("b", "b", 70001),
            ("c", "c", 70002),
            ("d", "c/sub", 70003),
            ("e", "c", 70004),
            ("f", "f", 500),
            ("g", "g", 70005),
        ]
        boxes = {
            name: homes.Mailbox(name, Path(path), uid, 70000)
            for name, path, uid in identities
        }
        result = homes.Result()
        with (
            patch.object(homes, "doveadm", return_value=list(boxes)),
            patch.object(homes, "mailbox", side_effect=lambda name, _root: boxes[name]),
            redirect_stderr(io.StringIO()),
        ):
            selected = list(homes.records(self.args, result))
        self.assertEqual(selected, [boxes["g"]])
        self.assertEqual(result.skipped, 6)

    def test_backend_outage_is_a_system_failure(self) -> None:
        """Distinguish an unavailable directory from a single ineligible identity."""
        error = subprocess.CalledProcessError(
            os.EX_TEMPFAIL, "doveadm", stderr="lookup failed"
        )
        with (
            patch.object(homes, "doveadm", return_value=["unavailable"]),
            patch.object(homes, "mailbox", side_effect=error),
            redirect_stderr(io.StringIO()),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            list(homes.records(self.args, homes.Result()))

    def test_writable_ancestor_aborts_before_userdb_iteration(self) -> None:
        """A writable ancestor invalidates the whole tree, including missing homes."""
        self.args.root = Path("/var/missing/mail")
        self.args.prepare_root = False
        root = SimpleNamespace(st_uid=0, st_mode=0o755)
        for mode in (0o775, 0o757):
            with (
                self.subTest(mode=mode),
                patch.object(
                    homes.os,
                    "fstat",
                    side_effect=[root, SimpleNamespace(st_uid=0, st_mode=mode)],
                ),
                patch.object(homes, "records") as records,
                self.assertRaisesRegex(ValueError, rf"^/var: .*mode {mode:04o}"),
            ):
                homes.reconcile(self.args, homes.Result())
            records.assert_not_called()

    def test_check_reports_drift_and_missing_home_together(self) -> None:
        """Both modes finish the pass, report the count and leave an unsafe home untouched."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            drift = root / "drift"
            drift.mkdir(mode=0o750)
            drift.chmod(0o750)
            uid, gid = os.getuid(), os.getgid()
            boxes = [
                homes.Mailbox(name, Path(name), uid, gid) for name in ("drift", "new")
            ]
            for options in (["--check"], []):
                with (
                    self.subTest(options=options),
                    patch.object(homes, "trusted"),
                    patch.object(homes, "records", return_value=iter(boxes)),
                    patch(
                        "sys.argv",
                        [
                            "provision",
                            *options,
                            str(root),
                            "0",
                            "999999",
                            "0",
                            "999999",
                        ],
                    ),
                ):
                    output, errors = io.StringIO(), io.StringIO()
                    with redirect_stdout(output), redirect_stderr(errors):
                        self.assertEqual(homes.main(), os.EX_DATAERR)
                    self.assertEqual(output.getvalue().strip(), "1")
                    self.assertIn("Skipping mailbox 'drift'", errors.getvalue())
                    self.assertEqual(drift.stat().st_mode & 0o777, 0o750)
                    self.assertEqual((root / "new").exists(), not options)
