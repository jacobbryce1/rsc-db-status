"""
Paginated data fetching with adaptive page sizing and retry logic.
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .auth import TokenManager
from .graphql_client import execute_graphql, test_query
from .query_builder import discover_working_query
from .config import PAGE_SIZE


def paginated_fetch(token_manager: TokenManager, query: str, data_key: str,
                    uses_filter: bool = True, page_size: int = PAGE_SIZE) -> list:
    """Paginated fetch with adaptive page size and retry logic."""
    all_nodes = []
    has_next_page = True
    cursor = None
    page = 1
    consecutive_errors = 0
    original_page_size = page_size

    while has_next_page:
        try:
            if uses_filter:
                variables = {"first": page_size, "after": cursor, "filter": []}
            else:
                variables = {"first": page_size, "after": cursor}

            data = execute_graphql(token_manager, query, variables)
            section = data.get(data_key)

            if section is None:
                raise Exception(
                    f"Query returned null for '{data_key}' — "
                    f"platform may not be licensed.")

            edges = section.get("edges", []) or []
            page_info = section.get("pageInfo", {}) or {}
            total_count = section.get("count", "?")

            for edge in edges:
                all_nodes.append(edge["node"])

            print(f"    Page {page}: {len(edges)} items "
                  f"(Total: {len(all_nodes)}/{total_count})")

            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")
            consecutive_errors = 0
            page += 1

            # Restore page size after success
            if page_size < original_page_size:
                page_size = min(page_size * 2, original_page_size)

        except Exception as e:
            consecutive_errors += 1
            print(f"    ⚠️ Error on page {page} (attempt "
                  f"{consecutive_errors}): {str(e)[:100]}")

            if consecutive_errors >= 3 and page_size > 50:
                page_size = max(50, page_size // 2)
                print(f"    ⚠️ Reducing page size to {page_size}")
                consecutive_errors = 0
            elif consecutive_errors >= 6:
                raise Exception(
                    f"Too many failures at page {page}: {e}")

            time.sleep(2 ** min(consecutive_errors, 5))

    return all_nodes


def get_platform_count(token_manager: TokenManager, query_name: str,
                       uses_filter: bool = True) -> int:
    """Quick count query to determine scale profile."""
    if uses_filter:
        q = f"""query($first: Int!, $after: String, $filter: [Filter!]) {{
            {query_name}(first: $first, after: $after, filter: $filter) {{
                count
            }}
        }}"""
        variables = {"first": 1, "after": None, "filter": []}
    else:
        q = f"""query($first: Int!, $after: String) {{
            {query_name}(first: $first, after: $after) {{
                count
            }}
        }}"""
        variables = {"first": 1, "after": None}

    try:
        data = execute_graphql(token_manager, q, variables)
        return data.get(query_name, {}).get("count", 0)
    except Exception:
        return 0


def fetch_platform(token_manager: TokenManager, platform: dict,
                   page_size: int) -> list:
    """Fetch a single platform's data."""
    name = platform["name"]
    query_name = platform["query_name"]
    data_key = platform["data_key"]
    uses_filter = platform["uses_filter"]
    candidate_fields = platform.get("candidate_fields", [])
    static_query = platform.get("query")

    print(f"\n  [{name}] Starting...")

    # Determine query
    if static_query:
        query = static_query
        if uses_filter:
            test_vars = {"first": 1, "after": None, "filter": []}
        else:
            test_vars = {"first": 1, "after": None}
        ok, err = test_query(token_manager, query, test_vars)
        if not ok:
            print(f"  [{name}] ❌ Static query failed ({err}). Skipping.")
            return []
    elif candidate_fields:
        query = discover_working_query(
            token_manager, query_name, candidate_fields, uses_filter)
        if not query:
            print(f"  [{name}] ❌ Discovery failed. Skipping.")
            return []
    else:
        if uses_filter:
            query = f"""query($first: Int!, $after: String, $filter: [Filter!]) {{
                {query_name}(first: $first, after: $after, filter: $filter) {{
                    count
                    edges {{ node {{ id name }} }}
                    pageInfo {{ endCursor hasNextPage }}
                }}
            }}"""
            test_vars = {"first": 1, "after": None, "filter": []}
        else:
            query = f"""query($first: Int!, $after: String) {{
                {query_name}(first: $first, after: $after) {{
                    count
                    edges {{ node {{ id name }} }}
                    pageInfo {{ endCursor hasNextPage }}
                }}
            }}"""
            test_vars = {"first": 1, "after": None}
        ok, err = test_query(token_manager, query, test_vars)
        if not ok:
            print(f"  [{name}] ❌ Not available ({err}). Skipping.")
            return []

    # Fetch
    try:
        nodes = paginated_fetch(
            token_manager, query, data_key, uses_filter, page_size)
    except Exception as e:
        print(f"  [{name}] ❌ Fetch failed: {str(e)[:100]}")
        return []

    # Tag nodes
    for node in nodes:
        node["_platform"] = name

    print(f"  [{name}] ✅ {len(nodes)} objects fetched")
    return nodes


def fetch_all_platforms_parallel(token_manager: TokenManager,
                                  platforms: list,
                                  profile: dict) -> list:
    """Fetch all platforms concurrently."""
    all_databases = []
    lock = threading.Lock()
    page_size = profile["page_size"]
    max_workers = min(profile["max_workers"], len(platforms))

    print(f"\n[*] Fetching platforms in parallel "
          f"(workers={max_workers}, page_size={page_size})")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_platform, token_manager, p, page_size): p["name"]
            for p in platforms
        }

        for future in as_completed(futures):
            platform_name = futures[future]
            try:
                nodes = future.result()
                with lock:
                    all_databases.extend(nodes)
            except Exception as e:
                print(f"  [{platform_name}] ❌ Exception: {e}")

    return all_databases
