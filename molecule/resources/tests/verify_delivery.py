"""Exercise Dovecot delivery, storage, TLS and Sieve on a managed test host."""

import base64
from collections.abc import Callable
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
import time
import unittest
import uuid

import gssapi


FORMATS = ('maildir', 'mbox', 'sdbox', 'mdbox')
PASSWORD = 'molecule-password'
AD_PASSWORD = 'Molecule-AD-Us3r!'
os.environ['KRB5CCNAME'] = 'FILE:/tmp/dovecot-test.ccache'
LMTP_PATH = '/var/spool/postfix/private/dovecot-lmtp'
AUTH_PATH = '/var/spool/postfix/private/auth'
MAIL_ROOT = Path('/var/vmail')


def maildir_message(home: Path) -> Path:
    """Find a delivered message before or after IMAP has selected the mailbox."""
    return next(path for folder in ('cur', 'new') for path in (home / 'mail' / folder).iterdir())


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
        root = MAIL_ROOT.stat()
        self.assertEqual((root.st_uid, stat.S_IMODE(root.st_mode)), (0, 0o711))
        self.assertEqual(stat.S_IMODE((MAIL_ROOT / 'drift@mail.test').stat().st_mode), 0o750)
        self.assertEqual(stat.S_IMODE(Path(AUTH_PATH).stat().st_mode), 0o600)
        for filename in ('users', 'sasl-users', 'sql.conf.ext', 'ldap.conf.ext'):
            self.assertEqual(stat.S_IMODE((Path('/etc/dovecot') / filename).stat().st_mode), 0o640)

    def test_out_of_range_delivery(self) -> None:
        """Even an active SQL record with a writable home must pass both ID bounds."""
        for address in ('baduid@mail.test', 'badgid@mail.test'):
            with self.subTest(address=address):
                with self.assertRaises((smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError)):
                    deliver(address)
                self.assertFalse(list((MAIL_ROOT / address).iterdir()))

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
        for uid, storage in enumerate(FORMATS, start=70001):
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
                self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)
                self.assertEqual((home.stat().st_uid, home.stat().st_gid), (uid, 70000))
                if storage == 'maildir':
                    message = maildir_message(home)
                    self.assertEqual((message.stat().st_uid, message.stat().st_gid), (uid, 70000))
                    denied = subprocess.run(
                        ['test', '-r', str(message)], user=70002, group=70000,
                        extra_groups=[], check=False,
                    )
                    self.assertEqual(denied.returncode, 1)
                elif storage == 'mbox':
                    self.assertTrue((home / 'inbox').is_file())
                elif storage == 'sdbox':
                    self.assertTrue(list((home / 'mail/mailboxes/INBOX/dbox-Mails').glob('u.*')))
                else:
                    self.assertTrue(list((home / 'mail/storage').glob('m.*')))
                    self.assertTrue((home / 'mail/mailboxes/INBOX/dbox-Mails').is_dir())

    def test_sieve_before(self) -> None:
        """A terminal administrator rule files the message in Junk."""
        recipient = 'maildir@example.test'
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



def imap_client() -> imaplib.IMAP4_SSL:
    """Open TLS with certificate verification and room for auth penalties."""
    return imaplib.IMAP4_SSL('localhost', ssl_context=tls_context(), timeout=60)


def submission_client() -> smtplib.SMTP:
    """Exercise the real Postfix listener over verified TLS."""
    client = smtplib.SMTP('localhost', 587, timeout=60)
    client.starttls(context=tls_context())
    client.ehlo()
    return client


def authenticate_submission(client: smtplib.SMTP, username: str, password: str) -> None:
    """Use one SASL exchange; SMTP.login retries failures with another mechanism."""
    client.auth('PLAIN', lambda _challenge=None: f'\0{username}\0{password}')


class SqlTests(unittest.TestCase):
    """Database-backed local and AD mailboxes share the same mail domain."""

    def test_sql_mailboxes(self) -> None:
        """SQL supplies both local-password and PAM-authenticated mailboxes."""
        for account, password in [('local', PASSWORD), ('adsql', AD_PASSWORD)]:
            with self.subTest(account=account):
                address = account + '@mail.test'
                message_id = deliver(address)
                with imap_client() as client:
                    client.login(address, password)
                    client.select('INBOX')
                    self.assertTrue(client.search(None, 'HEADER', 'Message-ID', message_id)[1][0])

    def test_local_password_does_not_fall_through(self) -> None:
        """A same-named AD account cannot override a SQL password mismatch."""
        with submission_client() as client:
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                authenticate_submission(client, 'local@mail.test', AD_PASSWORD)

    def test_inactive_sql_mailbox(self) -> None:
        """Inactive PostfixAdmin records do not authorize delivery."""
        with self.assertRaises(smtplib.SMTPRecipientsRefused):
            deliver('inactive@mail.test')


