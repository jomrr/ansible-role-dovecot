"""Exercise Dovecot delivery, storage, TLS and Sieve on a managed test host."""

import base64
import imaplib
import os
from pathlib import Path
import pwd
import smtplib
import socket
import ssl
import stat
import subprocess
import sys
import unittest
import uuid


FORMATS = ('maildir', 'mbox', 'sdbox', 'mdbox')
PASSWORD = 'molecule-password'
LMTP_PATH = '/var/spool/postfix/private/dovecot-lmtp'
AUTH_PATH = '/var/spool/postfix/private/auth'
MAIL_ROOT = Path('/var/vmail')


def tls_context() -> ssl.SSLContext:
    """Trust only the scenario's certificate and verify the endpoint name."""
    return ssl.create_default_context(cafile='/etc/dovecot-test/server.pem')


def lmtp_client() -> smtplib.LMTP:
    """Connect with Postfix's effective UID to exercise socket permissions."""
    original_uid = os.geteuid()
    try:
        os.seteuid(pwd.getpwnam('postfix').pw_uid)
        return smtplib.LMTP(LMTP_PATH, timeout=15)
    finally:
        os.seteuid(original_uid)


def deliver(recipient: str, kind: str = 'normal') -> str:
    """Deliver one identifiable message through the MTA's private socket."""
    message_id = f'<{uuid.uuid4()}@example.test>'
    message = (
        f'From: sender@example.test\r\nTo: {recipient}\r\n'
        f'Message-ID: {message_id}\r\nSubject: Dovecot delivery test\r\n'
        f'X-Dovecot-Test: {kind}\r\n\r\nDelivery fixture.\r\n'
    )
    with lmtp_client() as client:
        client.sendmail('sender@example.test', [recipient], message)
    return message_id


