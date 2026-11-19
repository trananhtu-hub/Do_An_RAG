from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ingestion.config import EXPECTED_QUESTIONS, Settings
from ingestion.store import Store

CANONICAL_DOMAINS = {"Secure", "Resilient", "High-Performing", "Cost-Optimized"}


def _table_chunks(store: Store, limit: int) -> list[dict[str, Any]]:
    query = """
    select id::text as id, content, metadata
    from public.chunks
    where content_type = 'table'
    order by random()
    limit %s
    """
    with store.connection.cursor() as cursor:
        cursor.execute(query, (limit,))
        return list(cursor.fetchall())


def _markdown_shape(content: str) -> tuple[int, int]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    rows = [line for line in lines if line.startswith("|") and line.endswith("|")]
    data_rows = [line for line in rows if not set(line) <= {"|", "-", ":", " "}]
    columns = len([cell for cell in rows[0].strip("|").split("|")]) if rows else 0
    return len(data_rows), columns


def check(store: Store, sample_tables: int) -> dict[str, Any]:
    database = store.database_stats()
    integrity = store.integrity_report()
    domains = database["domains"]
    unknown = sorted(domain for domain in domains if domain not in CANONICAL_DOMAINS)
    total_domain = sum(domains.values())
    shares = (
        {
            domain: round(count * 100.0 / total_domain, 2)
            for domain, count in sorted(domains.items())
        }
        if total_domain
        else {}
    )
    coverage = round(database["questions"] * 100.0 / EXPECTED_QUESTIONS, 2)

    table_samples = []
    for row in _table_chunks(store, sample_tables):
        meta = row["metadata"] or {}
        rows, cols = _markdown_shape(row["content"])
        table_samples.append(
            {
                "id": row["id"][:8],
                "document": meta.get("document"),
                "page": meta.get("page"),
                "metadata_rows": meta.get("rows"),
                "metadata_cols": meta.get("cols"),
                "markdown_rows": rows,
                "markdown_cols": cols,
                "shape_matches": meta.get("rows") in (None, rows)
                and meta.get("cols") in (None, cols),
            }
        )

    checks = {
        "no_empty_chunks": integrity["empty_chunks"] == 0,
        "no_null_embeddings": integrity["null_embeddings"] == 0,
        "embedding_dim_768": integrity["wrong_dimensions"] == 0,
        "children_have_parent": integrity["children_without_parent"] == 0,
        "token_counts_present": integrity["missing_token_counts"] == 0,
        "checksums_present": integrity["missing_checksums"] == 0,
        "no_duplicate_chunk_index": integrity["duplicate_chunk_indexes"] == 0,
        "domains_canonical": not unknown,
        "domain_total_100": total_domain == database["questions"],
        "question_coverage_ge_95": coverage >= 95.0,
        "tables_sampled_ok": all(sample["shape_matches"] for sample in table_samples),
    }
    return {
        "database": database,
        "integrity": integrity,
        "domain_shares_percent": shares,
        "unknown_domains": unknown,
        "question_coverage_percent": coverage,
        "expected_questions": EXPECTED_QUESTIONS,
        "table_samples": table_samples,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hậu kiểm kho tri thức sau khi nạp")
    parser.add_argument("--sample-tables", type=int, default=5)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    with Store(settings.database_url) as store:
        report = check(store, args.sample_tables)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
