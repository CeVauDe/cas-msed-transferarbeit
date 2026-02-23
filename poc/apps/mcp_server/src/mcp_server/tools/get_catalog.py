from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches

from mcp_server.config import AppConfig
from mcp_server.contracts.catalog_models import CatalogColumnModel
from mcp_server.services.loaders import load_catalog


@dataclass(frozen=True)
class CatalogContext:
    config: AppConfig


def _build_alias_index(catalog_columns: dict[str, CatalogColumnModel]) -> dict[str, str]:
    alias_index: dict[str, str] = {}
    for column_name, column_info in catalog_columns.items():
        aliases = column_info.aliases_de
        for alias in aliases:
            alias_index[alias.lower()] = column_name
    return alias_index


def get_catalog_handler(context: CatalogContext, term: str | None = None) -> dict[str, object]:
    catalog_path = context.config.contracts_dir / "catalog.yaml"
    catalog = load_catalog(catalog_path)
    columns = catalog.columns

    if term is None:
        return {
            "ok": True,
            "catalog_version": catalog.version,
            "columns": {name: item.model_dump(mode="python") for name, item in columns.items()},
        }

    normalized_term = term.strip().lower()
    if normalized_term == "":
        return {
            "ok": True,
            "catalog_version": catalog.version,
            "columns": {name: item.model_dump(mode="python") for name, item in columns.items()},
        }

    for column_name, column_info in columns.items():
        if normalized_term == column_name.lower():
            return {
                "ok": True,
                "catalog_version": catalog.version,
                "selection_required": False,
                "column": column_name,
                "definition": column_info.model_dump(mode="python"),
            }

    alias_index = _build_alias_index(columns)
    alias_hit = alias_index.get(normalized_term)
    if alias_hit is not None:
        return {
            "ok": True,
            "catalog_version": catalog.version,
            "selection_required": False,
            "column": alias_hit,
            "definition": columns[alias_hit].model_dump(mode="python"),
        }

    column_candidates = list(columns.keys()) + list(alias_index.keys())
    matches = get_close_matches(normalized_term, column_candidates, n=3, cutoff=0.3)
    resolved_candidates: list[str] = []
    for match in matches:
        if match in columns:
            resolved_candidates.append(match)
        else:
            resolved_candidates.append(alias_index[match])

    deduped_candidates = sorted(set(resolved_candidates))
    return {
        "ok": False,
        "selection_required": True,
        "error": {
            "error_code": "GLOSSARY_TERM_AMBIGUOUS",
            "message": "Unknown glossary term. Select one of the candidates.",
            "details": {
                "term": term,
                "candidates": deduped_candidates,
            },
        },
    }