class IdentityTests(unittest.TestCase):
    """Real Winbind, Kerberos, LDAP and Postfix integration."""

    def test_directory_password_login(self) -> None:
        """Winbind validates the full UPN while LDAP supplies the mailbox."""
        address = 'ad@mail.test'
        message_id = deliver(address)
        with imap_client() as client:
            client.login(address, AD_PASSWORD)
            self.assertEqual(client.select('INBOX')[0], 'OK')
            self.assertTrue(client.search(None, 'HEADER', 'Message-ID', message_id)[1][0])
        home = MAIL_ROOT / address
        message = home / 'inbox' if (home / 'inbox').is_file() else maildir_message(home)
        self.assertEqual((message.stat().st_uid, message.stat().st_gid), (70101, 70100))
        workers = subprocess.run(
            ['pgrep', '-u', 'doveauth', '-x', 'auth'], check=True,
            capture_output=True, text=True,
        )
        self.assertTrue(workers.stdout.strip())

    def test_submission_only(self) -> None:
        """SMTP-only credentials send mail but cannot log in or receive mail."""
        message_id = f'<{uuid.uuid4()}@example.test>'
        with submission_client() as client:
            authenticate_submission(client, 'sender@mail.test', PASSWORD)
            client.sendmail('sender@mail.test', ['maildir@example.test'],
                            f'Message-ID: {message_id}\r\n'
                            'Subject: Submission fixture\r\n\r\nMessage.\r\n')
            client.mail('ad@mail.test')
            self.assertGreaterEqual(client.rcpt('maildir@example.test')[0], 500)
        for _ in range(30):
            if search('maildir@example.test', 'INBOX', message_id):
                break
            time.sleep(0.2)
        else:
            self.fail('Postfix did not deliver the submitted message through LMTP')
        with submission_client() as client:
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                authenticate_submission(client, 'sender@mail.test', AD_PASSWORD)
        imap = imap_client()
        try:
            with self.assertRaises(imaplib.IMAP4.error):
                imap.login('sender@mail.test', PASSWORD)
        finally:
            imap.shutdown()
        with self.assertRaises(smtplib.SMTPRecipientsRefused):
            deliver('sender@mail.test')

    def test_disabled_directory_account(self) -> None:
        """Disabled AD accounts fail PAM and the mailbox eligibility lookup."""
        with submission_client() as client:
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                authenticate_submission(client, 'disabled@mail.test', AD_PASSWORD)
        with self.assertRaises(smtplib.SMTPRecipientsRefused):
            deliver('disabled@mail.test')

    def test_kerberos_authorization(self) -> None:
        """Real tickets authenticate users; IMAP and SMTP still enforce entitlement."""
        for account in ('ad', 'outsider'):
            with self.subTest(account=account):
                subprocess.run(['kinit', account + '@MAIL.TEST'], input=AD_PASSWORD + '\n',
                               text=True, check=True, capture_output=True)
                client = imap_client()
                try:
                    if account == 'ad':
                        client.authenticate('GSSAPI', kerberos_exchange('imap'))
                        self.assertEqual(client.select('INBOX')[0], 'OK')
                        self.assert_sieve_ticket()
                    else:
                        with self.assertRaises(imaplib.IMAP4.error):
                            client.authenticate('GSSAPI', kerberos_exchange('imap'))
                finally:
                    client.shutdown()
                with submission_client() as smtp:
                    exchange = kerberos_exchange('smtp')
                    status, challenge = smtp.docmd('AUTH', 'GSSAPI')
                    while status == 334:
                        response = exchange(base64.b64decode(challenge))
                        status, challenge = smtp.docmd(base64.b64encode(response).decode())
                    self.assertEqual(status, 235)
                    smtp.mail(account + '@mail.test')
                    status, _ = smtp.rcpt('maildir@example.test')
                    self.assertEqual(status, 250 if account == 'ad' else 554)
        subprocess.run(['kdestroy'], check=True)


    def assert_sieve_ticket(self) -> None:
        """ManageSieve must accept its own service principal over STARTTLS."""
        with socket.create_connection(('localhost', 4190), timeout=60) as client:
            with client.makefile('rwb', buffering=0) as stream:
                self.assertIn(b'STARTTLS', sieve_response(stream))
                stream.write(b'STARTTLS\r\n')
                self.assertRegex(sieve_response(stream), b'^OK')
            with tls_context().wrap_socket(client, server_hostname='localhost') as secure:
                with secure.makefile('rwb', buffering=0) as stream:
                    self.assertIn(b'GSSAPI', sieve_response(stream))
                    stream.write(b'AUTHENTICATE "GSSAPI"\r\n')
                    exchange = kerberos_exchange('sieve')
                    while True:
                        challenge = stream.readline()
                        if challenge.startswith(b'OK'):
                            break
                        self.assertRegex(challenge, b'^"[A-Za-z0-9+/=]*"\r\n$')
                        response = exchange(base64.b64decode(challenge.strip()[1:-1]))
                        stream.write(b'"' + base64.b64encode(response) + b'"\r\n')


