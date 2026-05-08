"""Phase 5 only: Generate reports from intermediate JSON.

SECURITY F-02: intermediate file path validated via safe_input_path().
"""
import json
from ..config import (
    INTERMEDIATE_FILE, INTERMEDIATE_DIR,
    OUTPUT_CSV, OUTPUT_JSON, OUTPUT_HTML
)
from ..reports.console import print_console_report
from ..reports.csv_report import write_csv_report
from ..reports.json_report import write_json_report
from ..reports.html_report import write_html_report
from ..security import safe_input_path


def run_reports(intermediate_file: str = None):
    """Generate all reports from saved intermediate data."""
    if intermediate_file is None:
        intermediate_file = INTERMEDIATE_FILE

    # SECURITY F-02: validate the path is inside the work directory
    try:
        intermediate_file = safe_input_path(intermediate_file, INTERMEDIATE_DIR)
    except (ValueError, FileNotFoundError) as e:
        print(f"[!] {e}")
        return

    with open(intermediate_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    databases = data["databases"]
    token_stats = {"refresh_count": 0, "token_ttl": 0, "buffer_seconds": 60}

    print(f"[*] Generating reports from {len(databases)} records...")
    print_console_report(databases, token_stats, 0)
    write_csv_report(databases, OUTPUT_CSV)
    write_json_report(databases, OUTPUT_JSON)
    write_html_report(databases, OUTPUT_HTML)
    print("[+] All reports generated.")