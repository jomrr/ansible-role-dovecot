"""Verify IMAP training against the Rspamd controller and its real Bayes store."""

import unittest
import uuid
from pathlib import Path

from mail_clients import imap_client


class LearningTests(unittest.TestCase):
    """Observe successful learning by message ID across one IMAP session."""

    def test_junk_moves(self) -> None:
        """APPEND and Trash produce no training; crossing back through Junk trains both classes."""
        message_id = f"{uuid.uuid4()}@example.test"
        message = (
            f"Message-ID: <{message_id}>\r\nFrom: sender@example.test\r\n"
            "To: maildir@example.test\r\nSubject: Meeting minutes\r\n\r\n"
            "The committee discussed budgets, travel arrangements, engineering progress, "
            "staffing requirements and next quarter's regional sales targets.\r\n"
        ).encode()
        with imap_client() as client:
            client.login("maildir@example.test", "molecule-password")
            self.assertEqual(client.append("Junk", None, None, message)[0], "OK")
            for source, target in (
                ("Junk", "Trash"),
                ("Trash", "Junk"),
                ("Junk", "INBOX"),
            ):
                self.assertEqual(client.select(source)[0], "OK")
                _, ids = client.uid("SEARCH", "HEADER", "Message-ID", message_id)
                self.assertEqual(len(ids[0].split()), 1)
                self.assertEqual(client.uid("MOVE", ids[0], target)[0], "OK")
        log = Path("/var/log/rspamd/rspamd.log").read_text(encoding="utf-8")
        learns = [
            line.split("learned message as ", 1)[1].split(":", 1)[0]
            for line in log.splitlines()
            if message_id in line and "learned message as " in line
        ]
        self.assertEqual(learns, ["spam", "ham"])


if __name__ == "__main__":
    unittest.main()
