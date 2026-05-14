#!/usr/bin/env python3
"""
Snapshot Field Discovery — Tests newestSnapshot and oldestSnapshot
across all platforms to find what works.
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


def test_snapshot_fields(token, platform_name, query_name, uses_filter):
    """Test various snapshot field configurations for a platform."""
    print(f"\n{'='*60}")
    print(f"  {platform_name} ({query_name})")
    print(f"{'='*60}")

    if uses_filter:
        param_str = "$first: Int!, $after: String, $filter: [Filter!]"
        arg_str = "first: $first, after: $after, filter: $filter"
        base_vars = {"first": 2, "after": None, "filter": []}
    else:
        param_str = "$first: Int!, $after: String"
        arg_str = "first: $first, after: $after"
        base_vars = {"first": 2, "after": None}

    # Test 1: newestSnapshot { id date }
    snapshot_variants = [
        ("newestSnapshot { id date }", "newestSnapshot with id+date"),
        ("newestSnapshot { date }", "newestSnapshot with date only"),
        ("newestSnapshot { id date indexTime }", "newestSnapshot with id+date+indexTime"),
        ("oldestSnapshot { id date }", "oldestSnapshot with id+date"),
        ("oldestSnapshot { date }", "oldestSnapshot with date only"),
        ("newestIndexedSnapshot { id date }", "newestIndexedSnapshot"),
        ("newestArchivedSnapshot { id date }", "newestArchivedSnapshot"),
        ("newestReplicatedSnapshot { id date }", "newestReplicatedSnapshot"),
        ("cdmNewestSnapshot { id date }", "cdmNewestSnapshot"),
        ("cdmOldestSnapshot { id date }", "cdmOldestSnapshot"),
    ]

    working_fields = []
    for field, label in snapshot_variants:
        q = f"""
        query({param_str}) {{
            {query_name}({arg_str}) {{
                edges {{ node {{ id name {field} }} }}
                pageInfo {{ endCursor hasNextPage }}
            }}
        }}
        """
        status, result = run_query(token, q, base_vars)
        if status == 200 and "errors" not in result:
            # Check if the data actually has values
            edges = (result.get("data", {}).get(query_name, {})
                     .get("edges", []))
            has_data = False
            sample_value = None
            for edge in edges:
                node = edge.get("node", {})
                # Extract the field name (first word before space or {)
                field_key = field.split("{")[0].strip().split(" ")[0]
                val = node.get(field_key)
                if val is not None:
                    has_data = True
                    sample_value = val
                    break

            icon = "✅" if has_data else "⚠️ (null)"
            print(f"  {icon} {label}: {json.dumps(sample_value)[:80] if sample_value else 'null'}")
            working_fields.append({
                "field": field,
                "label": label,
                "has_data": has_data,
                "sample": sample_value
            })
        else:
            err = ""
            if "errors" in result:
                err = result["errors"][0].get("message", "")[:80]
            elif "message" in result:
                err = result.get("message", "")[:80]
            print(f"  ❌ {label}: {err}")

    # Test 2: Introspect the type to see what snapshot fields exist
    print(f"\n  --- Introspecting {query_name} node type ---")

    # Get the type name first
    type_map = {
        "mssqlDatabases": "MssqlDatabase",
        "oracleDatabases": "OracleDatabase",
        "sapHanaDatabases": "SapHanaDatabase",
        "db2Databases": "Db2Database",
        "exchangeDatabases": "ExchangeDatabase",
        "postgreSQLDbClusters": "PostgreSQLDbCluster",
        "postgreSQLDatabases": "PostgreSQLDatabase",
        "mysqlDatabases": "MysqlDatabase",
        "mongoSources": "MongoSource",
        "mongoDatabases": "MongoDatabase",
        "mongoCollections": "MongoCollection",
        "azureSqlDatabases": "AzureSqlDatabase",
        "azureSqlManagedInstanceDatabases": "AzureSqlManagedInstanceDatabase",
        "gcpCloudSqlInstances": "GcpCloudSqlInstance",
        "awsNativeRdsInstances": "AwsNativeRdsInstance",
    }

    type_name = type_map.get(query_name, "")
    if type_name:
        introspect_q = f"""
        query {{
            __type(name: "{type_name}") {{
                fields {{
                    name
                    args {{ name type {{ name kind }} }}
                    type {{ name kind ofType {{ name kind }} }}
                }}
            }}
        }}
        """
        status, result = run_query(token, introspect_q)
        if status == 200 and result.get("data", {}).get("__type"):
            fields = result["data"]["__type"]["fields"]
            snapshot_fields = [f for f in fields if any(
                kw in f["name"].lower()
                for kw in ["snapshot", "newest", "oldest", "cdm"]
            )]
            print(f"  Found {len(snapshot_fields)} snapshot-related fields:")
            for f in snapshot_fields:
                args = f.get("args", [])
                arg_names = [a["name"] for a in args] if args else []
                type_info = f.get("type", {})
                type_name_str = type_info.get("name") or (
                    type_info.get("ofType", {}).get("name", "?"))
                arg_str = f" (args: {', '.join(arg_names)})" if arg_names else ""
                print(f"    • {f['name']}: {type_name_str}{arg_str}")
        else:
            print(f"  Could not introspect {type_name}")

    return working_fields


def main():
    print("=" * 60)
    print("  Snapshot Field Discovery — All Platforms")
    print("=" * 60)
    print(f"  Domain: {RSC_DOMAIN}")

    token = get_token()
    print("  ✅ Authenticated\n")

    # All platforms to test
    platforms = [
        ("MSSQL Databases", "mssqlDatabases", True),
        ("Oracle Databases", "oracleDatabases", True),
        ("SAP HANA Databases", "sapHanaDatabases", True),
        ("Db2 Databases", "db2Databases", True),
        ("Exchange Databases", "exchangeDatabases", True),
        ("PostgreSQL DB Clusters", "postgreSQLDbClusters", True),
        ("PostgreSQL Databases", "postgreSQLDatabases", True),
        ("MySQL Databases", "mysqlDatabases", True),
        ("MongoDB Sources", "mongoSources", True),
        ("MongoDB Databases", "mongoDatabases", True),
        ("MongoDB Collections", "mongoCollections", True),
        ("Azure SQL Databases", "azureSqlDatabases", False),
        ("Azure SQL MI Databases", "azureSqlManagedInstanceDatabases", False),
        ("GCP Cloud SQL Instances", "gcpCloudSqlInstances", False),
        ("AWS RDS Instances", "awsNativeRdsInstances", False),
    ]

    all_results = {}
    for name, query_name, uses_filter in platforms:
        try:
            results = test_snapshot_fields(token, name, query_name, uses_filter)
            all_results[name] = results
        except Exception as e:
            print(f"  ❌ Error testing {name}: {str(e)[:100]}")
            all_results[name] = []

    # Summary
    print("\n\n" + "=" * 60)
    print("  SUMMARY — Which snapshot fields work per platform")
    print("=" * 60)
    for platform_name, results in all_results.items():
        working_with_data = [r for r in results if r.get("has_data")]
        working_null = [r for r in results
                        if not r.get("has_data") and r in results]
        if working_with_data:
            fields = ", ".join(r["label"] for r in working_with_data)
            print(f"  ✅ {platform_name}: {fields}")
        else:
            null_fields = [r["label"] for r in results if not r.get("has_data")]
            if null_fields:
                print(f"  ⚠️  {platform_name}: Fields exist but all null: "
                      f"{', '.join(null_fields[:3])}")
            else:
                print(f"  ❌ {platform_name}: No snapshot fields available")


if __name__ == "__main__":
    main()