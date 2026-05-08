"""CLI entry point for the RSC Database Status Tool."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Rubrik RSC Database Status Report Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m db_status run              Full end-to-end run
  python -m db_status fetch            Fetch only (save intermediate)
  python -m db_status events           Event checks from intermediate
  python -m db_status report           Generate reports from intermediate
  python -m db_status count            Quick count of all platforms
  python -m db_status test             Test connectivity
        """)

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Full run
    subparsers.add_parser("run", help="Full end-to-end run (all phases)")

    # Individual phases
    subparsers.add_parser("fetch", help="Phase 1-3: Fetch and parse only")

    events_p = subparsers.add_parser("events",
                                      help="Phase 4: Event checks only")
    events_p.add_argument("--input", "-i", help="Intermediate JSON file",
                          default=None)

    report_p = subparsers.add_parser("report",
                                      help="Phase 5: Generate reports only")
    report_p.add_argument("--input", "-i", help="Intermediate JSON file",
                          default=None)

    # Utilities
    subparsers.add_parser("count", help="Quick count all platforms")
    subparsers.add_parser("test", help="Test connectivity and licenses")

    args = parser.parse_args()

    if args.command == "run" or args.command is None:
        from .runners.full_run import run_full
        run_full()

    elif args.command == "fetch":
        from .runners.fetch_only import run_fetch
        run_fetch()

    elif args.command == "events":
        from .runners.events_only import run_events
        run_events(intermediate_file=getattr(args, "input", None))

    elif args.command == "report":
        from .runners.report_only import run_reports
        run_reports(intermediate_file=getattr(args, "input", None))

    elif args.command == "count":
        from .auth import TokenManager
        from .pagination import get_platform_count
        from .platforms.definitions import PLATFORMS
        tm = TokenManager(buffer_seconds=60)
        tm.get_token()
        total = 0
        for p in PLATFORMS:
            c = get_platform_count(tm, p["query_name"], p["uses_filter"])
            if c > 0:
                print(f"  ✅ {p['name']}: {c}")
                total += c
            else:
                print(f"  ⬜ {p['name']}: 0")
        print(f"\n  📊 Total: {total}")

    elif args.command == "test":
        from .auth import TokenManager
        from .graphql_client import test_query
        from .platforms.definitions import PLATFORMS
        tm = TokenManager(buffer_seconds=60)
        tm.get_token()
        print("[+] Authentication successful\n")
        for p in PLATFORMS:
            qn = p["query_name"]
            uf = p["uses_filter"]
            if uf:
                q = f"""query($first:Int!,$after:String,$filter:[Filter!]){{
                    {qn}(first:$first,after:$after,filter:$filter){{ count }}
                }}"""
                v = {"first": 1, "after": None, "filter": []}
            else:
                q = f"""query($first:Int!,$after:String){{
                    {qn}(first:$first,after:$after){{ count }}
                }}"""
                v = {"first": 1, "after": None}
            ok, err = test_query(tm, q, v)
            icon = "✅" if ok else "❌"
            msg = "OK" if ok else err[:60]
            print(f"  {icon} {p['name']}: {msg}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
