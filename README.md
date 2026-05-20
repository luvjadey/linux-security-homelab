# Linux Security Homelab

**A hands-on enterprise-grade Linux security lab built to simulate real-world attack and defense scenarios - covering SSH hardening, firewall policy, intrusion prevention, audit logging, and automated threat detection. This is a personal homelab project built in an isolated virtual environment.**

---

## Overview

This project demonstrates practical implementation of core Linux security principles on a self-hosted Ubuntu Server instance. The goal was to build a hardened server from scratch, simulate a real brute-force attack, and prove that the defensive controls catch and respond to it automatically - without human intervention.

Every configuration decision in this lab mirrors what you'd find in production enterprise environments: least-privilege access, layered defenses, immutable audit trails, and automated response.

---

## Environment

| Component | Details |
|---|---|
| OS | Ubuntu Server 26.04 LTS |
| Hypervisor | VirtualBox (Bridged Adapter) |
| Host Machine | Windows (PowerShell SSH client) |
| VM IP | 10.20.24.98 |
| SSH Client | OpenSSH via PowerShell + Ed25519 keys |

---

## Phase 1 - Secure Linux Server

### 1. SSH Hardening

SSH is the primary remote access vector and the most commonly targeted service in brute-force attacks. The following hardening measures were applied to `/etc/ssh/sshd_config`:

```
PermitRootLogin no          # Eliminates direct root compromise via SSH
MaxAuthTries 3              # Limits attempts per connection session
PasswordAuthentication no   # Enforces key-only authentication
PubkeyAuthentication yes    # Ed25519 key pairs only
```

**Why Ed25519?** Ed25519 is an elliptic curve algorithm that is faster, smaller, and more resistant to side-channel attacks than RSA-2048. It produces 64-byte signatures vs RSA's 256-byte, with equivalent or stronger security guarantees.

Remote access is established from the Windows host via:
```powershell
ssh jade@10.20.24.98
```

---

### 2. UFW Firewall

UFW (Uncomplicated Firewall) provides a default-deny perimeter. Only explicitly allowed services can receive inbound traffic.

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw enable
```

**Result:** All inbound ports are blocked except SSH (port 22). This eliminates the entire attack surface of any unintended exposed services.

Verify status:
```bash
sudo ufw status verbose
```

---

### 3. Fail2Ban - Automated Intrusion Prevention

Fail2Ban monitors system logs for repeated authentication failures and automatically bans offending IPs using firewall rules. It acts as an automated response layer — no human intervention required.

**Configuration (`/etc/fail2ban/jail.local`):**
```ini
[DEFAULT]
ignoreself = false

[sshd]
enabled = true
maxretry = 5
findtime = 600
bantime = 600
```

| Parameter | Value | Meaning |
|---|---|---|
| `maxretry` | 5 | Ban after 5 failed attempts |
| `findtime` | 600 | Within a 10-minute window |
| `bantime` | 600 | Ban lasts 10 minutes |
| `ignoreself` | false | Loopback attacks are not exempt |

Check jail status:
```bash
sudo fail2ban-client status sshd
```

---

### 4. Auditd - Immutable Audit Logging

Auditd provides kernel-level syscall logging for critical system files. Unlike application logs, auditd operates below the application layer — it cannot be bypassed by a compromised application.

**Custom rules watch three high-value targets:**

```bash
# Monitor critical system files for any write or attribute changes
-w /etc/passwd -p wa -k passwd_changes
-w /etc/ssh/sshd_config -p wa -k sshd_config_changes
-w /etc/sudoers -p wa -k sudoers_changes
```

| File | Why It Matters |
|---|---|
| `/etc/passwd` | User account creation, UID manipulation |
| `/etc/ssh/sshd_config` | Backdoor insertion via SSH config tampering |
| `/etc/sudoers` | Privilege escalation by adding unauthorized sudo access |

Query audit events:
```bash
sudo ausearch -m USER_AUTH --start today
sudo ausearch -k passwd_changes
```

---

### 5. Brute-Force Attack Simulation (Hydra)

To prove the defensive stack works end-to-end, a controlled SSH brute-force attack was simulated using Hydra — a real-world penetration testing tool.

**Attack command:**
```bash
hydra -l fakeuser -P ~/wordlist.txt ssh://127.0.0.1 -t 4 -V
```

| Flag | Meaning |
|---|---|
| `-l fakeuser` | Non-existent username (intentional) |
| `-P wordlist.txt` | 20+ password wordlist |
| `ssh://127.0.0.1` | Targeting the VM's own loopback interface |
| `-t 4` | 4 parallel threads |
| `-V` | Verbose - shows every attempt |

