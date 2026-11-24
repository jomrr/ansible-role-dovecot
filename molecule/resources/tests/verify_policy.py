"""Check the Postfix policy and delivery results against the running mail services."""

import argparse
import imaplib
import os
import re
import smtplib
import socket
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

QUOTA_USER = "quota@example.test"
SENDER = "maildir@example.test"
LMTP = "/var/spool/postfix/private/dovecot-lmtp"
SESSION = "/run/dovecot-test-session.sock"


def imap(user: str) -> imaplib.IMAP4_SSL:
    """Connect with the CA and login credentials installed for this fixture."""
    context = ssl.create_default_context(cafile="/etc/dovecot-test/server.pem")
    client = imaplib.IMAP4_SSL("localhost", ssl_context=context, timeout=20)
    client.login(user, "molecule-password")
    return client


def hold_session() -> None:
    """Keep the same authenticated client until a later play reconnects to our socket."""
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with server_socket as server, imap("mbox@example.test") as client:
        server.bind(SESSION)
        os.chmod(SESSION, 0o600)
        server.listen(1)
        if os.fork():
            # The child owns the IMAP connection; __exit__ would send LOGOUT.
            os._exit(0)
        os.setsid()
        with open(os.devnull, "r+b", buffering=0) as sink:
            for fd in (0, 1, 2):
                os.dup2(sink.fileno(), fd)
        try:
            server.settimeout(600)
            peer, _ = server.accept()
            with peer:
                peer.sendall(client.noop()[0].encode())
        finally:
            Path(SESSION).unlink(missing_ok=True)


def message(recipient: str, body: str) -> EmailMessage:
    """Create a deliverable message including the envelope recipient in the header."""
    mail = EmailMessage()
    mail["From"] = SENDER
    mail["To"] = recipient
    mail["Subject"] = "Dovecot integration"
    mail.set_content(body)
    return mail


def policy(expected: int, *mail_options: str) -> None:
    """Exercise the SMTP recipient stage through real Postfix policy delegation."""
    with smtplib.SMTP("127.0.0.1", 10025, timeout=15) as client:
        client.ehlo()
        code, detail = client.mail(SENDER, options=mail_options)
        if code != 250:
            raise ValueError(f"SMTP MAIL expected 250, received {code} {detail!r}")
        code, detail = client.rcpt(QUOTA_USER)
        if code != expected:
            raise ValueError(f"SMTP RCPT expected {expected}, received {code} {detail!r}")


def lmtp_failure() -> int:
    """Return the LMTP error for a full mailbox at RCPT or end of DATA."""
    with smtplib.LMTP(LMTP, timeout=15) as client:
        try:
            client.send_message(message(QUOTA_USER, "full"))
        except smtplib.SMTPDataError as error:
            return error.smtp_code
        except smtplib.SMTPRecipientsRefused as error:
            return int(error.recipients[QUOTA_USER][0])
    raise ValueError("LMTP accepted a message for the full test mailbox")


def over_quota(temporary: bool) -> None:
    """Compare the LMTP delivery decision with the SMTP policy response."""
    code = lmtp_failure()
    if code // 100 != (4 if temporary else 5):
        raise ValueError(f"unexpected full-mailbox LMTP status {code}")
    policy(452 if temporary else 552)


def fill_mailbox() -> None:
    """Read actual IMAP usage and per-user limit after one delivery across the limit."""
    policy(250)
    # The empty mailbox has a 16 KiB quota plus 8 KiB of delivery grace.
    policy(552, "SIZE=32768")
    with smtplib.LMTP(LMTP, timeout=15) as client:
        client.send_message(message(QUOTA_USER, "x" * (17 * 1024)))
    with imap(QUOTA_USER) as client:
        _, replies = client.getquotaroot("INBOX")
        usage = re.search(rb"STORAGE (\d+) (\d+)", replies[1][0])
        if usage is None or int(usage[1]) < 16 or int(usage[2]) != 16:
            raise ValueError(f"unexpected IMAP quota {replies!r}")


def vacation() -> None:
    """Trigger one reply with an envelope sender on the independent SMTP receiver."""
    mail = message("delivery@example.test", "vacation probe")
    mail.replace_header("From", f"{socket.gethostname()}@replies.example.test")
    mail["X-Dovecot-Test"] = "away"
    with smtplib.LMTP(LMTP, timeout=15) as client:
        client.send_message(mail)


def main() -> None:
    """Separate checks for the configurations applied during the scenario."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("open", "verify", "defer"))
    stage = parser.parse_args().stage
    if stage == "open":
        hold_session()
    elif stage == "defer":
        over_quota(True)
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(20)
            peer.connect(SESSION)
            if peer.recv(20) != b"OK":
                sys.exit("Authenticated IMAP session did not survive account reconciliation")
        fill_mailbox()
        over_quota(False)
        vacation()


if __name__ == "__main__":
    main()
