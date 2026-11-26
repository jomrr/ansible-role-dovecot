# Ansible Role: dovecot

![GitHub](https://img.shields.io/github/license/jomrr/ansible-role-dovecot)
![GitHub last commit](https://img.shields.io/github/last-commit/jomrr/ansible-role-dovecot)
![GitHub issues](https://img.shields.io/github/issues-raw/jomrr/ansible-role-dovecot)
[![dev](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-role-dovecot/dev.yml?branch=dev&label=dev)](https://github.com/jomrr/ansible-role-dovecot/actions/workflows/dev.yml?query=branch%3Adev)
[![main](https://img.shields.io/github/actions/workflow/status/jomrr/ansible-role-dovecot/main.yml?branch=main&label=main)](https://github.com/jomrr/ansible-role-dovecot/actions/workflows/main.yml?query=branch%3Amain)

Install and configure Dovecot for secure LMTP delivery, virtual mailboxes and
Sieve filtering.

## Purpose

Provide final mail delivery from Postfix through a private LMTP socket. Virtual
accounts use Maildir, mbox, sdbox or mdbox storage, with optional IMAPS and
ManageSieve access. File and SQL passwords, PAM authentication and Kerberos SSO
can coexist with file, SQL and LDAP mailbox lookup.

## Scope

### Managed

- Distribution packages, private homes for file, SQL and LDAP mailboxes,
  optional shared storage ownership and submission-only accounts.
- Dovecot main configuration, LMTP and Postfix SASL sockets, TLS-only client
  access and optional Sieve filtering.
- Standard Drafts, Sent, Junk and Trash mailboxes with special-use flags.
- Optional Rspamd spam and ham learning from IMAP moves and copies.
- Dovecot's PAM service file, GSSAPI settings and local or TLS-verified SQL and
  LDAPS lookup connections.

### Not Managed

- Postfix routing, domains, aliases, recipient validation, DNS, firewall rules
  or certificate issuance.
- SPNs, keytab creation, distribution and rotation, domain membership, Winbind,
  shared host PAM stacks, Kerberos client configuration, SQL/LDAP servers and
  schemas, PostfixAdmin, mailbox migration and backups.

## Requirements

- Dovecot 2.4 is required. Debian, Fedora, openSUSE Leap, openSUSE Tumbleweed
  and Ubuntu use distribution packages. On AlmaLinux the role configures the
  official Dovecot CE 2.4 repository, pins its signing key and verifies metadata
  and RPM signatures. Its split protocol packages require EPEL runtime
  libraries. The role installs epel-release from AlmaLinux and enables CRB for
  the transaction. Upstream must publish CE RPMs for the host's EL release and
  architecture.
- Schedule migration from Dovecot 2.3 in a maintenance window. Back up mail,
  indexes and configuration and replace incompatible distribution plugins with
  their matching CE packages before bringing an existing AlmaLinux server back
  online.
- The configured MTA socket owner, group and socket parent directories must
  exist. With default paths, install Postfix before this role.
- For spam learning, install /usr/bin/rspamc on the IMAP host and configure an
  Rspamd controller that accepts privileged learning requests.
- IMAPS and ManageSieve require an existing matching PEM certificate chain and
  an unencrypted private key readable by root. Protect the key with mode 0600.
- With PAM enabled, the default `system` backend includes the host auth and
  account stacks. Debian, Ubuntu and openSUSE use common-auth and
  common-account. Fedora and AlmaLinux use password-auth. The caller maintains
  these stacks, NSS and domain membership, for example with
  jomrr.samba_ad_member and jomrr.pam.
- The `winbind` PAM backend requires a joined member with working Winbind,
  wbinfo and pam_winbind.so. Set dovecot_pam_group to a single AD group name
  resolvable by Winbind and NSS, for example `EXAMPLE\Mail Submitters`. The role
  resolves the group SID during convergence and check mode.
- GSSAPI requires a working Kerberos client configuration and a dedicated keytab
  containing imap/hostname, smtp/hostname and sieve/hostname principals for the
  enabled services. Provision it externally, readable by root:dovecot with mode
  0640 or stricter. Clients must support GSSAPI.
- SQL and LDAP need read-only lookup credentials. SQL over TCP and LDAP over
  LDAPS require a trusted CA. For local SQL, set host to the absolute MySQL
  socket filename or PostgreSQL socket directory and supply the PostgreSQL port.
  Protect the socket directory and grant the auth process access. Local
  PostgreSQL peer authentication must map the operating-system identity to the
  database login, or use a password-authenticated local rule.

## Dependencies

```yaml
collections:
  - name: community.general
    version: '>=12.0.0'
  - name: ansible.posix
    version: '>=2.0.0'
  - name: community.crypto
    version: '>=3.0.0'
  - name: containers.podman
    version: '>=1.20.0'
  - name: jomrr.samba
    version: '>=2.3.0'
  - name: ansible.mysql
    version: '>=4.0.0'
  - name: community.postgresql
    version: '>=4.0.0'
```

## Role Variables

### `dovecot_hostname`

Type: `str`. Required: `false`.

Hostname used in delivery greetings and generated messages. Defaults to the host
FQDN, with the inventory name as fallback.

### `dovecot_postmaster_address`

Type: `str`. Required: `true`.

Address receiving delivery error reports; required.

### `dovecot_mail_format`

Type: `str`. Required: `false`.

Default mailbox format, with optional per-user overrides.

Default:

```yaml
dovecot_mail_format: maildir
```

### `dovecot_mail_root`

Type: `str`. Required: `false`.

Parent directory for virtual mailbox homes.

Default:

```yaml
dovecot_mail_root: /var/vmail
```

### `dovecot_mail_ownership`

Type: `str`. Required: `false`.

Mailbox ownership policy for delivery and client processes.

Default:

```yaml
dovecot_mail_ownership: per_user
```

### `dovecot_first_valid_uid`

Type: `int`. Required: `false`.

Inclusive lower bound for per-user mailbox UIDs.

Default:

```yaml
dovecot_first_valid_uid: 70000
```

### `dovecot_last_valid_uid`

Type: `int`. Required: `false`.

Inclusive upper bound for per-user mailbox UIDs.

Default:

```yaml
dovecot_last_valid_uid: 99999
```

### `dovecot_first_valid_gid`

Type: `int`. Required: `false`.

Inclusive lower bound for per-user mailbox GIDs.

Default:

```yaml
dovecot_first_valid_gid: 70000
```

### `dovecot_last_valid_gid`

Type: `int`. Required: `false`.

Inclusive upper bound for per-user mailbox GIDs.

Default:

```yaml
dovecot_last_valid_gid: 99999
```

### `dovecot_mail_user`

Type: `str`. Required: `false`.

Unprivileged mailbox account in shared mode.

Default:

```yaml
dovecot_mail_user: vmail
```

### `dovecot_mail_group`

Type: `str`. Required: `false`.

Mailbox group in shared mode.

Default:

```yaml
dovecot_mail_group: vmail
```

### `dovecot_mail_uid`

Type: `int`. Required: `false`.

Numeric mailbox UID in shared mode.

Default:

```yaml
dovecot_mail_uid: 5000
```

### `dovecot_mail_gid`

Type: `int`. Required: `false`.

Numeric mailbox GID in shared mode.

Default:

```yaml
dovecot_mail_gid: 5000
```

### `dovecot_users`

Type: `list`. Required: `false`.

File-backed virtual accounts; removing an account preserves its stored mail.

Default:

```yaml
dovecot_users: []
```

### `dovecot_lmtp_socket`

Type: `str`. Required: `false`.

Local delivery socket accessible only to the configured MTA account.

Default:

```yaml
dovecot_lmtp_socket: /var/spool/postfix/private/dovecot-lmtp
```

### `dovecot_postfix_auth_enabled`

Type: `bool`. Required: `false`.

Expose a private SASL authentication socket for Postfix.

Default:

```yaml
dovecot_postfix_auth_enabled: true
```

### `dovecot_auth_socket`

Type: `str`. Required: `false`.

Local SASL authentication socket inside the Postfix queue directory.

Default:

```yaml
dovecot_auth_socket: /var/spool/postfix/private/auth
```

### `dovecot_socket_user`

Type: `str`. Required: `false`.

Existing MTA account allowed to access delivery and authentication sockets.

Default:

```yaml
dovecot_socket_user: postfix
```

### `dovecot_socket_group`

Type: `str`. Required: `false`.

Existing MTA group assigned to delivery and authentication sockets.

Default:

```yaml
dovecot_socket_group: postfix
```

### `dovecot_imap_enabled`

Type: `bool`. Required: `false`.

Enable IMAPS on dovecot_imaps_port.

Default:

```yaml
dovecot_imap_enabled: false
```

### `dovecot_listen`

Type: `list`. Required: `false`.

Bind addresses for explicitly enabled network services.

Default:

```yaml
dovecot_listen:
  - 127.0.0.1
```

### `dovecot_tls_certificate`

Type: `str`. Required: `false`.

Existing PEM certificate chain required for IMAPS or ManageSieve.

Default:

```yaml
dovecot_tls_certificate: ''
```

### `dovecot_tls_private_key`

Type: `str`. Required: `false`.

Existing root-readable PEM private key required for network services.

Default:

```yaml
dovecot_tls_private_key: ''
```

### `dovecot_tls_min_protocol`

Type: `str`. Required: `false`.

Minimum TLS version for client connections.

Default:

```yaml
dovecot_tls_min_protocol: TLSv1.2
```

### `dovecot_sieve_enabled`

Type: `bool`. Required: `false`.

Enable Pigeonhole filtering during LMTP delivery.

Default:

```yaml
dovecot_sieve_enabled: true
```

### `dovecot_sieve_before`

Type: `str`. Required: `false`.

Optional administrator Sieve script evaluated before personal scripts.

Default:

```yaml
dovecot_sieve_before: ''
```

### `dovecot_sieve_max_redirects`

Type: `int`. Required: `false`.

Maximum redirect actions per message. A positive limit requires a Sieve mail
transport.

Default:

```yaml
dovecot_sieve_max_redirects: 0
```

### `dovecot_managesieve_enabled`

Type: `bool`. Required: `false`.

Enable ManageSieve on dovecot_managesieve_port with STARTTLS required for remote
clients.

Default:

```yaml
dovecot_managesieve_enabled: false
```

### `dovecot_backup`

Type: `bool`. Required: `false`.

Back up managed files before replacement, except authentication and lookup
credentials.

Default:

```yaml
dovecot_backup: true
```

### `dovecot_sasl_users`

Type: `list`. Required: `false`.

SMTP authentication accounts without mailbox records; names must be disjoint
from mailbox identities.

Default:

```yaml
dovecot_sasl_users: []
```

### `dovecot_pam_enabled`

Type: `bool`. Required: `false`.

Enable password and account checks through the dedicated Dovecot PAM service.

Default:

```yaml
dovecot_pam_enabled: false
```

### `dovecot_pam_backend`

Type: `str`. Required: `false`.

Include the system PAM stack or use Winbind directly with the Dovecot mailbox
group.

Default:

```yaml
dovecot_pam_backend: system
```

### `dovecot_pam_service`

Type: `str`. Required: `false`.

Dedicated PAM service named dovecot, optionally followed by a hyphen or
underscore and a suffix.

Default:

```yaml
dovecot_pam_service: dovecot
```

### `dovecot_pam_group`

Type: `str`. Required: `false`.

NSS group authorized for PAM login. Direct Winbind requires an AD group name.
Localpart mapping also requires a group.

Default:

```yaml
dovecot_pam_group: ''
```

### `dovecot_pam_username_format`

Type: `str`. Required: `false`.

Identity passed to PAM; the complete original login is restored after successful
authentication.

Default:

```yaml
dovecot_pam_username_format: full
```

### `dovecot_pam_username_filter`

Type: `list`. Required: `false`.

Native Dovecot username patterns selecting PAM identities. At least one pattern
is required when PAM is enabled.

Default:

```yaml
dovecot_pam_username_filter: []
```

### `dovecot_auth_worker_user`

Type: `str`. Required: `false`.

Existing auth-worker account; empty preserves the native root default needed by
pam_unix.

Default:

```yaml
dovecot_auth_worker_user: ''
```

### `dovecot_gssapi_enabled`

Type: `bool`. Required: `false`.

Enable Kerberos GSSAPI with an externally provisioned service keytab.

Default:

```yaml
dovecot_gssapi_enabled: false
```

### `dovecot_krb5_keytab`

Type: `str`. Required: `false`.

Existing dedicated keytab readable by the Dovecot auth process; creation and
distribution are external.

Default:

```yaml
dovecot_krb5_keytab: /etc/dovecot/dovecot.keytab
```

### `dovecot_gssapi_hostname`

Type: `str`. Required: `false`.

Hostname registered in the IMAP and SMTP service principals. Defaults to the
effective Dovecot hostname.

### `dovecot_sql_enabled`

Type: `bool`. Required: `false`.

Enable independently configured SQL password and mailbox queries alongside file
and LDAP sources.

Default:

```yaml
dovecot_sql_enabled: false
```

### `dovecot_sql`

Type: `dict`. Required: `false`.

Local Unix socket or TLS-verified TCP connection with native Dovecot queries.

Default:

```yaml
dovecot_sql:
  driver: mysql
  host: localhost
  port: 3306
  database: postfixadmin
  username: dovecot
  password: ''
  ca_file: ''
  password_query: ''
  user_query: ''
  iterate_query: ''
```

### `dovecot_ldap_enabled`

Type: `bool`. Required: `false`.

Enable LDAP mailbox lookup without LDAP password authentication.

Default:

```yaml
dovecot_ldap_enabled: false
```

### `dovecot_ldap`

Type: `dict`. Required: `false`.

TLS-verified directory connection and mailbox selection; account and schema
management remain external.

Default:

```yaml
dovecot_ldap:
  uris: []
  bind_dn: ''
  bind_password: ''
  base: ''
  ca_file: ''
  user_filter: ''
  user_fields: {}
  iterate_filter: ''
  iterate_user: '%{ldap:mail}'
```

### `dovecot_home_provisioning`

Type: `str`. Required: `false`.

Reconcile per-user LDAP and SQL mailbox homes on role runs, also on a timer, or
externally.

Default:

```yaml
dovecot_home_provisioning: converge
```

### `dovecot_home_interval`

Type: `int`. Required: `false`.

Seconds between optional systemd home provisioning runs.

Default:

```yaml
dovecot_home_interval: 300
```

### `dovecot_selinux_type`

Type: `str`. Required: `false`.

Persistent SELinux file type for the mailbox tree on SELinux-enabled hosts.

Default:

```yaml
dovecot_selinux_type: mail_spool_t
```

### `dovecot_lmtp_enabled`

Type: `bool`. Required: `false`.

Enable LMTP delivery on the private MTA socket.

Default:

```yaml
dovecot_lmtp_enabled: true
```

### `dovecot_submission_host`

Type: `str`. Required: `false`.

SMTP endpoint (host or host:port) for messages generated during Sieve delivery.

Default:

```yaml
dovecot_submission_host: ''
```

### `dovecot_sieve_sendmail_enabled`

Type: `bool`. Required: `false`.

Allow local sendmail for Sieve when the SMTP endpoint is empty and the MTA
authorizes the mailbox UIDs.

Default:

```yaml
dovecot_sieve_sendmail_enabled: false
```

### `dovecot_imap_addresses`

Type: `list`. Required: `false`.

IMAPS bind addresses, defaulting to dovecot_listen.

Default:

```yaml
dovecot_imap_addresses: []
```

### `dovecot_imaps_port`

Type: `int`. Required: `false`.

Implicit TLS IMAP port.

Default:

```yaml
dovecot_imaps_port: 993
```

### `dovecot_managesieve_addresses`

Type: `list`. Required: `false`.

ManageSieve bind addresses, defaulting to dovecot_listen.

Default:

```yaml
dovecot_managesieve_addresses: []
```

### `dovecot_managesieve_port`

Type: `int`. Required: `false`.

ManageSieve port for STARTTLS clients.

Default:

```yaml
dovecot_managesieve_port: 4190
```

### `dovecot_imap_max_userip_connections`

Type: `int`. Required: `false`.

Optional IMAP connection limit per user and source IP address.

### `dovecot_imap_idle_notify_interval`

Type: `int`. Required: `false`.

Optional IMAP IDLE notification interval in seconds.

### `dovecot_tls_cipher_list`

Type: `str`. Required: `false`.

OpenSSL cipher list for TLS through 1.2, defaulting to the system policy.

Default:

```yaml
dovecot_tls_cipher_list: ''
```

### `dovecot_tls_curve_list`

Type: `str`. Required: `false`.

OpenSSL curve list, defaulting to the system policy.

Default:

```yaml
dovecot_tls_curve_list: ''
```

### `dovecot_tls_sni`

Type: `list`. Required: `false`.

Additional certificates selected by TLS server name.

Default:

```yaml
dovecot_tls_sni: []
```

### `dovecot_sieve_after`

Type: `str`. Required: `false`.

Administrator Sieve source executed after the personal or default script.

Default:

```yaml
dovecot_sieve_after: ''
```

### `dovecot_sieve_default`

Type: `str`. Required: `false`.

Administrator Sieve source used when a personal script is inactive.

Default:

```yaml
dovecot_sieve_default: ''
```

### `dovecot_sieve_extensions`

Type: `list`. Required: `false`.

Personal Sieve extension allowlist. An empty list enables local filters and,
with a transport, vacation and reject.

Default:

```yaml
dovecot_sieve_extensions: []
```

### `dovecot_sieve_max_script_size`

Type: `int`. Required: `false`.

Maximum Sieve script size in bytes.

Default:

```yaml
dovecot_sieve_max_script_size: 1048576
```

### `dovecot_sieve_quota_script_count`

Type: `int`. Required: `false`.

Maximum number of personal Sieve scripts.

Default:

```yaml
dovecot_sieve_quota_script_count: 20
```

### `dovecot_sieve_quota_storage_size`

Type: `int`. Required: `false`.

Maximum total personal Sieve storage in bytes.

Default:

```yaml
dovecot_sieve_quota_storage_size: 5242880
```

### `dovecot_spam_learning_enabled`

Type: `bool`. Required: `false`.

Train Rspamd on IMAP moves and copies into or out of Junk.

Default:

```yaml
dovecot_spam_learning_enabled: false
```

### `dovecot_spam_learning_host`

Type: `str`. Required: `false`.

Controller endpoint passed to rspamc.

Default:

```yaml
dovecot_spam_learning_host: 127.0.0.1:11334
```

### `dovecot_spam_learning_password`

Type: `str`. Required: `false`.

Optional Rspamd controller password for privileged learning commands.

Default:

```yaml
dovecot_spam_learning_password: ''
```

### `dovecot_lda_mailbox_autocreate`

Type: `bool`. Required: `false`.

Allow delivery to create missing destination mailboxes.

Default:

```yaml
dovecot_lda_mailbox_autocreate: false
```

### `dovecot_auth_cache_size`

Type: `int`. Required: `false`.

Authentication cache size in bytes. Zero disables caching.

Default:

```yaml
dovecot_auth_cache_size: 0
```

### `dovecot_auth_cache_ttl`

Type: `int`. Required: `false`.

Successful authentication cache lifetime in seconds when caching is enabled.

Default:

```yaml
dovecot_auth_cache_ttl: 3600
```

### `dovecot_auth_cache_negative_ttl`

Type: `int`. Required: `false`.

Failed authentication cache lifetime in seconds when caching is enabled.

Default:

```yaml
dovecot_auth_cache_negative_ttl: 3600
```

### `dovecot_recipient_delimiter`

Type: `str`. Required: `false`.

Recipient address extension delimiter. An empty string disables extensions.

Default:

```yaml
dovecot_recipient_delimiter: +
```

### `dovecot_quota_enabled`

Type: `bool`. Required: `false`.

Enforce count-based storage quota and advertise IMAP QUOTA when IMAPS is
enabled.

Default:

```yaml
dovecot_quota_enabled: false
```

### `dovecot_quota_storage_size`

Type: `int`. Required: `false`.

Default quota in bytes. Zero allows unlimited storage.

Default:

```yaml
dovecot_quota_storage_size: 0
```

### `dovecot_quota_grace`

Type: `int`. Required: `false`.

Additional bytes allowed on the delivery that first crosses the limit.

Default:

```yaml
dovecot_quota_grace: 0
```

### `dovecot_quota_full_tempfail`

Type: `bool`. Required: `false`.

Temporarily defer delivery when a mailbox is full.

Default:

```yaml
dovecot_quota_full_tempfail: false
```

### `dovecot_quota_status_enabled`

Type: `bool`. Required: `false`.

Expose a private Postfix recipient quota policy socket.

Default:

```yaml
dovecot_quota_status_enabled: false
```

### `dovecot_quota_status_socket`

Type: `str`. Required: `false`.

Absolute path of the Postfix quota policy socket.

Default:

```yaml
dovecot_quota_status_socket: /var/spool/postfix/private/quota-status
```

### `dovecot_quota_warning_thresholds`

Type: `list`. Required: `false`.

Storage percentages that invoke the warning program when crossed, highest first.

Default:

```yaml
dovecot_quota_warning_thresholds: []
```

### `dovecot_quota_warning_program`

Type: `str`. Required: `false`.

Absolute path to the administrator-provided quota warning executable.

Default:

```yaml
dovecot_quota_warning_program: ''
```

### `dovecot_quota_warning_user`

Type: `str`. Required: `false`.

Unprivileged account running the quota warning program.

Default:

```yaml
dovecot_quota_warning_user: nobody
```

### `dovecot_mail_plugins`

Type: `list`. Required: `false`.

Additional installed mail plugins inherited by each protocol.

Default:

```yaml
dovecot_mail_plugins: []
```

### `dovecot_services`

Type: `dict`. Required: `false`.

Native service settings keyed by service name, for example process_limit for
imap-login.

Default:

```yaml
dovecot_services: {}
```

### `dovecot_config`

Type: `str`. Required: `false`.

Trusted native configuration appended to the managed main configuration.

Default:

```yaml
dovecot_config: ''
```

## Managed Files

- `/etc/pam.d/<dovecot_pam_service>` Dedicated Dovecot service, root:root mode
  0644, managed when PAM is enabled. Its replacement follows dovecot_backup.
- `/etc/dovecot/dovecot.conf` Root-owned main configuration with mode 0600. It
  includes the enabled lookup files.
- `/etc/dovecot/users` File-backed mailbox password and user database,
  root:dovecot mode 0640; never backed up by this role.
- `/usr/local/share/dovecot/sieve/` Administrator delivery rules before.sieve,
  after.sieve and default.sieve, plus the optional IMAP rules learn-spam.sieve
  and learn-ham.sieve.
- `/var/cache/dovecot/sieve/` Rebuildable binaries in a separate cache directory
  for each active administrator script. Disabling a rule removes its source and
  cache.
- `/usr/local/lib/dovecot/rspamc-learn` Private executable for the two IMAPSieve
  learning sockets.
- `/etc/dovecot/rspamd-controller.password` Optional controller credential,
  root:dovecot-learn mode 0440. Disabling learning or clearing the password
  removes this file.
- `/usr/local/sbin/dovecot-provision-homes` Root-owned reconciler for per-user
  external homes. Timer mode also installs dovecot-provision-homes.service and
  .timer.
- `<dovecot_mail_root>/<account.name>/` Private mailbox homes, mode 0700;
  account removal preserves stored data.
- `/etc/dovecot/sasl-users` SMTP-only name:password_hash records, root:dovecot
  mode 0640; cleared when the list becomes empty.
- `/etc/dovecot/local-password-names` Generated names of accounts with local
  passwords. The mixed authentication chain uses this file to reject fallback
  after a wrong local password.
- `/etc/dovecot/sql.conf.ext` Optional SQL connection and queries, root:dovecot
  mode 0640; removed when disabled, never backed up.
- `/etc/dovecot/ldap.conf.ext` Optional LDAP mailbox connection and filters,
  root:dovecot mode 0640; removed when disabled, never backed up.

## Check Mode

Reports drift on an already provisioned host without changing configuration or
service state.

- A first check-mode run on a host without Dovecot cannot execute the required
  version probe or native configuration validators. Run a normal convergence
  first.

## Service Behavior

The role validates each changed configuration template before installing it and
enables the Dovecot service.

### Handlers

- Dovecot rereads the account files on change. Adding a mailbox or
  submission-only account leaves existing IMAP sessions connected. A reload for
  service settings can disconnect clients. Schedule changes to active mail
  storage and authentication policy accordingly.
- The role compiles administrator Sieve scripts before activation and starts a
  stopped service. A running master reloads changed settings. Activating a new
  SQL or LDAP driver restarts Dovecot so its configuration process loads the
  driver. Schedule this change when clients can reconnect. Changing credentials
  or queries for an active driver requires only a reload. On first adoption, a
  selected driver without a confirmed activation is treated as newly enabled.
- After successful activation the role records the configuration revision,
  lookup drivers and IMAPSieve state in /etc/dovecot/.ansible-activation.
  Following an interrupted run, correct the error and rerun the role to apply
  the pending configuration.
- Enabling or disabling IMAP spam learning restarts Dovecot. Connected clients
  must reconnect.

## Security Notes

- Install distribution security updates before enabling external access.
  Configuration compatibility with Dovecot 2.4 does not establish the security
  patch status of a distribution package; vendors backport fixes without
  changing the upstream version.
- CVE-2026-42007 affects editheader in unpatched Pigeonhole releases. Keep the
  role default with editheader disabled or select a dovecot_sieve_extensions
  allowlist containing only the required extensions. Check vendor backports
  before enabling editheader. Keep lda_mailbox_autocreate disabled with ACLs
  until vendor fixes for CVE-2026-40204 are installed.
- Dovecot binds its single LMTP listener to dovecot_lmtp_socket. Only the
  configured MTA owner has access (0600). This replaces the packaged listener
  under /run/dovecot. LMTP over TCP is disabled. The Postfix SASL socket also
  uses mode 0600. Network client services are disabled by default and bind only
  to loopback when enabled.
- IMAP port 143 is disabled. The default ports are 993 for IMAPS and 4190 for
  remote ManageSieve with STARTTLS. TLS 1.2 is the minimum, with TLS 1.3
  selectable. Plaintext password authentication over unencrypted remote
  connections is prohibited.
- File identities are full lowercase addresses. Use SHA512-CRYPT, BLF-CRYPT or
  ARGON2ID hashes and protect them with Vault. A * disables the file password; a
  separate enabled PAM or GSSAPI mechanism can still authenticate that identity.
- Each mailbox has a distinct stable UID by default. Dovecot obtains uid and gid
  from the matching userdb and bounds both IDs. Mode 0700 on each home prevents
  a mailbox process from traversing another user's home, including when users
  share a primary GID. The LMTP service starts privileged so it can switch to
  the recipient's credentials for storage operations. The master, privileged
  LMTP code and the sources that assign IDs are part of the trust boundary.
- Reserve the configured intervals exclusively for mailbox identities across
  file, SQL, LDAP and local accounts. Enforce UID uniqueness in the
  authoritative allocation system and retain IDs until archived data can no
  longer be accessed. With idmap ad, align the Winbind range with the published
  uidNumber/gidNumber attributes and the Dovecot limits.
- The default Sieve policy permits local filtering, including fileinto and
  imap4flags. The redirect limit is zero. Even with a mail transport, personal
  scripts require an explicit dovecot_sieve_extensions allowlist to use enotify
  or vnd.dovecot.report. Granting either extension allows messages to
  script-selected recipients independently of the redirect limit. A nonempty
  allowlist replaces the role's extension set. Review active scripts that
  require a removed extension before upgrading.
- Ansible validates the main configuration and each enabled SQL or LDAP
  configuration with doveconf before replacing the file. It validates
  administrator scripts with sievec. A rejected candidate stops the run before
  activation. The failure message identifies the affected file, line and
  recognized parser error while protecting setting values.
- Dovecot considers same-address local connections secured and permits local
  ManageSieve authentication without TLS. This native exception also applies
  with ssl=required. Local Unix accounts are part of the trusted boundary; IMAPS
  still uses implicit TLS.
- Authentication and mailbox authorization are separate. IMAP, ManageSieve and
  LMTP require a matching userdb record; no catch-all static userdb is created.
  SQL and LDAP may provide these records directly, without duplicating them in
  dovecot_users.
- SMTP AUTH does not consult userdb. With PAM or GSSAPI, Postfix must enforce
  submission entitlement with check_sasl_access before permitting authenticated
  relay, and envelope ownership with smtpd_sender_login_maps plus
  reject_authenticated_sender_login_mismatch. A valid AD ticket must not grant
  realm-wide relay. A disabled SQL mailbox or removal from an LDAP mailbox group
  can still leave an independent PAM or Kerberos identity eligible for SMTP
  AUTH. Revoke submission access in its authoritative policy as well.
- Keep canonical identities unique across credential sources. File accounts with
  real hashes and submission-only names are excluded from PAM. SQL password
  matches that fail verification cannot fall through to PAM: a native deny
  lookup rejects names found by the same password query. Queries must select the
  intended local credential population; SQL mailbox queries may independently
  include AD-authenticated accounts. No custom auth_source column is required.
  These password guards do not restrict GSSAPI; an AD principal must never
  collide with a separately owned local mailbox or submission identity.
- GSSAPI verifies tickets independently of password checks and does not run PAM
  account policy. LDAP mailbox filters should require explicit mail entitlement
  and exclude disabled AD accounts. When SQL owns AD mailbox authorization,
  disabling an AD account alone does not immediately revoke existing tickets or
  the SQL mailbox record; synchronize that lifecycle and Postfix submission
  authorization. Existing sessions and tickets require a deliberate revocation
  policy.
- The auth-worker defaults to root. pam_unix generally needs root to verify
  other accounts through /etc/shadow. pam_winbind can operate with a dedicated
  unprivileged account when the deployed PAM stack, Winbind socket permissions
  and NSS lookups allow it. Verify the complete stack; do not grant privileged
  pipe access merely to make a test pass.
- PAM requires at least one dovecot_pam_username_filter pattern. In full mode
  PAM receives the complete login. A domain wildcard admits every matching
  account accepted by the selected PAM service. An exclusion-only filter admits
  every name except the exclusions.
- Localpart mode requires a qualified login and dovecot_pam_group. The group
  check uses the local part and Dovecot restores the original mail identity.
  Limit the filter to the intended domain. Matching the same local part in
  multiple domains authorizes the same system credential for each address.
- In `system` mode a configured dovecot_pam_group is checked through NSS before
  password verification, including SMTP AUTH. Keep root and service accounts
  outside the mail group. File, SQL and Kerberos have independent policies.
- In `winbind` mode Dovecot passes the mailbox group SID as
  require_membership_of to pam_winbind for password authentication. The account
  stack checks membership in the same group through NSS and runs pam_winbind's
  account checks. This policy covers IMAP, SMTP AUTH and enabled ManageSieve.
  Other Winbind settings still come from pam_winbind.conf. Server logins use the
  host's own PAM policy and login groups. Host-stack controls such as MFA or
  pam_access apply to Dovecot in `system` mode.
- Internal SQL or LDAP lookup failures stop that lookup chain. Earlier
  successful file-backed lookups remain independent of an external outage.
  Kerberos tickets can remain valid while a DC is offline; Winbind offline logon
  and cached PAM login are caller-owned policies.

## Operational Notes

- With dovecot_imap_enabled and dovecot_spam_learning_enabled, moving or copying
  a message into Junk trains spam. Moving or copying it from Junk to another
  mailbox trains ham, except when the destination is Trash or Junk. Delivery,
  IMAP APPEND and flag changes do not train the classifier. IMAPSieve reports
  MOVE and COPY with the same event. The IMAP operation waits for the
  controller.
- The two administrator IMAPSieve rules use private sockets for the fixed
  learn_spam and learn_ham commands. Personal scripts retain their extension
  allowlist. Learning works independently of delivery Sieve and ManageSieve.
- dovecot_spam_learning_host defaults to 127.0.0.1:11334. The TCP connection
  carries the message and password in cleartext. Use loopback or a protected
  tunnel to a remote controller. To require authentication, exclude the IMAP
  host from Rspamd's secure_ip and supply the controller's privileged password
  through dovecot_spam_learning_password, for example from Ansible Vault. rspamc
  trims trailing whitespace when reading a password file. Only root and the
  dedicated dovecot-learn service account can read the file. Rotation replaces
  it without a backup.
- With dovecot_mail_ownership set to per_user (default), each dovecot_users
  entry requires numeric uid and gid, name and password_hash. The optional
  mail_format overrides the default. Formats are maildir, mbox, sdbox and mdbox.
  The default is maildir. Homes are `<mail_root>/<name>`, mail is stored under
  ~/mail and mbox INBOX under ~/inbox.
- In per_user mode, every directory from `/` through `dovecot_mail_root` must be
  owned by UID 0 with group and other write permissions clear. The role checks
  each existing component before creating storage and creates missing
  directories with mode 0711. The provisioning helper checks the full path on
  every run. Both stop at the first unsafe directory or symbolic link and report
  its absolute path.
- dovecot_first_valid_uid, dovecot_last_valid_uid, dovecot_first_valid_gid and
  dovecot_last_valid_gid bound the respective IDs inclusively. Both intervals
  default to 70000–99999. The role creates file-backed homes under a root-owned
  directory with mode 0711. With external userdbs, converge (default) enumerates
  eligible users and reads each effective LMTP home, UID and GID before creating
  missing homes with mode 0700. Existing external homes must already have the
  declared owner and mode. The helper uses trusted root-owned parent directories
  and refuses symlinks, conflicting owners, paths outside the root and
  out-of-range IDs. The helper provisions all eligible homes even when
  individual entries are invalid. It names each skipped mailbox in Ansible
  output or the timer journal and exits with status 65 after processing the
  batch. Ansible marks the task failed and systemd marks the service failed.
  Correct the reported entries and rerun the role or wait for the next timer
  interval. All records sharing a conflicting UID or overlapping home paths are
  skipped. Check mode reports the same errors and counts missing eligible homes.
  Failure to enumerate the userdb, loss of all effective lookups to backend
  errors or a filesystem write error fails the run.
- Timer mode also reconciles at dovecot_home_interval seconds (default 300).
  With none the operator provisions external homes. Supply iterate_query for an
  enabled SQL userdb and iterate_filter and iterate_user for LDAP. Match their
  eligibility to the lookup filters. Adding an AD group member or enabling a
  PostfixAdmin row takes effect after directory replication and reconciliation.
  To accept mail immediately, have the activation workflow provision the home
  before publishing the recipient to Postfix.
- SELinux-enabled hosts persist dovecot_selinux_type for the mailbox tree and
  apply it with restorecon. The default type is mail_spool_t. Reserve custom
  IMAPS and ManageSieve ports exclusively for those services. The role assigns
  the selected TCP ports the local pop_port_t and sieve_port_t mappings
  respectively. Review site-wide port assignments before repurposing a port and
  retire unused mappings explicitly.
- Before upgrading a shared deployment, set dovecot_mail_ownership: shared to
  retain its configured vmail account, IDs and directory layout. For migration
  to per_user, back up mail and indexes, pause delivery and client access,
  assign and verify IDs across all sources, and migrate the complete mailbox
  trees including indexes and Sieve files offline. Secure the parent as
  root:root mode 0711, verify each home as mode 0700 and check message ownership
  before restarting. The role does not recursively change existing mail
  ownership.
- dbox is represented by sdbox (one message per file) and mdbox (multiple
  messages per file). Preserve indexes with dbox backups. Changing mail_format
  or mail_root does not migrate messages; plan a doveadm backup/sync migration
  before changing either.
- On previous versions of this role, file-backed dbox INBOXes on Dovecot 2.4
  could live directly in ~/mail. The native location is
  ~/mail/mailboxes/INBOX/dbox-Mails. Before upgrading those accounts, quiesce
  delivery, back up mail and indexes and use doveadm backup from the old layout
  to a separate destination using the new layout. Verify INBOX counts and
  contents before switching over.
- The dovecot_users list controls only file-backed mailbox records. Removing an
  entry preserves stored mail; a matching SQL or LDAP record can still authorize
  that identity. Remove access in the authoritative source and use doveadm kick
  when immediate session revocation is needed.
- Generate a password hash interactively with doveadm pw -s SHA512-CRYPT, or
  ARGON2ID when supported. Do not put plaintext passwords on command lines. Keep
  Postfix accepted recipient lists synchronized with dovecot_users to reject
  unknown recipients at SMTP ingress.
- With jomrr.postfix, use postfix_dovecot_lmtp_transport:
  lmtp:unix:private/dovecot-lmtp and postfix_dovecot_auth_socket: private/auth.
  Configure virtual domains, mailbox recipients and sender ownership in that
  role. System mail recipients must be aliased to configured virtual accounts.
- ManageSieve stores user-owned personal scripts under ~/sieve. The role
  preserves these scripts. dovecot_sieve_before runs first,
  dovecot_sieve_default applies if no personal script is active, and
  dovecot_sieve_after runs last. A terminal stop ends the sequence.
- To enable vacation and reject with the default extension list, set
  dovecot_submission_host to an existing SMTP endpoint. For example, use
  127.0.0.1:10025 when the MTA already provides a listener there and restricts
  local callers and relay destinations. Set dovecot_sieve_max_redirects
  separately to permit redirects. With a custom allowlist, include the reply
  extensions you need.
- Sites that deliberately authorize mailbox UIDs to submit via local sendmail
  can leave dovecot_submission_host empty and set dovecot_sieve_sendmail_enabled
  to true. With the jomrr.postfix default of root-only local submission, use the
  SMTP endpoint. With neither transport configured, Sieve offers local filtering
  and the role rejects requests for outbound extensions or redirects.
- The role owns the complete main configuration. Review site-specific settings
  before adopting it. By default, dovecot_backup saves previous versions of the
  main configuration, Dovecot PAM service, administrator Sieve sources,
  provisioning program and units, and the managed CE repository key. Account
  files and SQL or LDAP credentials are excluded. If custom dovecot_config
  contains secrets, disable dovecot_backup before replacing that file and manage
  access to any earlier backups. After renewing certificates, validate the
  configuration and reload Dovecot.
- Enable dovecot_quota_enabled to count stored mail. Limits, grace and per-user
  quota_storage_size are in bytes, with zero storage limit meaning unlimited.
  IMAP publishes usage and the effective limit. SQL user queries can return
  quota_storage_size, and LDAP can map that field in user_fields. Keep the
  default outside the named quota root so individual limits take effect on
  2.4.1.
- For RCPT checks enable dovecot_quota_status_enabled. In Postfix place
  check_policy_service unix:private/quota-status after relay and recipient
  authorization. Successful and unknown lookups return DUNNO. A full mailbox
  returns 552 5.2.2, or 452 4.2.2 with dovecot_quota_full_tempfail. The policy
  service handles one connection per process for mbox locking. Size its
  process_limit for the number of concurrent Postfix policy connections.
- When the SMTP client declares SIZE, the policy checks that size at RCPT. The
  role sets 552 5.2.3 for a message too large for the recipient. Dovecot 2.4.5
  uses the configured mailbox-full reply for this case, including 452 when
  dovecot_quota_full_tempfail is enabled. Without SIZE, the RCPT check sees only
  the current quota usage. LMTP checks the actual message and applies the
  configured delivery grace.
- Optional quota warnings run the caller-owned dovecot_quota_warning_program
  under dovecot_quota_warning_user with the percentage and login as separate
  arguments. Use a root-owned executable, validate arguments and avoid
  inheriting relay rights. Mail processes can reach its private socket through
  the dovecot-quota group. Warning calls are advisory and may be triggered by
  local mailbox processes.
- The Dovecot auth cache defaults to zero. The PAM passdb checks the selected
  service on fresh logins. NSS and Winbind can cache group membership. Other
  cached lookups can remain stale or reuse expired entries on backend failure.
  Use doveadm auth cache flush to invalidate Dovecot entries.
- Extra plugins must be installed and compatible with all enabled mail
  processes. dovecot_services accepts native per-service settings.
  dovecot_config is trusted administrator configuration appended last. It can
  change authorization, TLS policy and process privileges. The main file uses
  mode 0600 with raw settings. Keep credentials in separate protected lookup
  files and review configuration backups.
- dovecot_sasl_users has required name and password_hash fields and no mailbox
  fields. Names must be unique and disjoint from dovecot_users and remote
  mailbox identities. Its passdb is scoped to SMTP, and no userdb record is
  created.
- Use `dovecot`, `dovecot-*` or `dovecot_*` for dovecot_pam_service. Enabling
  PAM replaces the service file. Review site-specific rules before adoption and
  select the backend that enforces the required policy. A file-backed PAM
  mailbox needs a dovecot_users entry with password_hash: "*". SQL- or
  LDAP-backed mailboxes use their authoritative record.
- dovecot_gssapi_enabled, dovecot_gssapi_hostname and dovecot_krb5_keytab
  consume existing Kerberos service credentials. UPN, ticket principal and
  mailbox address must be mapped deliberately. The default preserves the full
  lowercase identity; LDAP user_fields and SQL user queries can return a
  canonical mailbox user. SMTP AUTH does not run that userdb mapping. When UPN
  and mail address differ, Postfix must authorize the SASL principal and map it
  to the permitted envelope addresses. Delegated authentication requires a
  reviewed Kerberos policy.
- dovecot_sql_enabled activates dovecot_sql. Supply all dictionary fields shown
  below. Empty password_query or user_query disables that lookup; iterate_query
  enables doveadm enumeration. Queries use native Dovecot %{user} expansion,
  supported by Dovecot 2.4. Return password hashes with their {SCHEME} prefix;
  the fallback scheme is SHA512-CRYPT. Use SELECT-only credentials and include
  active/entitlement conditions. PostfixAdmin schema and account lifecycle are
  managed separately.
- dovecot_ldap_enabled activates dovecot_ldap. Supply uris, bind_dn,
  bind_password, base, ca_file, user_filter, user_fields, iterate_filter and
  iterate_user. LDAP is a mailbox source; passwords remain in PAM/Winbind or
  another configured passdb. Filters and fields use native Dovecot LDAP
  expansion. The LDAP userdb verifies LDAPS with its own ca_file. Outbound SMTP,
  including Sieve replies using submission_ssl, uses its configured trust or the
  system store. Older OpenLDAP builds also use LDAPTLS_CACERT within Dovecot
  processes for LDAP connections. The SQL and LDAP dictionaries replace their
  defaults as complete mappings.
- Lookup order is file, SQL, then LDAP for userdb, and file, SQL, then PAM for
  password authentication. SMTP-specific submission-only accounts run before the
  global passdbs. Identity collisions across remote sources remain an
  administrative error; first matching userdb records take precedence.
- Molecule uses a real Samba DC, the samba_ad_dc and samba_ad_member roles,
  native PAM, MariaDB, PostgreSQL and Postfix. SPN creation and keytab
  export/distribution occur only in test fixtures. On each supported
  distribution, a Sieve vacation reply must travel through the local Postfix
  instance and reach a separate SMTP receiver. Contributor hooks that build the
  Python GSSAPI test dependency require MIT Kerberos development headers
  (krb5-devel or libkrb5-dev).

## Supported Platforms

| OS Family | Distribution | Version | Container Image |
| --------- | ------------ | ------- | --------------- |
| RedHat | AlmaLinux | latest | [jomrr/molecule-almalinux:latest](https://hub.docker.com/r/jomrr/molecule-almalinux) |
| Debian | Debian | latest | [jomrr/molecule-debian:latest](https://hub.docker.com/r/jomrr/molecule-debian) |
| RedHat | Fedora | latest | [jomrr/molecule-fedora:latest](https://hub.docker.com/r/jomrr/molecule-fedora) |
| Suse | OpenSuse Leap | latest | [jomrr/molecule-opensuse-leap:latest](https://hub.docker.com/r/jomrr/molecule-opensuse-leap) |
| Suse | OpenSuse Tumbleweed | latest | [jomrr/molecule-opensuse-tumbleweed:latest](https://hub.docker.com/r/jomrr/molecule-opensuse-tumbleweed) |
| Debian | Ubuntu | latest | [jomrr/molecule-ubuntu:latest](https://hub.docker.com/r/jomrr/molecule-ubuntu) |

## Example Playbook

### Private LMTP delivery

Postfix must already be installed. Both accounts accept mail; password login
is disabled.

```yaml
---
- name: Configure mail delivery
  hosts: mail
  gather_facts: true
  roles:
    - role: jomrr.dovecot
      dovecot_postmaster_address: postmaster@example.com
      dovecot_users:
        - name: alice@example.com
          uid: 70001
          gid: 70000
          password_hash: '*'
        - name: archive@example.com
          uid: 70002
          gid: 70000
          password_hash: '*'
          mail_format: mdbox
```

### IMAPS, ManageSieve and spam filing

The password hash is supplied by Vault. Publish the listener only after
applying firewall and certificate policy.

```yaml
---
- name: Configure mailbox access
  hosts: mail
  gather_facts: true
  roles:
    - role: jomrr.dovecot
      dovecot_postmaster_address: postmaster@example.com
      dovecot_listen: ['*', '::']
      dovecot_imap_enabled: true
      dovecot_managesieve_enabled: true
      dovecot_tls_certificate: /etc/mail/tls/fullchain.pem
      dovecot_tls_private_key: /etc/mail/tls/privkey.pem
      dovecot_users:
        - name: alice@example.com
          uid: 70001
          gid: 70000
          password_hash: "{{ vault_alice_dovecot_hash }}"
      dovecot_sieve_before: |
        require ["fileinto"];
        if header :is "X-Spam-Flag" "YES" {
          fileinto "Junk";
          stop;
        }
```

### Mixed local, AD and submission-only identities

Dovecot verifies AD passwords against the mail group. The host enforces its
server-login group separately. The caller supplies domain membership, service
keytabs, TLS and Postfix submission policy. Local file users and AD mailboxes coexist.
Directory-managed mailboxes use the LDAP configuration in the next example.

```yaml
dovecot_pam_enabled: true
dovecot_pam_backend: winbind
dovecot_pam_service: dovecot
dovecot_pam_username_format: full
dovecot_pam_username_filter: ['*@example.com']
dovecot_pam_group: 'EXAMPLE\Mail Submitters'
dovecot_auth_worker_user: doveauth
dovecot_gssapi_enabled: true
dovecot_gssapi_hostname: mail.example.com
dovecot_krb5_keytab: /etc/dovecot/service.keytab
dovecot_users:
  - name: local@example.com
    uid: 70003
    gid: 70000
    password_hash: "{{ vault_local_mail_hash }}"
  - name: employee@example.com
    uid: 70004
    gid: 70000
    password_hash: '*'
dovecot_sasl_users:
  - name: scanner@example.com
    password_hash: "{{ vault_scanner_hash }}"
```

### PostfixAdmin passwords and mailbox records alongside AD

These queries use ordinary PostfixAdmin mailbox columns. They intentionally
exclude unusable * passwords from the local password source while retaining
active mailbox records for external authentication. Adjust the queries to the
actual schema and account lifecycle. File users and LDAP can remain enabled
concurrently. This example selects shared storage for an unmodified
PostfixAdmin schema. For isolated storage, join the user query to your
POSIX ID mapping and return an iteration query selecting the same eligible population.

```yaml
dovecot_mail_ownership: shared
dovecot_sql_enabled: true
dovecot_sql:
  driver: mysql
  host: db.example.com
  port: 3306
  database: postfixadmin
  username: dovecot_reader
  password: "{{ vault_mail_database_password }}"
  ca_file: /etc/mail/database-ca.pem
  password_query: >-
    SELECT username AS user, password FROM mailbox
    WHERE username = '%{user}' AND active = TRUE AND password <> '*'
  user_query: >-
    SELECT username AS user FROM mailbox
    WHERE username = '%{user}' AND active = TRUE
  iterate_query: SELECT username AS user FROM mailbox WHERE active = TRUE
```

### AD mailbox discovery without an Ansible mailbox list

This example accepts the directory mail address or UPN and returns mail as the
canonical mailbox identity. PAM itself must accept the supplied login. Adapt the
eligibility group and identity mapping to the directory. Publish the POSIX
attributes and run the role after granting membership to provision the private home.

```yaml
dovecot_ldap_enabled: true
dovecot_ldap:
  uris: ['ldaps://dc1.ad.example.com', 'ldaps://dc2.ad.example.com']
  bind_dn: CN=mail-reader,OU=Services,DC=ad,DC=example,DC=com
  bind_password: "{{ vault_mail_ldap_password }}"
  base: DC=ad,DC=example,DC=com
  ca_file: /etc/mail/directory-ca.pem
  user_filter: "(&(objectClass=user)(|(mail=%{user})(userPrincipalName=%{user}))\
    (uidNumber=*)(gidNumber=*)(memberOf=CN=MailUsers,OU=Groups,DC=ad,DC=example,DC=com)\
    (!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
  user_fields:
    user: '%{ldap:mail}'
    uid: '%{ldap:uidNumber}'
    gid: '%{ldap:gidNumber}'
  iterate_filter: "(&(objectClass=user)(mail=*)\
    (uidNumber=*)(gidNumber=*)(memberOf=CN=MailUsers,OU=Groups,DC=ad,DC=example,DC=com)\
    (!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
  iterate_user: '%{ldap:mail}'
```

### Local SQL, LMTP quotas and Sieve replies

Grant SELECT on the mailbox table to the SQL reader. The MTA owns the
private sockets and accepts the Sieve envelope sender on its internal listener.

```yaml
dovecot_sql_enabled: true
dovecot_sql:
  driver: mysql
  host: /run/mysqld/mysqld.sock
  port: 3306
  database: mail
  username: dovecot_reader
  password: "{{ vault_mail_database_password }}"
  password_query: ''
  user_query: >-
    SELECT address AS user, uid, gid, quota_bytes AS quota_storage_size
    FROM mailboxes WHERE address = '%{user}' AND active = TRUE
  iterate_query: SELECT address AS user FROM mailboxes WHERE active = TRUE
dovecot_quota_enabled: true
dovecot_quota_storage_size: 1073741824
dovecot_quota_status_enabled: true
dovecot_submission_host: 127.0.0.1:10025
```

## References

- [Dovecot CE packages and signing key](https://dovecot.org/download)
- [Dovecot quota](https://doc.dovecot.org/2.4.1/core/plugins/quota.html)
- [Dovecot 2.4.5 quota-status response handling](https://github.com/dovecot/core/blob/2.4.5/src/plugins/quota/quota-status.c#L232-L245)
- [Dovecot security advisory OXDC-ADV-2026-0003](https://documentation.open-xchange.com/dovecot/security/advisories/html/2026/oxdc-adv-2026-0003.html)
- [Dovecot LMTP process privileges](https://doc.dovecot.org/main/core/config/delivery/lmtp.html#security)
- [Dovecot LMTP and Postfix](https://doc.dovecot.org/main/howto/lmtp/postfix.html)
- [Dovecot 2.3 to 2.4 configuration changes](https://doc.dovecot.org/main/installation/upgrade/2.3-to-2.4.html)
- [Pigeonhole Sieve](https://doc.dovecot.org/main/core/plugins/sieve.html)
- [Dovecot IMAPSieve spam reporting](https://doc.dovecot.org/2.4.1/core/config/spam_reporting.html)
- [Rspamd client options](https://github.com/rspamd/rspamd/blob/master/doc/rspamc.1.md)
- [Dovecot TLS and secured connections](https://doc.dovecot.org/main/core/config/ssl.html)
- [Dovecot GSSAPI](https://doc.dovecot.org/2.4.2/core/config/auth/mechanisms/gssapi.html)
- [Dovecot PAM](https://doc.dovecot.org/2.4.2/core/config/auth/databases/pam.html)
- [Samba pam_winbind module options](https://www.samba.org/samba/docs/current/man-html/pam_winbind.8.html)
- [Dovecot SQL](https://doc.dovecot.org/2.4.2/core/config/auth/databases/sql.html)
- [Dovecot LDAP](https://doc.dovecot.org/2.4.2/core/config/auth/databases/ldap.html)
- [Postfix SASL](https://www.postfix.org/SASL_README.html)

## Author

[Jonas Mauer](https://github.com/jomrr)

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for the full license text.

Copyright (c) 2026 Jonas Mauer.
