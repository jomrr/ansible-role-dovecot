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
ManageSieve access.

## Scope

### Managed

- Distribution packages, a dedicated mailbox account, private mailbox homes and
  an authoritative virtual-user database.
- Dovecot main configuration, LMTP and Postfix SASL sockets, TLS-only client
  access and optional Sieve filtering.
- Standard Drafts, Sent, Junk and Trash mailboxes with special-use flags.

### Not Managed

- Postfix routing, domains, aliases, recipient validation, DNS, firewall rules
  or certificate issuance.
- System-user authentication, SQL/LDAP databases, mailbox migrations, backups or
  deletion of stored messages.

## Requirements

- Dovecot 2.3 or 2.4 from AlmaLinux, Debian, Fedora, openSUSE Leap, openSUSE
  Tumbleweed or Ubuntu packages.
- The configured MTA socket owner, group and socket parent directories must
  exist. With default paths, install Postfix before this role.
- IMAPS and ManageSieve require an existing matching PEM certificate chain and
  an unencrypted private key readable by root. Protect the key with mode 0600.

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

Authoritative virtual accounts; removing an account preserves its stored mail.

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

## Managed Files

- `/etc/dovecot/dovecot.conf` Complete managed configuration; packaged conf.d
  includes are not loaded.
- `/etc/dovecot/users` Authoritative password and user database, root:dovecot
  mode 0640; never backed up by this role.
- `/etc/dovecot/sieve-before.sieve` Optional administrator script and its .svbin
  binary; removed when disabled.
- `<dovecot_mail_root>/<account.name>/` Private mailbox homes, mode 0700;
  account removal preserves stored data.

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

- LMTP has no TCP listener. Postfix LMTP and SASL sockets use mode 0600 and the
  configured MTA owner. Network client services are disabled by default and bind
  only to loopback when enabled.
- IMAP port 143 is disabled. IMAPS uses implicit TLS on 993; ManageSieve
  requires STARTTLS for remote clients on 4190. TLS 1.2 is the minimum, with TLS
  1.3 selectable. Plaintext password authentication over unencrypted remote
  connections is prohibited.
- Only listed virtual accounts can receive mail or authenticate. Full lowercase
  user@domain identities are preserved. Passwords must be SHA512-CRYPT,
  BLF-CRYPT or ARGON2ID hashes; supported schemes depend on the installed
  Dovecot build. Use * for delivery-only accounts and Ansible Vault for hashes.
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

## Operational Notes

- Each dovecot_users entry requires name and password_hash, with an optional
  mail_format override. Formats are maildir, mbox, sdbox and mdbox. The default
  is maildir. Homes are `<mail_root>/<name>`, mail is stored under ~/mail and
  mbox INBOX under ~/inbox.
- dbox is represented by sdbox (one message per file) and mdbox (multiple
  messages per file). Preserve indexes with dbox backups. Changing mail_format
  or mail_root does not migrate messages; plan a doveadm backup/sync migration
  before changing either.
- The account list is authoritative. Removing an entry revokes new
  authentication and delivery but preserves mail and personal scripts. Existing
  authenticated sessions can require an explicit doveadm kick during urgent
  revocation.
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
- Useful extensions for a larger deployment include quota enforcement with LMTP
  rejection and monitoring, SQL/LDAP user databases, FTS search, and
  replication. These require explicit storage, identity and retention policies
  and are not implemented by this role.

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

## References

- [Dovecot LMTP and Postfix](https://doc.dovecot.org/main/howto/lmtp/postfix.html)
- [Dovecot 2.3 to 2.4 configuration changes](https://doc.dovecot.org/main/installation/upgrade/2.3-to-2.4.html)
- [Pigeonhole Sieve](https://doc.dovecot.org/main/core/plugins/sieve.html)
- [Dovecot TLS and secured connections](https://doc.dovecot.org/main/core/config/ssl.html)

## Author

[Jonas Mauer](https://github.com/jomrr)

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for the full license text.

Copyright (c) 2026 Jonas Mauer.
