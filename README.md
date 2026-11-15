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
ManageSieve access. File and SQL passwords, external PAM services and Kerberos
SSO can coexist with file, SQL and LDAP mailbox lookup.

## Scope

### Managed

- Distribution packages, a dedicated mailbox account, private mailbox homes and
  file-backed mailbox and submission-only accounts.
- Dovecot main configuration, LMTP and Postfix SASL sockets, TLS-only client
  access and optional Sieve filtering.
- Standard Drafts, Sent, Junk and Trash mailboxes with special-use flags.
- Dovecot PAM and GSSAPI settings and optional TLS-verified SQL and LDAP lookup
  connections.

### Not Managed

- Postfix routing, domains, aliases, recipient validation, DNS, firewall rules
  or certificate issuance.
- SPNs, keytab creation, distribution and rotation, domain membership, Winbind,
  PAM stacks, Kerberos client configuration, SQL/LDAP servers and schemas,
  PostfixAdmin, mailbox migration and backups.

## Requirements

- Dovecot 2.3 or 2.4 from AlmaLinux, Debian, Fedora, openSUSE Leap, openSUSE
  Tumbleweed or Ubuntu packages.
- The configured MTA socket owner, group and socket parent directories must
  exist. With default paths, install Postfix before this role.
- IMAPS and ManageSieve require an existing matching PEM certificate chain and
  an unencrypted private key readable by root. Protect the key with mode 0600.
- PAM uses a service provided by the caller. jomrr.samba_ad_member configures
  membership, Winbind and system authentication through jomrr.pam; Dovecot does
  not invoke these roles.
- GSSAPI requires a working Kerberos client configuration and a dedicated keytab
  containing imap/hostname, smtp/hostname and sieve/hostname principals for the
  enabled services. Provision it externally, readable by root:dovecot with mode
  0640 or stricter. Clients must support GSSAPI.
- SQL and LDAP require read-only lookup credentials and existing CA files. SQL
  uses certificate-verified TCP; LDAP uses LDAPS with mandatory certificate
  verification.

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

Hostname used in delivery greetings and generated messages.

Default:

```yaml
dovecot_hostname: '{{ ansible_facts.fqdn }}'
```

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

### `dovecot_mail_user`

Type: `str`. Required: `false`.

Unprivileged system account owning virtual mailboxes.

Default:

```yaml
dovecot_mail_user: vmail
```

### `dovecot_mail_group`

Type: `str`. Required: `false`.

System group owning virtual mailboxes.

Default:

```yaml
dovecot_mail_group: vmail
```

### `dovecot_mail_uid`

Type: `int`. Required: `false`.

Numeric UID reserved for virtual mailbox storage.

Default:

```yaml
dovecot_mail_uid: 5000
```

### `dovecot_mail_gid`

Type: `int`. Required: `false`.

Numeric GID reserved for virtual mailbox storage.

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

Enable IMAPS on port 993; plaintext IMAP remains disabled.

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

Maximum Sieve redirects per message; zero prohibits forwarding.

Default:

```yaml
dovecot_sieve_max_redirects: 0
```

### `dovecot_managesieve_enabled`

Type: `bool`. Required: `false`.

Enable ManageSieve on port 4190 with STARTTLS required for remote clients.

Default:

```yaml
dovecot_managesieve_enabled: false
```

### `dovecot_backup`

Type: `bool`. Required: `false`.

Back up the managed main configuration before replacement.

Default:

```yaml
dovecot_backup: false
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

Enable additional password verification and account checks through an externally
managed PAM service.

Default:

```yaml
dovecot_pam_enabled: false
```

### `dovecot_pam_service`

Type: `str`. Required: `false`.

Existing PAM service name; the role does not configure PAM or join an AD domain.

Default:

```yaml
dovecot_pam_service: dovecot
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

Native Dovecot username patterns selecting PAM users; file password and
submission-only accounts are excluded.

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

Exact hostname registered in the IMAP and SMTP service principals.

Default:

```yaml
dovecot_gssapi_hostname: '{{ dovecot_hostname }}'
```

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

TLS-verified SQL connection and native queries; no schema changes are performed.

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

## Managed Files

- `/etc/dovecot/dovecot.conf` Complete managed configuration; packaged conf.d
  includes are not loaded.
- `/etc/dovecot/users` File-backed mailbox password and user database,
  root:dovecot mode 0640; never backed up by this role.
- `/etc/dovecot/sieve-before.sieve` Optional administrator script and its .svbin
  binary; removed when disabled.
- `<dovecot_mail_root>/<account.name>/` Private mailbox homes, mode 0700;
  account removal preserves stored data.
- `/etc/dovecot/sasl-users` SMTP-only name:password_hash records, root:dovecot
  mode 0640; cleared when the list becomes empty.
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

