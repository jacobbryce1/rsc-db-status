# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ Yes    |

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

This tool handles RSC service account credentials and produces detailed reports of your backup estate — including database names, cluster topology, SLA assignments, snapshot history, and protection status. Responsible disclosure is important.

### How to Report

Use **GitHub's private vulnerability reporting**:

1. Go to the [Security tab](../../security) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details — include steps to reproduce, impact assessment, and any suggested remediation if you have one

We aim to acknowledge reports within **3 business days** and provide a fix or mitigation within **14 days** for high/critical issues.

### What to Include

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept code if applicable)
- The version(s) affected
- Any suggested fix

### Out of Scope

- Vulnerabilities in Rubrik Security Cloud (RSC) itself — report those directly to Rubrik
- Denial-of-service against the local Python process
- Issues that require physical access to the machine running the tool
- Rate-limit overages caused by misconfigured scale profiles

---

## Security Design

### Credential Handling

- All credentials (`RSC_DOMAIN`, `RSC_CLIENT_ID`, `RSC_CLIENT_SECRET`) are loaded exclusively from environment variables or a `.env` file via `python-dotenv` — never hardcoded in source.
- `RSC_DOMAIN` is validated against a strict hostname regex at startup. An invalid, missing, or placeholder value raises an immediate error and halts execution, preventing credential redirection to attacker-controlled hosts.
- The `.env` file is listed in `.gitignore` and must never be committed to version control.
- Token values are never written to stdout, log files, or exception messages. Only TTL metadata (duration in seconds) is logged.

### Token Lifecycle

- `TokenManager` proactively refreshes the access token 60 seconds before expiry, preventing mid-run failures on long scans.
- Token refresh is thread-safe — a single lock prevents concurrent threads from triggering redundant refresh calls.
- On receipt of a 401 or 403 response, the token is force-refreshed and the request retried.
- SSL errors during authentication are never retried — they raise immediately with a clear message, preventing silent MITM exposure.

### Network Security

- TLS certificate verification is explicitly enforced (`verify=True`) on every `requests` call in both `auth.py` and `graphql_client.py`.
- `SSLError` is caught and raised as a fatal error — it is never caught by the generic retry loop and never silently bypassed.
- All RSC API communication is HTTPS only. There is no HTTP fallback.
- The RSC GraphQL endpoint is derived from the validated `RSC_DOMAIN` — it cannot be redirected by environment variable injection.

### Output File Security

- All output files — HTML dashboard, CSV, JSON, and intermediate phase files — are written with `chmod 0o600` (owner read/write only) immediately at file creation using `os.open()` with `O_CREAT`.
- Permissions are applied at the file descriptor level before any data is written, closing the race window that would exist with a post-write `chmod`.
- Output files contain sensitive infrastructure metadata (database names, cluster topology, SLA assignments, snapshot dates, protection status) and should be treated accordingly.

### Path Traversal Prevention

- The `--input` argument used in phased execution (`events` and `report` commands) is resolved and validated against the configured work directory (`DB_STATUS_WORK_DIR`) before any file operation.
- Paths that resolve outside the work directory are rejected with a clear error. This prevents `--input ../../../../etc/passwd` style traversal attacks.
- The validation uses `pathlib.Path.resolve()` and `Path.relative_to()` — symbolic link traversal is handled correctly.

### Encrypted Disk Cache

- After each successful fetch and parse, all database records are written to an AES-256 encrypted cache file (`.db_status_cache.bin`) using the `cryptography` library's Fernet symmetric encryption scheme.
- A random 256-bit key is generated on first run and written to `.db_status_cache.key` with `chmod 0o600` (owner read/write only). The cache data file is opaque ciphertext — it cannot be read without the key file.
- Both `.db_status_cache.bin` and `.db_status_cache.key` are excluded from version control via `.gitignore`.
- If the `cryptography` package is unavailable, disk cache is disabled gracefully — the tool continues without persistence rather than falling back to plaintext storage.
- The cache is subject to a configurable TTL (`CACHE_TTL_HOURS`, default 12h). Expired caches are ignored and regenerated on the next run.

> **Treat `.db_status_cache.key` like a password.** It is the sole decryption key for the cache. Deleting it invalidates the cache file and forces a fresh API fetch on the next run.

### HTML Report Security

- The HTML report uses a virtual scrolling architecture: all records are serialised as a JSON array embedded in a `<script>` tag. Only visible rows (~30–50 at any time) are rendered in the DOM by JavaScript.
- Field values in the JSON payload are serialised via Python's `json.dumps()`, which handles all necessary escaping. Values inserted directly into HTML (headers, notes) are escaped with `html.escape(..., quote=True)`.
- The generated HTML includes a `Content-Security-Policy` meta tag restricting resource loading to prevent exfiltration via injected markup.
- A malicious RSC database name containing `<script>` tags will be serialised as a JSON string literal and rendered as text by the virtual scroller — it will not execute as JavaScript.

