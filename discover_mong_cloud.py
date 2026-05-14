#!/usr/bin/env python3
"""
Discovery script for:
1. MongoDB Sources — why newestSnapshot is null despite active SLA
2. MongoDB hierarchy — can we get parent snapshot for child objects
3. Azure SQL MI — alternative snapshot fields
"""
import os
import json
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

RSC_DOMAIN = os.environ.get("RSC_DOMAIN", "")
RSC_CLIENT_ID = os.environ.get("RSC_CLIENT_ID", "")
RSC_CLIENT_SECRET = os.environ.get("RSC_CLIENT_SECRET", "")
RSC_BASE_URL = f"https://{RSC_DOMAIN}"
RSC_TOKEN_URL = f"{RSC_BASE_URL}/api/client_token"
RSC_GRAPHQL_URL = f"{RSC_BASE_URL}/api/graphql"

# Known IDs from CSV output
MONGO_SOURCE_ID = "29c76bb0-84c5-52c7-95d8-42dea2a49255"  # sh2-mongodb, active SLA
MONGO_SOURCE_ID_2 = "da1d542b-2dfb-557b-97ad-e816aef29294"  # sh1-mongodb, active SLA
MONGO_DB_ID = "024d8eb1-7a5f-535f-93cd-022cb0327d77"  # misc_5GB_dbname_0
MONGO_COLLECTION_ID = "40c7409f-ba2d-52b7-a094-948a59ed1cfb"  # misc_5GB_col_2 (has snapshots)