def kerberos_exchange(service: str) -> Callable[[bytes], bytes]:
    """Perform RFC 4752 GSSAPI with a real ticket and no extra SASL security layer."""
    context = gssapi.SecurityContext(
        name=gssapi.Name(f'{service}@{socket.getfqdn()}',
                         name_type=gssapi.NameType.hostbased_service),
        usage='initiate',
    )

    def exchange(challenge: bytes) -> bytes:
        if not context.complete:
            return context.step(challenge or None) or b''
        offered = context.unwrap(challenge).message
        if len(offered) != 4 or not offered[0] & 1:
            raise ValueError('Server did not offer the TLS-protected SASL security layer')
        return context.wrap(b'\x01\x00\x00\x00', encrypt=False).message

    return exchange


class LocalPamTests(unittest.TestCase):
    """A native Unix password also works with explicitly selected local-part mapping."""

    def test_unix_password(self) -> None:
        """pam_unix reads shadow as root while the mail identity retains its domain."""
        with imap_client() as client:
            client.login('pamlocal@mail.test', PASSWORD)
            self.assertEqual(client.select('INBOX')[0], 'OK')
        for username, password in (
            ('pamlocal@mail.test', 'incorrect-password'),
            ('pamlocal', PASSWORD),
            ('pamlocal@unapproved.test', PASSWORD),
        ):
            with self.subTest(username=username):
                with submission_client() as smtp:
                    with self.assertRaises(smtplib.SMTPAuthenticationError):
                        authenticate_submission(smtp, username, password)


class OutageTests(unittest.TestCase):
    """An external identity outage cannot open access or break file-backed mailboxes."""

    def test_external_lookup_fails_closed(self) -> None:
        """A previously issued ticket cannot bypass the failed mailbox lookup."""
        client = imap_client()
        try:
            with self.assertRaises(imaplib.IMAP4.error):
                client.authenticate('GSSAPI', kerberos_exchange('imap'))
        finally:
            client.shutdown()

    def test_file_credentials_remain_available(self) -> None:
        """File-backed mailbox and submission credentials do not depend on the DC."""
        with imap_client() as client:
            client.login('maildir@example.test', PASSWORD)
            self.assertEqual(client.select('INBOX')[0], 'OK')
        with submission_client() as client:
            authenticate_submission(client, 'sender@mail.test', PASSWORD)
            client.mail('sender@mail.test')
            self.assertEqual(client.rcpt('maildir@example.test')[0], 250)


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
        for filename in ('sql.conf.ext', 'ldap.conf.ext'):
            self.assertFalse((Path('/etc/dovecot') / filename).exists())
        self.assertNotIn(
            '{SHA512-CRYPT}', Path('/etc/dovecot/sasl-users').read_text(encoding='utf-8'),
        )
        self.assertTrue((MAIL_ROOT / 'maildir@example.test/mail/cur').is_dir())
        with self.assertRaises(smtplib.SMTPRecipientsRefused) as failure:
            deliver('maildir@example.test')
        self.assertEqual(failure.exception.recipients['maildir@example.test'][0], 550)
        message_id = deliver('delivery@example.test', 'spam')
        shared = Path('/var/vmail-shared/delivery@example.test')
        owner = pwd.getpwnam('vmail')
        self.assertEqual((shared.stat().st_uid, shared.stat().st_gid), (owner.pw_uid, owner.pw_gid))
        self.assertTrue(search('delivery@example.test', 'INBOX', message_id))


def main() -> None:
    """Run the checks applicable to the scenario's current profile."""
    suite = unittest.TestSuite()
    classes: tuple[type[unittest.TestCase], ...] = (
        SecurityTests, ClientTests, SqlTests, IdentityTests,
    )
    if '--mda' in sys.argv:
        classes = (MdaTests,)
    elif '--sql' in sys.argv:
        classes = (SqlTests, LocalPamTests)
    elif '--outage' in sys.argv:
        classes = (OutageTests,)
    for test_class in classes:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
