from __future__ import annotations

from mcp_server.contracts.models import QueryTemplateModel


def build_response(
    rows: list[dict[str, object]],
    template: QueryTemplateModel,
    debug_enrichment: bool,
    template_version: str,
) -> dict[str, object]:
    response: dict[str, object] = {
        "mode": "default",
        "row_count": len(rows),
        "data": rows,
        "metadata": {
            "template_version": template_version,
        },
    }

    if debug_enrichment:
        response["mode"] = "debug"
        response["template_echo"] = template.model_dump(mode="python")
        response["sample_rows"] = rows[:5]

    return response