def get_token():
    resp = requests.post(RSC_TOKEN_URL, json={
        "client_id": RSC_CLIENT_ID,
        "client_secret": RSC_CLIENT_SECRET,
    }, headers={"Content-Type": "application/json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def run_query(token, query, variables=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    resp = requests.post(RSC_GRAPHQL_URL, json={
        "query": query,
        "variables": variables or {},
    }, headers=headers, timeout=30)
    return resp.status_code, resp.json()


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    token = get_token()
    print("✅ Authenticated\n")

    # ============================================================
    # SECTION 1: MongoDB Source — What snapshot fields exist?
    # ============================================================
    section("1. MongoDB Source — Full Introspection of MongoSource type")

    q = """
    query {
        __type(name: "MongoSource") {
            fields {
                name
                args { name type { name kind ofType { name kind } } }
                type { name kind ofType { name kind ofType { name kind } } }
            }
        }
    }
    """
    status, result = run_query(token, q)
    fields = result.get("data", {}).get("__type", {}).get("fields", [])
    relevant = [f for f in fields if any(
        kw in f["name"].lower()
        for kw in ["snapshot", "newest", "oldest", "cdm", "backup"]
    )]
    print(f"  Snapshot-related fields ({len(relevant)}):")
    for f in relevant:
        args = [a["name"] for a in f.get("args", [])]
        type_info = f.get("type", {})
        type_name = type_info.get("name") or (type_info.get("ofType", {}) or {}).get("name", "?")
        arg_str = f" (args: {', '.join(args)})" if args else ""
        print(f"    • {f['name']}: {type_name}{arg_str}")

    # ============================================================
    # SECTION 2: MongoDB Source — Try cdmNewestSnapshot/cdmOldestSnapshot
    # ============================================================
    section("2. MongoDB Source — Try cdm* snapshot fields")

    cdm_variants = [
        "cdmNewestSnapshot { id date }",
        "cdmOldestSnapshot { id date }",
        "newestSnapshot { id date }",
        "oldestSnapshot { id date }",
    ]

    for field in cdm_variants:
        q = f"""
        query($first: Int!, $after: String, $filter: [Filter!]) {{
            mongoSources(first: $first, after: $after, filter: $filter) {{
                edges {{ node {{ id name {field} }} }}
            }}
        }}
        """
        vars = {"first": 5, "after": None, "filter": []}
        status, result = run_query(token, q, vars)
        if status == 200 and "errors" not in result:
            edges = result.get("data", {}).get("mongoSources", {}).get("edges", [])
            has_data = False
            for edge in edges:
                node = edge.get("node", {})
                field_key = field.split("{")[0].strip().split(" ")[0]
                val = node.get(field_key)
                if val and isinstance(val, dict) and val.get("date"):
                    has_data = True
                    print(f"  ✅ {field}: {json.dumps(val)[:80]}")
                    break
            if not has_data:
                print(f"  ⚠️  {field}: field accepted but all values null")
        else:
            err = ""
            if "errors" in result:
                err = result.get("errors", [{}])[0].get("message", "")[:80]
            elif "message" in result:
                err = result.get("message", "")[:80]
            print(f"  ❌ {field}: {err}")

    # ============================================================
    # SECTION 3: MongoDB Source — Try snapshotConnection approach
    # ============================================================
    section("3. MongoDB Source — Try snapshotConnection for latest snapshot")

    q = """
    query($first: Int!, $after: String, $filter: [Filter!]) {
        mongoSources(first: $first, after: $after, filter: $filter) {
            edges { node {
                id name
                snapshotConnection(first: 1, sortOrder: DESC) {
                    nodes { id date }
                    count
                }
            } }
        }
    }
    """
    status, result = run_query(token, q, {"first": 5, "after": None, "filter": []})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("mongoSources", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            conn = node.get("snapshotConnection", {})
            nodes = conn.get("nodes", [])
            count = conn.get("count", 0)
            if nodes:
                print(f"  ✅ {node.get('name')}: {count} snapshots, "
                      f"latest: {nodes[0].get('date', 'no date')}")
            else:
                print(f"  ⚠️  {node.get('name')}: {count} snapshots, no nodes returned")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ snapshotConnection failed: {err}")

    # Try alternate sort argument
    q2 = """
    query($first: Int!, $after: String, $filter: [Filter!]) {
        mongoSources(first: $first, after: $after, filter: $filter) {
            edges { node {
                id name
                snapshotConnection(first: 1, sortBy: CREATION_TIME, sortOrder: DESC) {
                    nodes { id date }
                    count
                }
            } }
        }
    }
    """
    status, result = run_query(token, q2, {"first": 5, "after": None, "filter": []})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("mongoSources", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            conn = node.get("snapshotConnection", {})
            nodes = conn.get("nodes", [])
            count = conn.get("count", 0)
            if nodes:
                print(f"  ✅ {node.get('name')} (sortBy): {count} snapshots, "
                      f"latest: {nodes[0].get('date', 'no date')}")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ snapshotConnection (sortBy) failed: {err}")

    # ============================================================
    # SECTION 4: MongoDB Database — Get parent source info
    # ============================================================
    section("4. MongoDB Database — physicalPath to find parent source")

    q = """
    query($first: Int!, $after: String, $filter: [Filter!]) {
        mongoDatabases(first: $first, after: $after, filter: $filter) {
            edges { node {
                id name
                physicalPath { fid name objectType }
                logicalPath { fid name objectType }
            } }
        }
    }
    """
    status, result = run_query(token, q, {"first": 5, "after": None, "filter": []})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("mongoDatabases", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            print(f"\n  DB: {node.get('name')}")
            print(f"    physicalPath: {json.dumps(node.get('physicalPath', []))}")
            print(f"    logicalPath: {json.dumps(node.get('logicalPath', []))}")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ Failed: {err}")

    # ============================================================
    # SECTION 5: PostgreSQL Database — Get parent cluster info
    # ============================================================
    section("5. PostgreSQL Database — physicalPath to find parent cluster")

    q = """
    query($first: Int!, $after: String, $filter: [Filter!]) {
        postgreSQLDatabases(first: $first, after: $after, filter: $filter) {
            edges { node {
                id name
                physicalPath { fid name objectType }
                logicalPath { fid name objectType }
            } }
        }
    }
    """
    status, result = run_query(token, q, {"first": 5, "after": None, "filter": []})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("postgreSQLDatabases", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            print(f"\n  DB: {node.get('name')}")
            print(f"    physicalPath: {json.dumps(node.get('physicalPath', []))}")
            print(f"    logicalPath: {json.dumps(node.get('logicalPath', []))}")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ Failed: {err}")

    # ============================================================
    # SECTION 6: MySQL Database — Get parent info
    # ============================================================
    section("6. MySQL Database — physicalPath to find parent")

    q = """
    query($first: Int!, $after: String, $filter: [Filter!]) {
        mysqlDatabases(first: $first, after: $after, filter: $filter) {
            edges { node {
                id name
                physicalPath { fid name objectType }
                logicalPath { fid name objectType }
            } }
        }
    }
    """
    status, result = run_query(token, q, {"first": 5, "after": None, "filter": []})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("mysqlDatabases", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            print(f"\n  DB: {node.get('name')}")
            print(f"    physicalPath: {json.dumps(node.get('physicalPath', []))}")
            print(f"    logicalPath: {json.dumps(node.get('logicalPath', []))}")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ Failed: {err}")

    # ============================================================
    # SECTION 7: Azure SQL MI — Try alternative snapshot approaches
    # ============================================================
    section("7. Azure SQL MI — Full type introspection")

    q = """
    query {
        __type(name: "AzureSqlManagedInstanceDatabase") {
            fields {
                name
                args { name type { name kind ofType { name kind } } }
                type { name kind ofType { name kind ofType { name kind } } }
            }
        }
    }
    """
    status, result = run_query(token, q)
    fields = result.get("data", {}).get("__type", {}).get("fields", [])
    relevant = [f for f in fields if any(
        kw in f["name"].lower()
        for kw in ["snapshot", "newest", "oldest", "cdm", "backup", "polaris"]
    )]
    print(f"  Snapshot-related fields ({len(relevant)}):")
    for f in relevant:
        args = [a["name"] for a in f.get("args", [])]
        type_info = f.get("type", {})
        type_name = type_info.get("name") or (type_info.get("ofType", {}) or {}).get("name", "?")
        arg_str = f" (args: {', '.join(args)})" if args else ""
        print(f"    • {f['name']}: {type_name}{arg_str}")

    # ============================================================
    # SECTION 8: Azure SQL MI — Try snapshotConnection
    # ============================================================
    section("8. Azure SQL MI — Try snapshotConnection for latest")

    q = """
    query($first: Int!, $after: String) {
        azureSqlManagedInstanceDatabases(first: $first, after: $after) {
            edges { node {
                id name
                snapshotConnection(first: 1, sortOrder: DESC) {
                    nodes { id date }
                    count
                }
            } }
        }
    }
    """
    status, result = run_query(token, q, {"first": 5, "after": None})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("azureSqlManagedInstanceDatabases", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            conn = node.get("snapshotConnection", {})
            nodes_data = conn.get("nodes", [])
            count = conn.get("count", 0)
            if nodes_data:
                print(f"  ✅ {node.get('name')}: {count} snapshots, "
                      f"latest: {nodes_data[0].get('date', 'no date')}")
            else:
                print(f"  ⚠️  {node.get('name')}: {count} snapshots")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ snapshotConnection failed: {err}")

    # Try workloadSnapshotConnection
    q2 = """
    query($first: Int!, $after: String) {
        azureSqlManagedInstanceDatabases(first: $first, after: $after) {
            edges { node {
                id name
                workloadSnapshotConnection(first: 1, sortOrder: DESC) {
                    nodes { id date }
                    count
                }
            } }
        }
    }
    """
    status, result = run_query(token, q2, {"first": 5, "after": None})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("azureSqlManagedInstanceDatabases", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            conn = node.get("workloadSnapshotConnection", {})
            nodes_data = conn.get("nodes", [])
            count = conn.get("count", 0)
            if nodes_data:
                print(f"  ✅ {node.get('name')} (workload): {count} snapshots, "
                      f"latest: {nodes_data[0].get('date', 'no date')}")
            else:
                print(f"  ⚠️  {node.get('name')} (workload): {count} snapshots")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ workloadSnapshotConnection failed: {err}")

    # ============================================================
    # SECTION 9: MongoDB Collection — Verify physicalPath has source
    # ============================================================
    section("9. MongoDB Collection — Verify path to source")

    q = """
    query($first: Int!, $after: String, $filter: [Filter!]) {
        mongoCollections(first: $first, after: $after, filter: $filter) {
            edges { node {
                id name
                physicalPath { fid name objectType }
            } }
        }
    }
    """
    status, result = run_query(token, q, {"first": 3, "after": None, "filter": []})
    if status == 200 and "errors" not in result:
        edges = result.get("data", {}).get("mongoCollections", {}).get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            print(f"\n  Collection: {node.get('name')}")
            print(f"    physicalPath: {json.dumps(node.get('physicalPath', []))}")
    else:
        err = result.get("errors", [{}])[0].get("message", "")[:100] if "errors" in result else result.get("message", "")[:100]
        print(f"  ❌ Failed: {err}")

    # ============================================================
    # SECTION 10: Summary
    # ============================================================
    section("SUMMARY")
    print("""
  Next steps based on results:
  1. If MongoDB Sources have snapshotConnection data → use that
  2. If child objects have physicalPath with parent fid → build lookup table
  3. If Azure SQL MI has snapshotConnection → use that instead of newestSnapshot
    """)


if __name__ == "__main__":
    main()