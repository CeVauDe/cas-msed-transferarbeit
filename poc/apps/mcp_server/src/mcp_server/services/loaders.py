from __future__ import annotations

import json
from pathlib import Path

import yaml

from mcp_server.contracts.catalog_models import CatalogModel
from mcp_server.contracts.models import QueryTemplateModel
from mcp_server.contracts.policy_models import PolicyModel


def export_query_template_schema(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = QueryTemplateModel.model_json_schema()
    schema["$id"] = "urn:cas-msed:query-template:v1"
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    output_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_policy(path: Path) -> PolicyModel:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PolicyModel.model_validate(payload)


def load_catalog(path: Path) -> CatalogModel:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CatalogModel.model_validate(payload)
