from mcp_server.contracts.models import QueryTemplateModel
from mcp_server.services.response_builder import build_response


def test_response_builder_default_mode_hides_debug_fields() -> None:
    template = QueryTemplateModel.model_validate(
        {
            "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
            "filters": [],
            "group_by": [],
            "sort": [],
            "limit": 10,
        }
    )

    payload = build_response(
        rows=[{"wert_sum": 123.0}],
        template=template,
        debug_enrichment=False,
        template_version="v1",
    )

    assert payload["mode"] == "default"
    assert "template_echo" not in payload
    assert "sample_rows" not in payload


def test_response_builder_debug_mode_includes_debug_fields() -> None:
    template = QueryTemplateModel.model_validate(
        {
            "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
            "filters": [],
            "group_by": [],
            "sort": [],
            "limit": 10,
        }
    )

    payload = build_response(
        rows=[{"wert_sum": 123.0}],
        template=template,
        debug_enrichment=True,
        template_version="v1",
    )

    assert payload["mode"] == "debug"
    assert "template_echo" in payload
    assert "sample_rows" in payload


def test_response_builder_debug_mode_with_empty_rows_includes_debug_fields() -> None:
    template = QueryTemplateModel.model_validate(
        {
            "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
            "filters": [],
            "group_by": [],
            "sort": [],
            "limit": 10,
        }
    )

    payload = build_response(
        rows=[],
        template=template,
        debug_enrichment=True,
        template_version="v1",
    )

    assert payload["mode"] == "debug"
    assert "template_echo" in payload
    assert "sample_rows" in payload
    assert payload["sample_rows"] == []
    assert payload["row_count"] == 0