Enables and starts Dovecot on every convergence. Configuration or account
changes restart Dovecot after native candidate validation; unchanged runs leave
the running service untouched.

### Handlers

- Compile changed administrator Sieve scripts before restarting Dovecot.
- Restart Dovecot when the main configuration or virtual account database
  changes.

## Security Notes

- Install distribution security updates before enabling external access.
  Configuration compatibility with Dovecot 2.3/2.4 does not establish the
  security patch status of a distribution package; vendors backport fixes
  without changing the upstream version.
- CVE-2026-42007 affects the Sieve editheader extension in unpatched releases.
  Before exposing personal Sieve to untrusted accounts, require a vendor-fixed
  package or disable that extension in a separately reviewed configuration. As
  of 2026-11-15, Canonical still lists Ubuntu 26.04 as Needs evaluation. See
  [Canonical](https://ubuntu.com/security/CVE-2026-42007); successful tests do
  not resolve this.
- LMTP has no TCP listener. Postfix LMTP and SASL sockets use mode 0600 and the
  configured MTA owner. Network client services are disabled by default and bind
  only to loopback when enabled.
- IMAP port 143 is disabled. IMAPS uses implicit TLS on 993; ManageSieve
  requires STARTTLS for remote clients on 4190. TLS 1.2 is the minimum, with TLS
  1.3 selectable. Plaintext password authentication over unencrypted remote
  connections is prohibited.
- File identities are full lowercase addresses. Use SHA512-CRYPT, BLF-CRYPT or
  ARGON2ID hashes and protect them with Vault. A * disables the file password; a
  separate enabled PAM or GSSAPI mechanism can still authenticate that identity.
- The shared vmail UID has no login shell, is restricted by first/last valid UID
  and GID, and owns private storage. Virtual users share this Unix identity:
  this is not filesystem isolation between hostile tenants.
- Sieve redirects are disabled by default to prevent unintended forwarding.
  Standard Sieve extensions are available; external-program plugins are not
  enabled. Personal scripts belong to users and are never overwritten by the
  role.
- Native doveconf validates candidate configuration. sievec validates
  administrator scripts before replacement. These checks do not establish remote
  certificate trust or successful end-to-end delivery.
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
  realm-wide relay. These checks govern SMTP submission; a positive AUTH reply
  alone does not grant permission to send.
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
- PAM full identity mode is the default for UPNs. Local-part mode deliberately
  removes the domain only for the PAM call and restores the original mail login
  afterwards. Local-part mode requires a qualified user@domain login. Restrict
  dovecot_pam_username_filter to the intended domain in this mode; otherwise
  distinct mail domains can resolve to the same system account.
- Internal SQL or LDAP lookup failures stop that lookup chain. Earlier
  successful file-backed lookups remain independent of an external outage.
  Kerberos tickets can remain valid while a DC is offline; Winbind offline logon
  and cached PAM login are caller-owned policies.

## Operational Notes

- Each dovecot_users entry requires name and password_hash, with an optional
  mail_format override. Formats are maildir, mbox, sdbox and mdbox. The default
  is maildir. Homes are `<mail_root>/<name>`, mail is stored under ~/mail and
  mbox INBOX under ~/inbox.
- dbox is represented by sdbox (one message per file) and mdbox (multiple
  messages per file). Preserve indexes with dbox backups. Changing mail_format
  or mail_root does not migrate messages; plan a doveadm backup/sync migration
  before changing either.
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
- ManageSieve stores personal scripts under ~/sieve and activates them through
  ~/.dovecot.sieve. dovecot_sieve_before runs first; use stop after terminal
  actions when personal rules must not run. When enabling redirects or vacation
  replies, authorize the vmail sendmail identity and outbound envelope addresses
  in Postfix.
- The role owns the complete main configuration and ignores packaged snippets.
  Review existing custom settings before adopting it. Configuration backups are
  optional; mailbox backups and certificate renewal with a Dovecot restart are
  external responsibilities.
- Useful further extensions include quota enforcement with LMTP rejection,
  operational monitoring, FTS search and replication; storage and retention
  policy must be decided before enabling them.
- dovecot_sasl_users has required name and password_hash fields and no mailbox
  fields. Names must be unique and disjoint from dovecot_users and remote
  mailbox identities. Its passdb is scoped to SMTP, and no userdb record is
  created.
- dovecot_pam_enabled, dovecot_pam_service, dovecot_pam_username_format,
  dovecot_pam_username_filter and dovecot_auth_worker_user control the Dovecot
  side of PAM. A file-backed PAM mailbox needs a dovecot_users entry with
  password_hash: "*". A SQL- or LDAP-backed mailbox needs only its authoritative
  external record.
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
  supported in both 2.3 and 2.4. Return password hashes with their {SCHEME}
  prefix; the fallback scheme is SHA512-CRYPT. Use SELECT-only credentials and
  include active/entitlement conditions. Dovecot 2.3 MySQL connection passwords
  must not contain whitespace because its native connection parser cannot quote
  it. The role neither installs PostfixAdmin nor changes its schema.
- dovecot_ldap_enabled activates dovecot_ldap. Supply uris, bind_dn,
  bind_password, base, ca_file, user_filter, user_fields, iterate_filter and
  iterate_user. LDAP is a mailbox source; passwords remain in PAM/Winbind or
  another configured passdb. Filters and fields use native Dovecot LDAP
  expansion. The SQL and LDAP dictionaries replace their defaults as complete
  mappings.
- Lookup order is file, SQL, then LDAP for userdb, and file, SQL, then PAM for
  password authentication. SMTP-specific submission-only accounts run before the
  global passdbs. Identity collisions across remote sources remain an
  administrative error; first matching userdb records take precedence.
- Molecule uses a real Samba DC, the samba_ad_dc and samba_ad_member roles,
  native PAM, MariaDB, PostgreSQL and Postfix. SPN creation and keytab
  export/distribution occur only in test fixtures. Tests exercise the supported
  platform matrix and both Dovecot dialects when supplied by those
  distributions.

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
          password_hash: '*'
        - name: archive@example.com
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
          password_hash: "{{ vault_alice_dovecot_hash }}"
      dovecot_sieve_before: |
        require ["fileinto"];
        if header :is "X-Spam-Flag" "YES" {
          fileinto "Junk";
          stop;
        }
```

### Mixed local, AD and submission-only identities

The caller supplies domain membership, PAM, service keytabs, TLS and Postfix
submission policy. Local file users and AD-authenticated file mailboxes
coexist. For directory-managed AD mailboxes, configure LDAP as in the
following example instead of adding those identities to dovecot_users.

```yaml
dovecot_pam_enabled: true
dovecot_pam_service: dovecot
dovecot_pam_username_format: full
dovecot_pam_username_filter: ['*@example.com']
dovecot_auth_worker_user: doveauth
dovecot_gssapi_enabled: true
dovecot_gssapi_hostname: mail.example.com
dovecot_krb5_keytab: /etc/dovecot/service.keytab
dovecot_users:
  - name: local@example.com
    password_hash: "{{ vault_local_mail_hash }}"
  - name: employee@example.com
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
concurrently.

```yaml
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
eligibility group and identity mapping to the directory. Mailbox storage still
uses the dedicated vmail UID, not AD POSIX IDs.

```yaml
dovecot_ldap_enabled: true
dovecot_ldap:
  uris: ['ldaps://dc1.ad.example.com', 'ldaps://dc2.ad.example.com']
  bind_dn: CN=mail-reader,OU=Services,DC=ad,DC=example,DC=com
  bind_password: "{{ vault_mail_ldap_password }}"
  base: DC=ad,DC=example,DC=com
  ca_file: /etc/mail/directory-ca.pem
  user_filter: "(&(objectClass=user)(|(mail=%{user})(userPrincipalName=%{user}))\
    (memberOf=CN=MailUsers,OU=Groups,DC=ad,DC=example,DC=com)\
    (!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
  user_fields:
    user: '%{ldap:mail}'
  iterate_filter: "(&(objectClass=user)(mail=*)\
    (memberOf=CN=MailUsers,OU=Groups,DC=ad,DC=example,DC=com)\
    (!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
  iterate_user: '%{ldap:mail}'
```

## References

- [Dovecot security advisory OXDC-ADV-2026-0003](https://documentation.open-xchange.com/dovecot/security/advisories/html/2026/oxdc-adv-2026-0003.html)
- [Dovecot LMTP and Postfix](https://doc.dovecot.org/main/howto/lmtp/postfix.html)
- [Dovecot 2.3 to 2.4 configuration changes](https://doc.dovecot.org/main/installation/upgrade/2.3-to-2.4.html)
- [Pigeonhole Sieve](https://doc.dovecot.org/main/core/plugins/sieve.html)
- [Dovecot TLS and secured connections](https://doc.dovecot.org/main/core/config/ssl.html)
- [Dovecot GSSAPI](https://doc.dovecot.org/2.4.2/core/config/auth/mechanisms/gssapi.html)
- [Dovecot PAM](https://doc.dovecot.org/2.4.2/core/config/auth/databases/pam.html)
- [Dovecot SQL](https://doc.dovecot.org/2.4.2/core/config/auth/databases/sql.html)
- [Dovecot LDAP](https://doc.dovecot.org/2.4.2/core/config/auth/databases/ldap.html)
- [Postfix SASL](https://www.postfix.org/SASL_README.html)

## Author

[Jonas Mauer](https://github.com/jomrr)

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for the full license text.

Copyright (c) 2026 Jonas Mauer.
