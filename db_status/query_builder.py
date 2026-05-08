"""
Smart query builder with field discovery.
Tests which fields are available for each platform endpoint.
"""
from .auth import TokenManager
from .graphql_client import test_query


def discover_working_query(token_manager: TokenManager, query_name: str,
                           candidate_fields: list,
                           uses_filter: bool = True) -> str:
    """Discover which fields are available for a given query endpoint."""
    print(f"    [Discovery] Testing fields for {query_name}...")

    if uses_filter:
        param_str = "$first: Int!, $after: String, $filter: [Filter!]"
        arg_str = "first: $first, after: $after, filter: $filter"
        test_vars = {"first": 1, "after": None, "filter": []}
    else:
        param_str = "$first: Int!, $after: String"
        arg_str = "first: $first, after: $after"
        test_vars = {"first": 1, "after": None}

    # Test base query first
    base_query = f"""
    query({param_str}) {{
        {query_name}({arg_str}) {{
            count
            edges {{ node {{ id name }} }}
            pageInfo {{ endCursor hasNextPage }}
        }}
    }}
    """
    ok, err = test_query(token_manager, base_query, test_vars)
    if not ok:
        print(f"    [Discovery] Base query failed: {err}")
        return ""

    working_fields = ["id", "name"]
    failed_fields = []

    for field in candidate_fields:
        test_q = f"""
        query({param_str}) {{
            {query_name}({arg_str}) {{
                count
                edges {{ node {{ id name {field} }} }}
                pageInfo {{ endCursor hasNextPage }}
            }}
        }}
        """
        field_ok, _ = test_query(token_manager, test_q, test_vars)
        if field_ok:
            working_fields.append(field)
        else:
            failed_fields.append(field)

    if failed_fields:
        print(f"    [Discovery] Unavailable: {', '.join(failed_fields)}")

    fields_str = " ".join(working_fields)
    final_query = f"""
    query({param_str}) {{
        {query_name}({arg_str}) {{
            count
            edges {{ node {{ {fields_str} }} }}
            pageInfo {{ endCursor hasNextPage }}
        }}
    }}
    """
    print(f"    [Discovery] Final query: {len(working_fields)} fields")
    return final_query
