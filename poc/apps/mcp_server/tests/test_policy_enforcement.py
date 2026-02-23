from pathlib import Path

from mcp_server.services.loaders import load_policy
from mcp_server.services.validator import validate_template


def test_rejects_disallowed_aggregate_for_metric() -> None:
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "mcp_server"
        / "contracts"
        / "policy.yaml"
    )
    policy = load_policy(policy_path)

    template: dict[str, object] = {
        "metrics": [{"column": "Region", "aggregate": "sum", "alias": "region_sum"}],
        "filters": [],
        "group_by": [],
        "sort": [],
        "limit": 20,
    }

    result = validate_template(raw_template=template, policy=policy)
    assert result.valid is False
    assert result.error is not None
    assert result.error["error_code"] == "POLICY_VIOLATION"
