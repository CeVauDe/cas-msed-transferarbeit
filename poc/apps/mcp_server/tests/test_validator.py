from pathlib import Path

from mcp_server.contracts.policy_models import PolicyModel
from mcp_server.services.loaders import load_policy
from mcp_server.services.validator import validate_template


def _load_policy() -> PolicyModel:
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "mcp_server"
        / "contracts"
        / "policy.yaml"
    )
    return load_policy(policy_path)


def test_validate_template_accepts_valid_payload() -> None:
    policy = _load_policy()
    template: dict[str, object] = {
        "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
        "filters": [{"column": "Region", "op": "eq", "value": "Deutsche Schweiz"}],
        "group_by": ["Zeitschienen"],
        "sort": [{"column": "Zeitschienen", "direction": "asc"}],
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is True
    assert result.template is not None
    assert result.template.limit == policy.limits.default_limit


def test_validate_template_rejects_invalid_operator() -> None:
    policy = _load_policy()
    template: dict[str, object] = {
        "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
        "filters": [{"column": "Region", "op": "gte", "value": "Deutsche Schweiz"}],
        "group_by": [],
        "sort": [],
        "limit": 10,
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is False
    assert result.error is not None
    assert result.error["error_code"] == "POLICY_VIOLATION"


def test_validate_template_rejects_limit_above_max() -> None:
    policy = _load_policy()
    template: dict[str, object] = {
        "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
        "filters": [],
        "group_by": [],
        "sort": [],
        "limit": policy.limits.max_limit + 1,
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is False
    assert result.error is not None
    assert result.error["error_code"] == "POLICY_VIOLATION"
