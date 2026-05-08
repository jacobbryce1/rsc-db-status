
# RSC Database Status Report Generator

A scalable, modular tool for generating database status reports from Rubrik Security Cloud (RSC). Designed to handle environments from small labs to enterprise deployments with 100K+ databases.

## Features

- **Automatic token refresh** — never times out on long runs
- **Parallel platform fetching** — all platforms queried concurrently
- **Adaptive page sizing** — reduces on errors, restores on success
- **Rate limiting** — respects API limits with token bucket algorithm
- **Smart field discovery** — gracefully handles unlicensed features
- **Resumable phases** — crash at Phase 4? Resume without re-fetching
- **Progress reporting** — rate, ETA, batch status throughout
- **MSSQL event detection** — uses missed snapshots and missed recoverable ranges for status inference
- **Interactive HTML dashboard** — filterable, sortable report with status cards

## Supported Platforms

| Platform | Query Endpoint | Notes |
|----------|---------------|-------|
| MSSQL | `mssqlDatabases` | Full event checks (missed snapshots/ranges) |
| Oracle | `oracleDatabases` | |
| PostgreSQL | `postgreSQLDbClusters` + `postgreSQLDatabases` | Clusters and individual DBs |
| MySQL | `mysqlDatabases` | |
| MongoDB | `mongoSources` + `mongoDatabases` + `mongoCollections` | 3 hierarchy levels |
| SAP HANA | `sapHanaDatabases` | |
| MS Exchange | `exchangeDatabases` | |
| AWS RDS (all engines) | `awsNativeRdsInstances` | MySQL, PostgreSQL, SQL Server, Oracle, MariaDB |
| AWS Aurora | `awsNativeRdsClusters` | |
| Azure SQL | `azureSqlDatabases` | |
| Azure SQL MI | `azureSqlManagedInstanceDatabases` | Managed Instance |
| GCP Cloud SQL | `gcpCloudSqlInstances` | |
| DB2 | `db2Databases` | |
| Cassandra | `cassandraSources` + `cassandraKeyspaces` | |

## Scale Support

The tool automatically detects your environment size and selects the appropriate profile:

| Tier | DB Count | Page Size | Workers | Batch Size | Est. Runtime |
|------|----------|-----------|---------|------------|-------------|
| Small | <1K | 200 | 2 | 50 | ~30s |
| Medium | 1K-5K | 500 | 4 | 100 | ~2 min |
| Large | 5K-10K | 1000 | 8 | 200 | ~4 min |
| XLarge | 10K-50K | 1000 | 12 | 500 | ~12 min |
| XXLarge | 50K-100K+ | 1000 | 16 | 1000 | ~20 min |

## Status Detection

Status is determined using multiple signals:

- `unprotectableReasons` field
- Missed snapshot events (MSSQL per-database query)
- Missed recoverable range events (MSSQL per-database query)
- Snapshot recency (configurable staleness threshold)
- SLA pause status
- Cloud native state (GCP, AWS RDS)
- `isOnline` flag (when available)
- `isRelic` flag

## Prerequisites

- Python 3.8+
- A Rubrik Security Cloud service account with read access
- Network access to your RSC instance

## Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/rsc-db-status.git
cd rsc-db-status

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your RSC credentials
#Configuration
Set environment variables directly or in your .env file:
export RSC_DOMAIN="your-account.my.rubrik.com"
export RSC_CLIENT_ID="your-client-id"
export RSC_CLIENT_SECRET="your-client-secret"
export DB_STATUS_WORK_DIR="./db_status_work"   # optional

##Tunable Settings (in config.py)
| Setting | Default | Description |
|---------|---------|-------------|
| `PAGE_SIZE` | 200 | Default page size (overridden by scale profile) |
| `STALE_SNAPSHOT_DAYS` | 7 | Days without snapshot = Warning |
| `OFFLINE_SNAPSHOT_DAYS` | 30 | Days without snapshot = Offline |
| `ENABLE_MSSQL_EVENT_CHECKS` | True | Per-DB event queries for MSSQL |
| `MISSED_SNAPSHOT_LOOKBACK_HOURS` | 72 | Event lookback window |

##Usage
Full Run (All Phases)
python -m db_status run

Test Connectivity
python -m db_status test

Quick Count (No Data Fetched)
python -m db_status count

Phased Execution (Recommended for Large Environments)
For stability at scale, run each phase independently:
# Phase 1-3: Fetch all platforms, parse, save intermediate JSON
python -m db_status fetch

# Phase 4: Run MSSQL event checks against intermediate data
python -m db_status events --input ./db_status_work/raw_fetch_20250101_120000.json

# Phase 5: Generate reports from intermediate data (no API calls)
python -m db_status report --input ./db_status_work/raw_fetch_20250101_120000.json

Output Files
Each run generates three report files:
| File | Description |
|------|-------------|
| `db_status_report_TIMESTAMP.csv` | Full CSV export, sortable in Excel |
| `db_status_report_TIMESTAMP.json` | JSON with metadata and settings |
| `db_status_report_TIMESTAMP.html` | Interactive HTML dashboard |

HTML Report Features
Dashboard cards with Online/Offline/Warning/Relic counts
Filterable by: name search, status, platform, cluster, SLA
Sortable columns (click headers)
Color-coded status indicators
Truncated fields with hover for full text

Project Structure
rsc-db-status/
├── .env.example              # Template for credentials
├── .gitignore
├── README.md
├── requirements.txt
├── db_status/
│   ├── __init__.py
│   ├── __main__.py           # python -m db_status entry
│   ├── main.py               # CLI argument parsing
│   ├── config.py             # All settings and scale profiles
│   ├── auth.py               # TokenManager (auto-refresh)
│   ├── graphql_client.py     # API execution, rate limiting
│   ├── query_builder.py      # Smart field discovery
│   ├── pagination.py         # Adaptive paginated fetching
│   ├── parsers.py            # Node parsing, status determination
│   ├── events.py             # MSSQL event checks (batched)
│   ├── platforms/
│   │   ├── __init__.py
│   │   └── definitions.py    # All platform configs and fields
│   ├── runners/
│   │   ├── __init__.py
│   │   ├── full_run.py       # All phases end-to-end
│   │   ├── fetch_only.py     # Phase 1-3 only
│   │   ├── events_only.py    # Phase 4 only
│   │   └── report_only.py    # Phase 5 only
│   └── reports/
│       ├── __init__.py
│       ├── console.py        # Terminal summary
│       ├── csv_report.py     # CSV export
│       ├── json_report.py    # JSON export
│       └── html_report.py    # Interactive HTML
└── db_status_work/           # Runtime intermediate files (gitignored)

How Token Refresh Works
The TokenManager class handles authentication automatically:

On first call, authenticates and stores the token + expiry time
Before each API call, checks if token will expire within 60 seconds
If near expiry, proactively refreshes before the request
If a 401/403 is received mid-request, forces immediate refresh and retries
Thread-safe — works correctly with parallel fetching
Troubleshooting
"Feature not licensed"
Some platforms may not be enabled on your RSC instance. The tool will skip them automatically and report which ones are unavailable.

Timeouts on large environments
Use phased execution (fetch → events → report)
The tool will automatically reduce page size on repeated failures
Check network connectivity to RSC
Rate limiting (429 responses)
The tool respects Retry-After headers and uses a token bucket rate limiter. If you see frequent 429s, the scale profile will manage this, but you can also reduce rate_limit in config.py.

Contributing
Fork the repository
Create a feature branch (git checkout -b feature/my-feature)
Commit your changes (git commit -am 'Add feature')
Push to the branch (git push origin feature/my-feature)
Open a Pull Request

License