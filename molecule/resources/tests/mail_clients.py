"""Protocol clients and mailbox queries for the Dovecot integration checks."""

import imaplib
import os
import pwd
import re
import smtplib
import socket
import ssl
import subprocess
import uuid
from collections.abc import Callable

import gssapi

LMTP_PATH = "/var/spool/postfix/private/dovecot-lmtp"


def tls_context() -> ssl.SSLContext:
    """Trust only the scenario's certificate and verify the endpoint name."""
    return ssl.create_default_context(cafile="/etc/dovecot-test/server.pem")


def lmtp_client() -> smtplib.LMTP:
    """Connect with Postfix's effective UID to exercise socket permissions."""
    original_uid = os.geteuid()
    try:
        os.seteuid(pwd.getpwnam("postfix").pw_uid)
        return smtplib.LMTP(LMTP_PATH, timeout=15)
    finally:
        os.seteuid(original_uid)


def deliver(recipient: str, kind: str = "normal") -> str:
    """Deliver one identifiable message through the MTA's private socket."""
    message_id = f"<{uuid.uuid4()}@example.test>"
    message = (
        f"From: sender@example.test\r\nTo: {recipient}\r\n"
        f"Message-ID: {message_id}\r\nSubject: Dovecot delivery test\r\n"
        f"X-Dovecot-Test: {kind}\r\n\r\nDelivery fixture.\r\n"
    )
    with lmtp_client() as client:
        client.sendmail("sender@example.test", [recipient], message)
    return message_id


def search(recipient: str, mailbox: str, message_id: str) -> str:
    """Inspect messages through Dovecot regardless of the underlying format."""
    result = subprocess.run(
        [
            "doveadm",
            "search",
            "-u",
            recipient,
            "mailbox",
            mailbox,
            "header",
            "Message-ID",
            message_id,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sieve_response(stream: socket.SocketIO) -> bytes:
    """Read one ManageSieve response, including capability lines."""
    lines = []
    while True:
        line = stream.readline()
        if not line:
            raise ConnectionError("ManageSieve closed the connection")
        lines.append(line)
        if line.startswith((b"OK", b"NO", b"BYE")):
            # A multiline status message is a counted literal followed by the final CRLF.
            literal = re.search(rb" \{(\d+)\}\r\n$", line)
            if literal:
                remaining = int(literal.group(1)) + 2
                while remaining:
                    chunk = stream.read(remaining)
                    if not chunk:
                        raise ConnectionError(
                            "ManageSieve closed during a response literal"
                        )
                    lines.append(chunk)
                    remaining -= len(chunk)
            return b"".join(lines)


def imap_client() -> imaplib.IMAP4_SSL:
    """Open TLS with certificate verification and room for auth penalties."""
    return imaplib.IMAP4_SSL("localhost", ssl_context=tls_context(), timeout=60)


def submission_client() -> smtplib.SMTP:
    """Exercise the real Postfix listener over verified TLS."""
    client = smtplib.SMTP("localhost", 587, timeout=60)
    client.starttls(context=tls_context())
    client.ehlo()
    return client


def authenticate_submission(client: smtplib.SMTP, username: str, password: str) -> None:
    """Use one SASL exchange; SMTP.login retries failures with another mechanism."""
    client.auth("PLAIN", lambda _challenge=None: f"\0{username}\0{password}")


def kerberos_exchange(service: str) -> Callable[[bytes], bytes]:
    """Perform RFC 4752 GSSAPI with a real ticket and no extra SASL security layer."""
    context = gssapi.SecurityContext(
        name=gssapi.Name(
            f"{service}@{socket.getfqdn()}", name_type=gssapi.NameType.hostbased_service
        ),
        usage="initiate",
    )

    def exchange(challenge: bytes) -> bytes:
        if not context.complete:
            return context.step(challenge or None) or b""
        offered = context.unwrap(challenge).message
        if len(offered) != 4 or not offered[0] & 1:
            raise ValueError(
                "Server did not offer the TLS-protected SASL security layer"
            )
        return context.wrap(b"\x01\x00\x00\x00", encrypt=False).message

    return exchange
