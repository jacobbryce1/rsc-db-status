"""
Node parsing and status determination.
Converts raw GraphQL nodes into flat report rows.
"""
from datetime import datetime
from .config import STALE_SNAPSHOT_DAYS, OFFLINE_SNAPSHOT_DAYS


def determine_status(node: dict, newest_snapshot: dict) -> str:
    """Determine database status based on available signals."""
    if node.get("isRelic"):
        return "Relic (Decommissioned)"

    pause_status = node.get("slaPauseStatus", "")
    if pause_status and pause_status.upper() not in ("", "NOT_PAUSED"):
        return "Warning (SLA Paused)"

    reasons = node.get("unprotectableReasons", [])
    if isinstance(reasons, list) and len(reasons) > 0:
        return "Offline (Unprotectable)"

    state = node.get("state", "")
    if state and state.upper() in ("SUSPENDED", "STOPPED", "FAILED"):
        return f"Offline ({state})"

    rds_status = node.get("status", "")
    if rds_status and rds_status.lower() in (
        "stopped", "failed", "inaccessible-encryption-credentials"
    ):
        return f"Offline ({rds_status})"

    if node.get("isOnline") is False:
        return "Offline (DB Offline)"

    snap_date = newest_snapshot.get("date", "")
    if snap_date:
        try:
            snap_dt = datetime.fromisoformat(
                snap_date.replace("Z", "+00:00"))
            age_days = (datetime.now(snap_dt.tzinfo) - snap_dt).days
            if age_days > OFFLINE_SNAPSHOT_DAYS:
                return f"Offline (Stale: {age_days}d)"
            elif age_days > STALE_SNAPSHOT_DAYS:
                return f"Warning (Stale: {age_days}d)"
        except (ValueError, TypeError):
            pass

    if not snap_date and not node.get("isRelic"):
        sla_name = (node.get("effectiveSlaDomain") or {}).get("name", "")
        if sla_name and sla_name.lower() not in (
            "unprotected", "do not protect"
        ):
            return "Warning (No Snapshots)"

    return "Online"


def parse_node(node: dict) -> dict:
    """Parse a raw GraphQL node into a flat report row."""
    platform = node.get("_platform", "Unknown")
    sla = node.get("effectiveSlaDomain") or {}
    cluster = node.get("cluster") or {}
    newest = (node.get("newestSnapshot") or
              node.get("newestIndexedSnapshot") or {})
    oldest = node.get("oldestSnapshot") or {}

    status = determine_status(node, newest)

    reasons = node.get("unprotectableReasons", [])
    if isinstance(reasons, list):
        unprotected_reason = ", ".join(reasons)
    else:
        unprotected_reason = str(reasons) if reasons else ""

    return {
        "id": node.get("id", ""),
        "name": node.get("name", "Unknown"),
        "platform": platform,
        "sla_name": sla.get("name", "No SLA"),
        "cluster_name": cluster.get("name", node.get("region", "N/A")),
        "cluster_id": cluster.get("id", ""),
        "is_relic": node.get("isRelic", False),
        "recovery_model": node.get("recoveryModel", "N/A"),
        "unprotected_reason": unprotected_reason,
        "newest_snapshot": newest.get("date", ""),
        "oldest_snapshot": oldest.get("date", ""),
        "sla_pause_status": node.get("slaPauseStatus", ""),
        "total_missed_snapshots": 0,
        "total_missed_ranges": 0,
        "event_status": status,
        "db_engine": node.get("dbEngine", node.get("databaseVersion", "")),
        "region": node.get("region", ""),
        "instance_class": node.get("dbInstanceClass",
                                    node.get("instanceTier", "")),
        "service_tier": node.get("serviceTier", ""),
        "native_name": node.get("nativeName", node.get("databaseName", "")),
        "cloud_state": node.get("state", node.get("status", "")),
    }
