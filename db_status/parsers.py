"""
Node parsing and status determination.
Converts raw GraphQL nodes into flat report rows.
"""
from datetime import datetime, timezone
from .config import STALE_SNAPSHOT_DAYS, OFFLINE_SNAPSHOT_DAYS


def safe_get_snapshot_date(node: dict, field_name: str) -> str:
    """Safely extract a snapshot date from various response formats."""
    val = node.get(field_name)
    if val is None:
        return ""
    if isinstance(val, dict):
        return val.get("date", "") or ""
    if isinstance(val, str):
        return val
    return ""


def get_newest_snapshot_date(node: dict) -> str:
    """
    Extract newest snapshot date, trying multiple field names.
    Priority order based on discovery:
      1. cdmNewestSnapshot (MSSQL-specific)
      2. newestSnapshot (most platforms)
      3. newestIndexedSnapshot (cloud platforms)
      4. newestArchivedSnapshot (fallback)
      5. newestReplicatedSnapshot (fallback)
    """
    for field in [
        "cdmNewestSnapshot",
        "newestSnapshot",
        "newestIndexedSnapshot",
        "newestArchivedSnapshot",
        "newestReplicatedSnapshot",
    ]:
        date = safe_get_snapshot_date(node, field)
        if date:
            return date
    return ""


def get_oldest_snapshot_date(node: dict) -> str:
    """
    Extract oldest snapshot date, trying multiple field names.
    Priority order:
      1. cdmOldestSnapshot (MSSQL-specific)
      2. oldestSnapshot (most platforms)
    """
    for field in [
        "cdmOldestSnapshot",
        "oldestSnapshot",
    ]:
        date = safe_get_snapshot_date(node, field)
        if date:
            return date
    return ""


def determine_status(node: dict, newest_snapshot_date: str) -> str:
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

    if newest_snapshot_date:
        try:
            snap_dt = datetime.fromisoformat(
                newest_snapshot_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_days = (now - snap_dt).days
            if age_days > OFFLINE_SNAPSHOT_DAYS:
                return f"Offline (Stale: {age_days}d)"
            elif age_days > STALE_SNAPSHOT_DAYS:
                return f"Warning (Stale: {age_days}d)"
        except (ValueError, TypeError):
            pass

    if not newest_snapshot_date and not node.get("isRelic"):
        sla_name = (node.get("effectiveSlaDomain") or {}).get("name", "")
        if sla_name and sla_name.lower().replace("_", " ") not in (
            "unprotected", "do not protect"
        ):
            return "Warning (No Snapshots)"

    return "Online"


def parse_node(node: dict) -> dict:
    """Parse a raw GraphQL node into a flat report row."""
    platform = node.get("_platform", "Unknown")
    sla = node.get("effectiveSlaDomain") or {}
    cluster = node.get("cluster") or {}

    # Extract snapshot dates using priority fallback
    newest_snapshot_date = get_newest_snapshot_date(node)
    oldest_snapshot_date = get_oldest_snapshot_date(node)

    # Determine status
    status = determine_status(node, newest_snapshot_date)

    # Extract unprotectable reasons
    reasons = node.get("unprotectableReasons", [])
    if isinstance(reasons, list):
        unprotected_reason = ", ".join(str(r) for r in reasons)
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
        "newest_snapshot": newest_snapshot_date,
        "oldest_snapshot": oldest_snapshot_date,
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