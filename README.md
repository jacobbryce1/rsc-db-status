# RSC Database Status Report Generator

Scalable, modular reporting tool for generating database protection status reports from Rubrik Security Cloud (RSC). Designed to handle environments from small labs to enterprise deployments with 100K+ databases across all supported platforms.

> **Not affiliated with Rubrik.** This is an independent, community-built tool. See [Legal & Disclaimer](#legal--disclaimer) for full details.

---

## Overview

This tool connects to your RSC instance via the GraphQL API and queries all supported database platforms in parallel. It produces three report formats — interactive HTML dashboard, CSV, and JSON — with status determined from multiple signals including missed snapshot events, SLA pause status, snapshot recency, and cloud native state.

**v1.0.0** includes a full security hardening pass reviewed against OWASP Top 10 (2021), NIST SP 800-53 Rev.5, CIS Controls v8, and ISO 27001:2022. See [Security](#security) for details.

---

## Features

| Feature | Details |
|---------|---------|
| 🗄️ Multi-platform coverage | 14 database platforms across on-prem, AWS, Azure, and GCP |
| ⚡ Parallel platform fetching | All platforms queried concurrently |
| 📊 Interactive HTML dashboard | Filterable, sortable report with status cards |
| 📥 CSV / JSON export | Full data export for reporting and integration |
| 🔑 Automatic token refresh | Never times out on long-running scans |
| 📐 Adaptive page sizing | Reduces on errors, restores on success |
| 🚦 Rate limiting | Respects API limits with token bucket algorithm |
| 🔍 Smart field discovery | Gracefully handles unlicensed or unavailable features |
| 💾 Resumable phases | Crash at Phase 4? Resume without re-fetching |
| 📈 Progress reporting | Rate, ETA, and batch status throughout |
| 🔴 MSSQL event detection | Per-database missed snapshot and missed recoverable range checks |

---

## Supported Platforms

| Platform | Query Endpoint | Notes |
|----------|---------------|-------|
| MSSQL | `mssqlDatabases` | Full event checks (missed snapshots / ranges) |
| Oracle | `oracleDatabases` | |
| PostgreSQL | `postgreSQLDbClusters` + `postgreSQLDatabases` | Clusters and individual DBs |
| MySQL | `mysqlDatabases` | |
| MongoDB | `mongoSources` + `mongoDatabases` + `mongoCollections` | 3 hierarchy levels |
| SAP HANA | `sapHanaDatabases` | |
| MS Exchange | `exchangeDatabases` | |
| AWS RDS | `awsNativeRdsInstances` | MySQL, PostgreSQL, SQL Server, Oracle, MariaDB |
| AWS Aurora | `awsNativeRdsClusters` | |
| Azure SQL | `azureSqlDatabases` | |
| Azure SQL MI | `azureSqlManagedInstanceDatabases` | Managed Instance |
| GCP Cloud SQL | `gcpCloudSqlInstances` | |
| DB2 | `db2Databases` | |
| Cassandra | `cassandraSources` + `cassandraKeyspaces` | |

---

## Scale Support

The tool automatically detects your environment size and selects the appropriate profile:

| Tier | DB Count | Page Size | Workers | Batch Size | Est. Runtime |
|------|----------|-----------|---------|------------|-------------|
| Small | < 1K | 200 | 2 | 50 | ~30 seconds |
| Medium | 1K–5K | 500 | 4 | 100 | ~2 minutes |
| Large | 5K–10K | 1,000 | 8 | 200 | ~4 minutes |
| XLarge | 10K–50K | 1,000 | 12 | 500 | ~12 minutes |
| XXLarge | 50K–100K+ | 1,000 | 16 | 1,000 | ~20 minutes |

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.8 or higher |
| Network | HTTPS access to your RSC instance (port 443) |
| RSC Permissions | Service account with read access to all database object types |
| Disk Space | ~50 MB plus intermediate files during large runs |
| RAM | 256 MB minimum; 1 GB+ recommended for XXLarge environments |

> You must have a valid API key and an active Rubrik Security Cloud subscription. This tool does not bypass licensing or provide unauthorised access to any Rubrik features.

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jacobbryce1/rsc-db-status.git
cd rsc-db-status

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your RSC credentials

# Run
python -m db_status run
```

---

## Configuration

### 1. Create your `.env` file

```bash
cp .env.example .env
```

```dotenv
# .env
RSC_DOMAIN=your-account.my.rubrik.com
RSC_CLIENT_ID=your-client-id-here
RSC_CLIENT_SECRET=your-client-secret-here
DB_STATUS_WORK_DIR=./db_status_work   # optional
```

> ⚠️ **Never commit `.env` to version control.** It is already listed in `.gitignore`.
> `RSC_DOMAIN` must be a valid hostname — the app validates this at startup and will
> refuse to run if the value is missing or malformed.

### 2. RSC Service Account Setup

1. Log into RSC → **Settings** → **Service Accounts**
2. Create a new service account
3. Assign read access to all database object types *(principle of least privilege)*
4. Copy the Client ID and Secret into your `.env` file

### 3. Tunable Settings

All tunable settings live in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `RSC_DOMAIN` | *(required)* | Your RSC instance hostname |
| `RSC_CLIENT_ID` | *(required)* | Service account client ID |
| `RSC_CLIENT_SECRET` | *(required)* | Service account secret |
| `DB_STATUS_WORK_DIR` | `./db_status_work` | Directory for intermediate files |
| `PAGE_SIZE` | 200 | Default page size (overridden by scale profile) |
| `STALE_SNAPSHOT_DAYS` | 7 | Days without snapshot = Warning |
| `OFFLINE_SNAPSHOT_DAYS` | 30 | Days without snapshot = Offline |
| `ENABLE_MSSQL_EVENT_CHECKS` | `True` | Per-DB event queries for MSSQL |
| `MISSED_SNAPSHOT_LOOKBACK_HOURS` | 72 | Event lookback window |
| `EVENT_ERROR_RATE_THRESHOLD` | 0.10 | Warn if >10% of event checks fail |

---

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `python -m db_status run` | Full end-to-end run (all phases) |
| `python -m db_status fetch` | Phase 1–3: fetch and parse only, save intermediate |
| `python -m db_status events --input FILE` | Phase 4: MSSQL event checks from intermediate file |
| `python -m db_status report --input FILE` | Phase 5: generate reports from intermediate file |
| `python -m db_status count` | Quick count of all platforms (no data fetched) |
| `python -m db_status test` | Test connectivity and license status per platform |

### Phased Execution (Recommended for Large Environments)

For stability at scale, run each phase independently:

```bash
# Phase 1–3: fetch all platforms, parse, save intermediate JSON
python -m db_status fetch

# Phase 4: run MSSQL event checks against intermediate data
python -m db_status events --input ./db_status_work/raw_fetch_20250101_120000.json

# Phase 5: generate reports from intermediate data (no API calls)
python -m db_status report --input ./db_status_work/raw_fetch_20250101_120000.json
```

### Status Detection

Status is determined from multiple signals in priority order:

| Signal | Status Assigned |
|--------|----------------|
| `isRelic` flag | Relic (Decommissioned) |
| SLA pause status | Warning (SLA Paused) |
| `unprotectableReasons` field | Offline (Unprotectable) |
| Cloud native state (stopped/failed) | Offline (state) |
| `isOnline` = false | Offline (DB Offline) |
| Snapshot age > `OFFLINE_SNAPSHOT_DAYS` | Offline (Stale: Nd) |
| Snapshot age > `STALE_SNAPSHOT_DAYS` | Warning (Stale: Nd) |
| No snapshots + active SLA | Warning (No Snapshots) |
| MSSQL: > 5 missed snapshots or ranges | Likely Offline (Many Misses) |
| MSSQL: any missed snapshots or ranges | Warning (Some Misses) |
| All clear | Online |

---

## Output Files

Each run generates the following:

| File | Description |
|------|-------------|
| `db_status_report_TIMESTAMP.csv` | Full CSV export, sortable in Excel |
| `db_status_report_TIMESTAMP.json` | JSON export with metadata and settings |
| `db_status_report_TIMESTAMP.html` | Interactive HTML dashboard |
| `db_status_work/raw_fetch_TIMESTAMP.json` | Intermediate fetch data (gitignored) |
| `db_status_work/events_TIMESTAMP.json` | Intermediate event check results (gitignored) |

All output files are written with `chmod 0o600` (owner read/write only).

### HTML Dashboard Features

- Status summary cards: Online / Offline / Warning / Relic counts
- Filter by: name search, status, platform, cluster, SLA
- Sortable columns (click any header)
- Color-coded status indicators
- Truncated fields with hover for full text

---

## Architecture

```
RSC GraphQL API
         |
         | Parallel platform queries (adaptive page sizing)
         v
+--------------------------------+
|   TokenManager                 |
|   - Auto-refresh before expiry |
|   - Thread-safe locking        |
|   - Force refresh on 401/403   |
+---------------+----------------+
                |
                v
+--------------------------------+
|   Platform Fetcher             |
|   - Smart field discovery      |
|   - Adaptive pagination        |
|   - Parallel workers           |
+---------------+----------------+
                |
                v
+--------------------------------+
|   MSSQL Event Checker          |
|   - Missed snapshot queries    |
|   - Missed range queries       |
|   - Batched parallel execution |
+---------------+----------------+
                |
                v
+--------------------------------+
|   Report Generator             |
|   - Interactive HTML dashboard |
|   - CSV export                 |
|   - JSON export                |
|   - Console summary            |
+--------------------------------+
```

---

## Project Structure

```
rsc-db-status/
├── .env.example                    # Template for credentials
├── .gitignore
├── README.md
├── requirements.txt                # Pinned dependencies
├── db_status/
│   ├── __init__.py
│   ├── __main__.py                 # python -m db_status entry point
│   ├── main.py                     # CLI argument parsing
│   ├── config.py                   # All settings, validation, scale profiles
│   ├── auth.py                     # TokenManager (auto-refresh, SecretStr)
│   ├── graphql_client.py           # API execution, rate limiting, TLS enforcement
│   ├── query_builder.py            # Smart field discovery
│   ├── pagination.py               # Adaptive paginated fetching
│   ├── parsers.py                  # Node parsing, status determination
│   ├── events.py                   # MSSQL event checks (batched, parallel)
│   ├── security.py                 # Path validation, secure file writes
│   ├── platforms/
│   │   ├── __init__.py
│   │   └── definitions.py          # All platform configs and candidate fields
│   ├── runners/
│   │   ├── __init__.py
│   │   ├── full_run.py             # All phases end-to-end
│   │   ├── fetch_only.py           # Phase 1–3 only
│   │   ├── events_only.py          # Phase 4 only
│   │   └── report_only.py          # Phase 5 only
│   └── reports/
│       ├── __init__.py
│       ├── console.py              # Terminal summary
│       ├── csv_report.py           # CSV export
│       ├── json_report.py          # JSON export
│       └── html_report.py          # Interactive HTML dashboard
└── db_status_work/                 # Runtime intermediate files (gitignored)
```

---

## Security

This tool was reviewed against **OWASP Top 10 (2021)**, **NIST SP 800-53 Rev.5**, **CIS Controls v8**, and **ISO 27001:2022**. The following hardening measures are in place:

### Credential Protection
- Credentials are loaded exclusively from environment variables or `.env` — never hardcoded in source.
- `RSC_DOMAIN` is validated against a strict hostname regex at startup. Any invalid or missing value raises an immediate error, preventing credential redirection to attacker-controlled hosts.
- The app validates all required credentials are present before any API calls are made.

### Secure File Handling
- All output files (CSV, JSON, HTML) and intermediate files are written with `chmod 0o600` — owner read/write only.
- The `--input` argument for phased execution is validated against the work directory to prevent path traversal attacks.

### Network Security
- TLS certificate verification is explicitly enforced (`verify=True`) on all API calls. SSL errors are never retried and always raise immediately.
- All communication is HTTPS only.

### Error Handling
- Raw API response bodies and exception details are never printed to stdout. All error messages are sanitised before display.
- If more than 10% of MSSQL event checks fail, a prominent warning is emitted — systematic failures (lost permissions, connectivity issues) cannot silently produce zeroed-out results.

### Dependency Auditing
All dependencies are pinned to exact versions in `requirements.txt`. Run a local audit with:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

### Reporting Vulnerabilities
See [SECURITY.md](SECURITY.md) for the responsible disclosure process. Please do **not** open a public GitHub issue for security vulnerabilities.

---

## Troubleshooting

**"Configuration errors" on startup**
Check that `RSC_DOMAIN`, `RSC_CLIENT_ID`, and `RSC_CLIENT_SECRET` are all set in your `.env` file. `RSC_DOMAIN` must be a valid hostname (e.g. `your-account.my.rubrik.com`) — no `https://` prefix.

**"Authentication failed"**
Verify your `RSC_CLIENT_ID` and `RSC_CLIENT_SECRET`. Confirm the service account is active in RSC Settings → Service Accounts.

**"Feature not licensed"**
Some platforms may not be enabled on your RSC instance. The tool skips them automatically and reports which ones are unavailable. Use `python -m db_status test` to see a per-platform license check.

**Timeouts on large environments**
Use phased execution (`fetch` → `events` → `report`). The tool automatically reduces page size on repeated failures. Check network connectivity to RSC.

**Rate limiting (429 responses)**
The tool respects `Retry-After` headers and uses a token bucket rate limiter. If you see frequent 429s, the scale profile manages this automatically. You can also reduce `rate_limit` in `config.py`.

**"Invalid --input path" error**
The `--input` file must be inside the configured work directory (`DB_STATUS_WORK_DIR`). Paths outside this directory are rejected for security reasons.

---

## Testing

Test connectivity and per-platform license status:

```bash
python -m db_status test
```

Quick count of all platforms without fetching data:

```bash
python -m db_status count
```

Run the dependency security audit locally:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```

---

## Updating

```bash
cd rsc-db-status
source venv/bin/activate
git pull
pip install -r requirements.txt    # picks up any new pinned deps
./run.sh
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -am 'Add feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

Please run `pip-audit -r requirements.txt` before submitting and include test coverage for any new functionality.

---

## Legal & Disclaimer

This project is an **independent, open-source tool** and is **not affiliated with, authorized, maintained, sponsored, or endorsed by Rubrik, Inc.** in any way. All product and company names are the registered trademarks of their respective owners. The use of any trade name or trademark is for identification and reference purposes only and does not imply any affiliation with or endorsement by the trademark holder.

This software is provided **"as-is," without warranty of any kind**, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, and non-infringement. Use of this tool is entirely at your own risk. The authors and contributors are not responsible for any data loss, API rate-limit overages, account suspensions, security incidents, or other damages resulting from the use or misuse of this software.

You must have a valid API key and an active subscription or license for Rubrik Security Cloud (RSC). This software does not bypass any licensing checks or provide unauthorised access to Rubrik features.

For questions about the security design of this tool, open a GitHub Discussion. To report a vulnerability, follow the process in [SECURITY.md](SECURITY.md).

---

## License

[Apache 2.0](LICENSE)