**Attack flow:**
1. Hydra begins making rapid SSH login attempts
2. Fail2Ban detects failed attempts against `127.0.0.1` in the system journal
3. After 5 failures within the `findtime` window, Fail2Ban issues a ban
4. Hydra receives `Connection reset by peer` - the IP is firewalled
5. Fail2Ban logs the ban action with a precise timestamp

**Fail2Ban log output confirming the ban:**
```
fail2ban.filter   INFO    [sshd] Found 127.0.0.1 - 2026-05-20 19:30:22
fail2ban.filter   INFO    [sshd] Found 127.0.0.1 - 2026-05-20 19:30:23
fail2ban.filter   INFO    [sshd] Found 127.0.0.1 - 2026-05-20 19:30:23
fail2ban.filter   INFO    [sshd] Found 127.0.0.1 - 2026-05-20 19:30:23
fail2ban.filter   INFO    [sshd] Found 127.0.0.1 - 2026-05-20 19:30:23
fail2ban.actions  NOTICE  [sshd] Ban 127.0.0.1
```

**Post-attack Fail2Ban status:**
```
Status for the jail: sshd
|- Filter
|  |- Currently failed: 0
|  |- Total failed: 20
|  `- Journal matches: _SYSTEMD_UNIT=ssh.service + _COMM=sshd
`- Actions
   |- Currently banned: 1
   |- Total banned: 1
   `- Banned IP list: 127.0.0.1
```

> **Result: The brute-force attack was automatically detected and blocked. Zero valid credentials were found. The attacker IP was banned without any manual intervention.**

---

### 6. Python Log Parser (`log_parser.py`)

A custom Python script that parses `/var/log/auth.log` to surface suspicious SSH activity - repeated failures, invalid user attempts, and connection anomalies.

**What it does:**
- Reads and parses `auth.log` line by line
- Flags IPs with repeated failed authentication attempts
- Detects invalid username attempts (a common credential stuffing indicator)
- Outputs a clean summary with flagged IPs and attempt counts
- Prints `"No suspicious activity detected"` when the log is clean

**How to run:**
```bash
python3 ~/log_parser.py
```

**Why this matters:** In environments without a SIEM (Security Information and Event Management system), a lightweight log parser like this fills the gap — giving an operator a fast, human-readable view of authentication anomalies without requiring commercial tooling. This is the foundation of the centralized logging work in Phase 2.

---

## Defense-in-Depth Summary

This lab implements a layered security model - each control is independent, so failure of one layer does not compromise the others:

```
[ Attacker ]
     |
     v
[ UFW Firewall ]          - Layer 1: Block unauthorized ports entirely
     |
     v
[ SSH Hardening ]         - Layer 2: No root, no passwords, key-only access
     |
     v
[ Fail2Ban ]              - Layer 3: Auto-ban IPs exceeding failure threshold
     |
     v
[ Auditd ]                - Layer 4: Kernel-level immutable audit trail
     |
     v
[ Log Parser ]            - Layer 5: Human-readable anomaly detection
```

---

## Files

```
├── README.md
├── log_parser.py           # Python auth.log parser
├── screenshots/
│   ├── fail2ban_before.png     # Status before attack (banned: 0)
│   ├── hydra_attack.png        # Hydra running verbose output
│   ├── fail2ban_after.png      # Status after attack (banned: 1)
│   ├── fail2ban_log.png        # Ban action in fail2ban.log
│   └── auth_log.png            # Invalid user attempts in auth.log
```

---

## Roadmap

- **Phase 2** - Enterprise Features: WireGuard VPN, NGINX reverse proxy, Wazuh SIEM, Grafana monitoring dashboard
- **Phase 3** - Detection & Monitoring: Suricata IDS, OpenVAS vulnerability scanning, automated alerting pipelines

---

## Tools & Technologies

`Ubuntu Server` `UFW` `OpenSSH` `Ed25519` `Fail2Ban` `Auditd` `Hydra` `Python` `VirtualBox` `PowerShell`
