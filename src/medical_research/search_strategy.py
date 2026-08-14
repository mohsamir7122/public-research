from __future__ import annotations

from typing import Any


DATABASES = ("pubmed", "scopus", "web_of_science", "embase")


def _terms(block: Any) -> list[str]:
    if not isinstance(block, dict):
        return []
    values = block.get("terms", [])
    if not isinstance(values, list):
        raise ValueError("terms must be an array")
    return [str(value).strip() for value in values if str(value).strip()]


def _quote(term: str) -> str:
    escaped = term.replace('"', '\\"')
    return f'"{escaped}"'


def _or_group(terms: list[str], formatter) -> str:
    return "(" + " OR ".join(formatter(term) for term in terms) + ")"


def _concepts(config: dict[str, Any]) -> list[list[str]]:
    concepts = [_terms(config.get("population")), _terms(config.get("intervention"))]
    comparator = _terms(config.get("comparator"))
    if comparator and config.get("include_comparator_in_primary_search", False):
        concepts.append(comparator)
    if config.get("include_outcomes_in_primary_search"):
        outcomes = _terms(config.get("outcomes"))
        if outcomes:
            concepts.append(outcomes)
    concepts = [concept for concept in concepts if concept]
    if len(concepts) < 2:
        raise ValueError("at least population and intervention terms are required")
    return concepts


def build_queries(config: dict[str, Any]) -> dict[str, str]:
    concepts = _concepts(config)

    pubmed_groups = [_or_group(group, lambda term: f'{_quote(term)}[Title/Abstract]') for group in concepts]
    mesh = config.get("population", {}).get("mesh", []) if isinstance(config.get("population"), dict) else []
    if isinstance(mesh, list) and mesh:
        pubmed_groups[0] = "(" + pubmed_groups[0][1:-1] + " OR " + " OR ".join(f'{_quote(str(term))}[MeSH Terms]' for term in mesh if str(term).strip()) + ")"

    scopus_groups = [_or_group(group, lambda term: f"TITLE-ABS-KEY({_quote(term)})") for group in concepts]
    wos_groups = [_or_group(group, lambda term: f"TS={_quote(term)}") for group in concepts]
    embase_groups = [_or_group(group, lambda term: f'{_quote(term)}:ti,ab,kw') for group in concepts]

    return {
        "pubmed": " AND ".join(pubmed_groups),
        "scopus": " AND ".join(scopus_groups),
        "web_of_science": " AND ".join(wos_groups),
        "embase": " AND ".join(embase_groups),
    }