def search(recipient: str, mailbox: str, message_id: str) -> str:
    """Inspect messages through Dovecot regardless of the underlying format."""
    result = subprocess.run(
        ['doveadm', 'search', '-u', recipient, 'mailbox', mailbox,
         'header', 'Message-ID', message_id],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def sieve_response(stream: socket.SocketIO) -> bytes:
    """Read one ManageSieve response, including capability lines."""
    lines = []
    while True:
        line = stream.readline()
        if not line:
            raise ConnectionError('ManageSieve closed the connection')
        lines.append(line)
        if line.startswith((b'OK', b'NO', b'BYE')):
            return b''.join(lines)


class SecurityTests(unittest.TestCase):
    """Security properties shared by the client-access and delivery-only profiles."""

    def test_private_permissions(self) -> None:
        """LMTP and mailbox data retain private ownership and permissions."""
        metadata = Path(LMTP_PATH).stat()
        self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
        self.assertEqual(metadata.st_uid, pwd.getpwnam('postfix').pw_uid)
        self.assertEqual(stat.S_IMODE(MAIL_ROOT.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(Path('/etc/dovecot/users').stat().st_mode), 0o640)

    def test_no_plaintext_imap_or_network_lmtp(self) -> None:
        """Unrequested network protocols cannot accept connections."""
        for port in (24, 110, 143, 995):
            with self.subTest(port=port):
                with socket.socket() as client:
                    client.settimeout(3)
                    self.assertNotEqual(client.connect_ex(('127.0.0.1', port)), 0)


class ClientTests(unittest.TestCase):
    """Protocol tests for explicitly enabled, TLS-protected client access."""

    def test_delivery_only_account(self) -> None:
        """Accounts without a login password still receive mail."""
        message_id = deliver('delivery@example.test')
        self.assertTrue(search('delivery@example.test', 'INBOX', message_id))

    def test_unknown_recipient(self) -> None:
        """The user database rejects addresses that are not configured."""
        with self.assertRaises(smtplib.SMTPRecipientsRefused) as failure:
            deliver('unknown@example.test')
        self.assertEqual(failure.exception.recipients['unknown@example.test'][0], 550)

    def test_all_storage_formats(self) -> None:
        """LMTP delivery and IMAPS retrieval work for every promised format."""
        for storage in FORMATS:
            recipient = f'{storage}@example.test'
            with self.subTest(storage=storage):
                message_id = deliver(recipient)
                with imaplib.IMAP4_SSL('localhost', ssl_context=tls_context()) as client:
                    client.login(recipient, PASSWORD)
                    self.assertEqual(client.select('INBOX')[0], 'OK')
                    status, messages = client.search(None, 'HEADER', 'Message-ID', message_id)
                    self.assertEqual(status, 'OK')
                    self.assertTrue(messages[0])
                home = MAIL_ROOT / recipient
                if storage == 'maildir':
                    self.assertTrue((home / 'mail/cur').is_dir())
                elif storage == 'mbox':
                    self.assertTrue((home / 'inbox').is_file())
                elif storage == 'sdbox':
                    self.assertTrue(list((home / 'mail').rglob('u.*')))
                else:
                    self.assertTrue(list((home / 'mail/storage').glob('m.*')))

    def test_sieve_before(self) -> None:
        """Administrator filtering files spam into Junk for every format."""
        for storage in FORMATS:
            recipient = f'{storage}@example.test'
            with self.subTest(storage=storage):
                message_id = deliver(recipient, 'spam')
                self.assertTrue(search(recipient, 'Junk', message_id))
                self.assertFalse(search(recipient, 'INBOX', message_id))

    def test_rejected_credentials(self) -> None:
        """Incorrect passwords and delivery-only accounts cannot log in."""
        for recipient in ('maildir@example.test', 'delivery@example.test'):
            with self.subTest(recipient=recipient):
                with imaplib.IMAP4_SSL('localhost', ssl_context=tls_context()) as client:
                    with self.assertRaises(imaplib.IMAP4.error):
                        client.login(recipient, 'incorrect-password')

    def test_postfix_sasl(self) -> None:
        """Postfix's private auth endpoint accepts the configured identity."""
        metadata = Path(AUTH_PATH).stat()
        self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(15)
            original_uid = os.geteuid()
            try:
                os.seteuid(pwd.getpwnam('postfix').pw_uid)
                client.connect(AUTH_PATH)
            finally:
                os.seteuid(original_uid)
            with client.makefile('rwb', buffering=0) as stream:
                stream.write(f'VERSION\t1\t2\nCPID\t{os.getpid()}\n'.encode())
                while True:
                    line = stream.readline()
                    self.assertTrue(line)
                    if line == b'DONE\n':
                        break
                token = base64.b64encode(f'\0maildir@example.test\0{PASSWORD}'.encode())
                stream.write(b'AUTH\t1\tPLAIN\tservice=smtp\tsecured\tresp=' + token + b'\n')
                self.assertTrue(stream.readline().startswith(b'OK\t1\t'))

    def test_managesieve(self) -> None:
        """STARTTLS is mandatory and uploaded personal rules affect delivery."""
        token = base64.b64encode(f'\0maildir@example.test\0{PASSWORD}'.encode())
        with socket.create_connection(
            ('127.0.0.1', 4190), timeout=15, source_address=('127.0.0.2', 0)
        ) as client:
            with client.makefile('rwb', buffering=0) as stream:
                self.assertIn(b'STARTTLS', sieve_response(stream))
                stream.write(b'AUTHENTICATE "PLAIN" "' + token + b'"\r\n')
                self.assertIn(b'NO', sieve_response(stream))
        with socket.create_connection(
            ('127.0.0.1', 4190), timeout=15, source_address=('127.0.0.2', 0)
        ) as client:
            with client.makefile('rwb', buffering=0) as stream:
                self.assertIn(b'STARTTLS', sieve_response(stream))
                stream.write(b'STARTTLS\r\n')
                self.assertRegex(sieve_response(stream), b'^OK')
            with tls_context().wrap_socket(client, server_hostname='localhost') as secure:
                with secure.makefile('rwb', buffering=0) as stream:
                    # STARTTLS sends a fresh capability greeting automatically.
                    self.assertIn(b'SASL', sieve_response(stream))
                    stream.write(b'AUTHENTICATE "PLAIN" "' + token + b'"\r\n')
                    self.assertRegex(sieve_response(stream), b'^OK')
                    script = (
                        b'require ["fileinto"];\n'
                        b'if header :is "X-Dovecot-Test" "personal" {fileinto "Sent";}\n'
                    )
                    stream.write(f'PUTSCRIPT "molecule" {{{len(script)}+}}\r\n'.encode())
                    stream.write(script + b'\r\n')
                    self.assertRegex(sieve_response(stream), b'^OK')
                    stream.write(b'SETACTIVE "molecule"\r\n')
                    self.assertRegex(sieve_response(stream), b'^OK')
        message_id = deliver('maildir@example.test', 'personal')
        self.assertTrue(search('maildir@example.test', 'Sent', message_id))
        self.assertFalse(search('maildir@example.test', 'INBOX', message_id))


class MdaTests(unittest.TestCase):
    """Feature removal must close access while preserving stored messages."""

    def test_removed_features(self) -> None:
        """Only LMTP remains and disabled Sieve no longer filters messages."""
        for port in (993, 4190):
            with socket.socket() as client:
                client.settimeout(3)
                self.assertNotEqual(client.connect_ex(('127.0.0.1', port)), 0)
        with socket.socket(socket.AF_UNIX) as client:
            with self.assertRaises((FileNotFoundError, ConnectionRefusedError)):
                client.connect(AUTH_PATH)
        self.assertFalse(Path('/etc/dovecot/sieve-before.sieve').exists())
        self.assertFalse(Path('/etc/dovecot/sieve-before.svbin').exists())
        self.assertTrue((MAIL_ROOT / 'maildir@example.test/mail/cur').is_dir())
        with self.assertRaises(smtplib.SMTPRecipientsRefused) as failure:
            deliver('maildir@example.test')
        self.assertEqual(failure.exception.recipients['maildir@example.test'][0], 550)
        message_id = deliver('delivery@example.test', 'spam')
        self.assertTrue(search('delivery@example.test', 'INBOX', message_id))


def main() -> None:
    """Run the checks applicable to the scenario's current profile."""
    suite = unittest.TestSuite()
    for test_class in (SecurityTests, MdaTests if '--mda' in sys.argv else ClientTests):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