### Audit Trail Integrity

- During Phase 3b (snapshot date inheritance), child objects that lack their own snapshot may have their `event_status` promoted based on a parent cluster's or MongoDB Collection's snapshot date.
- Before any such mutation, the original status is written to `raw_event_status`. This write happens unconditionally for every record — records not affected by inheritance receive an empty string, while records whose status was derived receive the pre-inheritance value.
- `raw_event_status` is included in all three report outputs (CSV column, JSON field, HTML table column) so the pre-inheritance protection signal is never silently discarded. Investigators can filter on this field to distinguish genuinely protected databases from those whose status was derived.
- The inheritance logic uses only hardcoded constant strings (`"Online (Inherited from Parent)"`, `"Online (Via Collections)"`) when mutating `event_status`. No user-controlled or API-sourced data flows into these status strings, eliminating injection risk through this path.

### Memory Safety and Temporary Data

- During Phase 3b, raw GraphQL node data is temporarily attached to each parsed record as `_raw_node` to make `physicalPath` available for parent/child resolution without a second API call.
- The cleanup of `_raw_node` is performed inside a `try/finally` block in `run_full()`, guaranteeing that raw node data is removed from memory regardless of whether `inherit_snapshot_dates()` raises an exception. This prevents raw GraphQL payloads from persisting in the process beyond Phase 3b in any failure mode.
- Raw API response bodies are never printed to stdout or stderr. The `_safe_error_message()` helper in `graphql_client.py` extracts only the `message` field from error responses, bounded to 200 characters.
- Exception strings from `requests` (which may contain full URLs, headers, or partial payloads) are never propagated to user-visible output.

### Error Handling and Information Leakage

- If more than 10% of MSSQL event checks fail during a run, a prominent warning is emitted. This prevents systematic failures — such as lost API permissions or a connectivity disruption — from silently producing zeroed-out event data that looks like healthy results.

### Dependency Management

- All dependencies are pinned to exact versions in `requirements.txt`, including `certifi` for an explicit CA bundle.
- `python-dotenv` is used solely to load the `.env` file at startup — it has no network access and no write capability.
- `cryptography` provides the Fernet AES-256 implementation for the disk cache. No other use of the cryptography package is made.
- `pip-audit` should be run before each release and periodically during development:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

---

## Files Generated at Runtime

| File | Contents | Protected by |
|------|----------|--------------|
| `.env` | RSC credentials | `.gitignore`, OS file permissions |
| `.db_status_cache.key` | Fernet AES-256 encryption key | `.gitignore`, `chmod 0o600` |
| `.db_status_cache.bin` | AES-encrypted parsed database records | `.gitignore`, `chmod 0o600`, ciphertext |
| `db_status_work/raw_fetch_*.json` | Parsed database metadata | `.gitignore`, `chmod 0o600` |
| `db_status_work/events_*.json` | MSSQL event check results | `.gitignore`, `chmod 0o600` |
| `db_status_report_*.csv` | Full database status export (incl. `raw_event_status`) | `chmod 0o600` |
| `db_status_report_*.json` | Full database status export (incl. `raw_event_status`) | `chmod 0o600` |
| `db_status_report_*.html` | Interactive HTML dashboard (incl. Raw Status column) | `chmod 0o600` |

> Intermediate files in `db_status_work/` and the disk cache contain database metadata fetched from RSC. Treat them with the same sensitivity as the final reports. The cache files (`.db_status_cache.*`) should be backed up separately if you need cache persistence across reinstalls — deleting `.db_status_cache.key` permanently invalidates the cache data file.

---

## Threat Model

This tool is designed for **single-user, trusted-host execution** — a security analyst or administrator running the tool on their own workstation or a bastion host to generate point-in-time reports. The threat model assumes:

- **The host is trusted.** The tool does not defend against a compromised OS or a malicious local user with access to the work directory.
- **The RSC instance is trusted.** The tool validates the domain at startup but does not defend against a compromised RSC instance returning malicious data at scale. The HTML escaping mitigates the most practical risk (XSS via database names), but consumers of the JSON and CSV outputs should treat field values as untrusted data in downstream processing.
- **The `.env` file is protected by the OS.** File permissions and `.gitignore` are the primary controls — not encryption. Do not store `.env` on shared or world-readable filesystems.
- **Network path to RSC is trusted.** TLS verification is enforced, but the tool does not implement certificate pinning. A compromised CA in the system trust trust store could perform MITM undetected.

---

## Security Contact

For questions about the security design of this tool, open a GitHub Discussion rather than a private report.