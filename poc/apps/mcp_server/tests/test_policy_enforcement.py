from pathlib import Path

from mcp_server.services.loaders import load_policy
from mcp_server.services.validator import validate_template


def _load_policy():
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "mcp_server"
        / "contracts"
        / "policy.yaml"
    )
    return load_policy(policy_path)


def test_rejects_disallowed_aggregate_for_metric() -> None:
    policy = _load_policy()

    template: dict[str, object] = {
        "metrics": [{"column": "Region", "aggregate": "sum", "alias": "region_sum"}],
        "filters": [{"column": "Region", "op": "eq", "value": "DS"}],
        "group_by": [],
        "sort": [],
        "limit": 20,
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is False
    assert result.error is not None
    assert result.error["error_code"] == "POLICY_VIOLATION"


def test_rejects_query_without_region_filter() -> None:
    policy = _load_policy()

    template: dict[str, object] = {
        "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
        "filters": [],
        "group_by": ["Sender"],
        "sort": [],
        "limit": 10,
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is False
    assert result.error is not None
    assert result.error["error_code"] == "POLICY_VIOLATION"
    assert "Region" in result.error["message"]


def test_accepts_query_with_single_region_eq_filter() -> None:
    policy = _load_policy()

    template: dict[str, object] = {
        "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
        "filters": [{"column": "Region", "op": "eq", "value": "DS"}],
        "group_by": ["Sender"],
        "sort": [],
        "limit": 10,
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is True
