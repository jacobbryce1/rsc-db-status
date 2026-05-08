"""Console report output."""


def print_console_report(databases: list, token_stats: dict, elapsed: float):
    """Print summary to terminal."""
    total = len(databases)
    platforms = {}
    clusters = {}
    sla_counts = {}
    status_counts = {}
    relics = 0

    for db in databases:
        p = db.get("platform", "Unknown")
        platforms[p] = platforms.get(p, 0) + 1
        c = db.get("cluster_name", "Unknown")
        clusters[c] = clusters.get(c, 0) + 1
        s = db.get("sla_name", "No SLA")
        sla_counts[s] = sla_counts.get(s, 0) + 1
        st = db.get("event_status", "Unknown")
        status_counts[st] = status_counts.get(st, 0) + 1
        if db.get("is_relic"):
            relics += 1

    print("\n" + "=" * 60)
    print("  🔴🟢 DATABASE STATUS REPORT SUMMARY")
    print("=" * 60)
    print(f"  Total Databases: {total}")
    print(f"  Relics: {relics}")
    print(f"  Token Refreshes: {token_stats.get('refresh_count', 0)}")
    print(f"  Elapsed Time: {elapsed:.1f}s")
    print(f"\n  📊 By Status:")
    for st, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        icon = "🟢" if "Online" in st else "🔴" if "Offline" in st else "⚠️"
        print(f"    {icon} {st}: {count}")
    print(f"\n  🖥️  By Platform:")
    for p, count in sorted(platforms.items(), key=lambda x: -x[1]):
        print(f"    {p}: {count}")
    print(f"\n  🏢 By Cluster (top 15):")
    for c, count in sorted(clusters.items(), key=lambda x: -x[1])[:15]:
        print(f"    {c}: {count}")
    if len(clusters) > 15:
        print(f"    ... and {len(clusters) - 15} more clusters")
    print(f"\n  📋 By SLA (top 15):")
    for s, count in sorted(sla_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    {s}: {count}")
    print("=" * 60)
