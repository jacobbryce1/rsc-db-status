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

- All credentials (`RSC_DOMAIN`, `RSC_CLIENT_ID`, `RSC_CLIENT_SECRET`) are loaded exclusively from environment variables or a `.env` file — never hardcoded in source.
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

### HTML Report Security

- All database field values written into the HTML report are escaped with `html.escape(..., quote=True)` before insertion. This covers all data-attribute values, table cell contents, option element values, and hover title attributes.
- The generated HTML includes a `Content-Security-Policy` meta tag restricting resource loading to prevent exfiltration via injected markup.
- A malicious RSC database name containing `<script>` tags will render as escaped text, not execute as JavaScript.

### Error Handling and Information Leakage

- Raw API response bodies are never printed to stdout or stderr. The `_safe_error_message()` helper in `graphql_client.py` extracts only the `message` field from error responses, bounded to 200 characters.
- Exception strings from `requests` (which may contain full URLs, headers, or partial payloads) are never propagated to user-visible output.
- If more than 10% of MSSQL event checks fail during a run, a prominent warning is emitted. This prevents systematic failures — such as lost API permissions or a connectivity disruption — from silently producing zeroed-out event data that looks like healthy results.

### Dependency Management

- All dependencies are pinned to exact versions in `requirements.txt`, including `certifi` for an explicit CA bundle.
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
| `db_status_work/raw_fetch_*.json` | Parsed database metadata | `.gitignore`, `chmod 0o600` |
| `db_status_work/events_*.json` | MSSQL event check results | `.gitignore`, `chmod 0o600` |
| `db_status_report_*.csv` | Full database status export | `chmod 0o600` |
| `db_status_report_*.json` | Full database status export | `chmod 0o600` |
| `db_status_report_*.html` | Interactive HTML dashboard | `chmod 0o600` |

> Intermediate files in `db_status_work/` contain raw database metadata fetched from RSC. Treat them with the same sensitivity as the final reports.

---

## Threat Model

This tool is designed for **single-user, trusted-host execution** — a security analyst or administrator running the tool on their own workstation or a bastion host to generate point-in-time reports. The threat model assumes:

- **The host is trusted.** The tool does not defend against a compromised OS or a malicious local user with access to the work directory.
- **The RSC instance is trusted.** The tool validates the domain at startup but does not defend against a compromised RSC instance returning malicious data at scale. The HTML escaping mitigates the most practical risk (XSS via database names), but consumers of the JSON and CSV outputs should treat field values as untrusted data in downstream processing.
- **The `.env` file is protected by the OS.** File permissions and `.gitignore` are the primary controls — not encryption. Do not store `.env` on shared or world-readable filesystems.
- **Network path to RSC is trusted.** TLS verification is enforced, but the tool does not implement certificate pinning. A compromised CA in the system trust store could perform MITM undetected.

---

## Security Contact

For questions about the security design of this tool, open a GitHub Discussion rather than a private report.