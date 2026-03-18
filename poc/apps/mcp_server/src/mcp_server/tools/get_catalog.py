from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import get_close_matches

from mcp_server.config import AppConfig
from mcp_server.contracts.catalog_models import CatalogColumnModel
from mcp_server.logging import get_logger
from mcp_server.services.loaders import load_catalog

log = get_logger(__name__)


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
    log.info("get_catalog request received, term=%s", term)

    catalog_path = context.config.contracts_dir / "catalog.yaml"
    catalog = load_catalog(catalog_path)
    columns = catalog.columns

    def _full_catalog_response() -> dict[str, object]:
        return {
            "ok": True,
            "catalog_version": catalog.version,
            "columns": {name: item.model_dump(mode="python") for name, item in columns.items()},
            "metrics": {
                name: item.model_dump(mode="python") for name, item in catalog.metrics.items()
            },
            "timeslot_durations": {
                key: item.model_dump(mode="python")
                for key, item in catalog.timeslot_durations.items()
            },
        }

    if term is None:
        log.info("Returning full catalog, column_count=%d", len(columns))
        return _full_catalog_response()

    normalized_term = term.strip().lower()
    if normalized_term == "":
        log.info("Returning full catalog, column_count=%d", len(columns))
        return _full_catalog_response()

    for column_name, column_info in columns.items():
        if normalized_term == column_name.lower():
            log.debug(
                "Exact match found for term=%s, column=%s:\n%s",
                term,
                column_name,
                json.dumps(column_info.model_dump(mode="python"), indent=2, ensure_ascii=False),
            )
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
        log.debug(
            "Alias match found for term=%s, column=%s:\n%s",
            term,
            alias_hit,
            json.dumps(columns[alias_hit].model_dump(mode="python"), indent=2, ensure_ascii=False),
        )
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
    log.warning("Ambiguous term=%s, candidates=%s", term, deduped_candidates)
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
